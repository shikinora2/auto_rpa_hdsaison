import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from api.deps.auth import get_current_user
from core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    get_password_reset_expiry,
    get_refresh_expiry,
    hash_password,
    sanitize_role,
    sha256_text,
    verify_password,
)
from db.database import get_db
from db.models import AdminAuditLog, PasswordResetToken, RefreshToken, Role, User, UserRole
from config.settings import COOKIE_SECURE, COOKIE_SAMESITE, CSRF_COOKIE_NAME, CSRF_HEADER_NAME

router = APIRouter()

LOGIN_ATTEMPTS: dict[str, list[datetime]] = {}
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 60

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    access_max_age = 30 * 60
    refresh_max_age = 7 * 24 * 60 * 60
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=access_max_age,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=refresh_max_age,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=refresh_max_age,
        path="/",
    )


def _ensure_csrf_cookie(response: Response):
    refresh_max_age = 7 * 24 * 60 * 60
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=secrets.token_urlsafe(32),
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=refresh_max_age,
        path="/",
    )


def _clear_auth_cookies(response: Response):
    response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")


def _validate_csrf_cookie_header(request: Request):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr | None = None
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


class ForgotPasswordRequest(BaseModel):
    username_or_email: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(..., min_length=6, max_length=128)


class AdminCreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr | None = None
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="user")
    is_active: bool = False
    full_name: str | None = None


class AdminUpdateUserRequest(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    full_name: str | None = None


def _ensure_default_roles(db: Session):
    role_names = {r.name for r in db.query(Role).all()}
    for role_name, desc in (
        ("admin", "Administrator"),
        ("user", "Normal user"),
        ("hdsaison", "HDSaison operator"),
    ):
        if role_name not in role_names:
            db.add(Role(name=role_name, description=desc))
    db.commit()


def _get_user_role(db: Session, user_id: int) -> str:
    row = (
        db.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id)
        .order_by(Role.name.asc())
        .first()
    )
    return sanitize_role(row[0] if row else "user")


def _assign_role(db: Session, user_id: int, role_name: str, *, commit: bool = True):
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=500, detail=f"Role '{role_name}' not found")

    exists = db.query(UserRole).filter(UserRole.user_id == user_id, UserRole.role_id == role.id).first()
    if not exists:
        db.add(UserRole(user_id=user_id, role_id=role.id))
        if commit:
            db.commit()


def _issue_tokens(db: Session, user: User, role: str) -> dict:
    access_token = create_access_token(subject=str(user.id), role=role)
    refresh_token = create_refresh_token()
    refresh_hash = sha256_text(refresh_token)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=get_refresh_expiry(),
            revoked_at=None,
        )
    )
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": role,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
        },
    }


def _require_admin(current_user: dict):
    if str(current_user.get("role", "user")).lower().strip() != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")


def _replace_user_role(db: Session, user_id: int, role_name: str, *, commit: bool = True):
    normalized = sanitize_role(role_name)
    db.query(UserRole).filter(UserRole.user_id == user_id).delete(synchronize_session=False)
    if commit:
        db.commit()
    _assign_role(db, user_id, normalized, commit=commit)


def _write_audit(db: Session, admin_user_id: int, target_user_id: int, action: str, *, commit: bool = True):
    db.add(
        AdminAuditLog(
            admin_user_id=admin_user_id,
            target_user_id=target_user_id,
            action=action,
        )
    )
    if commit:
        db.commit()


def _check_login_rate_limit(identity: str):
    now = datetime.utcnow()
    records = LOGIN_ATTEMPTS.get(identity, [])
    records = [ts for ts in records if (now - ts).total_seconds() <= LOGIN_WINDOW_SECONDS]
    LOGIN_ATTEMPTS[identity] = records
    if len(records) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many failed login attempts. Try again later")


def _record_login_failure(identity: str):
    now = datetime.utcnow()
    records = LOGIN_ATTEMPTS.get(identity, [])
    records.append(now)
    LOGIN_ATTEMPTS[identity] = records


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    _ensure_default_roles(db)

    if db.query(User).filter(User.username == payload.username.strip()).first():
        raise HTTPException(status_code=400, detail="Username already exists")

    if payload.email and db.query(User).filter(User.email == payload.email.lower().strip()).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    user = User(
        username=payload.username.strip(),
        email=payload.email.lower().strip() if payload.email else None,
        password_hash=hash_password(payload.password),
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    user_count = db.query(User).count()
    assigned_role = "admin" if user_count == 1 else "user"
    if assigned_role == "admin":
        user.is_active = True
        db.add(user)
        db.commit()
    _assign_role(db, user.id, assigned_role)

    return {
        "status": "success",
        "message": "Đăng ký thành công",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": assigned_role,
            "is_active": user.is_active,
        },
    }


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    identity = payload.username.strip()
    _check_login_rate_limit(identity)

    user = (
        db.query(User)
        .filter((User.username == identity) | (User.email == identity.lower()))
        .first()
    )

    if not user:
        _record_login_failure(identity)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is pending approval")

    if not verify_password(payload.password, user.password_hash):
        _record_login_failure(identity)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    LOGIN_ATTEMPTS.pop(identity, None)

    role = _get_user_role(db, user.id)
    issued = _issue_tokens(db, user, role)
    _set_auth_cookies(response, issued["access_token"], issued["refresh_token"])
    return issued


