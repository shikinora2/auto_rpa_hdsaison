"""
Zalo Logic - Xử lý đăng nhập và tương tác với Zalo Web
Sử dụng Playwright (giống như rpa_logic.py)
Hỗ trợ lưu phiên đăng nhập bằng Persistent Context
"""
import time
import random
import os
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Thư mục lưu trữ dữ liệu ứng dụng
APP_DATA_DIR = "app_data"
if not os.path.exists(APP_DATA_DIR):
    os.makedirs(APP_DATA_DIR)

# Thư mục lưu session
SESSION_DIR = os.path.join(APP_DATA_DIR, "zalo_session")
ACCOUNTS_FILE = os.path.join(APP_DATA_DIR, "zalo_accounts.json")  # File lưu danh sách tài khoản


class ZaloLogin:
    """Xử lý đăng nhập Zalo Web sử dụng Playwright với Persistent Context"""
    
    LOGIN_URL = "https://id.zalo.me/account?continue=https%3A%2F%2Fchat.zalo.me%2F"
    CHAT_URL = "https://chat.zalo.me/"
    
    def __init__(self, page=None, context=None):
        """
        Khởi tạo ZaloLogin
        
        Args:
            page: Playwright Page instance (optional)
            context: Playwright BrowserContext instance (optional)
        """
        self.page = page
        self.context = context
        self.session_dir = SESSION_DIR
        
    def open_login_page(self):
        """Mở trang đăng nhập Zalo"""
        try:
            logger.info("Đang mở trang đăng nhập Zalo...")
            self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(1.5, 2.5))
            
            # Kiểm tra đã tải trang thành công
            current_url = self.page.url
            logger.info(f"Đã mở trang: {current_url}")
            
            return True
        except Exception as e:
            logger.error(f"Lỗi khi mở trang đăng nhập: {str(e)}")
            return False
    
    def wait_for_qr_code(self, timeout=10000):
        """
        Chờ mã QR xuất hiện
        
        Args:
            timeout: Thời gian chờ tối đa (milliseconds)
            
        Returns:
            bool: True nếu QR code xuất hiện, False nếu không
        """
        try:
            logger.info("Đang chờ mã QR xuất hiện...")
            
            # Có thể tìm QR code bằng nhiều cách, tùy thuộc vào cấu trúc HTML
            qr_selectors = [
                "canvas#qrcode",
                "canvas[class*='qrcode']",
                "div[class*='qr'] canvas",
                "img[alt*='QR']",
                "div[class*='qr-code']",
            ]
            
            for selector in qr_selectors:
                try:
                    qr_element = self.page.wait_for_selector(selector, timeout=timeout, state="visible")
                    if qr_element:
                        logger.info(f"✓ Đã tìm thấy mã QR (selector: {selector})")
                        return True
                except PlaywrightTimeoutError:
                    continue
            
            # Nếu không tìm thấy QR code cụ thể, kiểm tra xem có đang ở trang login không
            if "id.zalo.me" in self.page.url:
                logger.warning("Chưa tìm thấy QR code cụ thể nhưng đang ở trang đăng nhập")
                return True
            
            logger.warning("Không tìm thấy mã QR")
            return False
            
        except Exception as e:
            logger.error(f"Lỗi khi chờ QR code: {str(e)}")
            return False
    
    def wait_for_user_scan(self, max_wait_time=300):
        """
        Chờ người dùng quét mã QR và đăng nhập
        
        Args:
            max_wait_time: Thời gian chờ tối đa (giây), mặc định 5 phút
            
        Returns:
            bool: True nếu đăng nhập thành công, False nếu timeout
        """
        try:
            logger.info(f"⏳ Vui lòng quét mã QR để đăng nhập (thời gian chờ: {max_wait_time}s)...")
            
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                current_url = self.page.url
                
                # Kiểm tra nếu URL đã chuyển sang chat.zalo.me
                if "chat.zalo.me" in current_url:
                    logger.info("✓ Phát hiện chuyển hướng đến trang chat")
                    return True
                
                # Kiểm tra các element báo hiệu đăng nhập thành công
                try:
                    # Kiểm tra có xuất hiện trang chat không
                    if self.page.query_selector("div[class*='conv-item']"):
                        logger.info("✓ Phát hiện giao diện chat")
                        return True
                except:
                    pass

                # Chờ 1.5-2.5 giây trước khi kiểm tra lại
                time.sleep(random.uniform(1.5, 2.5))
                
                # Log tiến trình mỗi 30 giây
                elapsed = int(time.time() - start_time)
                if elapsed % 30 == 0 and elapsed > 0:
                    logger.info(f"Đang chờ đăng nhập... ({elapsed}/{max_wait_time}s)")
            
            logger.error(f"⏱️ Hết thời gian chờ ({max_wait_time}s)")
            return False
            
        except Exception as e:
            logger.error(f"Lỗi khi chờ người dùng quét mã: {str(e)}")
            return False
    
    def verify_login_success(self, timeout=30000):
        """
        Xác nhận đăng nhập thành công bằng cách kiểm tra khung trò chuyện
        
        Args:
            timeout: Thời gian chờ tối đa (milliseconds)
            
        Returns:
            bool: True nếu đăng nhập thành công, False nếu không
        """
        try:
            logger.info("Đang xác nhận đăng nhập thành công...")
            
            # Kiểm tra URL
            if "chat.zalo.me" not in self.page.url:
                logger.warning(f"URL không đúng: {self.page.url}")
                return False
            
            # Kiểm tra khung trò chuyện (conversation list)
            conversation_selectors = [
                "div#conversationList",
                "div[id='conversationList'][aria-label='grid']",
                "div[class*='conv-item']",
            ]
            
            for selector in conversation_selectors:
                try:
                    conv_element = self.page.wait_for_selector(selector, timeout=timeout, state="visible")
                    if conv_element:
                        logger.info(f"✓ Đã tìm thấy khung trò chuyện (selector: {selector})")
                        
                        # Kiểm tra thêm: có ít nhất 1 conversation item
                        try:
                            items = self.page.query_selector_all("div[class*='conv-item']")
                            logger.info(f"✓ Tìm thấy {len(items)} cuộc trò chuyện")
                        except:
                            pass
                        
                        return True
                except PlaywrightTimeoutError:
                    continue
            
            logger.error("❌ Không tìm thấy khung trò chuyện")
            return False
            
        except Exception as e:
            logger.error(f"Lỗi khi xác nhận đăng nhập: {str(e)}")
            return False
    
    def login(self, max_wait_time=300):
        """
        Quy trình đăng nhập Zalo hoàn chỉnh
        
        Args:
            max_wait_time: Thời gian chờ tối đa cho việc quét QR (giây)
            
        Returns:
            bool: True nếu đăng nhập thành công, False nếu không
        """
        try:
            logger.info("=== BẮT ĐẦU QUY TRÌNH ĐĂNG NHẬP ZALO ===")
            
            # Bước 1: Mở trang đăng nhập
            if not self.open_login_page():
                logger.error("❌ Không thể mở trang đăng nhập")
                return False
            
            # Bước 2: Chờ mã QR xuất hiện
            if not self.wait_for_qr_code():
                logger.error("❌ Không tìm thấy mã QR")
                return False
            
            logger.info("📱 Vui lòng mở ứng dụng Zalo và quét mã QR để đăng nhập")
            
            # Bước 3: Chờ người dùng quét mã
            if not self.wait_for_user_scan(max_wait_time):
                logger.error("❌ Đăng nhập không thành công (timeout hoặc lỗi)")
                return False

            # Bước 4: Xác nhận đăng nhập thành công
            time.sleep(random.uniform(2.5, 3.5))  # Chờ trang load hoàn toàn
            if not self.verify_login_success():
                logger.error("❌ Xác nhận đăng nhập thất bại")
                return False
            
            logger.info("✅ ĐĂNG NHẬP ZALO THÀNH CÔNG!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi trong quá trình đăng nhập: {str(e)}")
            return False
    
    def check_logged_in(self):
        """
        Kiểm tra xem đã đăng nhập chưa
        
        Returns:
            bool: True nếu đã đăng nhập, False nếu chưa
        """
        try:
            current_url = self.page.url
            
            # Kiểm tra URL
            if "chat.zalo.me" in current_url:
                # Kiểm tra có conversation list không
                if self.page.query_selector("div#conversationList"):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra trạng thái đăng nhập: {str(e)}")
            return False


