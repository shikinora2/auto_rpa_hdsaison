"""
Config API Routes
Đọc/ghi file config.json
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import os

from config.settings import CONFIG_FILE, DEFAULT_CONFIG

router = APIRouter()


class ConfigModel(BaseModel):
    """Schema cho config"""
    username: Optional[str] = None
    password: Optional[str] = None
    headless: Optional[bool] = None
    save_directory: Optional[str] = None
    save_format: Optional[str] = None


def load_config() -> dict:
    """Đọc config từ file"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Merge với default config
                return {**DEFAULT_CONFIG, **config}
        except Exception as e:
            print(f"Error loading config: {e}")
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> bool:
    """Lưu config vào file"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


@router.get("")
async def get_config():
    """Lấy toàn bộ config"""
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
    
    if save_config(current_config):
        return {"status": "success", "message": "Config updated successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save config")


@router.get("/credentials")
async def get_credentials():
    """Lấy thông tin đăng nhập (cho internal use)"""
    config = load_config()
    return {
        "username": config.get("username", ""),
        "password": config.get("password", "")
    }


@router.delete("")
async def reset_config():
    """Reset config về mặc định"""
    if save_config(DEFAULT_CONFIG):
        return {"status": "success", "message": "Config reset to default"}
    else:
        raise HTTPException(status_code=500, detail="Failed to reset config")
