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

# Thư mục lưu trữ dữ liệu ứng dụng - sử dụng đường dẫn tuyệt đối từ root project
_BASE_DIR = Path(__file__).resolve().parent.parent.parent  # auto_rpa_hdsaison/
APP_DATA_DIR = str(_BASE_DIR / "app_data")
if not os.path.exists(APP_DATA_DIR):
    os.makedirs(APP_DATA_DIR)

# Thư mục lưu session
SESSION_DIR = os.path.join(APP_DATA_DIR, "zalo_session")


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
    
    def wait_for_qr_code(self, timeout=3000):
        """
        Chờ mã QR xuất hiện
        timeout nhỏ (3s/selector) để tránh chặn quá lâu khi user quét nhanh
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
            
            # Nếu không tìm thấy QR code cụ thể, kiểm tra URL
            # (bao gồm cả trường hợp user đã quét rất nhanh và trang chuyển sang chat.zalo.me)
            current = self.page.url
            if "id.zalo.me" in current or "chat.zalo.me" in current:
                logger.info(f"✓ Đang ở trang đăng nhập / đã redirect: {current}")
                return True
            
            logger.warning("Không tìm thấy mã QR")
            return False
            
        except Exception as e:
            logger.error(f"Lỗi khi chờ QR code: {str(e)}")
            return False
    
    def wait_for_user_scan(self, max_wait_time=300, on_detected=None):
        """
        Chờ người dùng quét mã QR và đăng nhập.
        Xác định thành công khi URL chuyển sang chat.zalo.me.
        on_detected được gọi ngay lập tức khi URL đổi.
        """
        try:
            logger.info(f"⏳ Vui lòng quét mã QR để đăng nhập (thời gian chờ: {max_wait_time}s)...")
            start_time = time.time()

            while time.time() - start_time < max_wait_time:
                try:
                    if "chat.zalo.me" in self.page.url:
                        logger.info("✅ URL chuyển sang chat.zalo.me — đăng nhập thành công!")
                        if on_detected:
                            try:
                                on_detected()
                            except Exception as cb_err:
                                logger.warning(f"on_detected callback lỗi: {cb_err}")
                        return True
                except Exception:
                    pass

                time.sleep(1.5)

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
        Xác nhận đăng nhập thành công:
        - URL là chat.zalo.me
        - Avatar user (div.zavatar img) hoặc icon chat (i.fa-Message_28_Filled) hiển thị
        """
        try:
            logger.info("Đang xác nhận đăng nhập thành công...")
            
            if "chat.zalo.me" not in self.page.url:
                logger.warning(f"URL không đúng: {self.page.url}")
                return False
            
            # Ưu tiên kiểm tra avatar và icon chat — selector đặc trưng nhất
            reliable_selectors = [
                "div.zavatar img",
                "i.fa.fa-Message_28_Filled",
                "div.mmi-icon-wr",
            ]
            
            for selector in reliable_selectors:
                try:
                    el = self.page.wait_for_selector(selector, timeout=timeout, state="visible")
                    if el:
                        logger.info(f"✅ Đăng nhập xác nhận qua: {selector}")
                        return True
                except PlaywrightTimeoutError:
                    continue
            
            logger.error("❌ Không tìm thấy đầu hiệu đăng nhập")
            return False
            
        except Exception as e:
            logger.error(f"Lỗi khi xác nhận đăng nhập: {str(e)}")
            return False
    
    def login(self, max_wait_time=300, on_login_detected=None):
        """
        Quy trình đăng nhập Zalo hoàn chỉnh
        
        Args:
            max_wait_time: Thời gian chờ tối đa cho việc quét QR (giây)
            on_login_detected: Callback gọi ngay khi phát hiện đăng nhập
            
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
            # on_login_detected được gọi NGAY KHI phát hiện avatar/icon
            scan_ok = self.wait_for_user_scan(max_wait_time, on_detected=on_login_detected)
            if not scan_ok:
                logger.error("❌ Đăng nhập không thành công (timeout hoặc lỗi)")
                return False

            # Bước 4: Nếu on_login_detected đã phát hiện thành công (selector khớp)
            # thì bỏ qua verify vì đã chắc chắn. Nếu không (callback=None), verify lại.
            if on_login_detected is None:
                time.sleep(random.uniform(2.5, 3.5))
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
        Kiểm tra đã đăng nhập chưa (dùng khi kiểm tra session cũ)
        Xác định: URL là chat.zalo.me VÀ avatar user hoặc icon chat hiển thị
        """
        try:
            if "chat.zalo.me" not in self.page.url:
                return False
            
            return bool(
                self.page.query_selector("div.zavatar img") or
                self.page.query_selector("i.fa.fa-Message_28_Filled") or
                self.page.query_selector("div.mmi-icon-wr")
            )
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
    
    def create_persistent_context(self, playwright, headless=False):
        """
        Tạo persistent browser context
        
        Args:
            playwright: Playwright instance
            headless: Chạy headless mode hay không
            
        Returns:
            BrowserContext: Persistent context
        """
        try:
            logger.info(f"Đang tạo persistent context (headless={headless})...")
            
            # Tạo persistent context - tự động lưu cookies, storage, cache
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=self.session_dir,
                headless=headless,
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                # Các tùy chọn bổ sung
                accept_downloads=True,
                locale='vi-VN',
                timezone_id='Asia/Ho_Chi_Minh',
                # Thêm args cho headless mode
                args=['--disable-blink-features=AutomationControlled'] if not headless else [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-gpu',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            logger.info("✓ Đã tạo persistent context")
            return context
            
        except Exception as e:
            logger.error(f"Lỗi khi tạo persistent context: {str(e)}")
            raise
    
    def login_with_session(self, max_wait_time=300, headless=False, force_relogin=False, on_login_detected=None):
        """
        Đăng nhập Zalo với session persistence và hỗ trợ headless mode
        
        Headless mode:
        - Nếu đã có session hợp lệ: chạy headless
        - Nếu cần đăng nhập mới (quét QR): tự động chuyển sang non-headless,
          sau khi đăng nhập thành công sẽ đóng browser và chạy lại headless

        Args:
            max_wait_time: Thời gian chờ tối đa cho việc quét QR (giây)
            headless: Chạy headless mode hay không (mặc định False)
            force_relogin: Xóa cookie cũ và bắt buộc hiển thị QR quét lại (mặc định False)

        Returns:
            tuple: (success: bool, playwright_instance, context, page)
        """
        try:
            # KHÔNG dùng with để context không tự động đóng
            p = sync_playwright().start()

            # Bước 1: Tạo context (luôn non-headless để quét QR)
            logger.info(f"Bước 1: Tạo context với headless={headless}, force_relogin={force_relogin}")
            context = self.create_persistent_context(p, headless=headless)

            # Lấy page đầu tiên hoặc tạo mới
            if len(context.pages) > 0:
                page = context.pages[0]
            else:
                page = context.new_page()

            # Nếu force_relogin: xóa toàn bộ cookie và storage để buộc hiện QR
            if force_relogin:
                logger.info("🔄 force_relogin=True: Xóa cookie cũ để bắt buộc quét QR mới...")
                context.clear_cookies()
                try:
                    page.goto("about:blank")
                    page.evaluate("localStorage.clear(); sessionStorage.clear();")
                except Exception:
                    pass

            # Tạo ZaloLogin instance
            zalo = ZaloLogin(page=page, context=context)

            # Kiểm tra đã đăng nhập chưa (chỉ khi không force_relogin)
            if not force_relogin:
                logger.info("Đang kiểm tra session...")
                page.goto(ZaloLogin.CHAT_URL, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(2.5, 3.5))

                if zalo.check_logged_in():
                    logger.info("✅ Đã đăng nhập trước đó! Sử dụng session cũ")
                    if headless:
                        logger.info("✅ Chạy ở chế độ headless")

                    # Lưu thông tin session
                    self.save_session_info({
                        'last_login': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'status': 'active'
                    })

                    return True, p, context, page

            # Nếu chưa đăng nhập và đang ở headless mode
            if headless:
                logger.info("⚠️ Cần đăng nhập mới (quét QR code)")
                logger.info("🔄 Đang chuyển sang chế độ hiển thị browser để quét QR...")
                
                # Đóng context headless hiện tại
                context.close()
                p.stop()
                
                # Tạo lại context với non-headless để quét QR
                p = sync_playwright().start()
                context = self.create_persistent_context(p, headless=False)
                
                if len(context.pages) > 0:
                    page = context.pages[0]
                else:
                    page = context.new_page()
                
                zalo = ZaloLogin(page=page, context=context)
                logger.info("📱 Đã mở trình duyệt. Vui lòng quét QR code...")

            # Thực hiện đăng nhập mới
            logger.info("Session không còn hiệu lực, cần đăng nhập lại...")
            success = zalo.login(max_wait_time, on_login_detected=on_login_detected)

            if success:
                # Lưu thông tin session
                self.save_session_info({
                    'last_login': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'active'
                })
                
                logger.info("✅ Đăng nhập thành công!")
                
                # Nếu user chọn headless ban đầu, thông báo sẽ đóng browser
                if headless:
                    logger.info("ℹ️ Đăng nhập hoàn tất. Browser sẽ đóng và chạy lại ở chế độ ngầm...")

                return True, p, context, page

            return False, p, context, page

        except Exception as e:
            logger.error(f"Lỗi khi đăng nhập với session: {str(e)}")
            return False, None, None, None


    def connect_headless_only(self):
        """
        Kết nối Zalo ở chế độ headless sử dụng session đã lưu.
        KHÔNG hiện QR, KHÔNG mở browser hiện ra màn hình.
        Dùng cho các task tự động (gửi tin, kết bạn) sau khi đã đăng nhập trước.

        Returns:
            tuple: (success: bool, playwright_instance, context, page)
                   success=False nếu session đã hết hạn (user cần login lại)
        """
        p = None
        context = None
        try:
            p = sync_playwright().start()
            context = self.create_persistent_context(p, headless=True)
            page = context.pages[0] if context.pages else context.new_page()

            page.goto(ZaloLogin.CHAT_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(2.0, 3.0))

            zalo = ZaloLogin(page=page, context=context)
            if zalo.check_logged_in():
                logger.info("✅ [headless] Session còn hợp lệ, đã kết nối headless")
                return True, p, context, page

            logger.warning("⚠️ [headless] Session đã hết hạn, cần đăng nhập lại")
            context.close()
            p.stop()
            return False, None, None, None

        except Exception as e:
            logger.error(f"Lỗi khi kết nối headless: {e}")
            try:
                if context:
                    context.close()
                if p:
                    p.stop()
            except Exception:
                pass
            return False, None, None, None

    def connect_with_session(self, headless=False):
        """
        Kết nối Zalo sử dụng session đã lưu với chế độ hiển thị tùy chọn.

        Args:
            headless: True để chạy ẩn, False để hiện browser

        Returns:
            tuple: (success: bool, playwright_instance, context, page)
                   success=False nếu session đã hết hạn (user cần login lại)
        """
        p = None
        context = None
        try:
            p = sync_playwright().start()
            context = self.create_persistent_context(p, headless=headless)
            page = context.pages[0] if context.pages else context.new_page()

            page.goto(ZaloLogin.CHAT_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(2.0, 3.0))

            zalo = ZaloLogin(page=page, context=context)
            if zalo.check_logged_in():
                mode = "headless" if headless else "headful"
                logger.info(f"✅ [{mode}] Session còn hợp lệ, đã kết nối Zalo")
                return True, p, context, page

            logger.warning("⚠️ Session Zalo đã hết hạn, cần đăng nhập lại")
            context.close()
            p.stop()
            return False, None, None, None

        except Exception as e:
            logger.error(f"Lỗi khi kết nối Zalo với session: {e}")
            try:
                if context:
                    context.close()
                if p:
                    p.stop()
            except Exception:
                pass
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




if __name__ == "__main__":
    # Chạy test
    test_zalo_login()