@router.post("/refresh")
def refresh_token(
    request: Request,
    response: Response,
    payload: TokenRefreshRequest | None = None,
    db: Session = Depends(get_db),
):
    payload_refresh = payload.refresh_token if payload else None
    cookie_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    using_cookie_refresh = bool(cookie_refresh and not payload_refresh)
    refresh_token_value = payload_refresh or cookie_refresh
    if not refresh_token_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    if using_cookie_refresh:
        _validate_csrf_cookie_header(request)

    token_hash = sha256_text(refresh_token_value)
    token_row = db.query(RefreshToken.user_id).filter(RefreshToken.token_hash == token_hash).first()

    if not token_row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    now = datetime.utcnow()
    consumed = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at >= now,
        )
        .update({"revoked_at": now}, synchronize_session=False)
    )
    if consumed != 1:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    db.commit()

    user = db.query(User).filter(User.id == token_row.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    role = _get_user_role(db, user.id)
    issued = _issue_tokens(db, user, role)
    _set_auth_cookies(response, issued["access_token"], issued["refresh_token"])
    return issued


@router.post("/logout")
def logout(request: Request, response: Response, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _ = current_user
    refresh_token_value = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token_value:
        token_hash = sha256_text(refresh_token_value)
        db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": datetime.utcnow()}, synchronize_session=False)
        db.commit()

    _clear_auth_cookies(response)
    return {"status": "success", "message": "Logged out"}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from current password")

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()

    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": datetime.utcnow()}, synchronize_session=False)
    db.commit()

    return {"status": "success", "message": "Đổi mật khẩu thành công"}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    identity = payload.username_or_email.strip()
    user = (
        db.query(User)
        .filter((User.username == identity) | (User.email == identity.lower()))
        .first()
    )

    if not user:
        return {"status": "success", "message": "Nếu tài khoản tồn tại, mã reset đã được tạo"}

    reset_token_plain = create_password_reset_token()
    reset_token_hash = sha256_text(reset_token_plain)

    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=reset_token_hash,
            expires_at=get_password_reset_expiry(),
            used_at=None,
        )
    )
    db.commit()

    return {
        "status": "success",
        "message": "Nếu tài khoản tồn tại, hướng dẫn reset đã được gửi",
    }


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = sha256_text(payload.reset_token)
    now = datetime.utcnow()
    consumed = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at >= now,
        )
        .update({"used_at": now}, synchronize_session=False)
    )

    if consumed != 1:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    db.commit()

    token_row = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    if not token_row:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user = db.query(User).filter(User.id == token_row.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()

    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": datetime.utcnow()}, synchronize_session=False)
    db.commit()

    return {"status": "success", "message": "Reset mật khẩu thành công"}


@router.get("/me")
def me(response: Response, current_user=Depends(get_current_user)):
    # Backward compatibility: phiên đăng nhập cũ (trước khi bật CSRF) sẽ nhận token mới.
    _ensure_csrf_cookie(response)
    return {
        "status": "success",
        "user": current_user,
    }


@router.get("/users")
def list_users(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)

    users = db.query(User).order_by(User.created_at.desc()).all()
    payload = []
    for row in users:
        payload.append(
            {
                "id": row.id,
                "username": row.username,
                "email": row.email,
                "is_active": row.is_active,
                "role": _get_user_role(db, row.id),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return {"status": "success", "users": payload}


@router.post("/users")
def create_user(payload: AdminCreateUserRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)
    _ensure_default_roles(db)

    username = payload.username.strip()
    email = payload.email.lower().strip() if payload.email else None

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    if email and db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    try:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(payload.password),
            is_active=payload.is_active,
        )
        db.add(user)
        db.flush()

        _replace_user_role(db, user.id, payload.role, commit=False)
        _write_audit(db, current_user["id"], user.id, "create_user", commit=False)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create user")

    return {
        "status": "success",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": _get_user_role(db, user.id),
            "is_active": user.is_active,
        },
    }


@router.post("/users/{user_id}/approve")
def approve_user(user_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    db.add(user)
    db.commit()
    _write_audit(db, current_user["id"], user.id, "approve_user")

    return {"status": "success", "message": "User approved"}


@router.patch("/users/{user_id}")
def update_user(user_id: int, payload: AdminUpdateUserRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.username is not None:
        username = payload.username.strip()
        exists = db.query(User).filter(User.username == username, User.id != user_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Username already exists")
        user.username = username

    if payload.email is not None:
        email = payload.email.lower().strip()
        exists = db.query(User).filter(User.email == email, User.id != user_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Email already exists")
        user.email = email

    if payload.is_active is not None:
        user.is_active = payload.is_active

    if payload.password:
        user.password_hash = hash_password(payload.password)

    db.add(user)
    db.commit()

    if payload.role:
        _replace_user_role(db, user.id, payload.role)

    _write_audit(db, current_user["id"], user.id, "update_user")
    return {"status": "success", "message": "User updated"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)

    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    _write_audit(db, current_user["id"], user_id, "delete_user")
    return {"status": "success", "message": "User deleted"}
