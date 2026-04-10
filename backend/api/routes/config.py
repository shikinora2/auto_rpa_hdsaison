"""
Config API Routes
Đọc/ghi file config.json

Cải tiến bảo mật & ổn định:
  - asyncio.Lock để serialize các thao tác đọc/ghi config
  - Blocking I/O chạy qua asyncio.to_thread() để không block event loop
  - atomic_write_json() để tránh file hỏng khi crash giữa chừng
  - Mã hóa password trước khi lưu, tự động migrate plain text cũ
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import asyncio

from config.settings import CONFIG_FILE, DEFAULT_CONFIG
from utils.file_utils import atomic_write_json, safe_read_json
from utils.encryption import encrypt_value, decrypt_value, is_encrypted
from api.deps.auth import require_roles

router = APIRouter(dependencies=[Depends(require_roles("admin", "hdsaison"))])

# Lock toàn module để serialize mọi thao tác đọc/ghi config.
# Tránh race condition khi nhiều async request ghi đồng thời.
_config_lock = asyncio.Lock()

_ALLOWED_CONFIG_KEYS = {"username", "password", "headless", "save_format"}


class ConfigModel(BaseModel):
    """Schema cho config"""
    username: Optional[str] = None
    password: Optional[str] = None
    headless: Optional[bool] = None
    save_format: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Sync core — gọi từ thread pool, KHÔNG gọi trực tiếp trong async handler
# ─────────────────────────────────────────────────────────────────────────────

def _load_config_sync() -> dict:
    """
    Đọc config từ file (sync, chạy trong thread).
    Tự động giải mã password và migrate plain text → encrypted nếu cần.
    """
    raw = safe_read_json(CONFIG_FILE, default=None)
    if raw is None:
        return DEFAULT_CONFIG.copy()

    # Chỉ giữ các key hợp lệ để loại bỏ key legacy (vd: save_directory)
    sanitized_raw = {k: v for k, v in raw.items() if k in _ALLOWED_CONFIG_KEYS}
    config = {**DEFAULT_CONFIG, **sanitized_raw}

    # Giải mã password (decrypt_value tự xử lý cả plain text cũ — auto migrate)
    raw_password = config.get("password", "")
    if raw_password:
        decrypted = decrypt_value(raw_password)
        config["password"] = decrypted

        # Nếu password chưa encrypt (plain text cũ), migrate ngay
        if not is_encrypted(raw_password):
            _save_config_sync(config)  # lưu lại với password đã mã hóa

    # Nếu file gốc có key legacy thì ghi lại bản đã được sanitize
    if any(k not in _ALLOWED_CONFIG_KEYS for k in raw.keys()):
        _save_config_sync(config)

    return config


def _save_config_sync(config: dict) -> bool:
    """
    Lưu config vào file (sync, chạy trong thread).
    Mã hóa password trước khi ghi, dùng atomic write.
    """
    try:
        to_save = {k: v for k, v in dict(config).items() if k in _ALLOWED_CONFIG_KEYS}
        if to_save.get("password"):
            to_save["password"] = encrypt_value(to_save["password"])
        return atomic_write_json(CONFIG_FILE, to_save)
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Async wrappers — offload blocking I/O ra thread pool, không chặn event loop
# ─────────────────────────────────────────────────────────────────────────────

async def _load_config_async() -> dict:
    """Async wrapper: chạy _load_config_sync() trong thread pool."""
    return await asyncio.to_thread(_load_config_sync)


async def _save_config_async(config: dict) -> bool:
    """Async wrapper: chạy _save_config_sync() trong thread pool."""
    return await asyncio.to_thread(_save_config_sync, config)


# ─────────────────────────────────────────────────────────────────────────────
# Public API (gọi từ các module khác, ví dụ zalo.py dùng load_config())
# ─────────────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """
    Public sync helper — dùng trong sync context (vd: bên trong thread pool executor).
    Nếu đang trong async handler, hãy dùng _load_config_async() thay thế.
    """
    return _load_config_sync()


def save_config(config: dict) -> bool:
    """
    Public sync helper — dùng trong sync context (vd: bên trong thread pool executor).
    """
    return _save_config_sync(config)


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Route Handlers
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def get_config():
    """Lấy toàn bộ config"""
    async with _config_lock:
        config = await _load_config_async()
    # Không trả về password
    return {
        "username": config.get("username", ""),
        "headless": config.get("headless", False),
        "save_format": config.get("save_format", "PDF"),
        "has_password": bool(config.get("password", ""))
    }


@router.post("")
async def update_config(config_data: ConfigModel):
    """Cập nhật config"""
    async with _config_lock:
        current_config = await _load_config_async()

        if config_data.username is not None:
            current_config["username"] = config_data.username
        if config_data.password is not None and config_data.password != "":
            current_config["password"] = config_data.password
        if config_data.headless is not None:
            current_config["headless"] = config_data.headless
        if config_data.save_format is not None:
            current_config["save_format"] = config_data.save_format

        ok = await _save_config_async(current_config)

    if ok:
        return {"status": "success", "message": "Config updated successfully"}
    raise HTTPException(status_code=500, detail="Failed to save config")


@router.get("/credentials")
async def get_credentials():
    """Lấy thông tin đăng nhập (cho internal use)"""
    async with _config_lock:
        config = await _load_config_async()
    return {
        "username": config.get("username", ""),
        "password": config.get("password", "")
    }


@router.delete("")
async def reset_config():
    """Reset config về mặc định"""
    async with _config_lock:
        ok = await _save_config_async(DEFAULT_CONFIG)
    if ok:
        return {"status": "success", "message": "Config reset to default"}
    raise HTTPException(status_code=500, detail="Failed to reset config")
