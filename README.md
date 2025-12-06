# 🤖 Auto RPA HD Saison

> Tool tự động hóa quản lý hợp đồng HD Saison với giao diện hiện đại

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Status](https://img.shields.io/badge/Status-Stable-success.svg)

---

## ✨ Tính năng

### 🏠 Trang Chủ
- Đăng nhập tập trung
- Chế độ chạy ngầm (Headless) - Áp dụng toàn cục
- Log real-time

### 📋 Tác Vụ RPA
- Kiểm tra số lượng hợp đồng
- Tải file hàng loạt (PDF/JSON)
- Cào chi tiết ra Excel
- Pause/Stop control

### 📱 Auto Zalo
- Gửi tin nhắn hàng loạt
- Quản lý template (Lưu/Load/Xóa)
- Multi-account support
- Smart Headless (tự động mở khi cần QR)

### 📄 Kiểm Tra Hợp Đồng
- Xử lý file offline (PDF/JSON → Excel)
- Batch processing
- Không cần đăng nhập

### 🤖 Gemini & Google Sheet
- Tích hợp AI phân tích
- Sync tự động với Google Sheets

---

## ⚙️ Headless Mode

**Chạy ngầm không hiển thị trình duyệt**

```
✅ Tăng tốc 15-30%
✅ Tiết kiệm RAM ~200MB
✅ Không chiếm màn hình
✅ Smart: Tự động mở khi cần (QR Zalo)
```

**Cách dùng:**
1. Tab Trang Chủ → Tick "⚙️ Chạy ngầm"
2. Áp dụng cho tất cả tác vụ

---

## 📦 Cài đặt

```bash
# Clone repo
git clone https://github.com/shikinora2/auto_rpa_hdsaison.git
cd auto_rpa_hdsaison

# Cài dependencies
pip install -r requirements.txt

# Cài Playwright
python -m playwright install chromium

# Chạy
python app_ui.py
```

**Yêu cầu:**
- Python 3.8+
- Windows 10/11 (khuyến nghị)

---

## 🚀 Sử dụng nhanh

### 1. Đăng nhập
```
Tab Trang Chủ → Nhập user/pass → Lưu cấu hình
```

### 2. RPA Tasks
```
Tab Tác Vụ → Chọn ngày → Chọn folder → Tải File
```

### 3. Auto Zalo
```
Tab Auto Zalo → Thêm account → Import Excel → Gửi
```

### 4. Template Management
```
Soạn tin → 💾 Lưu → Đặt tên
Dropdown → Chọn template → 🗑️ Xóa (nếu cần)
```

---

## 📁 Cấu trúc

```
auto_rpa_hdsaison/
├── app_ui.py                # Main GUI
├── rpa_logic.py             # RPA automation
├── zalo_logic.py            # Zalo automation
├── logic_convert_pdf.py     # PDF extraction
├── google_sheet_logic.py    # Google Sheets
├── app_data/                # Config, sessions, templates
├── downloads_contracts/     # Downloaded files
└── requirements.txt         # Dependencies
```

---

## ⚙️ Cấu hình

### config.json (tự động tạo)
```json
{
  "username": "base64_encoded",
  "password": "base64_encoded"
}
```
⚠️ Đã ignore trong `.gitignore` - không commit lên Git

### Zalo Session
- Lưu tại: `app_data/zalo_session_*/`
- Persistent login - không cần quét QR mỗi lần

### Templates
- Lưu tại: `app_data/message_templates/`
- Format: JSON với `{name}` và `{phone}` variables

---

## 💡 Tips

### Khi nào dùng Headless?
✅ Tải file hàng loạt  
✅ Cào dữ liệu định kỳ  
✅ Không cần quan sát  
❌ Đăng nhập lần đầu  
❌ Debug lỗi  

### Performance
| Tác vụ | Thường | Headless | Tiết kiệm |
|--------|--------|----------|-----------|
| 100 HĐ | 5 min | 3.5 min | 30% |
| 100 PDF | 15 min | 11 min | 27% |

---

## 🔧 Troubleshooting

### "Playwright not installed"
```bash
python -m playwright install chromium
```

### "Headless timeout"
- Tắt Headless lần đầu để đăng nhập
- Sau đó bật lại

### "Google Sheets API Error"
- Kiểm tra `credentials.json`
- Xóa `token.json` và authorize lại

### "Zalo QR not detected"
- Xóa folder `app_data/zalo_session_[account]/`
- Chạy lại với Headless OFF

---

## 🔐 Bảo mật

**Không commit lên Git:**
- ✅ `app_data/` - Chứa credentials, sessions
- ✅ `credentials.json` - Google API
- ✅ `token.json` - OAuth token
- ✅ `downloads_contracts/` - Dữ liệu khách hàng

Xem chi tiết: [GITIGNORE_GUIDE.md](GITIGNORE_GUIDE.md)

---

## 📝 Changelog

### v1.3.0 (06/12/2025) - Current
- ✨ Template Management (Save/Load/Delete)
- ✨ Custom dialog với CustomTkinter
- 🎨 Simplified UI (xóa progress bars)
- 🔔 Task completion notifications

### v1.2.0 (05/12/2025)
- ⚙️ Smart Headless Mode
- ⚙️ Global headless control

### v1.0.0
- 🎉 Initial release

---

## 🤝 Contributing

```bash
git checkout -b feature/amazing-feature
git commit -m "Add feature"
git push origin feature/amazing-feature
```

Tạo Pull Request trên GitHub

---

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
