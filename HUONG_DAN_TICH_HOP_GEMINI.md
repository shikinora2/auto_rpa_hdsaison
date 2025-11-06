# HƯỚNG DẪN TÍCH HỢP GEMINI API

## 📋 Tổng Quan

Tôi đã thêm UI nút "Kết nối API Gemini" vào tab **Tác Vụ** trong ứng dụng. Dưới đây là hướng dẫn từng bước để tích hợp Gemini API vào ứng dụng của bạn.

## 🎯 Các Thay Đổi Đã Thực Hiện

### 1. Thêm UI Components (app_ui.py)

**Vị trí:** Tab "Tác Vụ" - Sau phần "TÁC VỤ XỬ LÝ FILE (OFFLINE)"

**Các thành phần đã thêm:**
- ✅ Frame "KẾT NỐI API GEMINI"
- ✅ Entry để nhập API Key (có chế độ ẩn/hiện)
- ✅ Checkbox "Hiện API Key"
- ✅ Label hiển thị trạng thái kết nối
- ✅ Nút "Kết Nối Gemini"

### 2. Thêm Các Hàm Xử Lý

**Các hàm đã được thêm vào class App:**

1. `toggle_api_key_visibility()` - Hiện/ẩn API Key
2. `connect_gemini()` - Xử lý sự kiện click nút kết nối
3. `_run_gemini_connection(api_key)` - Thread worker để kết nối API
4. `_save_gemini_config(api_key)` - Lưu API Key vào file config
5. `_load_gemini_config()` - Load API Key khi khởi động app

### 3. Tự Động Load API Key

API Key sẽ được tự động load từ file `app_data/gemini_config.json` khi khởi động ứng dụng.

---

## 🚀 HƯỚNG DẪN TÍCH HỢP TỪNG BƯỚC

### BƯỚC 1: Cài Đặt Thư Viện Gemini

```bash
pip install google-generativeai
```

### BƯỚC 2: Lấy API Key

1. Truy cập: https://makersuite.google.com/app/apikey
2. Đăng nhập bằng tài khoản Google
3. Click "Create API Key"
4. Copy API Key

### BƯỚC 3: Cập Nhật Hàm `_run_gemini_connection`

**File:** `app_ui.py`  
**Vị trí:** Dòng ~1270

**Thay thế code hiện tại:**

```python
def _run_gemini_connection(self, api_key):
    """Thread worker để kết nối Gemini API"""
    try:
        self.log_to_gui("⏳ Đang kết nối với Gemini API...")
        self.gemini_status_label.configure(text="⏳ Đang kết nối...", text_color="orange")
        
        # Import thư viện Gemini
        import google.generativeai as genai
        
        # Cấu hình API Key
        genai.configure(api_key=api_key)
        
        # Tạo model
        model = genai.GenerativeModel('gemini-pro')
        
        # Test kết nối
        response = model.generate_content("Xin chào, bạn có hoạt động không?")
        
        if response and response.text:
            self.log_to_gui("✅ Kết nối Gemini API thành công!")
            self.log_to_gui(f"📝 Phản hồi test: {response.text[:100]}...")
            self.gemini_status_label.configure(text="✅ Đã kết nối", text_color="green")
            
            # Lưu API Key vào config
            self._save_gemini_config(api_key)
            
            # Lưu model vào biến instance để sử dụng sau
            self.gemini_model = model
            
            messagebox.showinfo(
                "Thành công",
                "Đã kết nối với Gemini API thành công!",
                parent=self
            )
        else:
            raise Exception("Không nhận được phản hồi từ Gemini")
            
    except Exception as e:
        self.log_to_gui(f"❌ Lỗi kết nối Gemini API: {str(e)}")
        self.gemini_status_label.configure(text="❌ Kết nối thất bại", text_color="red")
        messagebox.showerror(
            "Lỗi kết nối",
            f"Không thể kết nối với Gemini API:\n{str(e)}",
            parent=self
        )
```

### BƯỚC 4: Thêm Biến Instance Cho Model

**File:** `app_ui.py`  
**Vị trí:** Trong hàm `__init__` (sau dòng ~75)

```python
# Biến quản lý trạng thái tạm dừng
self.is_paused = False

# Biến lưu Gemini model
self.gemini_model = None  # THÊM DÒNG NÀY
```

---

## 💡 CÁC TÍNH NĂNG CÓ THỂ TÍCH HỢP

### 1. Chat với Gemini

Tạo một hàm để chat với Gemini:

```python
def chat_with_gemini(self, message):
    """Chat với Gemini AI"""
    if not self.gemini_model:
        self.log_to_gui("❌ Chưa kết nối với Gemini API!")
        return None
    
    try:
        response = self.gemini_model.generate_content(message)
        return response.text
    except Exception as e:
        self.log_to_gui(f"❌ Lỗi chat: {str(e)}")
        return None
```

### 2. Xử Lý File Excel với Gemini

Tạo hàm để phân tích dữ liệu Excel:

