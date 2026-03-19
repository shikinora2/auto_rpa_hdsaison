#!/usr/bin/env bash
# =============================================================
# start.sh — Khởi động backend HD Saison RPA Tool trên Ubuntu
# Chạy: chmod +x start.sh && ./start.sh
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$SCRIPT_DIR"
VENV_DIR="$PROJECT_ROOT/.venv"

echo "=================================================="
echo " HD Saison RPA Tool — Backend Startup"
echo "=================================================="

# 1. Tạo virtual environment nếu chưa có
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/5] Tạo Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# 2. Kích hoạt venv
source "$VENV_DIR/bin/activate"

# 3. Cài dependencies
echo "[2/5] Cài đặt Python dependencies..."
pip install -q --upgrade pip
pip install -q -r "$BACKEND_DIR/requirements.txt"

# 4. Cài Playwright browsers (chromium + system deps)
echo "[3/5] Cài đặt Playwright browsers..."
playwright install chromium
playwright install-deps chromium

# 5. Build frontend nếu chưa có dist
FRONTEND_DIST="$PROJECT_ROOT/frontend/dist"
if [ ! -d "$FRONTEND_DIST" ]; then
    echo "[4/5] Build frontend..."
    cd "$PROJECT_ROOT/frontend"
    npm install
    npm run build
    cd "$BACKEND_DIR"
else
    echo "[4/5] Frontend dist đã tồn tại, bỏ qua build."
fi

# 6. Copy .env nếu chưa có
if [ ! -f "$BACKEND_DIR/.env" ] && [ -f "$BACKEND_DIR/.env.example" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo "  → Đã tạo backend/.env từ .env.example, hãy chỉnh sửa nếu cần."
fi

# 7. Khởi động uvicorn
echo "[5/5] Khởi động backend tại http://0.0.0.0:8000 ..."
cd "$BACKEND_DIR"
exec "$VENV_DIR/bin/uvicorn" main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1
