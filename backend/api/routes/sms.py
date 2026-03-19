"""
SMS Gateway Router
FastAPI router cho tích hợp Android SMS Gateway (Local Mode)
"""
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.sms_gateway import SmsGatewayService


router = APIRouter()


# ============== Pydantic Models ==============

class SmsGatewayConfig(BaseModel):
    device_ip: str = Field("", description="IP của thiết bị Android trên mạng LAN")
    device_port: int = Field(8080, description="Port của Gateway app (mặc định 8080)")
    username: str = Field("", description="Username từ Gateway app")
    password: str = Field("", description="Password từ Gateway app")
    enabled: bool = Field(False, description="Bật/tắt SMS Gateway")


class SendSmsRequest(BaseModel):
    phone_numbers: List[str] = Field(..., description="Danh sách số điện thoại (vd: +84xxxxxxxxx)")
    message: str = Field(..., min_length=1, description="Nội dung tin nhắn")


# ============== Endpoints ==============

@router.get("/config", summary="Đọc cấu hình SMS Gateway")
async def get_config():
    """Trả về cấu hình gateway hiện tại (che password)."""
    cfg = SmsGatewayService.load_config()
    # Ẩn password trong response
    safe_cfg = dict(cfg)
    if safe_cfg.get("password"):
        safe_cfg["password"] = "****"
    return {"success": True, "config": safe_cfg}


@router.post("/config", summary="Lưu cấu hình SMS Gateway")
async def save_config(config: SmsGatewayConfig):
    """Lưu cấu hình gateway vào file JSON."""
    try:
        data = config.model_dump()
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
    if not cfg.get("enabled"):
        raise HTTPException(
            status_code=400,
            detail="SMS Gateway chưa được bật. Vào cấu hình để kích hoạt."
        )
    if not cfg.get("device_ip"):
        raise HTTPException(
            status_code=400,
            detail="Chưa cấu hình IP thiết bị Android"
        )

    result = await SmsGatewayService.send_sms(
        phone_numbers=request.phone_numbers,
        text=request.message,
        config=cfg,
    )

    # Ghi lịch sử dù thành công hay thất bại
    entry = {
        "id": result.get("message_id", ""),
        "phones": request.phone_numbers,
        "message": request.message,
        "status": "sent" if result["success"] else "failed",
        "error": result.get("error"),
        "sent_at": datetime.now().isoformat(),
    }
    try:
        SmsGatewayService.append_history(entry)
    except Exception:
        pass  # Lịch sử không quan trọng bằng việc gửi tin

    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Lỗi không xác định"))

    return {
        "success": True,
        "message_id": result.get("message_id"),
        "phones": request.phone_numbers,
        "message": "Đã gửi SMS thành công",
    }


@router.get("/messages", summary="Lịch sử tin nhắn đã gửi")
async def get_messages(limit: int = 100):
    """Trả về lịch sử các tin nhắn đã gửi (mới nhất trước)."""
    history = SmsGatewayService.load_history()
    return {
        "success": True,
        "total": len(history),
        "messages": history[:limit],
    }


@router.delete("/messages", summary="Xóa toàn bộ lịch sử tin nhắn")
async def clear_messages():
    """Xóa toàn bộ lịch sử gửi tin nhắn."""
    try:
        SmsGatewayService.clear_history()
        return {"success": True, "message": "Đã xóa toàn bộ lịch sử tin nhắn"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