class ZaloSessionManager:
    """Quản lý phiên đăng nhập Zalo với Persistent Context"""
    
    def __init__(self, session_dir=SESSION_DIR):
        """
        Khởi tạo Session Manager
        
        Args:
            session_dir: Thư mục lưu session
        """
        self.session_dir = session_dir
        self.session_info_file = os.path.join(session_dir, "session_info.json")
        self._ensure_session_dir()
    
    def _ensure_session_dir(self):
        """Tạo thư mục session nếu chưa tồn tại"""
        Path(self.session_dir).mkdir(parents=True, exist_ok=True)
    
    def has_session(self):
        """
        Kiểm tra có session đã lưu không
        
        Returns:
            bool: True nếu có session, False nếu không
        """
        # Kiểm tra folder có tồn tại và có files không
        if not os.path.exists(self.session_dir):
            return False
        
        # Kiểm tra có file session_info.json
        if os.path.exists(self.session_info_file):
            return True
        
        # Kiểm tra có files trong folder (cookies, storage, etc)
        files = os.listdir(self.session_dir)
        return len(files) > 0
    
    def get_session_info(self):
        """
        Lấy thông tin session đã lưu
        
        Returns:
            dict: Thông tin session hoặc None
        """
        if not os.path.exists(self.session_info_file):
            return None
        
        try:
            with open(self.session_info_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi khi đọc session info: {str(e)}")
            return None
    
    def save_session_info(self, info):
        """
        Lưu thông tin session
        
        Args:
            info: Dict chứa thông tin session
        """
        try:
            with open(self.session_info_file, 'w', encoding='utf-8') as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
            logger.info("✓ Đã lưu thông tin session")
        except Exception as e:
            logger.error(f"Lỗi khi lưu session info: {str(e)}")
    
    def delete_session(self):
        """Xóa session đã lưu"""
        try:
            import shutil
            if os.path.exists(self.session_dir):
                shutil.rmtree(self.session_dir)
                logger.info("✓ Đã xóa session")
                self._ensure_session_dir()
                return True
        except Exception as e:
            logger.error(f"Lỗi khi xóa session: {str(e)}")
            return False
    
    def create_persistent_context(self, playwright):
        """
        Tạo persistent browser context
        
        Args:
            playwright: Playwright instance
            
        Returns:
            BrowserContext: Persistent context
        """
        try:
            logger.info("Đang tạo persistent context...")
            
            # Tạo persistent context - tự động lưu cookies, storage, cache
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=self.session_dir,
                headless=False,
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                # Các tùy chọn bổ sung
                accept_downloads=True,
                locale='vi-VN',
                timezone_id='Asia/Ho_Chi_Minh'
            )
            
            logger.info("✓ Đã tạo persistent context")
            return context
            
        except Exception as e:
            logger.error(f"Lỗi khi tạo persistent context: {str(e)}")
            raise
    
    def login_with_session(self, max_wait_time=300):
        """
        Đăng nhập Zalo với session persistence

        Args:
            max_wait_time: Thời gian chờ tối đa cho việc quét QR (giây)

        Returns:
            tuple: (success: bool, playwright_instance, context, page)
        """
        try:
            # KHÔNG dùng with để context không tự động đóng
            p = sync_playwright().start()

            # Tạo persistent context
            context = self.create_persistent_context(p)

            # Lấy page đầu tiên hoặc tạo mới
            if len(context.pages) > 0:
                page = context.pages[0]
            else:
                page = context.new_page()

            # Tạo ZaloLogin instance
            zalo = ZaloLogin(page=page, context=context)

            # Kiểm tra đã đăng nhập chưa
            logger.info("Đang kiểm tra session...")
            page.goto(ZaloLogin.CHAT_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(2.5, 3.5))

            if zalo.check_logged_in():
                logger.info("✅ Đã đăng nhập trước đó! Sử dụng session cũ")

                # Lưu thông tin session
                self.save_session_info({
                    'last_login': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'active'
                })

                return True, p, context, page

            # Nếu chưa đăng nhập, thực hiện đăng nhập mới
            logger.info("Session không còn hiệu lực, cần đăng nhập lại...")
            success = zalo.login(max_wait_time)

            if success:
                # Lưu thông tin session
                self.save_session_info({
                    'last_login': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'active'
                })

                return True, p, context, page

            return False, p, context, page

        except Exception as e:
            logger.error(f"Lỗi khi đăng nhập với session: {str(e)}")
            return False, None, None, None


