"""
Backend Configuration Settings
"""
import os
from pathlib import Path

# Load .env nếu có (dùng trên VPS để set biến môi trường dễ hơn)
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    with open(_env_file, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # auto_rpa_hdsaison/
BACKEND_DIR = BASE_DIR / "backend"
APP_DATA_DIR = BASE_DIR / "app_data"
DOWNLOADS_DIR = BASE_DIR / "downloads_contracts"

# Tạo thư mục nếu chưa tồn tại
APP_DATA_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Config file
CONFIG_FILE = APP_DATA_DIR / "config.json"

# SMS Gateway
SMS_GATEWAY_CONFIG_FILE = APP_DATA_DIR / "sms_gateway_config.json"
SMS_HISTORY_FILE = APP_DATA_DIR / "sms_history.json"

# Zalo session
ZALO_SESSION_DIR = APP_DATA_DIR / "zalo_session"
ZALO_ACCOUNTS_FILE = APP_DATA_DIR / "zalo_accounts.json"

# Server settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}

# CORS settings
# Thêm origins bổ sung qua env var ALLOWED_ORIGINS (phân cách bằng dấu phẩy)
# Ví dụ: ALLOWED_ORIGINS=http://192.168.1.10:5173,https://myapp.example.com
_extra_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
CORS_ORIGINS = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:3000",  # Alternative
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
] + _extra_origins

# Upload settings
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".pdf", ".json"}

# Default config template
DEFAULT_CONFIG = {
    "username": "",
    "password": "",
    "headless": False,
    "save_format": "PDF"
}
