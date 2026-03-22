# automation marketing (Web)

Hệ thống automation marketing với kiến trúc Web:
- Backend: FastAPI + Playwright
- Frontend: React + Vite
- Realtime log/status: WebSocket

## Tính năng chính

- Quản lý phiên đăng nhập HPO
- Chạy tác vụ RPA: kiểm tra hợp đồng, tải file, cào chi tiết
- Auto Zalo: đăng nhập QR, gửi tin nhắn, kết bạn hàng loạt
- SMS Gateway: cấu hình, gửi SMS, theo dõi lịch sử
- Dashboard realtime trạng thái và tiến độ

## Kiến trúc thư mục

```text
auto_rpa_hdsaison/
├── backend/                 # FastAPI app + business logic
├── frontend/                # React app
├── app_data/                # Dữ liệu runtime (config/session/history)
├── downloads_contracts/     # File tải về
├── Dockerfile
├── docker-compose.yml
├── test.bat                 # Chạy test/lint/build 1 lệnh (Windows)
└── DEPLOY_DOCKER_UBUNTU.md
```

## Chạy local (Windows)

### 1) Chạy nhanh môi trường dev

```bat
dev.bat
```

### 2) Chạy kiểm thử toàn bộ (1 lệnh)

```bat
test.bat
```

`test.bat` sẽ chạy lần lượt:
- Backend: `pytest`
- Frontend: `npm run lint`
- Frontend: `npm run build`

Fail-fast: bước nào lỗi sẽ dừng ngay với exit code != 0.

## Deploy chuẩn Docker trên Ubuntu VPS

### Chạy nhanh

```bash
cp backend/.env.example backend/.env
docker-compose build
docker-compose up -d
```

API endpoint: `http://<VPS_IP>:8000`

Hướng dẫn đầy đủ: xem `DEPLOY_DOCKER_UBUNTU.md`.

## Cấu hình môi trường

### Backend

File mẫu: `backend/.env.example`

Biến quan trọng:
- `ALLOWED_ORIGINS` (CORS)
- `ENCRYPTION_KEY` (mã hóa password trong config)
- `API_HOST` (mặc định `0.0.0.0`)
- `API_PORT` (mặc định `8000`)
- `DEBUG` (`true/false`, mặc định `false`)

### Frontend

File mẫu: `frontend/.env.example`

Tùy chọn:
- `VITE_API_BASE_URL`
- `VITE_WS_BASE_URL`

Nếu frontend được serve cùng backend (production), có thể để trống để dùng đường dẫn tương đối `/api`.

## API & Docs

- Health: `/api/health`
- Swagger docs: `/docs`
- WebSocket logs: `/ws/logs`

## Dữ liệu cần backup

Backup định kỳ 2 thư mục:
- `app_data/`
- `downloads_contracts/`

Khi chạy Docker, 2 thư mục này đã được mount volume từ host.

## Lưu ý bảo mật

- Không commit dữ liệu nhạy cảm trong `app_data/`
- Không commit key/credential thật vào `.env`
- Dùng `ENCRYPTION_KEY` riêng cho từng môi trường

## Tài liệu liên quan

- `GITIGNORE_GUIDE.md`
- `DEPLOY_DOCKER_UBUNTU.md`

## 📄 License

MIT License - Free to use and modify

---

## 👤 Author

**shikinora2**
- GitHub: [@shikinora2](https://github.com/shikinora2)
- Repo: [auto_rpa_hdsaison](https://github.com/shikinora2/auto_rpa_hdsaison)

---

## 📞 Support

- 📖 Đọc [Troubleshooting](#-troubleshooting)
- 🐛 Tạo [Issue](https://github.com/shikinora2/auto_rpa_hdsaison/issues)
- 📚 Xem [GITIGNORE_GUIDE.md](GITIGNORE_GUIDE.md)

---

<div align="center">

**Version 1.3.0** • **December 6, 2025** • **✅ Stable**

⭐ Star this repo if helpful!

</div>