def test_zalo_login():
    """Hàm test cho ZaloLogin sử dụng Playwright với Session Management"""
    session_manager = ZaloSessionManager()

    logger.info("=== TEST ZALO LOGIN VỚI SESSION PERSISTENCE ===")

    # Kiểm tra session
    if session_manager.has_session():
        logger.info("✓ Tìm thấy session đã lưu")
        session_info = session_manager.get_session_info()
        if session_info:
            logger.info(f"  - Lần đăng nhập cuối: {session_info.get('last_login', 'N/A')}")
    else:
        logger.info("ℹ️ Chưa có session, sẽ đăng nhập mới")

    # Đăng nhập
    success, p, context, page = session_manager.login_with_session(max_wait_time=300)

    if success:
        wait_time = random.uniform(28, 32)
        logger.info(f"✅ Test thành công! Giữ trình duyệt mở trong {wait_time:.1f} giây...")
        time.sleep(wait_time)

        # Đóng context và playwright (session vẫn được lưu)
        context.close()
        p.stop()
        logger.info("ℹ️ Đã đóng trình duyệt (session đã được lưu)")
    else:
        logger.error("❌ Test thất bại!")
        if context:
            context.close()
        if p:
            p.stop()


def quick_login():
    """Đăng nhập nhanh với session management"""
    session_manager = ZaloSessionManager()
    return session_manager.login_with_session(max_wait_time=300)


