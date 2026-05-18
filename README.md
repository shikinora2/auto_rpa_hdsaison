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
└── test.bat                 # Chạy test/lint/build 1 lệnh (Windows)
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
- Frontend: `npm run test:run`
- Frontend: `npm run build`

Fail-fast: bước nào lỗi sẽ dừng ngay với exit code != 0.

## Cấu hình môi trường

### Backend

File mẫu: `backend/.env.example`

Biến quan trọng:
- `ALLOWED_ORIGINS` (CORS)
- `ENCRYPTION_KEY` (mã hóa password trong config)
- `API_HOST` (mặc định `0.0.0.0`)
- `API_PORT` (mặc định `8000`)
- `DEBUG` (`true/false`, mặc định `false`)
- `HPO_BASE_URL` (domain gốc, hệ thống tự nối các suffix như `/login`, `/dashboard`, `/contracts`)
- `ZALO_CHAT_BASE_URL` (domain chat gốc, mặc định `https://chat.zalo.me`)
- `ZALO_CHAT_PATH` (hậu tố đường dẫn chat, mặc định `/`)
- `ZALO_ID_BASE_URL` (domain id gốc, mặc định `https://id.zalo.me`)
- `ZALO_LOGIN_PATH` (hậu tố đăng nhập, mặc định `/account`)

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

## Lưu ý bảo mật

- Không commit dữ liệu nhạy cảm trong `app_data/`
- Không commit key/credential thật vào `.env`
- Dùng `ENCRYPTION_KEY` riêng cho từng môi trường

## Tài liệu liên quan

- `GITIGNORE_GUIDE.md`

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
