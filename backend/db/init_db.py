from sqlalchemy.orm import Session

from core.security import hash_password
from config.settings import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME
from db.database import Base, engine
from db.models import Role, User, UserRole


def init_db_schema():
    Base.metadata.create_all(bind=engine)


def seed_default_roles(db: Session):
    existing = {r.name for r in db.query(Role).all()}
    for role_name, desc in (("admin", "Administrator"), ("user", "Normal user")):
        if role_name not in existing:
            db.add(Role(name=role_name, description=desc))
    db.commit()


def seed_default_admin(db: Session):
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if not admin_role:
        admin_role = Role(name="admin", description="Administrator")
        db.add(admin_role)
        db.commit()
        db.refresh(admin_role)

    admin_user = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
    if not admin_user:
        admin_user = User(
            username=DEFAULT_ADMIN_USERNAME,
            email=DEFAULT_ADMIN_EMAIL,
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            is_active=True,
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

    link = (
        db.query(UserRole)
        .filter(UserRole.user_id == admin_user.id, UserRole.role_id == admin_role.id)
        .first()
    )
    if not link:
        db.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
        db.commit()
