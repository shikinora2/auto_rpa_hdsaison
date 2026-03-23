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

# Session cache TTL (đăng nhập HPO/Zalo)
SESSION_CACHE_TTL_HOURS = int(os.getenv("SESSION_CACHE_TTL_HOURS", "24"))
SESSION_CACHE_TTL_SECONDS = SESSION_CACHE_TTL_HOURS * 3600

# Cleanup service
CLEANUP_ENABLED = os.getenv("CLEANUP_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "1800"))
CLEANUP_UPLOAD_RETENTION_HOURS = int(os.getenv("CLEANUP_UPLOAD_RETENTION_HOURS", "72"))
CLEANUP_DOWNLOAD_RETENTION_HOURS = int(os.getenv("CLEANUP_DOWNLOAD_RETENTION_HOURS", "336"))
CLEANUP_SESSION_RETENTION_HOURS = int(
    os.getenv("CLEANUP_SESSION_RETENTION_HOURS", str(max(SESSION_CACHE_TTL_HOURS + 12, 36)))
)
CLEANUP_AUTH_TOKEN_RETENTION_DAYS = int(os.getenv("CLEANUP_AUTH_TOKEN_RETENTION_DAYS", "7"))

# Database (mặc định SQLite local, có thể override bằng PostgreSQL/MySQL URL)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(APP_DATA_DIR / 'app.db').as_posix()}")

# Auth/JWT
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
PASSWORD_RESET_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "15"))
DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "123456")
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@local")

# Cookie/CSRF settings
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes", "on"}
_cookie_samesite = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
COOKIE_SAMESITE = _cookie_samesite if _cookie_samesite in {"lax", "strict", "none"} else "lax"
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "csrf_token")
CSRF_HEADER_NAME = os.getenv("CSRF_HEADER_NAME", "X-CSRF-Token")

# Zalo session
ZALO_SESSION_DIR = APP_DATA_DIR / "zalo_session"
ZALO_ACCOUNTS_FILE = APP_DATA_DIR / "zalo_accounts.json"

# Server settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
CLEAR_SESSION_ON_STARTUP = os.getenv("CLEAR_SESSION_ON_STARTUP", "false").strip().lower() in {"1", "true", "yes", "on"}

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
