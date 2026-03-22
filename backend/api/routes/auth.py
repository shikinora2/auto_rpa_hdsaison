from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
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
from db.models import PasswordResetToken, RefreshToken, Role, User, UserRole

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr | None = None
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


class ForgotPasswordRequest(BaseModel):
    username_or_email: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(..., min_length=6, max_length=128)


def _ensure_default_roles(db: Session):
    role_names = {r.name for r in db.query(Role).all()}
    for role_name, desc in (("admin", "Administrator"), ("user", "Normal user")):
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


def _assign_role(db: Session, user_id: int, role_name: str):
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=500, detail=f"Role '{role_name}' not found")

    exists = db.query(UserRole).filter(UserRole.user_id == user_id, UserRole.role_id == role.id).first()
    if not exists:
        db.add(UserRole(user_id=user_id, role_id=role.id))
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
        },
    }


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
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    user_count = db.query(User).count()
    assigned_role = "admin" if user_count == 1 else "user"
    _assign_role(db, user.id, assigned_role)

    return {
        "status": "success",
        "message": "Đăng ký thành công",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": assigned_role,
        },
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    identity = payload.username.strip()
    user = (
        db.query(User)
        .filter((User.username == identity) | (User.email == identity.lower()))
        .first()
    )

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    role = _get_user_role(db, user.id)
    return _issue_tokens(db, user, role)


@router.post("/refresh")
def refresh_token(payload: TokenRefreshRequest, db: Session = Depends(get_db)):
    token_hash = sha256_text(payload.refresh_token)
    token_row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
        .first()
    )

    if not token_row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if token_row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = db.query(User).filter(User.id == token_row.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    token_row.revoked_at = datetime.utcnow()
    db.commit()

    role = _get_user_role(db, user.id)
    return _issue_tokens(db, user, role)


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
        "message": "Tạo token reset thành công",
        "reset_token": reset_token_plain,
        "note": "MVP: token trả trực tiếp; production nên gửi qua email/SMS",
    }


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = sha256_text(payload.reset_token)
    token_row = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
        )
        .first()
    )

    if not token_row:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    if token_row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token expired")

    user = db.query(User).filter(User.id == token_row.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(payload.new_password)
    token_row.used_at = datetime.utcnow()
    db.add(user)
    db.add(token_row)
    db.commit()

    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": datetime.utcnow()}, synchronize_session=False)
    db.commit()

    return {"status": "success", "message": "Reset mật khẩu thành công"}


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return {
        "status": "success",
        "user": current_user,
    }
