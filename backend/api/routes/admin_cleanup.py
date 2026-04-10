"""
Admin cleanup endpoints.
"""
from fastapi import APIRouter, Depends
from pathlib import Path

from api.deps.auth import require_roles
from services.cleanup_service import get_cleanup_service
from api.websocket.connection_manager import manager
from services.sms_gateway import SmsGatewayService
from config.settings import APP_DATA_DIR


router = APIRouter()


@router.get("/cleanup/stats")
async def cleanup_stats(current_user=Depends(require_roles("admin"))):
    """Lấy cấu hình cleanup và thống kê lần chạy gần nhất."""
    service = get_cleanup_service()
    return {
        "status": "success",
        "running": service.is_running(),
        "config": service.get_runtime_config(),
        "last_run": service.get_last_summary(),
    }


@router.post("/cleanup/run")
async def run_cleanup_now(current_user=Depends(require_roles("admin"))):
    """Chạy cleanup thủ công ngay lập tức."""
    service = get_cleanup_service()
    summary = await service.run_once(trigger="manual")
    return {
        "status": "success",
        "message": "Cleanup completed",
        "summary": summary,
    }


@router.post("/cleanup/reset-runtime")
async def reset_runtime_state(current_user=Depends(require_roles("admin", "user", "hdsaison"))):
    """Reset trạng thái runtime để đưa hệ thống về trạng thái như user mới đăng nhập."""
    summary = {
        "rpa_stopped": False,
        "zalo_stopped": False,
        "rpa_session_cleared": False,
        "zalo_session_cleared": False,
        "sms_history_cleared": False,
        "ws_history_cleared": False,
        "uploads_cleared": False,
        "uploads_deleted_count": 0,
    }

    # RPA runtime state
    try:
        from api.routes.rpa import rpa_state, _rpa_state_lock

        with _rpa_state_lock:
            rpa_state["stop_event"].set()
            rpa_state["pause_event"].set()
            rpa_state["is_running"] = False
            rpa_state["is_paused"] = False
            rpa_state["current_task"] = None
        summary["rpa_stopped"] = True
    except Exception:
        pass

    # Zalo runtime state
    try:
        from api.routes.zalo import zalo_state, _zalo_state_lock, _clear_qr_cache

        with _zalo_state_lock:
            zalo_state["stop_requested"] = True
            zalo_state["is_paused"] = False
            zalo_state["is_running"] = False
            zalo_state["current_task"] = None
            zalo_state["session_active"] = False
            zalo_state["zalo_name"] = ""
        _clear_qr_cache(current_user["id"])
        summary["zalo_stopped"] = True
    except Exception:
        pass

    # Clear HPO session (disk + cache)
    try:
        from services.rpa_session_manager import get_rpa_session_manager

        rpa_session_manager = get_rpa_session_manager(current_user["id"])
        await rpa_session_manager.logout(status_callback=None)
        summary["rpa_session_cleared"] = True
    except Exception:
        pass

    # Clear Zalo session on disk
    try:
        from api.routes.zalo import get_session_manager

        zalo_session_manager = get_session_manager(current_user["id"])
        zalo_session_manager.delete_session()
        summary["zalo_session_cleared"] = True
    except Exception:
        pass

    # Clear SMS message history
    try:
        SmsGatewayService.clear_history()
        summary["sms_history_cleared"] = True
    except Exception:
        pass

    # Clear WebSocket log history
    try:
        manager.clear_history()
        summary["ws_history_cleared"] = True
    except Exception:
        pass

    # Clear uploaded files (customer excel, image attachments, temp uploads)
    try:
        upload_dir = APP_DATA_DIR / "uploads"
        deleted_count = 0
        if upload_dir.exists() and upload_dir.is_dir():
            for item in upload_dir.iterdir():
                try:
                    if item.is_file():
                        item.unlink(missing_ok=True)
                        deleted_count += 1
                except Exception:
                    continue
        summary["uploads_cleared"] = True
        summary["uploads_deleted_count"] = deleted_count
    except Exception:
        pass

    await manager.broadcast_status("completed", {
        "task": "runtime_reset",
        "reset_summary": summary,
    })

    return {
        "status": "success",
        "message": "Đã reset trạng thái runtime thành công",
        "summary": summary,
    }
