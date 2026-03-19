"""
Config API Routes
Đọc/ghi file config.json

Cải tiến bảo mật & ổn định:
  - asyncio.Lock để tránh race condition khi nhiều request ghi đồng thời
  - atomic_write_json() để tránh file hỏng khi crash giữa chừng
  - Mã hóa password trước khi lưu, tự động migrate plain text cũ
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio

from config.settings import CONFIG_FILE, DEFAULT_CONFIG
from utils.file_utils import atomic_write_json, safe_read_json
from utils.encryption import encrypt_value, decrypt_value, is_encrypted

router = APIRouter()

# Lock toàn module để serialize mọi thao tác đọc/ghi config
# (Giải quyết race condition khi nhiều async request ghi đồng thời)
_config_lock = asyncio.Lock()


class ConfigModel(BaseModel):
    """Schema cho config"""
    username: Optional[str] = None
    password: Optional[str] = None
    headless: Optional[bool] = None
    save_directory: Optional[str] = None
    save_format: Optional[str] = None


def load_config() -> dict:
    """
    Đọc config từ file.
    Tự động giải mã password và migrate plain text → encrypted nếu cần.
    """
    raw = safe_read_json(CONFIG_FILE, default=None)
    if raw is None:
        return DEFAULT_CONFIG.copy()

    config = {**DEFAULT_CONFIG, **raw}

    # Giải mã password (tự động xử lý cả plain text cũ chưa encrypt)
    raw_password = config.get("password", "")
    if raw_password:
        decrypted = decrypt_value(raw_password)
        config["password"] = decrypted

        # Nếu password chưa encrypt (plain text cũ), migrate ngay
        if not is_encrypted(raw_password):
            _save_config_sync(config)  # lưu lại với password đã mã hóa

    return config


def _save_config_sync(config: dict) -> bool:
    """
    Lưu config vào file (sync, nội bộ).
    Mã hóa password trước khi ghi.
    Dùng atomic write để tránh corrupt khi crash.
    """
    try:
        to_save = dict(config)
        # Mã hóa password trước khi ghi ra file
        if to_save.get("password"):
            to_save["password"] = encrypt_value(to_save["password"])
        return atomic_write_json(CONFIG_FILE, to_save)
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def save_config(config: dict) -> bool:
    """
    Public sync wrapper — dùng cho các call không trong async context.
    Với async routes hãy dùng _save_config_sync() sau khi đã acquire lock.
    """
    return _save_config_sync(config)


@router.get("")
async def get_config():
    """Lấy toàn bộ config"""
    async with _config_lock:
        config = load_config()
    # Không trả về password
    return {
        "username": config.get("username", ""),
        "headless": config.get("headless", False),
        "save_directory": config.get("save_directory", ""),
        "save_format": config.get("save_format", "PDF"),
        "has_password": bool(config.get("password", ""))
    }


@router.post("")
async def update_config(config_data: ConfigModel):
    """Cập nhật config"""
    async with _config_lock:
        current_config = load_config()

        # Chỉ cập nhật các field được gửi lên (không None)
        if config_data.username is not None:
            current_config["username"] = config_data.username
        if config_data.password is not None and config_data.password != "":
            current_config["password"] = config_data.password
        if config_data.headless is not None:
            current_config["headless"] = config_data.headless
        if config_data.save_directory is not None:
            current_config["save_directory"] = config_data.save_directory
        if config_data.save_format is not None:
            current_config["save_format"] = config_data.save_format

        if _save_config_sync(current_config):
            return {"status": "success", "message": "Config updated successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save config")


@router.get("/credentials")
async def get_credentials():
    """Lấy thông tin đăng nhập (cho internal use)"""
    async with _config_lock:
        config = load_config()
    return {
        "username": config.get("username", ""),
        "password": config.get("password", "")
    }


@router.delete("")
async def reset_config():
    """Reset config về mặc định"""
    async with _config_lock:
        if _save_config_sync(DEFAULT_CONFIG):
            return {"status": "success", "message": "Config reset to default"}
        else:
            raise HTTPException(status_code=500, detail="Failed to reset config")
