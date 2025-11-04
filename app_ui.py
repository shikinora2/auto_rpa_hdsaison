import customtkinter
from customtkinter import filedialog
from tkinter import messagebox
import threading
import rpa_logic  # Logic RPA (Tải file & Cào chi tiết)
import logic_convert_pdf # Logic (Trích xuất file local)
from datetime import date
import os
import json
import base64
import zalo_logic

customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("Trình Tải & Trích Xuất Hợp Đồng (v6 - Tabs)")
        self.geometry("850x700")

        # === CẤU HÌNH GRID CHO CỬA SỔ CHÍNH ===
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === CẤU HÌNH GRID CHO CỬA SỔ CHÍNH ===
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Biến kiểm soát luồng
        self.rpa_thread = None
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()

        # Thư mục lưu trữ dữ liệu ứng dụng
        self.app_data_dir = "app_data"
        if not os.path.exists(self.app_data_dir):
            os.makedirs(self.app_data_dir)

        self.config_file = os.path.join(self.app_data_dir, "config.json")

        # === TẠO TABVIEW ===
        self.tabview = customtkinter.CTkTabview(self, width=600, height=650)
        self.tabview.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        
        # Tạo 3 tabs
        self.tabview.add("Trang Chủ")
        self.tabview.add("Tác Vụ")
        self.tabview.add("Auto Zalo")
        
        # Cấu hình grid cho từng tab
        self.tabview.tab("Trang Chủ").grid_columnconfigure(0, weight=1)
        self.tabview.tab("Trang Chủ").grid_rowconfigure(2, weight=1)
        
        self.tabview.tab("Tác Vụ").grid_columnconfigure(0, weight=1)
        self.tabview.tab("Tác Vụ").grid_rowconfigure(4, weight=1)
        
        self.tabview.tab("Auto Zalo").grid_columnconfigure(0, weight=1)
        self.tabview.tab("Auto Zalo").grid_rowconfigure(1, weight=1)

        # Biến lưu dữ liệu khách hàng cho Zalo
        self.zalo_customer_data = []  # List of dict: [{name, phone, address, ...}, ...]
        self.zalo_excel_path = None

        # Biến quản lý tài khoản Zalo
        self.current_account_id = None  # ID tài khoản đang chọn
        self.account_manager = zalo_logic.ZaloAccountManager()  # Khởi tạo ngay

        # Biến quản lý trạng thái tạm dừng
        self.is_paused = False

        # === TAB 1: TRANG CHỦ ===
        self.create_home_tab()
        
        # === TAB 2: TÁC VỤ ===
        self.create_tasks_tab()
        
        # === TAB 3: AUTO ZALO ===
        self.create_zalo_tab()

        self.load_config()
        self.load_zalo_session_info()  # Load thông tin session Zalo

    def create_home_tab(self):
        """Tạo nội dung cho tab Trang Chủ (Đăng nhập + Log)"""
        home_tab = self.tabview.tab("Trang Chủ")
        
        # === PHẦN ĐĂNG NHẬP ===
        self.login_frame = customtkinter.CTkFrame(home_tab)
        self.login_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        self.login_title = customtkinter.CTkLabel(
            self.login_frame,
            text="ĐĂNG NHẬP HỆ THỐNG",
            font=customtkinter.CTkFont(weight="bold", size=14)
        )
        self.login_title.pack(pady=(10, 8), padx=10)
        
        # Frame chứa các input
        login_inputs = customtkinter.CTkFrame(self.login_frame, fg_color="transparent")
        login_inputs.pack(pady=(0, 10), padx=20, fill="x")
        
        self.username_label = customtkinter.CTkLabel(
            login_inputs, 
            text="Tên đăng nhập:", 
            font=customtkinter.CTkFont(size=11)
        )
        self.username_label.pack(pady=(5, 2), anchor="w")
        self.username_entry = customtkinter.CTkEntry(
            login_inputs, 
            placeholder_text="Nhập tên đăng nhập", 
            height=32
        )
        self.username_entry.pack(pady=3, fill="x")

        self.password_label = customtkinter.CTkLabel(
            login_inputs, 
            text="Mật khẩu:", 
            font=customtkinter.CTkFont(size=11)
        )
        self.password_label.pack(pady=(8, 2), anchor="w")
        self.password_entry = customtkinter.CTkEntry(
            login_inputs, 
            placeholder_text="Nhập mật khẩu", 
            show="*", 
            height=32
        )
        self.password_entry.pack(pady=3, fill="x")
        
        # Checkboxes
        checkbox_frame = customtkinter.CTkFrame(login_inputs, fg_color="transparent")
        checkbox_frame.pack(pady=8, fill="x")
        
        self.show_password_check = customtkinter.CTkCheckBox(
            checkbox_frame, 
            text="Hiện mật khẩu", 
            command=self.toggle_password_visibility,
            font=customtkinter.CTkFont(size=10)
        )
        self.show_password_check.pack(side="left", padx=(0, 10))
        
        self.save_creds_check = customtkinter.CTkCheckBox(
            checkbox_frame, 
            text="Lưu thông tin đăng nhập",
            font=customtkinter.CTkFont(size=10)
        )
        self.save_creds_check.pack(side="left")

        # === PHẦN LOG TRẠNG THÁI ===
        self.log_label = customtkinter.CTkLabel(
            home_tab,
            text="TRẠNG THÁI HỆ THỐNG",
            font=customtkinter.CTkFont(weight="bold", size=13)
        )
        self.log_label.grid(row=1, column=0, sticky="w", padx=10, pady=(10, 5))
        
        self.log_textbox = customtkinter.CTkTextbox(
            home_tab, 
            state="disabled", 
            wrap="word", 
            font=customtkinter.CTkFont(size=10)
        )
        self.log_textbox.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

    def create_tasks_tab(self):
        """Tạo nội dung cho tab Tác Vụ (Các nút điều khiển)"""
        tasks_tab = self.tabview.tab("Tác Vụ")
        
        # === BỘ LỌC NGÀY ===
        self.date_frame = customtkinter.CTkFrame(tasks_tab)
        self.date_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        self.date_title = customtkinter.CTkLabel(
            self.date_frame,
            text="BỘ LỌC NGÀY",
            font=customtkinter.CTkFont(weight="bold", size=13)
        )
        self.date_title.pack(pady=(10, 5))
        
        # Grid container cho date picker
        date_grid = customtkinter.CTkFrame(self.date_frame, fg_color="transparent")
        date_grid.pack(pady=(5, 10), padx=15, fill="x")
        date_grid.grid_columnconfigure((1, 2, 3), weight=1)
        
        today = date.today()
        current_year = today.year
        self.days = [f"{i:02d}" for i in range(1, 32)]
        self.months = [f"{i:02d}" for i in range(1, 13)]
        self.years = [str(y) for y in range(current_year - 5, current_year + 2)]
        
        # Từ ngày
        self.start_date_label = customtkinter.CTkLabel(
            date_grid, 
            text="Từ:", 
            font=customtkinter.CTkFont(size=11, weight="bold")
        )
        self.start_date_label.grid(row=0, column=0, padx=6, pady=6, sticky="w")
        
        self.start_day_combo = customtkinter.CTkComboBox(
            date_grid, 
            values=self.days, 
            width=60, 
            height=30,
            font=customtkinter.CTkFont(size=11)
        )
        self.start_day_combo.grid(row=0, column=1, padx=3, pady=6, sticky="ew")
        self.start_day_combo.set(today.strftime("%d"))
        
        self.start_month_combo = customtkinter.CTkComboBox(
            date_grid, 
            values=self.months, 
            width=60, 
            height=30,
            font=customtkinter.CTkFont(size=11)
        )
        self.start_month_combo.grid(row=0, column=2, padx=3, pady=6, sticky="ew")
        self.start_month_combo.set(today.strftime("%m"))
        
        self.start_year_combo = customtkinter.CTkComboBox(
            date_grid, 
            values=self.years, 
            width=80, 
            height=30,
            font=customtkinter.CTkFont(size=11)
        )
        self.start_year_combo.grid(row=0, column=3, padx=3, pady=6, sticky="ew")
        self.start_year_combo.set(str(current_year))
        
        # Đến ngày
        self.end_date_label = customtkinter.CTkLabel(
            date_grid, 
            text="Đến:", 
            font=customtkinter.CTkFont(size=11, weight="bold")
        )
        self.end_date_label.grid(row=1, column=0, padx=6, pady=6, sticky="w")
        
        self.end_day_combo = customtkinter.CTkComboBox(
            date_grid, 
            values=self.days, 
            width=60, 
            height=30,
            font=customtkinter.CTkFont(size=11)
        )
        self.end_day_combo.grid(row=1, column=1, padx=3, pady=6, sticky="ew")
        self.end_day_combo.set(today.strftime("%d"))
        
        self.end_month_combo = customtkinter.CTkComboBox(
            date_grid, 
            values=self.months, 
            width=60, 
            height=30,
            font=customtkinter.CTkFont(size=11)
        )
        self.end_month_combo.grid(row=1, column=2, padx=3, pady=6, sticky="ew")
        self.end_month_combo.set(today.strftime("%m"))
        
        self.end_year_combo = customtkinter.CTkComboBox(
            date_grid, 
            values=self.years, 
            width=80, 
            height=30,
            font=customtkinter.CTkFont(size=11)
        )
        self.end_year_combo.grid(row=1, column=3, padx=3, pady=6, sticky="ew")
        self.end_year_combo.set(str(current_year))

        # === CHỌN THƯ MỤC VÀ HÌNH THỨC ===
        settings_frame = customtkinter.CTkFrame(tasks_tab)
        settings_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        # Chọn thư mục
        folder_container = customtkinter.CTkFrame(settings_frame, fg_color="transparent")
        folder_container.pack(pady=8, padx=12, fill="x")
        
        self.folder_label = customtkinter.CTkLabel(
            folder_container, 
            text="Thư mục lưu:", 
            font=customtkinter.CTkFont(size=11)
        )
        self.folder_label.pack(side="left", padx=(0, 5))
        
        self.folder_entry = customtkinter.CTkEntry(
            folder_container, 
            state="disabled", 
            height=30,
            font=customtkinter.CTkFont(size=10)
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=3)
        
        self.folder_button = customtkinter.CTkButton(
            folder_container,
            text="Chọn",
            command=self.select_folder,
            width=70,
            height=30,
            font=customtkinter.CTkFont(size=10)
        )
        self.folder_button.pack(side="left", padx=(3, 0))
        
        default_save_path = os.path.abspath("downloads_contracts")
        self.folder_entry.configure(state="normal")
        self.folder_entry.insert(0, default_save_path)
        self.folder_entry.configure(state="disabled")
        
        # Hình thức lưu
        format_container = customtkinter.CTkFrame(settings_frame, fg_color="transparent")
        format_container.pack(pady=(0, 8), padx=12, fill="x")
        
        self.save_format_label = customtkinter.CTkLabel(
            format_container, 
            text="Định dạng lưu:", 
            font=customtkinter.CTkFont(size=11)
        )
        self.save_format_label.pack(side="left", padx=(0, 8))
        
        self.save_format_button = customtkinter.CTkSegmentedButton(
            format_container, 
            values=["PDF", "JSON"],
            command=self.on_save_format_change,
            font=customtkinter.CTkFont(size=10),
            height=30
        )
        self.save_format_button.pack(side="left", fill="x", expand=True)
        self.save_format_button.set("PDF")

        # === TÁC VỤ ONLINE (RPA) ===
        self.rpa_frame = customtkinter.CTkFrame(tasks_tab)
        self.rpa_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        self.rpa_label = customtkinter.CTkLabel(
            self.rpa_frame, 
            text="🌐 TÁC VỤ TỰ ĐỘNG HÓA (ONLINE)", 
            font=customtkinter.CTkFont(weight="bold", size=12)
        )
        self.rpa_label.pack(pady=(10, 8))

        # Grid buttons
        rpa_buttons = customtkinter.CTkFrame(self.rpa_frame, fg_color="transparent")
        rpa_buttons.pack(fill="x", padx=10, pady=(0, 10))
        rpa_buttons.grid_columnconfigure((0, 1), weight=1)
        
        # Hàng 1
        self.check_button = customtkinter.CTkButton(
            rpa_buttons,
            text="Kiểm tra số lượng",
            command=self.start_check_thread,
            fg_color="#00695C",
            hover_color="#004D40",
            height=36,
            font=customtkinter.CTkFont(size=11)
        )
        self.check_button.grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        
        self.start_button = customtkinter.CTkButton(
            rpa_buttons,
            text="Tải File (PDF)",
            command=self.start_rpa_thread,
            height=36,
            font=customtkinter.CTkFont(size=11)
        )
        self.start_button.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        
        # Hàng 2
        self.scrape_details_button = customtkinter.CTkButton(
            rpa_buttons,
            text="Lấy Chi Tiết (Excel)",
            command=self.start_detail_scrape_thread,
            fg_color="#004D40",
            hover_color="#00695C",
            height=36,
            font=customtkinter.CTkFont(size=11)
        )
        self.scrape_details_button.grid(row=1, column=0, padx=4, pady=4, sticky="ew")
        
        self.open_excel_button = customtkinter.CTkButton(
            rpa_buttons,
            text="Mở Thư Mục Excel",
            command=self.open_excel_folder,
            fg_color="#1565C0",
            hover_color="#0D47A1",
            height=36,
            font=customtkinter.CTkFont(size=11)
        )
        self.open_excel_button.grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        
        # Hàng 3 - Điều khiển
        self.pause_button = customtkinter.CTkButton(
            rpa_buttons,
            text="Tạm Dừng",
            command=self.toggle_pause,
            state="disabled",
            fg_color="gray",
            text_color_disabled="white",
            height=32,
            font=customtkinter.CTkFont(size=10)
        )
        self.pause_button.grid(row=2, column=0, padx=4, pady=4, sticky="ew")

        self.stop_button = customtkinter.CTkButton(
            rpa_buttons,
            text="Kết Thúc (RPA)",
            command=self.stop_rpa,
            state="disabled",
            fg_color="#D32F2F",
            hover_color="#B71C1C",
            height=32,
            font=customtkinter.CTkFont(size=10)
        )
        self.stop_button.grid(row=2, column=1, padx=4, pady=4, sticky="ew")

        # === TÁC VỤ OFFLINE (LOCAL) ===
        self.local_frame = customtkinter.CTkFrame(tasks_tab)
        self.local_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        self.local_label = customtkinter.CTkLabel(
            self.local_frame,
            text="TÁC VỤ XỬ LÝ FILE (OFFLINE)",
            font=customtkinter.CTkFont(weight="bold", size=12)
        )
        self.local_label.pack(pady=(10, 8))
        
        self.extract_button = customtkinter.CTkButton(
            self.local_frame,
            text="Trích xuất File (PDF/JSON) sang Excel",
            command=self.start_extraction_thread,
            fg_color="#4E342E",
            hover_color="#6D4C41",
            height=36,
            font=customtkinter.CTkFont(size=11)
        )
        self.extract_button.pack(fill="x", padx=10, pady=(0, 10))

    def create_zalo_tab(self):
        """Tạo nội dung cho tab Auto Zalo với ScrollableFrame"""
        zalo_tab = self.tabview.tab("Auto Zalo")

        # === TIÊU ĐỀ ===
        zalo_title = customtkinter.CTkLabel(
            zalo_tab,
            text="TỰ ĐỘNG HÓA ZALO",
            font=customtkinter.CTkFont(weight="bold", size=14)
        )
        zalo_title.grid(row=0, column=0, pady=(10, 5), sticky="ew", padx=10)

        # === SCROLLABLE FRAME ===
        scrollable_frame = customtkinter.CTkScrollableFrame(zalo_tab, fg_color="transparent")
        scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        scrollable_frame.grid_columnconfigure(0, weight=1)

        # === 1. QUẢN LÝ TÀI KHOẢN ZALO ===
        account_frame = customtkinter.CTkFrame(scrollable_frame)
        account_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        account_frame.grid_columnconfigure(1, weight=1)
        account_frame.grid_columnconfigure(5, weight=1)

        account_title = customtkinter.CTkLabel(
            account_frame,
            text="Quản Lý Tài Khoản Zalo",
            font=customtkinter.CTkFont(weight="bold", size=12)
        )
        account_title.grid(row=0, column=0, columnspan=6, pady=(10, 8), padx=10, sticky="w")

        # Tài khoản
        account_label = customtkinter.CTkLabel(
            account_frame, text="Tài khoản:", font=customtkinter.CTkFont(size=10)
        )
        account_label.grid(row=1, column=0, padx=(15, 5), pady=5, sticky="w")

        self.account_combobox = customtkinter.CTkComboBox(
            account_frame, values=["Chưa có tài khoản"], width=180,
            command=self.on_account_selected, font=customtkinter.CTkFont(size=10)
        )
        self.account_combobox.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.account_combobox.set("Chưa có tài khoản")

        # Nút thêm tài khoản
        add_account_btn = customtkinter.CTkButton(
            account_frame, text="+", width=30, height=28,
            command=self.add_zalo_account, font=customtkinter.CTkFont(size=14)
        )
        add_account_btn.grid(row=1, column=2, padx=5, pady=5)

        # Nút xóa tài khoản
        delete_account_btn = customtkinter.CTkButton(
            account_frame, text="X", width=30, height=28,
            command=self.delete_zalo_account, fg_color="#DC3545", hover_color="#C82333",
            font=customtkinter.CTkFont(size=14)
        )
        delete_account_btn.grid(row=1, column=3, padx=5, pady=5)

        # Họ tên Zalo
        zalo_name_title = customtkinter.CTkLabel(
            account_frame, text="Họ tên:", font=customtkinter.CTkFont(size=10)
        )
        zalo_name_title.grid(row=1, column=4, padx=(15, 5), pady=5, sticky="w")

        self.zalo_name_label = customtkinter.CTkLabel(
            account_frame, text="Chưa cập nhật", font=customtkinter.CTkFont(size=10),
            text_color="gray"
        )
        self.zalo_name_label.grid(row=1, column=5, padx=5, pady=5, sticky="w")

        # Phiên đăng nhập
        session_title = customtkinter.CTkLabel(
            account_frame, text="Phiên đăng nhập:", font=customtkinter.CTkFont(size=10)
        )
        session_title.grid(row=2, column=0, padx=(15, 5), pady=5, sticky="w")

        self.zalo_session_label = customtkinter.CTkLabel(
            account_frame, text="Chưa đăng nhập", font=customtkinter.CTkFont(size=10),
            text_color="gray"
        )
        self.zalo_session_label.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="w")

        # Trạng thái
        status_title = customtkinter.CTkLabel(
            account_frame, text="Trạng thái:", font=customtkinter.CTkFont(size=10)
        )
        status_title.grid(row=2, column=4, padx=(15, 5), pady=5, sticky="w")

        self.zalo_status_label = customtkinter.CTkLabel(
            account_frame, text="❌ Inactive", font=customtkinter.CTkFont(size=10),
            text_color="red"
        )
        self.zalo_status_label.grid(row=2, column=5, padx=5, pady=5, sticky="w")

        # Nút kiểm tra và cập nhật
        check_button = customtkinter.CTkButton(
            account_frame, text="Kiểm tra & Cập nhật",
            command=self.check_zalo_status, height=32,
            font=customtkinter.CTkFont(size=10)
        )
        check_button.grid(row=3, column=0, columnspan=3, padx=15, pady=(5, 10), sticky="ew")

        # Nút mở Zalo
        open_zalo_btn = customtkinter.CTkButton(
            account_frame, text="Mở Zalo",
            command=self.open_zalo_window, height=32,
            fg_color="#0068FF", hover_color="#0052CC",
            font=customtkinter.CTkFont(size=10)
        )
        open_zalo_btn.grid(row=3, column=4, columnspan=2, padx=15, pady=(5, 10), sticky="ew")

        # === 2. NHẬP DỮ LIỆU KHÁCH HÀNG ===

        # === 2. NHẬP DỮ LIỆU KHÁCH HÀNG ===
        data_frame = customtkinter.CTkFrame(scrollable_frame)
        data_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        data_frame.grid_columnconfigure(0, weight=1)

        data_title = customtkinter.CTkLabel(
            data_frame,
            text="� Nhập Dữ Liệu Khách Hàng",
            font=customtkinter.CTkFont(weight="bold", size=12)
        )
        data_title.grid(row=0, column=0, pady=(10, 8), padx=10, sticky="w")

        # Hiển thị file đã chọn
        self.zalo_file_label = customtkinter.CTkLabel(
            data_frame,
            text="Chưa chọn file",
            font=customtkinter.CTkFont(size=10),
            text_color="gray"
        )
        self.zalo_file_label.grid(row=1, column=0, padx=15, pady=(0, 5), sticky="w")

        # Nút chọn file Excel
        self.select_excel_button = customtkinter.CTkButton(
            data_frame,
            text="Chọn File Excel",
            command=self.select_zalo_excel,
            height=32,
            font=customtkinter.CTkFont(size=11)
        )
        self.select_excel_button.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))

        # Hiển thị số lượng khách hàng
        self.zalo_customer_count_label = customtkinter.CTkLabel(
            data_frame,
            text="Số khách hàng: 0",
            font=customtkinter.CTkFont(size=10, weight="bold"),
            text_color="#0068FF"
        )
        self.zalo_customer_count_label.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="w")

        # === 2. KẾT BẠN HÀNG LOẠT ===
        friend_frame = customtkinter.CTkFrame(scrollable_frame)
        friend_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        friend_frame.grid_columnconfigure(0, weight=1)

        friend_title = customtkinter.CTkLabel(
            friend_frame,
            text="� Kết Bạn Hàng Loạt",
            font=customtkinter.CTkFont(weight="bold", size=12)
        )
        friend_title.grid(row=0, column=0, pady=(10, 8), padx=10, sticky="w")

        # Hướng dẫn
        friend_help = customtkinter.CTkLabel(
            friend_frame,
            text="Gửi lời mời kết bạn đến tất cả số điện thoại trong danh sách",
            font=customtkinter.CTkFont(size=9),
            text_color="gray"
        )
        friend_help.grid(row=1, column=0, padx=15, pady=(0, 5), sticky="w")

        # Checkbox bỏ qua khách hàng đã xử lý
        self.skip_processed_var = customtkinter.BooleanVar(value=True)  # Mặc định bật
        self.skip_processed_checkbox = customtkinter.CTkCheckBox(
            friend_frame,
            text="Bỏ qua khách hàng đã kết bạn thành công",
            variable=self.skip_processed_var,
            font=customtkinter.CTkFont(size=10),
            text_color="#28A745"
        )
        self.skip_processed_checkbox.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="w")

        # Frame chứa các nút
        buttons_frame = customtkinter.CTkFrame(friend_frame, fg_color="transparent")
        buttons_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 15))
        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=0)

        # Nút kết bạn
        self.add_friend_button = customtkinter.CTkButton(
            buttons_frame,
            text="Kết Bạn Hàng Loạt",
            command=self.add_friends_bulk,
            fg_color="#FFC107",
            hover_color="#E0A800",
            text_color="black",
            height=36,
            font=customtkinter.CTkFont(size=11, weight="bold")
        )
        self.add_friend_button.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        # Nút tạm dừng/tiếp tục (Zalo)
        self.zalo_pause_button = customtkinter.CTkButton(
            buttons_frame,
            text="Tạm dừng",
            command=self.toggle_pause,
            fg_color="#6C757D",
            hover_color="#5A6268",
            height=36,
            width=120,
            font=customtkinter.CTkFont(size=11, weight="bold"),
            state="disabled"  # Mặc định disabled
        )
        self.zalo_pause_button.grid(row=0, column=1, sticky="ew")

        # === 3. NHẮN TIN HÀNG LOẠT ===
        message_frame = customtkinter.CTkFrame(scrollable_frame)
        message_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        message_frame.grid_columnconfigure(0, weight=1)

        message_title = customtkinter.CTkLabel(
            message_frame,
            text="� Nhắn Tin Hàng Loạt",
            font=customtkinter.CTkFont(weight="bold", size=12)
        )
        message_title.grid(row=0, column=0, pady=(10, 8), padx=10, sticky="w")

        # Hướng dẫn sử dụng biến
        help_label = customtkinter.CTkLabel(
            message_frame,
            text="Biến có sẵn: {name}, {phone}, {address}, {cccd}, {dob}, {contract_id}, {gender}",
            font=customtkinter.CTkFont(size=9),
            text_color="gray"
        )
        help_label.grid(row=1, column=0, padx=15, pady=(0, 5), sticky="w")

        # TextBox nhập kịch bản
        message_label = customtkinter.CTkLabel(
            message_frame,
            text="Kịch bản tin nhắn:",
            font=customtkinter.CTkFont(size=10)
        )
        message_label.grid(row=2, column=0, padx=15, pady=(0, 3), sticky="w")

        self.zalo_message_template = customtkinter.CTkTextbox(
            message_frame,
            height=120,
            font=customtkinter.CTkFont(size=10)
        )
        self.zalo_message_template.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 10))

        # Template mặc định
        default_template = """Xin chào anh/chị {name},

Chúng tôi xin thông báo về hợp đồng {contract_id}:
- Số điện thoại: {phone}
- Địa chỉ: {address}
- Số CCCD: {cccd}

Vui lòng liên hệ nếu có thắc mắc.
Trân trọng!"""
        self.zalo_message_template.insert("1.0", default_template)

        # Checkbox bỏ qua khách hàng đã gửi tin nhắn
        self.skip_sent_messages_var = customtkinter.BooleanVar(value=True)  # Mặc định bật
        self.skip_sent_messages_checkbox = customtkinter.CTkCheckBox(
            message_frame,
            text="Bỏ qua khách hàng đã gửi tin nhắn thành công",
            variable=self.skip_sent_messages_var,
            font=customtkinter.CTkFont(size=10),
            text_color="#28A745"
        )
        self.skip_sent_messages_checkbox.grid(row=4, column=0, padx=15, pady=(0, 5), sticky="w")

        # Nút gửi tin nhắn
        self.send_message_button = customtkinter.CTkButton(
            message_frame,
            text="Gửi Tin Nhắn Hàng Loạt",
            command=self.send_bulk_messages,
            fg_color="#28A745",
            hover_color="#218838",
            height=36,
            font=customtkinter.CTkFont(size=11, weight="bold")
        )
        self.send_message_button.grid(row=5, column=0, sticky="ew", padx=15, pady=(0, 15))

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
        save_format = "JSON" if save_format_value == "JSON" else "PDF"

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

    def load_zalo_session_info(self):
        """Load thông tin session Zalo khi khởi động ứng dụng"""
        try:
            import zalo_logic

            # Khởi tạo account manager
            self.account_manager = zalo_logic.ZaloAccountManager()

            # Load danh sách tài khoản
            self.load_account_list()

        except Exception as e:
            print(f"Lỗi khi load session info: {str(e)}")

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

    # --- HÀM PLACEHOLDER CHO ZALO & GOOGLE SHEETS ---
    def open_zalo_window(self):
        """Mở cửa sổ mới để xử lý Zalo với Session Management"""
        self.log_to_gui("🔵 Đang mở Zalo với session management...")
        
        # Chạy trong thread riêng để không block UI
        zalo_thread = threading.Thread(
            target=self._run_zalo_login,
            daemon=True
        )
        zalo_thread.start()
    
    def check_zalo_status(self):
        """Kiểm tra trạng thái đăng nhập Zalo - Mở Zalo, kiểm tra cookie và cập nhật họ tên"""
        # Chạy trong thread riêng
        thread = threading.Thread(
            target=self._run_check_zalo_status,
            daemon=True
        )
        thread.start()

    def _run_check_zalo_status(self):
        """Thread worker để kiểm tra và cập nhật thông tin Zalo"""
        try:
            import zalo_logic
            import zalo_automation
            from datetime import datetime

            # Kiểm tra đã chọn tài khoản chưa
            if not self.current_account_id:
                self.log_to_gui("❌ Vui lòng chọn tài khoản trước!")
                messagebox.showwarning(
                    "Cảnh báo",
                    "Vui lòng chọn tài khoản Zalo trước khi kiểm tra!",
                    parent=self
                )
                return

            self.log_to_gui("⏳ Đang kiểm tra trạng thái Zalo...")

            # Lấy session manager cho tài khoản đã chọn
            session_manager = self.account_manager.get_session_manager(self.current_account_id)

            # Đăng nhập Zalo
            success, p, context, page = session_manager.login_with_session(max_wait_time=30)

            if not success:
                self.log_to_gui("❌ Không thể kết nối Zalo")
                if context:
                    context.close()
                if p:
                    p.stop()
                return

            self.log_to_gui("✅ Đã kết nối Zalo")

            # Tạo automation instance
            automation = zalo_automation.ZaloAutomation(page)

            # Lấy tên Zalo (sẽ tự động lưu vào session)
            my_zalo_name = automation.get_my_zalo_name(session_manager)

            # Cập nhật thời gian kiểm tra
            current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            session_info = session_manager.get_session_info() or {}
            session_info['last_check'] = current_time
            session_manager.save_session_info(session_info)

            # Cập nhật thông tin tài khoản trong account manager
            last_login = session_info.get('last_login', current_time)
            self.account_manager.update_account(
                self.current_account_id,
                zalo_name=my_zalo_name,
                last_login=last_login,
                status='active'
            )

            self.log_to_gui(f"✅ Cập nhật thành công!")
            self.log_to_gui(f"   👤 Họ tên: {my_zalo_name}")
            self.log_to_gui(f"   📅 Phiên đăng nhập: {last_login}")
            self.log_to_gui(f"   🔄 Kiểm tra lúc: {current_time}")

            # Reload danh sách tài khoản để cập nhật tên Zalo
            self.load_account_list()

            # Cleanup
            try:
                if context:
                    context.close()
                if p:
                    p.stop()
            except:
                pass

        except Exception as e:
            self.log_to_gui(f"❌ Lỗi khi kiểm tra: {str(e)}")
    
    def clear_zalo_session(self):
        """Xóa session Zalo đã lưu"""
        try:
            # Kiểm tra đã chọn tài khoản chưa
            if not self.current_account_id:
                messagebox.showwarning(
                    "Cảnh báo",
                    "Vui lòng chọn tài khoản trước!",
                    parent=self
                )
                return

            # Xác nhận trước khi xóa
            result = messagebox.askyesno(
                "Xác nhận xóa session",
                "Bạn có chắc muốn xóa phiên đăng nhập Zalo?\nBạn sẽ phải quét QR lại lần sau.",
                parent=self
            )

            if result:
                session_manager = self.account_manager.get_session_manager(self.current_account_id)
                if session_manager.delete_session():
                    self.log_to_gui("✅ Đã xóa phiên đăng nhập Zalo")

                    # Cập nhật trạng thái tài khoản
                    self.account_manager.update_account(
                        self.current_account_id,
                        status='inactive',
                        last_login=None
                    )

                    # Reload danh sách tài khoản
                    self.load_account_list()

                    messagebox.showinfo(
                        "Thành công",
                        "Đã xóa phiên đăng nhập Zalo!",
                        parent=self
                    )
                else:
                    self.log_to_gui("❌ Không thể xóa phiên đăng nhập")
                    messagebox.showerror(
                        "Lỗi",
                        "Không thể xóa phiên đăng nhập!",
                        parent=self
                    )
            
        except Exception as e:
            self.log_to_gui(f"❌ Lỗi khi xóa session: {str(e)}")
    
    def _run_zalo_login(self):
        """Logic đăng nhập Zalo với Session Management"""
        playwright_instance = None
        context = None

        try:
            import zalo_logic

            # Kiểm tra đã chọn tài khoản chưa
            if not self.current_account_id:
                self.log_to_gui("❌ Vui lòng chọn tài khoản trước!")
                messagebox.showwarning(
                    "Cảnh báo",
                    "Vui lòng chọn tài khoản Zalo trước khi mở Zalo!",
                    parent=self
                )
                return

            self.log_to_gui("⏳ Đang khởi tạo Zalo Session Manager...")

            # Lấy session manager cho tài khoản đã chọn
            session_manager = self.account_manager.get_session_manager(self.current_account_id)

            # Kiểm tra session hiện có
            if session_manager.has_session():
                self.log_to_gui("✓ Tìm thấy phiên đăng nhập đã lưu")
                session_info = session_manager.get_session_info()
                if session_info:
                    self.log_to_gui(f"  - Lần đăng nhập cuối: {session_info.get('last_login', 'N/A')}")
            else:
                self.log_to_gui("ℹ️ Chưa có phiên đăng nhập, sẽ đăng nhập mới")

            self.log_to_gui("📱 Đang mở Zalo...")

            # Đăng nhập với session persistence
            success, playwright_instance, context, page = session_manager.login_with_session(max_wait_time=300)

            if success:
                self.log_to_gui("✅ Đăng nhập Zalo thành công!")
                self.log_to_gui("💾 Phiên đăng nhập đã được lưu tự động")
                self.log_to_gui("ℹ️ Trình duyệt sẽ vẫn mở để bạn sử dụng Zalo")
                self.log_to_gui("💡 Nhấn nút 'Kiểm tra & Cập nhật' để cập nhật thông tin tài khoản")
                self.log_to_gui("⚠️ Đóng cửa sổ trình duyệt khi bạn hoàn tất công việc")

                # Giữ browser mở - chờ người dùng đóng
                # Context sẽ tự động lưu khi đóng
                try:
                    # Chờ cho đến khi context bị đóng
                    while not page.is_closed():
                        import time
                        import random
                        time.sleep(random.uniform(0.8, 1.2))
                except:
                    pass

                self.log_to_gui("ℹ️ Đã đóng trình duyệt Zalo")

            else:
                self.log_to_gui("❌ Đăng nhập Zalo thất bại hoặc hết thời gian chờ")

        except ImportError as e:
            if "playwright" in str(e):
                self.log_to_gui("❌ Lỗi: Chưa cài đặt Playwright!")
                self.log_to_gui("💡 Vui lòng chạy: pip install playwright")
                self.log_to_gui("💡 Sau đó chạy: playwright install chromium")
            else:
                self.log_to_gui(f"❌ Lỗi import: {str(e)}")
        except Exception as e:
            self.log_to_gui(f"❌ Lỗi khi mở Zalo: {str(e)}")
        finally:
            # Cleanup khi kết thúc
            try:
                if context:
                    context.close()
                if playwright_instance:
                    playwright_instance.stop()
            except:
                pass

        
    def export_to_sheet_window(self):
        """Mở cửa sổ mới để xuất sang Google Sheets (sẽ code logic sau)"""
        self.log_to_gui("🟢 Chức năng 'Xuất sang Sheet' đang được phát triển...")
        # TODO: Tạo TopLevel window cho Google Sheets export

    # === CÁC HÀM XỬ LÝ CHO TAB ZALO ===

    def select_zalo_excel(self):
        """Chọn file Excel chứa dữ liệu khách hàng"""
        try:
            file_path = filedialog.askopenfilename(
                title="Chọn file Excel chứa dữ liệu khách hàng",
                filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
            )

            if not file_path:
                return

            self.log_to_gui(f"📂 Đang đọc file: {file_path}")

            # Đọc file Excel
            import openpyxl
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active

            # Đọc header (dòng đầu tiên)
            headers = []
            for cell in ws[1]:
                headers.append(str(cell.value).strip() if cell.value else "")

            # Mapping các cột phổ biến
            column_mapping = {}

            # Pass 1: Tìm các cột ưu tiên cao
            for idx, header in enumerate(headers):
                header_lower = header.lower()

                # Tên khách hàng
                if 'name' not in column_mapping:
                    if any(x in header_lower for x in ['tên kh', 'họ tên', 'name', 'customer', 'profile']):
                        column_mapping['name'] = idx

                # Số điện thoại (ưu tiên SĐT chính)
                if 'phone' not in column_mapping:
                    if 'sđt (chính)' in header_lower or 'sđt chính' in header_lower:
                        column_mapping['phone'] = idx

                # Địa chỉ thường trú (ưu tiên cao nhất)
                if 'address' not in column_mapping:
                    if 'địa chỉ thường trú' in header_lower:
                        column_mapping['address'] = idx

                # CCCD
                if 'cccd' not in column_mapping:
                    if any(x in header_lower for x in ['cccd', 'cmnd', 'số cccd', 'số cmnd']):
                        column_mapping['cccd'] = idx

                # Ngày sinh
                if 'dob' not in column_mapping:
                    if any(x in header_lower for x in ['ngày sinh', 'dob', 'sinh']):
                        column_mapping['dob'] = idx

                # ID Hợp đồng
                if 'contract_id' not in column_mapping:
                    if any(x in header_lower for x in ['id hợp đồng', 'hợp đồng', 'contract', 'mã hợp đồng']):
                        column_mapping['contract_id'] = idx

                # Giới tính
                if 'gender' not in column_mapping:
                    if any(x in header_lower for x in ['giới tính', 'gender', 'sex']):
                        column_mapping['gender'] = idx

                # Ghi chú (để kiểm tra trạng thái đã xử lý)
                if 'note' not in column_mapping:
                    if any(x in header_lower for x in ['ghi chú', 'ghi chu', 'note', 'notes', 'status', 'trạng thái']):
                        column_mapping['note'] = idx

            # Pass 2: Tìm các cột fallback (nếu chưa tìm thấy)
            for idx, header in enumerate(headers):
                header_lower = header.lower()

                # SĐT fallback
                if 'phone' not in column_mapping:
                    if any(x in header_lower for x in ['số điện thoại', 'phone', 'sđt']):
                        column_mapping['phone'] = idx

                # Địa chỉ tạm trú (fallback 1)
                if 'address' not in column_mapping:
                    if 'địa chỉ tạm trú' in header_lower:
                        column_mapping['address'] = idx

                # Địa chỉ công ty hoặc địa chỉ chung (fallback 2)
                if 'address' not in column_mapping:
                    if any(x in header_lower for x in ['địa chỉ công ty', 'địa chỉ', 'address']):
                        column_mapping['address'] = idx

            # Đọc dữ liệu
            self.zalo_customer_data = []
            processed_count = 0  # Đếm số khách hàng đã xử lý

            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or all(cell is None for cell in row):
                    continue  # Bỏ qua dòng trống

                customer = {}

                # Lấy dữ liệu theo mapping
                customer['name'] = str(row[column_mapping.get('name', 0)] or "").strip()
                customer['phone'] = str(row[column_mapping.get('phone', 1)] or "").strip()
                customer['address'] = str(row[column_mapping.get('address', 2)] or "").strip()
                customer['cccd'] = str(row[column_mapping.get('cccd', 3)] or "").strip()
                customer['dob'] = str(row[column_mapping.get('dob', 4)] or "").strip()
                customer['contract_id'] = str(row[column_mapping.get('contract_id', 5)] or "").strip()
                customer['gender'] = str(row[column_mapping.get('gender', 6)] or "").strip()

                # Đọc cột "Ghi chú" nếu có
                note = ""
                if 'note' in column_mapping:
                    note = str(row[column_mapping.get('note')] or "").strip()
                customer['note'] = note

                # Kiểm tra trạng thái đã xử lý
                customer['is_processed'] = False
                if note:
                    # Kiểm tra nếu đã kết bạn thành công, đã là bạn bè, hoặc đã gửi lời mời
                    if '✅ Kết bạn thành công' in note or '✅ Đã là bạn bè' in note or '⚠️ Đã gửi lời mời trước đó' in note or '✅ Gửi tin nhắn thành công' in note:
                        customer['is_processed'] = True
                        processed_count += 1

                # Chỉ thêm nếu có ít nhất tên hoặc số điện thoại
                if customer['name'] or customer['phone']:
                    self.zalo_customer_data.append(customer)

            wb.close()

            # Cập nhật UI
            self.zalo_excel_path = file_path
            filename = file_path.split('/')[-1].split('\\')[-1]
            self.zalo_file_label.configure(
                text=f"✓ {filename}",
                text_color="green"
            )

            # Hiển thị số lượng khách hàng và trạng thái
            unprocessed_count = len(self.zalo_customer_data) - processed_count
            status_text = f"Tổng: {len(self.zalo_customer_data)}"
            if processed_count > 0:
                status_text += f" (✅ {processed_count} đã xử lý, 🔄 {unprocessed_count} chưa xử lý)"

            self.zalo_customer_count_label.configure(
                text=status_text,
                text_color="#28A745"
            )

            self.log_to_gui(f"✅ Đã tải {len(self.zalo_customer_data)} khách hàng từ Excel")
            if processed_count > 0:
                self.log_to_gui(f"   📊 Trạng thái: {processed_count} đã xử lý, {unprocessed_count} chưa xử lý")
            self.log_to_gui(f"   📋 Các cột được nhận diện: {', '.join(column_mapping.keys())}")

        except ImportError:
            self.log_to_gui("❌ Lỗi: Chưa cài đặt openpyxl. Chạy: pip install openpyxl")
            messagebox.showerror("Lỗi", "Chưa cài đặt thư viện openpyxl!", parent=self)
        except Exception as e:
            self.log_to_gui(f"❌ Lỗi khi đọc file Excel: {str(e)}")
            messagebox.showerror("Lỗi", f"Không thể đọc file Excel:\n{str(e)}", parent=self)

    def save_results_to_excel(self, results):
        """
        Lưu kết quả kết bạn vào file Excel

        Args:
            results: List of dict với keys: phone, name, zalo_name, status
        """
        try:
            from openpyxl import load_workbook
            from openpyxl.styles import PatternFill, Font
            from datetime import datetime

            # Load workbook
            wb = load_workbook(self.zalo_excel_path)
            ws = wb.active

            # Tìm hoặc tạo cột "Ghi chú" và "Tên Zalo"
            headers = []
            for cell in ws[1]:
                headers.append(str(cell.value).strip() if cell.value else "")

            # Tìm cột "Ghi chú"
            note_col_idx = None
            for idx, header in enumerate(headers):
                if header.lower() in ['ghi chú', 'ghi chu', 'note', 'notes', 'status', 'trạng thái']:
                    note_col_idx = idx
                    break

            # Nếu không có cột "Ghi chú", tạo mới
            if note_col_idx is None:
                note_col_idx = len(headers)
                ws.cell(row=1, column=note_col_idx + 1, value="Ghi chú")
                headers.append("Ghi chú")

            # Tìm hoặc tạo cột "Tên Zalo"
            zalo_name_col_idx = None
            for idx, header in enumerate(headers):
                if header.lower() in ['tên zalo', 'ten zalo', 'zalo name', 'zalo']:
                    zalo_name_col_idx = idx
                    break

            # Nếu không có cột "Tên Zalo", tạo mới
            if zalo_name_col_idx is None:
                zalo_name_col_idx = len(headers)
                ws.cell(row=1, column=zalo_name_col_idx + 1, value="Tên Zalo")

            # Tìm cột số điện thoại để mapping
            phone_col_idx = None
            for idx, header in enumerate(headers):
                header_lower = header.lower()
                if any(x in header_lower for x in ['sđt', 'phone', 'số điện thoại', 'điện thoại']):
                    phone_col_idx = idx
                    break

            if phone_col_idx is None:
                self.log_to_gui("⚠️ Không tìm thấy cột số điện thoại trong Excel")
                return

            # Tạo mapping từ phone -> result
            phone_to_result = {}
            for result in results:
                phone = str(result.get('phone', '')).strip()
                if phone:
                    phone_to_result[phone] = result

            # Định nghĩa màu sắc
            green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
            red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

            # Cập nhật từng dòng
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updated_count = 0

            for row_idx in range(2, ws.max_row + 1):
                phone_cell = ws.cell(row=row_idx, column=phone_col_idx + 1)
                phone = str(phone_cell.value or "").strip()

                if phone in phone_to_result:
                    result = phone_to_result[phone]
                    status = result.get('status', 'unknown')
                    zalo_name = result.get('zalo_name', '')

                    # Tạo message ghi chú và chọn màu
                    if status == 'success':
                        note = f"✅ Kết bạn thành công ({timestamp})"
                        fill_color = green_fill
                    elif status == 'already_friend':
                        note = f"✅ Đã là bạn bè ({timestamp})"
                        fill_color = green_fill
                    elif status == 'already_sent':
                        note = f"⚠️ Đã gửi lời mời trước đó ({timestamp})"
                        fill_color = yellow_fill
                    elif status == 'failed':
                        note = f"❌ Kết bạn thất bại ({timestamp})"
                        fill_color = red_fill
                    else:
                        note = f"❓ Không xác định ({timestamp})"
                        fill_color = None

                    # Ghi vào cột "Ghi chú"
                    note_cell = ws.cell(row=row_idx, column=note_col_idx + 1, value=note)
                    if fill_color:
                        note_cell.fill = fill_color

                    # Ghi vào cột "Tên Zalo" nếu có
                    if zalo_name:
                        zalo_cell = ws.cell(row=row_idx, column=zalo_name_col_idx + 1, value=zalo_name)
                        if fill_color:
                            zalo_cell.fill = fill_color

                    updated_count += 1

            # Lưu file
            wb.save(self.zalo_excel_path)
            wb.close()

            self.log_to_gui(f"   📝 Đã cập nhật {updated_count}/{len(results)} dòng trong Excel")

        except Exception as e:
            raise Exception(f"Lỗi khi lưu Excel: {str(e)}")

    def save_message_results_to_excel(self, details):
        """
        Lưu kết quả gửi tin nhắn vào file Excel

        Args:
            details: List of dict với keys: phone, name, status
        """
        try:
            from openpyxl import load_workbook
            from openpyxl.styles import PatternFill
            from datetime import datetime

            # Load workbook
            wb = load_workbook(self.zalo_excel_path)
            ws = wb.active

            # Tìm hoặc tạo cột "Ghi chú"
            headers = []
            for cell in ws[1]:
                headers.append(str(cell.value).strip() if cell.value else "")

            # Tìm cột "Ghi chú"
            note_col_idx = None
            for idx, header in enumerate(headers):
                if header.lower() in ['ghi chú', 'ghi chu', 'note', 'notes', 'status', 'trạng thái']:
                    note_col_idx = idx
                    break

            # Nếu không có cột "Ghi chú", tạo mới
            if note_col_idx is None:
                note_col_idx = len(headers)
                ws.cell(row=1, column=note_col_idx + 1, value="Ghi chú")

            # Tìm cột số điện thoại để mapping
            phone_col_idx = None
            for idx, header in enumerate(headers):
                header_lower = header.lower()
                if any(x in header_lower for x in ['sđt', 'phone', 'số điện thoại', 'điện thoại']):
                    phone_col_idx = idx
                    break

            if phone_col_idx is None:
                self.log_to_gui("⚠️ Không tìm thấy cột số điện thoại trong Excel")
                return

            # Tạo mapping từ phone -> detail
            phone_to_detail = {}
            for detail in details:
                phone = str(detail.get('phone', '')).strip()
                if phone:
                    phone_to_detail[phone] = detail

            # Định nghĩa màu sắc
            green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
            gray_fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")

            # Cập nhật từng dòng
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updated_count = 0

            for row_idx in range(2, ws.max_row + 1):
                phone_cell = ws.cell(row=row_idx, column=phone_col_idx + 1)
                phone = str(phone_cell.value or "").strip()

                if phone in phone_to_detail:
                    detail = phone_to_detail[phone]
                    status = detail.get('status', 'unknown')

                    # Tạo message ghi chú và chọn màu
                    if status == 'success':
                        note = f"✅ Gửi tin nhắn thành công ({timestamp})"
                        fill_color = green_fill
                    elif status == 'failed':
                        note = f"❌ Gửi tin nhắn thất bại ({timestamp})"
                        fill_color = red_fill
                    elif status == 'no_phone':
                        note = f"⚠️ Không có số điện thoại ({timestamp})"
                        fill_color = gray_fill
                    elif status == 'error':
                        note = f"❌ Lỗi khi gửi tin nhắn ({timestamp})"
                        fill_color = red_fill
                    else:
                        note = f"❓ Không xác định ({timestamp})"
                        fill_color = None

                    # Ghi vào cột "Ghi chú"
                    note_cell = ws.cell(row=row_idx, column=note_col_idx + 1, value=note)
                    if fill_color:
                        note_cell.fill = fill_color

                    updated_count += 1

            # Lưu file
            wb.save(self.zalo_excel_path)
            wb.close()

            self.log_to_gui(f"   📝 Đã cập nhật {updated_count}/{len(details)} dòng trong Excel")

        except Exception as e:
            raise Exception(f"Lỗi khi lưu Excel: {str(e)}")

    def send_bulk_messages(self):
        """Gửi tin nhắn hàng loạt cho khách hàng"""
        # Kiểm tra dữ liệu
        if not self.zalo_customer_data:
            messagebox.showwarning(
                "Cảnh báo",
                "Vui lòng chọn file Excel chứa dữ liệu khách hàng trước!",
                parent=self
            )
            return

        # Lọc khách hàng theo checkbox
        skip_sent = self.skip_sent_messages_var.get()
        customers_to_process = []

        if skip_sent:
            # Chỉ lấy khách hàng chưa gửi tin nhắn thành công
            customers_to_process = [c for c in self.zalo_customer_data if not c.get('is_processed', False)]
            skipped_count = len(self.zalo_customer_data) - len(customers_to_process)

            if len(customers_to_process) == 0:
                messagebox.showinfo(
                    "Thông báo",
                    "Tất cả khách hàng đã được gửi tin nhắn thành công!\n\n"
                    "Bỏ tick '☑️ Bỏ qua khách hàng đã gửi tin nhắn thành công' nếu muốn gửi lại.",
                    parent=self
                )
                return
        else:
            # Xử lý tất cả
            customers_to_process = self.zalo_customer_data
            skipped_count = 0

        # Lấy template
        template = self.zalo_message_template.get("1.0", "end-1c").strip()
        if not template:
            messagebox.showwarning(
                "Cảnh báo",
                "Vui lòng nhập kịch bản tin nhắn!",
                parent=self
            )
            return

        # Xác nhận
        confirm_msg = f"Bạn có chắc muốn gửi tin nhắn đến {len(customers_to_process)} khách hàng?"
        if skipped_count > 0:
            confirm_msg += f"\n\n(Bỏ qua {skipped_count} khách hàng đã gửi thành công)"
        confirm_msg += "\n\nLưu ý: Bạn cần đăng nhập Zalo trước!"

        result = messagebox.askyesno(
            "Xác nhận",
            confirm_msg,
            parent=self
        )

        if not result:
            return

        # Lưu danh sách cần xử lý vào biến tạm
        self.current_customers_to_process = customers_to_process

        # Reset trạng thái tạm dừng
        self.is_paused = False
        self.zalo_pause_button.configure(text="Tạm dừng", fg_color="#6C757D", hover_color="#5A6268")
        self.zalo_pause_button.configure(state="normal")  # Enable nút tạm dừng

        # Chạy trong thread riêng
        thread = threading.Thread(
            target=self._run_send_bulk_messages,
            args=(template,),
            daemon=True
        )
        thread.start()

    def add_friends_bulk(self):
        """Kết bạn hàng loạt với khách hàng"""
        # Kiểm tra dữ liệu
        if not self.zalo_customer_data:
            messagebox.showwarning(
                "Cảnh báo",
                "Vui lòng chọn file Excel chứa dữ liệu khách hàng trước!",
                parent=self
            )
            return

        # Lọc khách hàng theo checkbox
        skip_processed = self.skip_processed_var.get()
        customers_to_process = []

        if skip_processed:
            # Chỉ lấy khách hàng chưa kết bạn thành công
            customers_to_process = [c for c in self.zalo_customer_data if not c.get('is_processed', False)]
            skipped_count = len(self.zalo_customer_data) - len(customers_to_process)

            if len(customers_to_process) == 0:
                messagebox.showinfo(
                    "Thông báo",
                    "Tất cả khách hàng đã được kết bạn thành công!\n\n"
                    "Bỏ tick '☑️ Bỏ qua khách hàng đã kết bạn thành công' nếu muốn gửi lại.",
                    parent=self
                )
                return
        else:
            # Xử lý tất cả
            customers_to_process = self.zalo_customer_data
            skipped_count = 0

        # Đếm số khách hàng có số điện thoại
        phone_count = sum(1 for c in customers_to_process if c.get('phone'))

        if phone_count == 0:
            messagebox.showwarning(
                "Cảnh báo",
                "Không tìm thấy số điện thoại nào trong dữ liệu chưa xử lý!",
                parent=self
            )
            return

        # Xác nhận
        confirm_msg = f"Bạn có chắc muốn gửi lời mời kết bạn đến {phone_count} số điện thoại?"
        if skipped_count > 0:
            confirm_msg += f"\n\n(Bỏ qua {skipped_count} khách hàng đã kết bạn thành công)"
        confirm_msg += "\n\nLưu ý: Bạn cần đăng nhập Zalo trước!"

        result = messagebox.askyesno(
            "Xác nhận",
            confirm_msg,
            parent=self
        )

        if not result:
            return

        # Lưu danh sách cần xử lý vào biến tạm
        self.current_customers_to_process = customers_to_process

        # Reset trạng thái tạm dừng
        self.is_paused = False
        self.zalo_pause_button.configure(text="Tạm dừng", fg_color="#6C757D", hover_color="#5A6268")
        self.zalo_pause_button.configure(state="normal")  # Enable nút tạm dừng

        # Chạy trong thread riêng
        thread = threading.Thread(
            target=self._run_add_friends_bulk,
            daemon=True
        )
        thread.start()

    def toggle_pause(self):
        """Chuyển đổi trạng thái tạm dừng/tiếp tục"""
        self.is_paused = not self.is_paused

        if self.is_paused:
            self.zalo_pause_button.configure(text="Tiếp tục", fg_color="#28A745", hover_color="#218838")
            self.log_to_gui("Đã tạm dừng - Click 'Tiếp tục' để chạy tiếp")
        else:
            self.zalo_pause_button.configure(text="Tạm dừng", fg_color="#6C757D", hover_color="#5A6268")
            self.log_to_gui("Tiếp tục chạy...")



    def _run_send_bulk_messages(self, template):
        """Thread worker để gửi tin nhắn hàng loạt"""
        try:
            import time
            import zalo_logic
            import zalo_automation

            # Kiểm tra đã chọn tài khoản chưa
            if not self.current_account_id:
                self.log_to_gui("❌ Vui lòng chọn tài khoản trước!")
                messagebox.showerror(
                    "Lỗi",
                    "Vui lòng chọn tài khoản Zalo trước khi gửi tin nhắn!",
                    parent=self
                )
                return

            self.log_to_gui("⏳ Đang khởi tạo Zalo...")

            # Lấy session manager cho tài khoản đã chọn
            session_manager = self.account_manager.get_session_manager(self.current_account_id)
            success, p, context, page = session_manager.login_with_session(max_wait_time=60)

            if not success:
                self.log_to_gui("❌ Không thể đăng nhập Zalo. Vui lòng đăng nhập thủ công trước!")
                if context:
                    context.close()
                if p:
                    p.stop()
                return

            self.log_to_gui("✅ Đã đăng nhập Zalo")

            # Sử dụng danh sách đã lọc
            customers = getattr(self, 'current_customers_to_process', self.zalo_customer_data)
            self.log_to_gui(f"📤 Bắt đầu gửi tin nhắn đến {len(customers)} khách hàng...")

            # Tạo automation instance
            automation = zalo_automation.ZaloAutomation(page)

            # Gửi tin nhắn hàng loạt (với hỗ trợ pause)
            result = automation.send_bulk_messages(
                customers,
                template,
                callback=self.log_to_gui,
                delay=3,
                is_paused_func=lambda: self.is_paused
            )

            # Hiển thị kết quả
            self.log_to_gui("\n" + "="*50)
            self.log_to_gui(f"✅ HOÀN TẤT GỬI TIN NHẮN HÀNG LOẠT")
            self.log_to_gui(f"   - Thành công: {result['success']}")
            self.log_to_gui(f"   - Thất bại: {result['failed']}")
            if result['errors']:
                self.log_to_gui(f"\n❌ Các lỗi:")
                for error in result['errors'][:10]:  # Hiển thị tối đa 10 lỗi
                    self.log_to_gui(f"   - {error}")
            self.log_to_gui("="*50)

            # Ghi kết quả vào file Excel
            if self.zalo_excel_path and result.get('details'):
                self.log_to_gui("\n💾 Đang lưu kết quả vào file Excel...")
                try:
                    self.save_message_results_to_excel(result['details'])
                    self.log_to_gui("✅ Đã lưu kết quả vào file Excel")
                except Exception as e:
                    self.log_to_gui(f"⚠️ Không thể lưu kết quả vào Excel: {str(e)}")

            # Disable nút điều khiển
            self.zalo_pause_button.configure(state="disabled")

            # Giữ trình duyệt mở
            self.log_to_gui("\nℹ️ Trình duyệt vẫn mở, bạn có thể tiếp tục sử dụng Zalo")
            self.log_to_gui("⚠️ Đóng cửa sổ trình duyệt khi hoàn tất")

            # Chờ người dùng đóng
            try:
                import random
                while not page.is_closed():
                    time.sleep(random.uniform(0.8, 1.2))
            except:
                pass

            # Cleanup
            try:
                if context:
                    context.close()
                if p:
                    p.stop()
            except:
                pass

        except ImportError as e:
            self.log_to_gui(f"❌ Lỗi import: {str(e)}")
            self.log_to_gui("💡 Vui lòng cài đặt: pip install playwright")
            self.zalo_pause_button.configure(state="disabled")
        except Exception as e:
            self.log_to_gui(f"❌ Lỗi khi gửi tin nhắn: {str(e)}")
            self.zalo_pause_button.configure(state="disabled")

    def _run_add_friends_bulk(self):
        """Thread worker để kết bạn hàng loạt"""
        try:
            import time
            import zalo_logic
            import zalo_automation

            # Kiểm tra đã chọn tài khoản chưa
            if not self.current_account_id:
                self.log_to_gui("❌ Vui lòng chọn tài khoản trước!")
                messagebox.showerror(
                    "Lỗi",
                    "Vui lòng chọn tài khoản Zalo trước khi kết bạn!",
                    parent=self
                )
                return

            self.log_to_gui("⏳ Đang khởi tạo Zalo...")

            # Lấy session manager cho tài khoản đã chọn
            session_manager = self.account_manager.get_session_manager(self.current_account_id)
            success, p, context, page = session_manager.login_with_session(max_wait_time=60)

            if not success:
                self.log_to_gui("❌ Không thể đăng nhập Zalo. Vui lòng đăng nhập thủ công trước!")
                if context:
                    context.close()
                if p:
                    p.stop()
                return

            self.log_to_gui("✅ Đã đăng nhập Zalo")

            # Sử dụng danh sách đã lọc và lọc thêm khách hàng có số điện thoại
            customers = getattr(self, 'current_customers_to_process', self.zalo_customer_data)
            customers_with_phone = [c for c in customers if c.get('phone')]
            self.log_to_gui(f"➕ Bắt đầu kết bạn với {len(customers_with_phone)} số điện thoại...")

            # Tạo automation instance
            automation = zalo_automation.ZaloAutomation(page)

            # Lấy tên Zalo của tài khoản đang đăng nhập (truyền session_manager để lưu tên)
            my_zalo_name = automation.get_my_zalo_name(session_manager)
            self.log_to_gui(f"👤 Tài khoản Zalo: {my_zalo_name}")

            # Kết bạn từng người
            success_count = 0
            failed_count = 0
            already_sent_count = 0
            already_friend_count = 0  # Đếm số người đã là bạn bè
            results = []  # Lưu kết quả chi tiết

            for idx, customer in enumerate(customers_with_phone, 1):
                # Kiểm tra tạm dừng
                import random
                while self.is_paused:
                    time.sleep(random.uniform(0.4, 0.6))

                phone = customer.get('phone', '').strip()
                name = customer.get('name', 'N/A')
                contract_id = customer.get('contract_id', '')

                self.log_to_gui(f"\n{'='*60}")
                self.log_to_gui(f"➕ [{idx}/{len(customers_with_phone)}] Đang kết bạn: {name} ({phone})")

                # Gọi hàm kết bạn (trả về tuple: success/status, display_name)
                result, display_name = automation.add_friend_by_phone(phone, contract_id, my_zalo_name)

                # Xử lý kết quả
                if result == "already_sent":
                    # Đã gửi lời mời trước đó
                    already_sent_count += 1
                    result_msg = f"⚠️ [{idx}/{len(customers_with_phone)}] Đã gửi lời mời trước đó: {phone}"
                    if display_name:
                        result_msg += f" - Tên Zalo: {display_name}"
                    self.log_to_gui(result_msg)
                    results.append({
                        'phone': phone,
                        'name': name,
                        'zalo_name': display_name,
                        'status': 'already_sent'
                    })
                elif result == "already_friend":
                    # Đã là bạn bè
                    already_friend_count += 1
                    result_msg = f"✅ [{idx}/{len(customers_with_phone)}] Đã là bạn bè: {phone}"
                    if display_name:
                        result_msg += f" - Tên Zalo: {display_name}"
                    self.log_to_gui(result_msg)
                    results.append({
                        'phone': phone,
                        'name': name,
                        'zalo_name': display_name,
                        'status': 'already_friend'
                    })
                elif result:
                    # Thành công
                    success_count += 1
                    result_msg = f"✅ [{idx}/{len(customers_with_phone)}] Thành công: {phone}"
                    if display_name:
                        result_msg += f" - Tên Zalo: {display_name}"
                    self.log_to_gui(result_msg)
                    results.append({
                        'phone': phone,
                        'name': name,
                        'zalo_name': display_name,
                        'status': 'success'
                    })
                else:
                    # Thất bại
                    failed_count += 1
                    self.log_to_gui(f"❌ [{idx}/{len(customers_with_phone)}] Thất bại: {phone}")
                    results.append({
                        'phone': phone,
                        'name': name,
                        'zalo_name': None,
                        'status': 'failed'
                    })

                # Đóng modal sau mỗi lần kết bạn (thành công hoặc thất bại)
                self.log_to_gui("🔄 Đóng modal và chuẩn bị kết bạn tiếp...")
                automation.close_modal_after_add_friend()

                # Delay giữa các lần kết bạn (random 2.5-3.5s)
                if idx < len(customers_with_phone):
                    import random
                    delay = random.uniform(2.5, 3.5)
                    self.log_to_gui(f"⏳ Chờ {delay:.1f} giây trước khi kết bạn tiếp...")
                    time.sleep(delay)

            # Hiển thị kết quả
            self.log_to_gui("\n" + "="*60)
            self.log_to_gui(f"✅ HOÀN TẤT KẾT BẠN HÀNG LOẠT")
            self.log_to_gui(f"   - Tổng số: {len(customers_with_phone)}")
            self.log_to_gui(f"   - Thành công: {success_count}")
            self.log_to_gui(f"   - Đã là bạn bè: {already_friend_count}")
            self.log_to_gui(f"   - Đã gửi lời mời trước đó: {already_sent_count}")
            self.log_to_gui(f"   - Thất bại: {failed_count}")

            # Hiển thị danh sách thành công
            if success_count > 0:
                self.log_to_gui(f"\n📋 Danh sách kết bạn thành công ({success_count}):")
                for idx, result in enumerate([r for r in results if r['status'] == 'success'], 1):
                    zalo_name_info = f" - Zalo: {result['zalo_name']}" if result['zalo_name'] else ""
                    self.log_to_gui(f"   {idx}. {result['name']} ({result['phone']}){zalo_name_info}")

            # Hiển thị danh sách đã gửi lời mời trước đó
            if already_sent_count > 0:
                self.log_to_gui(f"\n⚠️ Danh sách đã gửi lời mời trước đó ({already_sent_count}):")
                for idx, result in enumerate([r for r in results if r['status'] == 'already_sent'], 1):
                    zalo_name_info = f" - Zalo: {result['zalo_name']}" if result['zalo_name'] else ""
                    self.log_to_gui(f"   {idx}. {result['name']} ({result['phone']}){zalo_name_info}")

            # Hiển thị danh sách thất bại
            if failed_count > 0:
                self.log_to_gui(f"\n❌ Danh sách kết bạn thất bại ({failed_count}):")
                for idx, result in enumerate([r for r in results if r['status'] == 'failed'], 1):
                    self.log_to_gui(f"   {idx}. {result['name']} ({result['phone']})")

            self.log_to_gui("="*60)

            # Ghi kết quả vào file Excel
            if self.zalo_excel_path and results:
                self.log_to_gui("\n💾 Đang lưu kết quả vào file Excel...")
                try:
                    self.save_results_to_excel(results)
                    self.log_to_gui("✅ Đã lưu kết quả vào file Excel")
                except Exception as e:
                    self.log_to_gui(f"⚠️ Không thể lưu kết quả vào Excel: {str(e)}")

            # Disable nút điều khiển
            self.zalo_pause_button.configure(state="disabled")

            # Giữ trình duyệt mở
            self.log_to_gui("\nℹ️ Trình duyệt vẫn mở, bạn có thể tiếp tục sử dụng Zalo")
            self.log_to_gui("⚠️ Đóng cửa sổ trình duyệt khi hoàn tất")

            # Chờ người dùng đóng
            try:
                import random
                while not page.is_closed():
                    time.sleep(random.uniform(0.8, 1.2))
            except:
                pass

            # Cleanup
            try:
                if context:
                    context.close()
                if p:
                    p.stop()
            except:
                pass

        except ImportError as e:
            self.log_to_gui(f"❌ Lỗi import: {str(e)}")
            self.log_to_gui("💡 Vui lòng cài đặt: pip install playwright")
            self.zalo_pause_button.configure(state="disabled")
        except Exception as e:
            self.log_to_gui(f"❌ Lỗi khi kết bạn: {str(e)}")
            self.zalo_pause_button.configure(state="disabled")

    # === QUẢN LÝ NHIỀU TÀI KHOẢN ZALO ===

    def load_account_list(self):
        """Load danh sách tài khoản vào combobox"""
        try:
            accounts = self.account_manager.get_all_accounts()

            if not accounts:
                self.account_combobox.configure(values=["Chưa có tài khoản"])
                self.account_combobox.set("Chưa có tài khoản")
                return

            # Tạo danh sách hiển thị: "Tên tài khoản (Tên Zalo)"
            account_list = []
            for account in accounts:
                zalo_name = account.get('zalo_name', 'Chưa cập nhật')
                display_name = f"{account['account_name']} ({zalo_name})"
                account_list.append(display_name)

            self.account_combobox.configure(values=account_list)

            # Chọn tài khoản đầu tiên nếu chưa có
            if not self.current_account_id and accounts:
                self.current_account_id = accounts[0]['id']
                self.account_combobox.set(account_list[0])
                self.update_account_info_display(accounts[0])

        except Exception as e:
            self.log_to_gui(f"❌ Lỗi khi load danh sách tài khoản: {str(e)}")

    def on_account_selected(self, choice):
        """Xử lý khi chọn tài khoản từ combobox"""
        if choice == "Chưa có tài khoản":
            return

        try:
            # Lấy account_name từ choice (format: "Tên tài khoản (Tên Zalo)")
            account_name = choice.split(" (")[0]

            # Tìm tài khoản theo tên
            accounts = self.account_manager.get_all_accounts()
            for account in accounts:
                if account['account_name'] == account_name:
                    self.current_account_id = account['id']
                    self.update_account_info_display(account)
                    self.log_to_gui(f"✅ Đã chọn tài khoản: {account_name}")
                    break

        except Exception as e:
            self.log_to_gui(f"❌ Lỗi khi chọn tài khoản: {str(e)}")

    def update_account_info_display(self, account):
        """Cập nhật hiển thị thông tin tài khoản"""
        # Cập nhật họ tên Zalo
        zalo_name = account.get('zalo_name', 'Chưa cập nhật')
        if zalo_name and zalo_name != 'Chưa cập nhật':
            self.zalo_name_label.configure(text=zalo_name, text_color="#0068FF")
        else:
            self.zalo_name_label.configure(text="Chưa cập nhật", text_color="gray")

        # Cập nhật phiên đăng nhập
        last_login = account.get('last_login', 'Chưa đăng nhập')
        if last_login and last_login != 'Chưa đăng nhập':
            self.zalo_session_label.configure(text=last_login, text_color="white")
        else:
            self.zalo_session_label.configure(text="Chưa đăng nhập", text_color="gray")

        # Cập nhật trạng thái
        status = account.get('status', 'inactive')
        if status == 'active':
            self.zalo_status_label.configure(text="✅ Active", text_color="green")
        else:
            self.zalo_status_label.configure(text="❌ Inactive", text_color="red")

    def add_zalo_account(self):
        """Thêm tài khoản Zalo mới"""
        # Tạo dialog nhập tên tài khoản
        dialog = customtkinter.CTkInputDialog(
            text="Nhập tên tài khoản (ví dụ: Tài khoản 1, Zalo công ty, ...):",
            title="Thêm Tài Khoản Zalo"
        )
        account_name = dialog.get_input()

        if not account_name:
            return

        try:
            import zalo_logic

            # Khởi tạo account manager nếu chưa có
            if not self.account_manager:
                self.account_manager = zalo_logic.ZaloAccountManager()

            # Thêm tài khoản mới
            new_account = self.account_manager.add_account(account_name)

            self.log_to_gui(f"✅ Đã thêm tài khoản: {account_name}")
            self.log_to_gui(f"   ID: {new_account['id']}")
            self.log_to_gui(f"   Session directory: {new_account['session_dir']}")

            # Reload danh sách
            self.load_account_list()

            # Chọn tài khoản mới
            self.current_account_id = new_account['id']
            self.account_combobox.set(f"{account_name} (Chưa cập nhật)")
            self.update_account_info_display(new_account)

            messagebox.showinfo(
                "Thành công",
                f"Đã thêm tài khoản: {account_name}\n\nVui lòng click 'Kiểm tra & Cập nhật' để đăng nhập!",
                parent=self
            )

        except Exception as e:
            self.log_to_gui(f"❌ Lỗi khi thêm tài khoản: {str(e)}")
            messagebox.showerror(
                "Lỗi",
                f"Không thể thêm tài khoản!\n{str(e)}",
                parent=self
            )

    def delete_zalo_account(self):
        """Xóa tài khoản Zalo hiện tại"""
        if not self.current_account_id:
            messagebox.showwarning(
                "Cảnh báo",
                "Vui lòng chọn tài khoản cần xóa!",
                parent=self
            )
            return

        try:
            account = self.account_manager.get_account_by_id(self.current_account_id)
            if not account:
                return

            # Xác nhận xóa
            result = messagebox.askyesno(
                "Xác nhận xóa",
                f"Bạn có chắc muốn xóa tài khoản:\n{account['account_name']}?\n\nSession và dữ liệu sẽ bị xóa vĩnh viễn!",
                parent=self
            )

            if result:
                # Xóa tài khoản
                if self.account_manager.delete_account(self.current_account_id):
                    self.log_to_gui(f"✅ Đã xóa tài khoản: {account['account_name']}")

                    # Reset current account
                    self.current_account_id = None

                    # Reload danh sách
                    self.load_account_list()

                    messagebox.showinfo(
                        "Thành công",
                        f"Đã xóa tài khoản: {account['account_name']}",
                        parent=self
                    )
                else:
                    messagebox.showerror(
                        "Lỗi",
                        "Không thể xóa tài khoản!",
                        parent=self
                    )

        except Exception as e:
            self.log_to_gui(f"❌ Lỗi khi xóa tài khoản: {str(e)}")




if __name__ == "__main__":
    app = App()
    app.mainloop()

