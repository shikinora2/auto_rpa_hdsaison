"""
Admin cleanup endpoints.
"""
from fastapi import APIRouter, Depends

from api.deps.auth import require_roles
from services.cleanup_service import get_cleanup_service


router = APIRouter(dependencies=[Depends(require_roles("admin"))])


@router.get("/cleanup/stats")
async def cleanup_stats():
    """Lấy cấu hình cleanup và thống kê lần chạy gần nhất."""
    service = get_cleanup_service()
    return {
        "status": "success",
        "running": service.is_running(),
        "config": service.get_runtime_config(),
        "last_run": service.get_last_summary(),
    }


@router.post("/cleanup/run")
async def run_cleanup_now():
    """Chạy cleanup thủ công ngay lập tức."""
    service = get_cleanup_service()
    summary = await service.run_once(trigger="manual")
    return {
        "status": "success",
        "message": "Cleanup completed",
        "summary": summary,
    }
