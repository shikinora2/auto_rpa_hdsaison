"""
SMS Gateway Router
FastAPI router cho tích hợp Android SMS Gateway (Local Mode)
"""
from datetime import datetime
from typing import List, Literal

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from services.sms_gateway import SmsGatewayService
from api.deps.auth import require_roles


router = APIRouter(dependencies=[Depends(require_roles("admin", "user"))])


# ============== Pydantic Models ==============

class SmsGatewayConfig(BaseModel):
    connection_mode: Literal["local"] = Field(
        "local",
        description="Chế độ kết nối: local"
    )
    device_ip: str = Field("", description="IP của thiết bị Android trên mạng LAN")
    device_port: int = Field(8080, description="Port của Gateway app (mặc định 8080)")
    username: str = Field("", description="Username từ Gateway app")
    password: str = Field("", description="Password từ Gateway app")
    enabled: bool = Field(False, description="Bật/tắt SMS Gateway")
    use_specific_sim: bool = Field(False, description="Bật chọn SIM cụ thể khi gửi SMS")
    sim_number: int = Field(1, ge=1, le=2, description="SIM dùng để gửi (1-2)")


class SendSmsRequest(BaseModel):
    phone_numbers: List[str] = Field(..., description="Danh sách số điện thoại (vd: +84xxxxxxxxx)")
    message: str = Field(..., min_length=1, description="Nội dung tin nhắn")


# ============== Endpoints ==============

@router.get("/config", summary="Đọc cấu hình SMS Gateway", dependencies=[Depends(require_roles("admin"))])
async def get_config():
    """Trả về cấu hình gateway hiện tại (che password)."""
    cfg = SmsGatewayService.load_config()
    # Ẩn password trong response
    safe_cfg = dict(cfg)
    if safe_cfg.get("password"):
        safe_cfg["password"] = "****"
    return {"success": True, "config": safe_cfg}


@router.post("/config", summary="Lưu cấu hình SMS Gateway", dependencies=[Depends(require_roles("admin"))])
async def save_config(config: SmsGatewayConfig):
    """Lưu cấu hình gateway vào file JSON."""
    try:
        data = config.model_dump()
        data["connection_mode"] = "local"
        # Nếu password là "****" (không thay đổi), giữ nguyên giá trị cũ
        if data.get("password") == "****":
            old = SmsGatewayService.load_config()
            data["password"] = old.get("password", "")
        SmsGatewayService.save_config(data)
        return {"success": True, "message": "Đã lưu cấu hình SMS Gateway"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", summary="Kiểm tra kết nối tới Android Gateway")
async def check_health():
    """Ping Android SMS Gateway app để kiểm tra kết nối."""
    result = await SmsGatewayService.check_health()
    return result


@router.post("/send", summary="Gửi SMS qua Android Gateway")
async def send_sms(request: SendSmsRequest):
    """Gửi SMS tới một hoặc nhiều số điện thoại qua Android Gateway."""
    cfg = SmsGatewayService.load_config()

    step = "validate_config_enabled"
    if not cfg.get("enabled"):
        raise HTTPException(
            status_code=400,
            detail="[validate_config_enabled] SMS Gateway chưa được bật. Vào cấu hình để kích hoạt."
        )

    step = "validate_config_device"
    if not cfg.get("device_ip"):
        raise HTTPException(
            status_code=400,
            detail="[validate_config_device] Chưa cấu hình IP thiết bị Android"
        )

    step = "validate_payload"
    if not request.phone_numbers:
        raise HTTPException(
            status_code=400,
            detail="[validate_payload] Danh sách số điện thoại trống"
        )

    runtime_cfg = dict(cfg)

    step = "health_check"
    health = await SmsGatewayService.check_health(runtime_cfg)
    if health.get("status") == "error":
        raise HTTPException(
            status_code=503,
            detail="[health_check] Gateway chưa sẵn sàng: " + str(health.get("message", "Vui lòng kiểm tra lại kết nối")),
        )

    step = "gateway_send"
    result = await SmsGatewayService.send_sms(
        phone_numbers=request.phone_numbers,
        text=request.message,
        config=runtime_cfg,
    )

    gateway_state = str(result.get("response", {}).get("state") or "pending").lower() if result.get("success") else "failed"

    # Ghi lịch sử dù thành công hay thất bại
    entry = {
        "id": result.get("message_id", ""),
        "phones": request.phone_numbers,
        "message": request.message,
        "status": gateway_state,
        "error": result.get("error"),
        "sent_at": datetime.now().isoformat(),
        "gateway_state": result.get("response", {}).get("state"),
        "device_id": result.get("response", {}).get("deviceId"),
    }
    try:
        SmsGatewayService.append_history(entry)
    except Exception:
        pass  # Lịch sử không quan trọng bằng việc gửi tin

    if not result["success"]:
        upstream_status = result.get("http_status")
        error_step = result.get("step") or step
        if isinstance(upstream_status, int) and 400 <= upstream_status < 600:
            status_code = upstream_status
        else:
            status_code = 502
        raise HTTPException(
            status_code=status_code,
            detail=f"[{error_step}] " + str(result.get("error", "Lỗi không xác định")),
        )

    return {
        "success": True,
        "message_id": result.get("message_id"),
        "phones": request.phone_numbers,
        "message": "Đã gửi SMS thành công",
    }


@router.get("/status/{message_id}", summary="Kiểm tra trạng thái tin nhắn")
async def get_message_status(message_id: str):
    """Lấy trạng thái thực tế mới nhất của SMS từ Gateway."""
    result = await SmsGatewayService.get_message_status(message_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Lỗi lấy trạng thái SMS"))
    return result

@router.get("/messages", summary="Lịch sử tin nhắn đã gửi")
async def get_messages(limit: int = 100, sync: bool = False):
    """Trả về lịch sử các tin nhắn đã gửi (mới nhất trước)."""
    sync_result = None
    if sync:
        try:
            sync_result = await SmsGatewayService.sync_history_statuses(limit=min(limit, 100))
        except Exception:
            sync_result = None

    history = SmsGatewayService.load_history()
    payload = {
        "success": True,
        "total": len(history),
        "messages": history[:limit],
    }
    if sync_result is not None:
        payload["sync"] = sync_result
    return payload


@router.delete("/messages", summary="Xóa toàn bộ lịch sử tin nhắn", dependencies=[Depends(require_roles("admin"))])
async def clear_messages():
    """Xóa toàn bộ lịch sử gửi tin nhắn."""
    try:
        SmsGatewayService.clear_history()
        return {"success": True, "message": "Đã xóa toàn bộ lịch sử tin nhắn"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
