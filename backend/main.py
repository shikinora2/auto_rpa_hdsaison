"""
automation marketing - Backend API
FastAPI server với WebSocket support
"""
# ⚠️ QUAN TRỌNG: Phải đặt WindowsProactorEventLoopPolicy TRƯỚC khi import asyncio
# Playwright dùng asyncio.create_subprocess_exec() nội bộ, cần ProactorEventLoop trên Windows
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path
import os

# Thêm thư mục backend vào path để import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import (
    CORS_ORIGINS,
    APP_DATA_DIR,
    API_HOST,
    API_PORT,
    DEBUG,
    CLEAR_SESSION_ON_STARTUP
)
from api.websocket.connection_manager import manager
from api.routes import auth, config, rpa, zalo, files, sms, admin_cleanup
from services.sms_gateway import SmsGatewayService
from services.sms_gateway_ws import sms_gateway_ws_hub, parse_ws_json
from db.database import SessionLocal
from db.init_db import init_db_schema, seed_default_roles, seed_default_admin
from services.cleanup_service import get_cleanup_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    import shutil
    # Startup
    print("=" * 60)

    # Database init (MVP): tạo schema nếu chưa có + seed role mặc định
    try:
        init_db_schema()
        db = SessionLocal()
        try:
            seed_default_roles(db)
            seed_default_admin(db)
        finally:
            db.close()
        print("DB schema ready (users/roles/auth tables).")
    except Exception as e:
        print(f"DB init warning: {e}")
    print("automation marketing - Backend API v1.0.0")
    print("=" * 60)
    print(f"Server running at http://{API_HOST}:{API_PORT}")
    print(f"API docs at http://localhost:{API_PORT}/docs")
    print(f"WebSocket endpoint: ws://localhost:{API_PORT}/ws/logs")
    print("=" * 60)
    
    if CLEAR_SESSION_ON_STARTUP:
        print("Dọn dẹp session (Zalo & RPA) do CLEAR_SESSION_ON_STARTUP=true...")
        try:
            if APP_DATA_DIR.exists():
                for item in APP_DATA_DIR.iterdir():
                    if item.is_dir() and (item.name == "rpa_sessions" or item.name.startswith("zalo_session")):
                        shutil.rmtree(item, ignore_errors=True)
                        print(f"  - Đã xóa session cũ: {item.name}")
        except Exception as e:
            print(f"Lỗi khi dọn dẹp session: {e}")
    else:
        print("Giữ session đăng nhập hiện có (cache TTL điều khiển tại runtime).")

    cleanup_service = get_cleanup_service()
    await cleanup_service.start()
    print("Cleanup service started.")
    print("=" * 60)
    
    yield
    
    # Shutdown
    await cleanup_service.stop()
    print("Shutting down server...")


# Khởi tạo FastAPI app
app = FastAPI(
    title="automation marketing API",
    description="Backend API for automation marketing tool",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(config.router, prefix="/api/config", tags=["Config"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(rpa.router, prefix="/api/rpa", tags=["RPA"])
app.include_router(zalo.router, prefix="/api/zalo", tags=["Zalo"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(sms.router, prefix="/api/sms", tags=["SMS Gateway"])
app.include_router(admin_cleanup.router, prefix="/api/admin", tags=["Admin"])


@app.get("/")
async def root():
    """Health check / SPA entry point — trả về index.html nếu có FE build"""
    frontend_index = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "index.html"
    if frontend_index.exists():
        return FileResponse(str(frontend_index))
    return {
        "status": "ok",
        "message": "automation marketing API is running",
        "version": "1.0.0",
        "websocket_url": f"ws://localhost:{API_PORT}/ws/logs"
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "websocket_connections": manager.connection_count,
        "sms_gateway_ws_connections": sms_gateway_ws_hub.connection_count,
        "version": "1.0.0"
    }


@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for realtime logs
    Clients connect here to receive log messages from RPA/Zalo operations
    """
    await manager.connect(websocket)
    try:
        while True:
            # Giữ kết nối mở, nhận ping từ client
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.websocket("/ws/sms-gateway/device")
async def sms_gateway_device_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for Android SMS Gateway device.
    Device should authenticate first, then handle command/response messages.
    """
    await sms_gateway_ws_hub.connect(websocket)
    authed = False

    try:
        while True:
            raw = await websocket.receive_text()

            if raw == "ping":
                await sms_gateway_ws_hub.refresh_heartbeat(websocket)
                await websocket.send_text("pong")
                continue

            payload = parse_ws_json(raw)
            if not payload:
                await websocket.send_json({"type": "error", "error": "invalid_json"})
                continue

            msg_type = str(payload.get("type") or "").strip().lower()

            if msg_type == "auth":
                cfg = SmsGatewayService.load_config()
                expected_username = str(cfg.get("username") or "").strip()
                expected_password = str(cfg.get("password") or "")
                recv_username = str(payload.get("username") or "").strip()
                recv_password = str(payload.get("password") or "")

                if not expected_username or not expected_password:
                    await websocket.send_json(
                        {
                            "type": "auth_ack",
                            "success": False,
                            "error": "server_credentials_not_configured",
                        }
                    )
                    await websocket.close(code=1008)
                    break

                if recv_username != expected_username or recv_password != expected_password:
                    await websocket.send_json(
                        {
                            "type": "auth_ack",
                            "success": False,
                            "error": "invalid_credentials",
                        }
                    )
                    await websocket.close(code=1008)
                    break

                device_id = str(payload.get("device_id") or payload.get("deviceId") or "").strip()
                if not device_id:
                    await websocket.send_json(
                        {
                            "type": "auth_ack",
                            "success": False,
                            "error": "device_id_required",
                        }
                    )
                    await websocket.close(code=1008)
                    break

                metadata = {
                    "device_name": payload.get("device_name") or payload.get("deviceName"),
                    "platform": payload.get("platform") or "android",
                    "app_version": payload.get("app_version") or payload.get("appVersion"),
                }
                meta = await sms_gateway_ws_hub.authenticate_device(
                    websocket,
                    device_id=device_id,
                    metadata=metadata,
                )
                authed = True
                await websocket.send_json(
                    {
                        "type": "auth_ack",
                        "success": True,
                        "device_id": meta.get("device_id"),
                        "message": "authenticated",
                    }
                )
                continue

            if not authed:
                await websocket.send_json({"type": "error", "error": "unauthorized"})
                continue

            if msg_type == "response":
                resolved = await sms_gateway_ws_hub.resolve_response(websocket, payload)
                if not resolved:
                    await websocket.send_json({"type": "error", "error": "unknown_request"})
                continue

            if msg_type == "event":
                await sms_gateway_ws_hub.refresh_heartbeat(websocket)
                continue

            await websocket.send_json({"type": "error", "error": "unsupported_message_type"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"SMS gateway websocket error: {e}")
    finally:
        await sms_gateway_ws_hub.disconnect(websocket)


# ============== Serve Frontend (Production) ==============
# Khi FE đã được build (`npm run build`), backend tự serve file tĩnh.
# Truy cập http://VPS_IP:8000/ sẽ load React app.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="fe_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Catch-all: trả về index.html cho React Router (SPA)"""
        index_file = _FRONTEND_DIST / "index.html"
        return FileResponse(str(index_file))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=DEBUG
    )
