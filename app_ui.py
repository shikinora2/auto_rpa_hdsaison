import customtkinter
from customtkinter import filedialog
import threading
import rpa_logic  # Logic RPA (Tải file & Cào chi tiết)
import logic_convert_pdf # Logic (Trích xuất file local)
from datetime import date
import os
import json
import base64

customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("Trình Tải & Trích Xuất Hợp Đồng (v5 - Flex)")
        self.geometry("600x850") # Tối ưu kích thước

        # === CẤU HÌNH GRID CHO CỬA SỔ CHÍNH ===
        # Cột 0 (cột duy nhất) sẽ tự động co giãn theo chiều ngang (weight=1)
        self.grid_columnconfigure(0, weight=1)
        # Hàng 4 (chứa log_textbox) sẽ tự động co giãn theo chiều dọc (weight=1)
        # Các hàng khác sẽ giữ nguyên kích thước
        self.grid_rowconfigure(4, weight=1)

        # Biến kiểm soát luồng
        self.rpa_thread = None
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        self.config_file = "config.json"

        # --- Frame chứa các input ---
        self.input_frame = customtkinter.CTkFrame(self)
        self.input_frame.grid(row=0, column=0, sticky="ew", pady=10, padx=15)
        
        # Cấu hình 2 cột chính cho input_frame
        self.input_frame.grid_columnconfigure(0, weight=1)  # Cột trái (Đăng nhập)
        self.input_frame.grid_columnconfigure(1, weight=1)  # Cột phải (Filter ngày)

        # === CỘT TRÁI: THÔNG TIN ĐĂNG NHẬP ===
        self.login_frame = customtkinter.CTkFrame(self.input_frame)
        self.login_frame.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        
        self.login_title = customtkinter.CTkLabel(self.login_frame, text="ĐĂNG NHẬP", font=customtkinter.CTkFont(weight="bold", size=12))
        self.login_title.pack(pady=(8, 4), padx=10)
        
        self.username_label = customtkinter.CTkLabel(self.login_frame, text="Tên đăng nhập:", font=customtkinter.CTkFont(size=11))
        self.username_label.pack(pady=(8, 2), padx=15, anchor="w")
        self.username_entry = customtkinter.CTkEntry(self.login_frame, placeholder_text="user", height=28)
        self.username_entry.pack(pady=3, padx=15, fill="x")

        self.password_label = customtkinter.CTkLabel(self.login_frame, text="Mật khẩu:", font=customtkinter.CTkFont(size=11))
        self.password_label.pack(pady=(8, 2), padx=15, anchor="w")
        self.password_entry = customtkinter.CTkEntry(self.login_frame, placeholder_text="pass", show="*", height=28)
        self.password_entry.pack(pady=3, padx=15, fill="x")
        
        self.show_password_check = customtkinter.CTkCheckBox(self.login_frame, text="Hiện mật khẩu", command=self.toggle_password_visibility, font=customtkinter.CTkFont(size=10))
        self.show_password_check.pack(pady=6, padx=15, anchor="w")
        
        self.save_creds_check = customtkinter.CTkCheckBox(self.login_frame, text="Lưu thông tin", font=customtkinter.CTkFont(size=10))
        self.save_creds_check.pack(pady=(0, 8), padx=15, anchor="w")

        # === CỘT PHẢI: BỘ LỌC NGÀY ===
        self.date_container = customtkinter.CTkFrame(self.input_frame)
        self.date_container.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        
        self.date_title = customtkinter.CTkLabel(self.date_container, text="BỘ LỌC NGÀY", font=customtkinter.CTkFont(weight="bold", size=12))
        self.date_title.pack(pady=(8, 4), padx=10)
        
        self.date_frame = customtkinter.CTkFrame(self.date_container, fg_color="transparent")
        self.date_frame.pack(pady=6, padx=12, fill="both", expand=True)
        
        today = date.today()
        current_year = today.year
        self.days = [f"{i:02d}" for i in range(1, 32)]
        self.months = [f"{i:02d}" for i in range(1, 13)]
        self.years = [str(y) for y in range(current_year - 5, current_year + 2)]
        
        # Cấu hình các cột
        self.date_frame.grid_columnconfigure((1, 2, 3), weight=1)
        
        # --- Hàng "Từ Ngày" ---
        self.start_date_label = customtkinter.CTkLabel(self.date_frame, text="Từ:", font=customtkinter.CTkFont(size=11))
        self.start_date_label.grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.start_day_combo = customtkinter.CTkComboBox(self.date_frame, values=self.days, width=55, height=28, font=customtkinter.CTkFont(size=11))
        self.start_day_combo.grid(row=0, column=1, padx=3, pady=6, sticky="ew")
        self.start_day_combo.set(today.strftime("%d"))
        self.start_month_combo = customtkinter.CTkComboBox(self.date_frame, values=self.months, width=55, height=28, font=customtkinter.CTkFont(size=11))
        self.start_month_combo.grid(row=0, column=2, padx=3, pady=6, sticky="ew")
        self.start_month_combo.set(today.strftime("%m"))
        self.start_year_combo = customtkinter.CTkComboBox(self.date_frame, values=self.years, width=70, height=28, font=customtkinter.CTkFont(size=11))
        self.start_year_combo.grid(row=0, column=3, padx=3, pady=6, sticky="ew")
        self.start_year_combo.set(str(current_year))
        
        # --- Hàng "Đến Ngày" ---
        self.end_date_label = customtkinter.CTkLabel(self.date_frame, text="Đến:", font=customtkinter.CTkFont(size=11))
        self.end_date_label.grid(row=1, column=0, padx=6, pady=6, sticky="w")
        self.end_day_combo = customtkinter.CTkComboBox(self.date_frame, values=self.days, width=55, height=28, font=customtkinter.CTkFont(size=11))
        self.end_day_combo.grid(row=1, column=1, padx=3, pady=6, sticky="ew")
        self.end_day_combo.set(today.strftime("%d"))
        self.end_month_combo = customtkinter.CTkComboBox(self.date_frame, values=self.months, width=55, height=28, font=customtkinter.CTkFont(size=11))
        self.end_month_combo.grid(row=1, column=2, padx=3, pady=6, sticky="ew")
        self.end_month_combo.set(today.strftime("%m"))
        self.end_year_combo = customtkinter.CTkComboBox(self.date_frame, values=self.years, width=70, height=28, font=customtkinter.CTkFont(size=11))
        self.end_year_combo.grid(row=1, column=3, padx=3, pady=6, sticky="ew")
        self.end_year_combo.set(str(current_year))
        
        # === CHỌN THƯ MỤC VÀ HÌNH THỨC (BÊN DƯỚI BỘ LỌC NGÀY) ===
        # 3. Chọn thư mục lưu
        self.folder_frame = customtkinter.CTkFrame(self.date_container, fg_color="transparent")
        self.folder_frame.pack(pady=(8, 3), padx=12, fill="x")
        
        self.folder_label = customtkinter.CTkLabel(self.folder_frame, text="Thư mục:", font=customtkinter.CTkFont(size=10))
        self.folder_label.pack(side="left", padx=(0, 3))
        self.folder_entry = customtkinter.CTkEntry(self.folder_frame, state="disabled", height=26, font=customtkinter.CTkFont(size=9))
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=2)
        self.folder_button = customtkinter.CTkButton(self.folder_frame, text="Chọn", command=self.select_folder, width=50, height=26, font=customtkinter.CTkFont(size=10))
        self.folder_button.pack(side="left", padx=(2, 0))
        
        default_save_path = os.path.abspath("downloads_contracts")
        self.folder_entry.configure(state="normal")
        self.folder_entry.insert(0, default_save_path)
        self.folder_entry.configure(state="disabled")

        # 4. Hình thức lưu
        self.save_format_frame = customtkinter.CTkFrame(self.date_container, fg_color="transparent")
        self.save_format_frame.pack(pady=(0, 8), padx=12, fill="x")
        
        self.save_format_label = customtkinter.CTkLabel(self.save_format_frame, text="Hình thức:", font=customtkinter.CTkFont(size=10))
        self.save_format_label.pack(side="left", padx=(0, 5))
        
        self.save_format_button = customtkinter.CTkSegmentedButton(
            self.save_format_frame, 
            values=["PDF", "JSON"],
            command=self.on_save_format_change,
            font=customtkinter.CTkFont(size=9),
            height=26
        )
        self.save_format_button.pack(side="left", fill="x", expand=True, padx=2)
        self.save_format_button.set("PDF")
        
        # === 5. KHUNG ĐIỀU KHIỂN CHÍNH (SẮP XẾP LẠI) ===
        
        # --- NHÓM 1: TÁC VỤ ONLINE (RPA) ---
        self.rpa_frame = customtkinter.CTkFrame(self)
        self.rpa_frame.grid(row=2, column=0, sticky="ew", pady=(3, 3), padx=15)
        
        self.rpa_label = customtkinter.CTkLabel(self.rpa_frame, text="TÁC VỤ TỰ ĐỘNG HÓA (ONLINE)", font=customtkinter.CTkFont(weight="bold", size=12))
        self.rpa_label.pack(pady=(6, 3))

        # Grid container cho các nút RPA
        self.rpa_buttons_frame = customtkinter.CTkFrame(self.rpa_frame, fg_color="transparent")
        self.rpa_buttons_frame.pack(fill="x", padx=8, pady=(3, 6))
        self.rpa_buttons_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Hàng 1: 2 nút chính (Kiểm tra và Tải File)
        self.check_button = customtkinter.CTkButton(
            self.rpa_buttons_frame, 
            text="Kiểm tra số lượng", 
            command=self.start_check_thread, 
            fg_color="#00695C", 
            hover_color="#004D40",
            height=32,
            font=customtkinter.CTkFont(size=11)
        )
        self.check_button.grid(row=0, column=0, padx=3, pady=3, sticky="ew")
        
        self.start_button = customtkinter.CTkButton(
            self.rpa_buttons_frame, 
            text="Tải File (PDF)", 
            command=self.start_rpa_thread,
            height=32,
            font=customtkinter.CTkFont(size=11)
        )
        self.start_button.grid(row=0, column=1, padx=3, pady=3, sticky="ew")
        
        # Hàng 2: 2 nút (Lấy chi tiết và Mở Excel)
        self.scrape_details_button = customtkinter.CTkButton(
            self.rpa_buttons_frame, 
            text="Lấy Chi Tiết (Excel)", 
            command=self.start_detail_scrape_thread,
            fg_color="#004D40",
            hover_color="#00695C",
            height=32,
            font=customtkinter.CTkFont(size=11)
        )
        self.scrape_details_button.grid(row=1, column=0, padx=3, pady=3, sticky="ew")
        
        self.open_excel_button = customtkinter.CTkButton(
            self.rpa_buttons_frame, 
            text="📂 Mở Thư Mục Excel", 
            command=self.open_excel_folder,
            fg_color="#1565C0",
            hover_color="#0D47A1",
            height=32,
            font=customtkinter.CTkFont(size=11)
        )
        self.open_excel_button.grid(row=1, column=1, padx=3, pady=3, sticky="ew")
        
        # Hàng 3: 2 nút điều khiển
        self.pause_button = customtkinter.CTkButton(
            self.rpa_buttons_frame, 
            text="Tạm Dừng", 
            command=self.toggle_pause, 
            state="disabled", 
            fg_color="gray", 
            text_color_disabled="white",
            height=28,
            font=customtkinter.CTkFont(size=10)
        )
        self.pause_button.grid(row=2, column=0, padx=3, pady=3, sticky="ew")

        self.stop_button = customtkinter.CTkButton(
            self.rpa_buttons_frame, 
            text="Kết Thúc (RPA)", 
            command=self.stop_rpa, 
            state="disabled", 
            fg_color="#D32F2F", 
            hover_color="#B71C1C",
            height=28,
            font=customtkinter.CTkFont(size=10)
        )
        self.stop_button.grid(row=2, column=1, padx=3, pady=3, sticky="ew")

        # --- NHÓM 2: TÁC VỤ OFFLINE (LOCAL) ---
        self.local_frame = customtkinter.CTkFrame(self)
        self.local_frame.grid(row=1, column=0, sticky="ew", pady=(3, 6), padx=15)
        
        self.local_label = customtkinter.CTkLabel(self.local_frame, text="TÁC VỤ XỬ LÝ FILE (OFFLINE)", font=customtkinter.CTkFont(weight="bold", size=12))
        self.local_label.pack(pady=(6, 3))
        
        self.extract_button = customtkinter.CTkButton(
            self.local_frame, 
            text="Trích xuất File (PDF/JSON) sang Excel", 
            command=self.start_extraction_thread,
            fg_color="#4E342E",
            hover_color="#6D4C41",
            height=32,
            font=customtkinter.CTkFont(size=11)
        )
        self.extract_button.pack(fill="x", padx=8, pady=(3, 6))
        
        # === KHUNG TRẠNG THÁI (LOG) - ƯU TIÊN HIỂN THỊ ===
        self.log_label = customtkinter.CTkLabel(self, text="TRẠNG THÁI:", font=customtkinter.CTkFont(weight="bold", size=12))
        self.log_label.grid(row=3, column=0, sticky="w", padx=15, pady=(6, 3))
        
        self.log_textbox = customtkinter.CTkTextbox(self, state="disabled", wrap="word", font=customtkinter.CTkFont(size=10))
        self.log_textbox.grid(row=4, column=0, sticky="nsew", pady=(0, 15), padx=15)

        self.load_config()

    def on_save_format_change(self, value):
        if value == "JSON":
            self.start_button.configure(text="Tải File (JSON)")
        else:
            self.start_button.configure(text="Tải File (PDF)")
    
    def open_excel_folder(self):
        """Mở thư mục chứa file Excel đã xuất"""
        import subprocess
        folder_path = self.folder_entry.get()
        if folder_path and os.path.exists(folder_path):
            try:
                # Mở thư mục trong File Explorer
                subprocess.Popen(f'explorer "{folder_path}"')
                self.log_to_gui(f"✅ Đã mở thư mục: {folder_path}")
            except Exception as e:
                self.log_to_gui(f"❌ Lỗi khi mở thư mục: {e}")
        else:
            self.log_to_gui("❌ Thư mục không tồn tại hoặc chưa được chọn!")

    def log_to_gui(self, message):
        self.after(0, self._update_log_textbox, message)

    def _update_log_textbox(self, message):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

        # Kiểm tra các thông điệp kết thúc
        end_messages = ["HOÀN TẤT", "LỖI", "DỪNG THEO YÊU CẦU", "KHÔNG TÌM THẤY", "THẤT BẠI"]
        if any(msg in message.upper() for msg in end_messages):
            self._enable_all_controls()

    def _get_common_inputs(self):
        """Hàm nội bộ để lấy các thông tin chung cho RPA"""
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        start_day = self.start_day_combo.get()
        start_month = self.start_month_combo.get()
        start_year = self.start_year_combo.get()
        end_day = self.end_day_combo.get()
        end_month = self.end_month_combo.get()
        end_year = self.end_year_combo.get()
        
        start_date_str = f"{start_day}{start_month}{start_year}"
        end_date_str = f"{end_day}{end_month}{end_year}"

        if not username or not password:
            self.log_to_gui("LỖI: Vui lòng nhập Tên đăng nhập và Mật khẩu.")
            return None
        
        if self.save_creds_check.get() == 1:
            self.save_config(username, password)
        else:
            self.clear_config()
            
        return username, password, start_date_str, end_date_str
    
    def _disable_all_controls(self, is_rpa_task=True):
        """Vô hiệu hóa tất cả các nút điều khiển chính"""
        self.start_button.configure(state="disabled")
        self.check_button.configure(state="disabled")
        self.scrape_details_button.configure(state="disabled")
        self.extract_button.configure(state="disabled") 
        
        if is_rpa_task:
            self.pause_button.configure(state="normal", text="Tạm Dừng", fg_color="#F9A825", hover_color="#F57F17")
            self.stop_button.configure(state="normal")
        else:
            self.pause_button.configure(state="disabled", text="Tạm Dừng", fg_color="gray")
            self.stop_button.configure(state="disabled")


    def _enable_all_controls(self):
        """Kích hoạt lại các nút điều khiển chính (trạng thái chờ)"""
        self.start_button.configure(state="normal")
        self.check_button.configure(state="normal")
        self.scrape_details_button.configure(state="normal")
        self.extract_button.configure(state="normal")
        self.pause_button.configure(state="disabled", text="Tạm Dừng", fg_color="gray")
        self.stop_button.configure(state="disabled")

    # === TÁC VỤ 1: CHẠY LUỒNG TRÍCH XUẤT LOCAL EXCEL ===
    
    def start_extraction_thread(self):
        """Bắt đầu luồng trích xuất (Excel) (chạy độc lập)"""
        self._disable_all_controls(is_rpa_task=False)
        
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        self.log_to_gui("--- BẮT ĐẦU TRÍCH XUẤT FILE LOCAL SANG EXCEL ---")

        extraction_thread = threading.Thread(
            target=self._run_extraction_logic,
            daemon=True 
        )
        extraction_thread.start()

    def _run_extraction_logic(self):
        """Hàm logic chạy trong luồng (thread) trích xuất"""
        try:
            self.log_to_gui("Vui lòng chọn thư mục chứa file (PDF, JSON)...")
            source_directory = filedialog.askdirectory(title="Chọn thư mục chứa file PDF/JSON cần trích xuất")
            
            if not source_directory:
                self.log_to_gui("Đã hủy. Tác vụ trích xuất dừng lại.")
                self.after(0, self._enable_all_controls)
                return

            self.log_to_gui(f"Đang quét thư mục: {source_directory}")

            results = logic_convert_pdf.process_directory(source_directory)

            if not results:
                self.log_to_gui("Không tìm thấy file hợp đồng (PDF/JSON) nào trong thư mục đã chọn.")
                self.after(0, self._enable_all_controls)
                return

            self.log_to_gui(f"Đã trích xuất xong {len(results)} hợp đồng.")

            self.log_to_gui("Vui lòng chọn nơi lưu file Excel...")
            save_path = filedialog.asksaveasfilename(
                title="Lưu file Excel",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile="Danh_sach_hop_dong_local.xlsx"
            )

            if not save_path:
                self.log_to_gui("Đã hủy lưu file. Tác vụ trích xuất dừng lại.")
                self.after(0, self._enable_all_controls)
                return

            self.log_to_gui(f"Đang xuất ra file Excel: {save_path}")
            logic_convert_pdf.export_data_to_excel(results, save_path)
            
            self.log_to_gui(f"✅ HOÀN TẤT! Đã lưu file Excel thành công (từ file local).")

        except Exception as e:
            if "openpyxl" in str(e):
                self.log_to_gui("❌ LỖI: Vui lòng cài đặt 'openpyxl' để xuất Excel.")
                self.log_to_gui("Chạy lệnh: pip install openpyxl")
            else:
                self.log_to_gui(f"❌ LỖI TRÍCH XUẤT: {e}")
        finally:
            self.after(0, self._enable_all_controls)
            
    # === TÁC VỤ 2: CHẠY LUỒNG KIỂM TRA (RPA) ===
    
    def start_check_thread(self):
        """Lấy thông tin và bắt đầu luồng CHỈ KIỂM TRA."""
        self.pause_event.set()
        self.stop_event.clear()
        inputs = self._get_common_inputs()
        if not inputs: return
        username, password, start_date_str, end_date_str = inputs
        
        self._disable_all_controls(is_rpa_task=True)
        self.pause_button.configure(state="disabled", text="Tạm Dừng", fg_color="gray") # Không thể tạm dừng khi Kiểm tra
        
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        self.log_to_gui("--- BẮT ĐẦU KIỂM TRA SỐ LƯỢNG HỢP ĐỒNG ---")

        self.rpa_thread = threading.Thread(
            target=rpa_logic.check_contract_count,
            args=(username, password, start_date_str, end_date_str,
                  self.pause_event, self.stop_event, self.log_to_gui),
            daemon=True 
        )
        self.rpa_thread.start()

    # === TÁC VỤ 3: CHẠY LUỒNG TẢI FILE (RPA) ===
    
    def start_rpa_thread(self):
        """Lấy thông tin và bắt đầu luồng TẢI FILE/LƯU JSON."""
        self.pause_event.set()
        self.stop_event.clear()
        inputs = self._get_common_inputs()
        if not inputs: return
        username, password, start_date_str, end_date_str = inputs

        save_directory = self.folder_entry.get()
        if not save_directory:
            self.log_to_gui("LỖI: Vui lòng chọn thư mục lưu file.")
            return

        save_format_value = self.save_format_button.get()
        save_format = "JSON" if save_format_value == "Lưu dạng JSON" else "PDF"

        self._disable_all_controls(is_rpa_task=True)
        
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        self.log_to_gui(f"--- BẮT ĐẦU KỊCH BẢN TẢI FILE (LƯU DẠNG: {save_format}) ---")

        self.rpa_thread = threading.Thread(
            target=rpa_logic.run_scrape_and_download_files,
            args=(username, password, start_date_str, end_date_str,
                  save_directory, save_format,
                  self.pause_event, self.stop_event, self.log_to_gui),
            daemon=True 
        )
        self.rpa_thread.start()

    # === TÁC VỤ 4: CHẠY LUỒNG CÀO CHI TIẾT (RPA) ===
    
    def start_detail_scrape_thread(self):
        """Lấy thông tin và bắt đầu luồng CÀO CHI TIẾT."""
        self.pause_event.set()
        self.stop_event.clear()
        inputs = self._get_common_inputs()
        if not inputs: return
        username, password, start_date_str, end_date_str = inputs

        save_directory = self.folder_entry.get()
        if not save_directory:
            self.log_to_gui("LỖI: Vui lòng chọn thư mục lưu file (Excel).")
            return

        self._disable_all_controls(is_rpa_task=True)
        
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        self.log_to_gui(f"--- BẮT ĐẦU KỊCH BẢN CÀO (SCRAPE) CHI TIẾT RA EXCEL ---")

        self.rpa_thread = threading.Thread(
            target=rpa_logic.run_scrape_and_export_details,
            args=(username, password, start_date_str, end_date_str,
                  save_directory,
                  self.pause_event, self.stop_event, self.log_to_gui),
            daemon=True 
        )
        self.rpa_thread.start()

    # --- Các hàm helper còn lại ---
    
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    config_data = json.load(f)
                    # Giải mã cả username và password
                    encoded_user = config_data.get("username", "")
                    encoded_pass = config_data.get("password", "")
                    username = base64.b64decode(encoded_user.encode()).decode() if encoded_user else ""
                    password = base64.b64decode(encoded_pass.encode()).decode() if encoded_pass else ""
                    self.username_entry.insert(0, username)
                    self.password_entry.insert(0, password)
                    self.save_creds_check.select()
            except Exception as e:
                self.log_to_gui(f"Lỗi: Không thể đọc tệp config.json. Lỗi: {e}")

    def save_config(self, username, password):
        try:
            # Mã hóa cả username và password
            encoded_user = base64.b64encode(username.encode()).decode()
            encoded_pass = base64.b64encode(password.encode()).decode()
            config_data = {"username": encoded_user, "password": encoded_pass}
            with open(self.config_file, "w") as f:
                json.dump(config_data, f)
            self.log_to_gui("Đã lưu thông tin đăng nhập (đã mã hóa).")
        except Exception as e:
            self.log_to_gui(f"Lỗi: Không thể lưu config. Lỗi: {e}")

    def clear_config(self):
        if os.path.exists(self.config_file):
            try:
                os.remove(self.config_file)
                self.log_to_gui("Đã xóa thông tin đăng nhập đã lưu.")
            except Exception as e:
                self.log_to_gui(f"Lỗi: Không thể xóa config. Lỗi: {e}")

    def toggle_password_visibility(self):
        if self.show_password_check.get() == 1:
            self.password_entry.configure(show="")
        else:
            self.password_entry.configure(show="*")
            
    def select_folder(self):
        path = filedialog.askdirectory(initialdir=self.folder_entry.get())
        if path:
            self.folder_entry.configure(state="normal")
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, path)
            self.folder_entry.configure(state="disabled")

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.configure(text="Tiếp Tục", fg_color="#4CAF50", hover_color="#388E3C")
            self.log_to_gui("...Đã tạm dừng. Nhấn 'Tiếp Tục' để chạy...")
        else:
            self.pause_event.set()
            self.pause_button.configure(text="Tạm Dừng", fg_color="#F9A825", hover_color="#F57F17")
            self.log_to_gui("...Đang tiếp tục...")

    def stop_rpa(self):
        if self.rpa_thread and self.rpa_thread.is_alive():
            self.log_to_gui("--- !!! ĐANG GỬI LỆNH DỪNG, VUI LÒNG CHỜ... !!! ---")
            self.stop_event.set()
            self.pause_event.set() 
            self._disable_all_controls(is_rpa_task=False) # Tắt hết nút
            self.stop_button.configure(text="Đang dừng...")


if __name__ == "__main__":
    app = App()
    app.mainloop()

