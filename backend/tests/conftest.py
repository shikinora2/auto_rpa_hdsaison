from fastapi.testclient import TestClient
from uuid import uuid4

from main import app


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
    login_resp = client.post("/api/auth/login", json={"username": username, "password": password})
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
