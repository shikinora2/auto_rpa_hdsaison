import sys
import types

try:
    import playwright.sync_api  # type: ignore # pragma: no cover
except ModuleNotFoundError:  # pragma: no cover
    playwright_mod = types.ModuleType("playwright")
    sync_api_mod = types.ModuleType("playwright.sync_api")

    def _sync_playwright_unavailable(*args, **kwargs):
        raise RuntimeError("playwright is not installed in test environment")

    sync_api_mod.sync_playwright = _sync_playwright_unavailable
    playwright_mod.sync_api = sync_api_mod
    sys.modules.setdefault("playwright", playwright_mod)
    sys.modules.setdefault("playwright.sync_api", sync_api_mod)

from fastapi.testclient import TestClient
from uuid import uuid4

from main import app
from config.settings import DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME
from db.database import SessionLocal
from db.models import Role, User, UserRole


def _reset_runtime_states() -> None:
    from api.routes.rpa import rpa_state
    from api.routes.zalo import zalo_state, _clear_qr_cache

    rpa_state["is_running"] = False
    rpa_state["is_paused"] = False
    rpa_state["current_task"] = None
    rpa_state["stop_event"].clear()
    rpa_state["pause_event"].set()

    zalo_state["is_running"] = False
    zalo_state["is_paused"] = False
    zalo_state["stop_requested"] = False
    zalo_state["current_task"] = None
    zalo_state["session_active"] = False
    zalo_state["zalo_name"] = ""
    _clear_qr_cache()


import pytest


@pytest.fixture(scope="function")
def client():
    _reset_runtime_states()
    with TestClient(app) as test_client:
        yield test_client
    _reset_runtime_states()


@pytest.fixture(scope="function")
def auth_headers(client):
    username = f"user_{uuid4().hex[:8]}"
    password = "Pass@12345"
    client.post(
        "/api/auth/register",
        json={"username": username, "password": password, "email": f"{username}@example.com"},
    )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None
        user.is_active = True
        db.commit()
    finally:
        db.close()

    login_resp = client.post("/api/auth/login", json={"username": username, "password": password})
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def admin_headers(client):
    """Lấy token admin; fallback bằng cách nâng quyền test user nếu cần."""
    login_resp = client.post(
        "/api/auth/login",
        json={"username": DEFAULT_ADMIN_USERNAME, "password": DEFAULT_ADMIN_PASSWORD},
    )
    if login_resp.status_code == 200:
        token = login_resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    username = f"admin_fallback_{uuid4().hex[:8]}"
    password = _create_active_user_with_role(client, username=username, role_name="admin")

    promoted_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert promoted_login.status_code == 200
    token = promoted_login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_active_user_with_role(client, username: str, role_name: str) -> str:
    password = "Pass@12345"
    client.post(
        "/api/auth/register",
        json={"username": username, "password": password, "email": f"{username}@example.com"},
    )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None
        user.is_active = True

        role = db.query(Role).filter(Role.name == role_name).first()
        if role is None:
            role = Role(name=role_name, description=f"{role_name} role")
            db.add(role)
            db.flush()

        link = db.query(UserRole).filter(UserRole.user_id == user.id, UserRole.role_id == role.id).first()
        if link is None:
            db.add(UserRole(user_id=user.id, role_id=role.id))

        db.commit()
    finally:
        db.close()

    return password


@pytest.fixture(scope="function")
def hdsaison_headers(client):
    username = f"hdsaison_{uuid4().hex[:8]}"
    password = _create_active_user_with_role(client, username=username, role_name="hdsaison")
    login_resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