class ZaloAccountManager:
    """Quản lý nhiều tài khoản Zalo"""

    def __init__(self, accounts_file=ACCOUNTS_FILE):
        """
        Khởi tạo Account Manager

        Args:
            accounts_file: File lưu danh sách tài khoản
        """
        self.accounts_file = accounts_file
        self.accounts = self._load_accounts()

        # Tự động dọn dẹp session cũ và trống
        self._cleanup_unused_sessions()

    def _load_accounts(self):
        """
        Load danh sách tài khoản từ file

        Returns:
            list: Danh sách tài khoản
        """
        if not os.path.exists(self.accounts_file):
            return []

        try:
            with open(self.accounts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi khi đọc file accounts: {str(e)}")
            return []

    def _save_accounts(self):
        """Lưu danh sách tài khoản vào file"""
        try:
            with open(self.accounts_file, 'w', encoding='utf-8') as f:
                json.dump(self.accounts, f, ensure_ascii=False, indent=2)
            logger.info("✓ Đã lưu danh sách tài khoản")
        except Exception as e:
            logger.error(f"Lỗi khi lưu file accounts: {str(e)}")

    def get_all_accounts(self):
        """
        Lấy danh sách tất cả tài khoản

        Returns:
            list: Danh sách tài khoản
        """
        return self.accounts

    def get_account_by_id(self, account_id):
        """
        Lấy thông tin tài khoản theo ID

        Args:
            account_id: ID tài khoản

        Returns:
            dict: Thông tin tài khoản hoặc None
        """
        for account in self.accounts:
            if account.get('id') == account_id:
                return account
        return None

    def add_account(self, account_name, zalo_name="", phone=""):
        """
        Thêm tài khoản mới

        Args:
            account_name: Tên tài khoản (do người dùng đặt)
            zalo_name: Tên Zalo (lấy từ Zalo)
            phone: Số điện thoại (optional)

        Returns:
            dict: Thông tin tài khoản mới
        """
        from datetime import datetime
        import uuid

        # Tạo ID unique
        account_id = str(uuid.uuid4())[:8]

        # Tạo session directory riêng cho tài khoản (trong app_data)
        session_dir = os.path.join(APP_DATA_DIR, f"zalo_session_{account_id}")

        new_account = {
            'id': account_id,
            'account_name': account_name,
            'zalo_name': zalo_name,
            'phone': phone,
            'session_dir': session_dir,
            'created_at': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            'last_login': None,
            'status': 'inactive'
        }

        self.accounts.append(new_account)
        self._save_accounts()

        logger.info(f"✓ Đã thêm tài khoản: {account_name} (ID: {account_id})")
        return new_account

    def update_account(self, account_id, **kwargs):
        """
        Cập nhật thông tin tài khoản

        Args:
            account_id: ID tài khoản
            **kwargs: Các trường cần cập nhật
        """
        for account in self.accounts:
            if account.get('id') == account_id:
                account.update(kwargs)
                self._save_accounts()
                logger.info(f"✓ Đã cập nhật tài khoản: {account_id}")
                return True
        return False

    def delete_account(self, account_id):
        """
        Xóa tài khoản

        Args:
            account_id: ID tài khoản

        Returns:
            bool: True nếu thành công
        """
        account = self.get_account_by_id(account_id)
        if not account:
            return False

        # Xóa session directory
        session_dir = account.get('session_dir')
        if session_dir and os.path.exists(session_dir):
            import shutil
            try:
                shutil.rmtree(session_dir)
                logger.info(f"✓ Đã xóa session directory: {session_dir}")
            except Exception as e:
                logger.error(f"Lỗi khi xóa session directory: {str(e)}")

        # Xóa khỏi danh sách
        self.accounts = [acc for acc in self.accounts if acc.get('id') != account_id]
        self._save_accounts()

        logger.info(f"✓ Đã xóa tài khoản: {account_id}")
        return True

    def get_session_manager(self, account_id):
        """
        Lấy ZaloSessionManager cho tài khoản

        Args:
            account_id: ID tài khoản

        Returns:
            ZaloSessionManager: Session manager hoặc None
        """
        account = self.get_account_by_id(account_id)
        if not account:
            return None

        session_dir = account.get('session_dir')
        return ZaloSessionManager(session_dir=session_dir)

    def _cleanup_unused_sessions(self):
        """
        Tự động xóa các session cũ và trống không sử dụng
        - Xóa session không có trong danh sách tài khoản
        - Xóa session trống (không có dữ liệu)
        """
        try:
            import shutil

            # Lấy danh sách session_dir đang được sử dụng
            used_session_dirs = set()
            for account in self.accounts:
                session_dir = account.get('session_dir')
                if session_dir:
                    used_session_dirs.add(os.path.basename(session_dir))

            # Quét thư mục app_data để tìm các session directory
            if not os.path.exists(APP_DATA_DIR):
                return

            deleted_count = 0
            for item in os.listdir(APP_DATA_DIR):
                item_path = os.path.join(APP_DATA_DIR, item)

                # Chỉ xử lý thư mục có tên bắt đầu bằng "zalo_session"
                if not os.path.isdir(item_path):
                    continue
                if not item.startswith("zalo_session"):
                    continue

                # Kiểm tra xem session có đang được sử dụng không
                if item in used_session_dirs:
                    continue

                # Xóa session không được sử dụng
                try:
                    shutil.rmtree(item_path)
                    logger.info(f"🗑️ Đã xóa session không sử dụng: {item}")
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ Không thể xóa {item}: {str(e)}")

            if deleted_count > 0:
                logger.info(f"✓ Đã dọn dẹp {deleted_count} session cũ")

        except Exception as e:
            logger.error(f"Lỗi khi dọn dẹp session: {str(e)}")




if __name__ == "__main__":
    # Chạy test
    test_zalo_login()