```python
def analyze_excel_with_gemini(self, excel_path):
    """Phân tích file Excel bằng Gemini"""
    if not self.gemini_model:
        self.log_to_gui("❌ Chưa kết nối với Gemini API!")
        return
    
    try:
        import pandas as pd
        
        # Đọc file Excel
        df = pd.read_excel(excel_path)
        
        # Chuyển đổi thành text để gửi cho Gemini
        data_summary = f"Dữ liệu Excel:\n{df.head(10).to_string()}"
        
        # Gửi yêu cầu phân tích
        prompt = f"""
        Phân tích dữ liệu sau và đưa ra nhận xét:
        {data_summary}
        
        Hãy tóm tắt:
        1. Số lượng bản ghi
        2. Các cột chính
        3. Nhận xét về dữ liệu
        """
        
        response = self.gemini_model.generate_content(prompt)
        self.log_to_gui(f"📊 Phân tích Gemini:\n{response.text}")
        
        return response.text
        
    except Exception as e:
        self.log_to_gui(f"❌ Lỗi phân tích: {str(e)}")
        return None
```

### 3. Xử Lý Hình Ảnh/PDF với Gemini Vision

Sử dụng `gemini-pro-vision` để phân tích hình ảnh:

```python
def analyze_image_with_gemini(self, image_path):
    """Phân tích hình ảnh bằng Gemini Vision"""
    try:
        import google.generativeai as genai
        from PIL import Image
        
        # Tạo model vision
        vision_model = genai.GenerativeModel('gemini-pro-vision')
        
        # Mở hình ảnh
        img = Image.open(image_path)
        
        # Phân tích
        response = vision_model.generate_content([
            "Mô tả chi tiết nội dung trong hình ảnh này",
            img
        ])
        
        self.log_to_gui(f"🖼️ Phân tích hình ảnh:\n{response.text}")
        return response.text
        
    except Exception as e:
        self.log_to_gui(f"❌ Lỗi phân tích hình ảnh: {str(e)}")
        return None
```

---

## 🔧 TÍCH HỢP VÀO CÁC TÁC VỤ HIỆN CÓ

### Tích hợp vào "Lấy Chi Tiết (Excel)"

Sau khi cào dữ liệu, có thể dùng Gemini để phân tích:

```python
# Trong hàm start_detail_scrape_thread, sau khi xuất Excel
def start_detail_scrape_thread(self):
    # ... code hiện tại ...
    
    # Sau khi xuất Excel thành công
    if self.gemini_model:
        self.log_to_gui("🤖 Đang phân tích dữ liệu bằng Gemini...")
        analysis = self.analyze_excel_with_gemini(excel_path)
        if analysis:
            self.log_to_gui(f"📊 Kết quả phân tích:\n{analysis}")
```

### Tích hợp vào "Kiểm Tra Hợp Đồng"

Dùng Gemini để kiểm tra tính hợp lệ của hợp đồng:

```python
def validate_contract_with_gemini(self, contract_data):
    """Kiểm tra hợp đồng bằng Gemini"""
    if not self.gemini_model:
        return None
    
    prompt = f"""
    Kiểm tra thông tin hợp đồng sau:
    - Số hợp đồng: {contract_data.get('contract_id')}
    - Số CCCD: {contract_data.get('cccd')}
    - Họ tên: {contract_data.get('name')}
    
    Hãy kiểm tra:
    1. Định dạng số hợp đồng có hợp lệ không?
    2. Số CCCD có đúng 12 số không?
    3. Có vấn đề gì cần lưu ý không?
    """
    
    response = self.gemini_model.generate_content(prompt)
    return response.text
```

---

## 📝 GHI CHÚ QUAN TRỌNG

### Giới Hạn API

- **Gemini API Free:** 60 requests/phút
- **Nếu vượt quá:** Cần nâng cấp lên paid plan

### Bảo Mật

- API Key được mã hóa base64 trước khi lưu
- File config: `app_data/gemini_config.json`
- **KHÔNG** commit file này lên Git

### Xử Lý Lỗi

Luôn wrap các lời gọi API trong try-except:

```python
try:
    response = self.gemini_model.generate_content(prompt)
except Exception as e:
    self.log_to_gui(f"❌ Lỗi Gemini: {str(e)}")
```

---

## 🎓 TÀI LIỆU THAM KHẢO

- **Gemini API Docs:** https://ai.google.dev/docs
- **Python SDK:** https://github.com/google/generative-ai-python
- **Cookbook:** https://github.com/google-gemini/cookbook

---

## ✅ CHECKLIST HOÀN THÀNH

- [x] Thêm UI nút kết nối Gemini
- [x] Thêm các hàm xử lý cơ bản
- [x] Lưu/Load API Key tự động
- [ ] Cài đặt thư viện `google-generativeai`
- [ ] Lấy API Key từ Google AI Studio
- [ ] Cập nhật hàm `_run_gemini_connection` với code thực
- [ ] Test kết nối
- [ ] Tích hợp vào các tác vụ cụ thể

---

**Chúc bạn tích hợp thành công! 🚀**

