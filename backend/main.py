"""
HD Saison RPA Tool - Backend API
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
    DOWNLOADS_DIR,
    API_HOST,
    API_PORT,
    DEBUG
)
from api.websocket.connection_manager import manager
from api.routes import config, rpa, zalo, files


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    print("=" * 60)
    print("HD SAISON RPA Tool - Backend API v1.0.0")
    print("=" * 60)
    print(f"Server running at http://{API_HOST}:{API_PORT}")
    print(f"API docs at http://localhost:{API_PORT}/docs")
    print(f"WebSocket endpoint: ws://localhost:{API_PORT}/ws/logs")
    print("=" * 60)
    
    yield
    
    # Shutdown
    print("Shutting down server...")


# Khởi tạo FastAPI app
app = FastAPI(
    title="HD Saison RPA Tool API",
    description="Backend API for HD Saison RPA automation tool",
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

# Static files cho downloads
app.mount("/downloads", StaticFiles(directory=str(DOWNLOADS_DIR)), name="downloads")

# Include API routers
app.include_router(config.router, prefix="/api/config", tags=["Config"])
app.include_router(rpa.router, prefix="/api/rpa", tags=["RPA"])
app.include_router(zalo.router, prefix="/api/zalo", tags=["Zalo"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])


@app.get("/")
async def root():
    """Health check / SPA entry point — trả về index.html nếu có FE build"""
    frontend_index = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "index.html"
    if frontend_index.exists():
        return FileResponse(str(frontend_index))
    return {
        "status": "ok",
        "message": "HD Saison RPA Tool API is running",
        "version": "1.0.0",
        "websocket_url": f"ws://localhost:{API_PORT}/ws/logs"
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "websocket_connections": manager.connection_count,
        "app_data_dir": str(APP_DATA_DIR),
        "downloads_dir": str(DOWNLOADS_DIR)
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
