"""
Zalo Automation - Tự động hóa gửi tin nhắn và kết bạn hàng loạt
Sử dụng Playwright để tương tác với Zalo Web
"""
import time
import random
import logging
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ZaloAutomation:
    """Class xử lý tự động hóa Zalo"""
    
    CHAT_URL = "https://chat.zalo.me/"
    
    def __init__(self, page: Page):
        """
        Khởi tạo ZaloAutomation

        Args:
            page: Playwright Page instance đã đăng nhập Zalo
        """
        self.page = page

    def get_my_zalo_name(self, session_manager=None):
        """
        Lấy tên Zalo của tài khoản đang đăng nhập
        Flow: Lấy từ thẻ <title> của trang web -> Lưu vào session

        Args:
            session_manager: ZaloSessionManager instance để lưu tên

        Returns:
            str: Tên Zalo hoặc "nhân viên" nếu không lấy được
        """
        try:
            # Kiểm tra xem đã lưu tên trong session chưa
            if session_manager:
                session_info = session_manager.get_session_info()
                if session_info and session_info.get('zalo_name'):
                    cached_name = session_info.get('zalo_name')
                    logger.info(f"✓ Tên Zalo (từ cache): {cached_name}")
                    return cached_name

            logger.info("🔍 Đang lấy tên Zalo của tài khoản...")

            # Lấy tên từ thẻ <title> của trang
            logger.info("📍 Đang lấy tên từ thẻ <title>...")

            # Đợi trang load xong (random 1.5-2.5s)
            time.sleep(random.uniform(1.5, 2.5))

            # Lấy title của trang
            title = self.page.title()
            logger.info(f"✓ Title trang: {title}")

            # Parse tên từ title (format: "Zalo - Tên Người Dùng")
            my_name = None
            if title and " - " in title:
                parts = title.split(" - ", 1)
                if len(parts) == 2:
                    my_name = parts[1].strip()
                    logger.info(f"✓ Tên Zalo: {my_name}")

            if not my_name:
                logger.warning("⚠️ Không lấy được tên Zalo từ title, sử dụng mặc định")
                my_name = "nhân viên"

            # Lưu tên vào session
            if session_manager and my_name != "nhân viên":
                logger.info("📍 Đang lưu tên vào session...")
                session_info = session_manager.get_session_info() or {}
                session_info['zalo_name'] = my_name
                session_manager.save_session_info(session_info)
                logger.info("✓ Đã lưu tên vào session")

            return my_name

        except Exception as e:
            logger.error(f"Lỗi khi lấy tên Zalo: {str(e)}")
            return "nhân viên"

    def search_and_open_chat(self, phone_number: str, timeout: int = 10000):
        """
        Tìm kiếm và mở chat với số điện thoại
        
        Args:
            phone_number: Số điện thoại cần tìm
            timeout: Thời gian chờ tối đa (milliseconds)
            
        Returns:
            bool: True nếu thành công, False nếu không
        """
        try:
            logger.info(f"Đang tìm kiếm: {phone_number}")
            
            # Tìm ô search
            search_selectors = [
                "input[placeholder*='Tìm kiếm']",
                "input[placeholder*='Search']",
                "input[type='text'][class*='search']",
                "div[class*='search'] input",
            ]
            
            search_box = None
            for selector in search_selectors:
                try:
                    search_box = self.page.wait_for_selector(selector, timeout=timeout, state="visible")
                    if search_box:
                        logger.info(f"✓ Tìm thấy ô tìm kiếm: {selector}")
                        break
                except PlaywrightTimeoutError:
                    continue
            
            if not search_box:
                logger.error("❌ Không tìm thấy ô tìm kiếm")
                return False
            
            # Nhập số điện thoại
            search_box.click()
            search_box.fill("")  # Clear
            time.sleep(random.uniform(0.3, 0.7))
            search_box.type(phone_number, delay=100)
            time.sleep(random.uniform(1.5, 2.5))  # Chờ kết quả tìm kiếm
            
            # Tìm và click vào kết quả đầu tiên
            result_selectors = [
                "div[class*='search-result'] div[class*='item']:first-child",
                "div[class*='result'] div[class*='conv-item']:first-child",
                "div[class*='contact-item']:first-child",
            ]
            
            for selector in result_selectors:
                try:
                    result = self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    if result:
                        result.click()
                        logger.info("✓ Đã mở chat")
                        time.sleep(random.uniform(0.8, 1.5))
                        return True
                except PlaywrightTimeoutError:
                    continue
            
            logger.warning(f"⚠️ Không tìm thấy kết quả cho: {phone_number}")
            return False
            
        except Exception as e:
            logger.error(f"Lỗi khi tìm kiếm: {str(e)}")
            return False
    
    def send_message(self, message: str, timeout: int = 10000):
        """
        Gửi tin nhắn trong chat đang mở
        
        Args:
            message: Nội dung tin nhắn
            timeout: Thời gian chờ tối đa (milliseconds)
            
        Returns:
            bool: True nếu thành công, False nếu không
        """
        try:
            logger.info("Đang gửi tin nhắn...")
            
            # Tìm ô nhập tin nhắn
            input_selectors = [
                "div[contenteditable='true'][class*='input']",
                "div[contenteditable='true'][role='textbox']",
                "textarea[placeholder*='Nhập']",
                "div[class*='chat-input'] div[contenteditable='true']",
            ]
            
            input_box = None
            for selector in input_selectors:
                try:
                    input_box = self.page.wait_for_selector(selector, timeout=timeout, state="visible")
                    if input_box:
                        logger.info(f"✓ Tìm thấy ô nhập tin nhắn: {selector}")
                        break
                except PlaywrightTimeoutError:
                    continue
            
            if not input_box:
                logger.error("❌ Không tìm thấy ô nhập tin nhắn")
                return False
            
            # Nhập tin nhắn
            input_box.click()
            time.sleep(random.uniform(0.2, 0.5))

            # Nhập từng dòng (xử lý xuống dòng)
            lines = message.split('\n')
            for i, line in enumerate(lines):
                input_box.type(line, delay=50)
                if i < len(lines) - 1:
                    # Shift+Enter để xuống dòng
                    self.page.keyboard.press("Shift+Enter")
                    time.sleep(random.uniform(0.05, 0.15))

            time.sleep(random.uniform(0.3, 0.7))
            
            # Tìm và click nút gửi
            send_selectors = [
                "button[class*='send']",
                "div[class*='send-btn']",
                "i[class*='send']",
            ]
            
            for selector in send_selectors:
                try:
                    send_btn = self.page.wait_for_selector(selector, timeout=3000, state="visible")
                    if send_btn:
                        send_btn.click()
                        logger.info("✓ Đã gửi tin nhắn")
                        time.sleep(random.uniform(0.8, 1.5))
                        return True
                except PlaywrightTimeoutError:
                    continue
            
            # Nếu không tìm thấy nút gửi, thử Enter
            logger.info("Không tìm thấy nút gửi, thử Enter...")
            self.page.keyboard.press("Enter")
            time.sleep(random.uniform(0.8, 1.5))
            logger.info("✓ Đã gửi tin nhắn (Enter)")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi gửi tin nhắn: {str(e)}")
            return False
    
    def send_message_to_phone(self, phone_number: str, message: str):
        """
        Tìm kiếm và gửi tin nhắn đến số điện thoại
        
        Args:
            phone_number: Số điện thoại
            message: Nội dung tin nhắn
            
        Returns:
            bool: True nếu thành công, False nếu không
        """
        try:
            # Bước 1: Tìm và mở chat
            if not self.search_and_open_chat(phone_number):
                return False
            
            # Bước 2: Gửi tin nhắn
            if not self.send_message(message):
                return False
            
            logger.info(f"✅ Đã gửi tin nhắn đến {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi gửi tin nhắn đến {phone_number}: {str(e)}")
            return False
    
    def add_friend_by_phone(self, phone_number: str, contract_id: str = "", my_zalo_name: str = "", timeout: int = 10000):
        """
        Thêm bạn bằng số điện thoại theo flow:
        1. Mở Zalo
        2. Tìm nút "Thêm bạn"
        3. Nhập số điện thoại
        4. Nhấn "Tìm kiếm"
        5. Kiểm tra bảng "Thông tin tài khoản"
        6. Nhấn "Kết bạn" (mở form)
        7. Nhập nội dung lời mời kết bạn
        8. Nhấn nút "Kết bạn" (gửi lời mời)

        Args:
            phone_number: Số điện thoại
            contract_id: Mã hợp đồng (từ Excel)
            my_zalo_name: Tên Zalo của tài khoản đang đăng nhập
            timeout: Thời gian chờ tối đa (milliseconds)

        Returns:
            tuple: (success: bool, display_name: str or None)
        """
        try:
            logger.info(f"🔍 Bắt đầu kết bạn với: {phone_number}")

            # Bước 1: Tìm nút "Thêm bạn" chính
            logger.info("📍 Bước 1: Tìm nút 'Thêm bạn'...")
            add_friend_btn_selectors = [
                'div[data-id="btn_Main_AddFrd"]',
                'div[icon="outline-add-new-contact-2"]',
                'div.z--btn--v2:has(i.fa-outline-add-new-contact-2)',
            ]

            add_friend_btn = None
            for selector in add_friend_btn_selectors:
                try:
                    add_friend_btn = self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    if add_friend_btn:
                        logger.info(f"✓ Tìm thấy nút 'Thêm bạn': {selector}")
                        break
                except PlaywrightTimeoutError:
                    continue

            if not add_friend_btn:
                logger.error("❌ Không tìm thấy nút 'Thêm bạn'")
                return False, None

            # Click nút "Thêm bạn"
            add_friend_btn.click()
            logger.info("✓ Đã click nút 'Thêm bạn'")
            time.sleep(random.uniform(0.8, 1.5))

            # Bước 2: Nhập số điện thoại
            logger.info(f"📍 Bước 2: Nhập số điện thoại {phone_number}...")
            phone_input_selectors = [
                'input[data-id="txt_Main_AddFrd_Phone"]',
                'input.phone-i-input',
                'input[placeholder*="Số điện thoại"]',
            ]

            phone_input = None
            for selector in phone_input_selectors:
                try:
                    phone_input = self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    if phone_input:
                        logger.info(f"✓ Tìm thấy ô nhập SĐT: {selector}")
                        break
                except PlaywrightTimeoutError:
                    continue

            if not phone_input:
                logger.error("❌ Không tìm thấy ô nhập số điện thoại")
                return False, None

            # Nhập số điện thoại
            phone_input.click()
            phone_input.fill("")  # Clear
            time.sleep(random.uniform(0.2, 0.5))
            phone_input.type(phone_number, delay=100)
            logger.info(f"✓ Đã nhập số điện thoại: {phone_number}")
            time.sleep(random.uniform(0.3, 0.7))

            # Bước 3: Nhấn nút "Tìm kiếm"
            logger.info("📍 Bước 3: Nhấn nút 'Tìm kiếm'...")
            search_btn_selectors = [
                'div[data-id="btn_Main_AddFrd_Search"]',
                'div.z--btn--v2.btn-primary:has-text("Tìm kiếm")',
                'div.z--btn--v2:has(div:text("Tìm kiếm"))',
            ]

            search_btn = None
            for selector in search_btn_selectors:
                try:
                    search_btn = self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    if search_btn:
                        logger.info(f"✓ Tìm thấy nút 'Tìm kiếm': {selector}")
                        break
                except PlaywrightTimeoutError:
                    continue

            if not search_btn:
                logger.error("❌ Không tìm thấy nút 'Tìm kiếm'")
                return False, None

            # Click nút tìm kiếm
            search_btn.click()
            logger.info("✓ Đã click nút 'Tìm kiếm'")
            time.sleep(random.uniform(1.5, 2.5))  # Chờ kết quả tìm kiếm

            # Bước 4: Kiểm tra bảng "Thông tin tài khoản"
            logger.info("📍 Bước 4: Kiểm tra bảng 'Thông tin tài khoản'...")
            account_info_selectors = [
                'span.zl-modal__dialog__header__title-text:has-text("Thông tin tài khoản")',
                'span[title="Thông tin tài khoản"]',
            ]

            account_info_found = False
            for selector in account_info_selectors:
                try:
                    account_info = self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    if account_info:
                        logger.info("✓ Tìm thấy bảng 'Thông tin tài khoản'")
                        account_info_found = True
                        break
                except PlaywrightTimeoutError:
                    continue

            if not account_info_found:
                logger.warning(f"⚠️ SĐT {phone_number} không thể kết bạn được (không hiện bảng thông tin)")
                return False, None

            # Bước 5: Lấy tên hiển thị Zalo
            logger.info("📍 Bước 5: Lấy tên hiển thị Zalo...")
            display_name = None

            try:
                # Tìm tất cả các div.truncate có title
                name_elements = self.page.query_selector_all('div.truncate[title]')
                for elem in name_elements:
                    title = elem.get_attribute('title')
                    if title and len(title) > 0 and title != "Thông tin tài khoản":
                        display_name = title
                        logger.info(f"✓ Tên hiển thị Zalo: {display_name}")
                        break
            except Exception as e:
                logger.warning(f"⚠️ Không lấy được tên hiển thị: {str(e)}")

            # Bước 6: Kiểm tra nếu đã gửi lời mời trước đó (có nút "Hủy kết bạn")
            logger.info("📍 Bước 6: Kiểm tra trạng thái kết bạn...")
            try:
                undo_btn = self.page.wait_for_selector(
                    'div.truncate[data-translate-inner="STR_UNDO_REQUEST"]:has-text("Hủy kết bạn")',
                    timeout=2000,
                    state="visible"
                )
                if undo_btn:
                    logger.warning(f"⚠️ Đã gửi lời mời kết bạn trước đó cho {phone_number}")
                    logger.info("ℹ️ Bỏ qua khách hàng này và chuyển sang người tiếp theo")
                    return "already_sent", display_name  # Trả về trạng thái đặc biệt
            except PlaywrightTimeoutError:
                pass  # Không có nút "Hủy kết bạn" - OK, tiếp tục

            # Bước 7: Nhấn nút "Kết bạn" (mở form lời mời)
            logger.info("📍 Bước 7: Nhấn nút 'Kết bạn' (mở form)...")
            add_friend_final_selectors = [
                'div.z--btn--v2:has-text("Kết bạn")',
                'div.z--btn--v2.btn-neutral:has(div:text("Kết bạn"))',
            ]

            add_friend_final_btn = None
            for selector in add_friend_final_selectors:
                try:
                    add_friend_final_btn = self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    if add_friend_final_btn:
                        logger.info(f"✓ Tìm thấy nút 'Kết bạn': {selector}")
                        break
                except PlaywrightTimeoutError:
                    continue

            if not add_friend_final_btn:
                logger.error("❌ Không tìm thấy nút 'Kết bạn' trong bảng thông tin")
                return False, display_name

            # Click nút "Kết bạn" để mở form
            add_friend_final_btn.click()
            logger.info("✓ Đã click nút 'Kết bạn' - Mở form lời mời")
            time.sleep(random.uniform(1.2, 2.0))

            # Bước 8: Nhập nội dung lời mời kết bạn
            logger.info("📍 Bước 8: Nhập nội dung lời mời kết bạn...")

            # Tạo nội dung lời mời
            if not my_zalo_name:
                my_zalo_name = "nhân viên"

            if contract_id:
                greeting_message = f"Xin chào, mình là {my_zalo_name} bên công ty tài chính HDSAISON, vui lòng đồng ý kết bạn để được hỗ trợ hợp đồng {contract_id}"
            else:
                greeting_message = f"Xin chào, mình là {my_zalo_name} bên công ty tài chính HDSAISON, vui lòng đồng ý kết bạn để được hỗ trợ"

            logger.info(f"📝 Nội dung: {greeting_message}")

            # Tìm textarea nhập lời mời
            greeting_textarea_selectors = [
                'textarea[data-id="txt_AddFrd_Msg"]',
                'textarea.friend-profile__addfriend__msg',
                'textarea[placeholder*="Nhập lời chào"]',
            ]

            greeting_textarea = None
            for selector in greeting_textarea_selectors:
                try:
                    greeting_textarea = self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    if greeting_textarea:
                        logger.info(f"✓ Tìm thấy ô nhập lời mời: {selector}")
                        break
                except PlaywrightTimeoutError:
                    continue

            if not greeting_textarea:
                logger.error("❌ Không tìm thấy ô nhập lời mời kết bạn")
                return False, display_name

            # Nhập nội dung lời mời
            greeting_textarea.click()
            greeting_textarea.fill("")  # Clear
            time.sleep(random.uniform(0.2, 0.5))
            greeting_textarea.type(greeting_message, delay=50)
            logger.info("✓ Đã nhập nội dung lời mời")
            time.sleep(random.uniform(0.3, 0.7))

            # Bước 9: Nhấn nút "Kết bạn" (gửi lời mời)
            logger.info("📍 Bước 9: Nhấn nút 'Kết bạn' (gửi lời mời)...")
            send_request_btn_selectors = [
                'div[data-id="btn_AddFrd_Add"]',
                'div.z--btn--v2.btn-primary:has-text("Kết bạn")',
                'div.z--btn--v2.btn-primary:has(div:text("Kết bạn"))',
            ]

            send_request_btn = None
            for selector in send_request_btn_selectors:
                try:
                    send_request_btn = self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    if send_request_btn:
                        logger.info(f"✓ Tìm thấy nút 'Kết bạn' (gửi): {selector}")
                        break
                except PlaywrightTimeoutError:
                    continue

            if not send_request_btn:
                logger.error("❌ Không tìm thấy nút 'Kết bạn' để gửi lời mời")
                return False, display_name

            # Click nút gửi lời mời
            send_request_btn.click()
            logger.info(f"✅ Đã gửi lời mời kết bạn đến {phone_number}")
            if display_name:
                logger.info(f"   📝 Tên hiển thị: {display_name}")
            logger.info(f"   💬 Lời mời: {greeting_message}")
            time.sleep(random.uniform(1.2, 2.0))

            return True, display_name

        except Exception as e:
            logger.error(f"❌ Lỗi khi thêm bạn {phone_number}: {str(e)}")
            return False, None

    def close_modal_after_add_friend(self):
        """
        Đóng modal sau khi kết bạn (thành công hoặc thất bại)
        Nhấn nút X hoặc phím ESC
        """
        try:
            # Cách 1: Tìm và click nút X (close button)
            close_btn_selectors = [
                'div.modal-header-icon[data-disabled=""] i.fa-close',
                'div.modal-header-icon i.fa-close',
                'i.fa-close.f16.pre',
                'div[icon="close f16"]',
            ]

            close_btn_found = False
            for selector in close_btn_selectors:
                try:
                    close_btn = self.page.wait_for_selector(selector, timeout=2000, state="visible")
                    if close_btn:
                        close_btn.click()
                        logger.info("✓ Đã click nút X để đóng modal")
                        close_btn_found = True
                        time.sleep(random.uniform(0.3, 0.7))
                        break
                except PlaywrightTimeoutError:
                    continue

            # Cách 2: Nếu không tìm thấy nút X, nhấn phím ESC
            if not close_btn_found:
                self.page.keyboard.press("Escape")
                logger.info("✓ Đã nhấn phím ESC để đóng modal")
                time.sleep(random.uniform(0.3, 0.7))

        except Exception as e:
            logger.warning(f"⚠️ Không thể đóng modal: {str(e)}")
            # Thử nhấn ESC làm phương án cuối cùng
            try:
                self.page.keyboard.press("Escape")
                time.sleep(random.uniform(0.3, 0.7))
            except:
                pass
    
    def send_bulk_messages(self, customer_list: list, template: str, callback=None, delay: int = 3,
                          is_paused_func=None, is_stopped_func=None):
        """
        Gửi tin nhắn hàng loạt

        Args:
            customer_list: Danh sách khách hàng (list of dict)
            template: Template tin nhắn với biến {name}, {phone}, etc.
            callback: Hàm callback để báo tiến trình
            delay: Thời gian chờ giữa các tin nhắn (giây)
            is_paused_func: Hàm kiểm tra trạng thái tạm dừng (trả về True/False)
            is_stopped_func: Hàm kiểm tra trạng thái dừng (trả về True/False)

        Returns:
            dict: Kết quả {success: int, failed: int, errors: list, details: list}
        """
        result = {"success": 0, "failed": 0, "errors": [], "details": []}

        for idx, customer in enumerate(customer_list, 1):
            # Kiểm tra dừng
            if is_stopped_func and is_stopped_func():
                if callback:
                    callback("\n🛑 Đã dừng theo yêu cầu người dùng")
                break

            # Kiểm tra tạm dừng
            if is_paused_func:
                while is_paused_func():
                    if is_stopped_func and is_stopped_func():  # Kiểm tra dừng trong khi tạm dừng
                        if callback:
                            callback("\n🛑 Đã dừng theo yêu cầu người dùng")
                        break
                    time.sleep(random.uniform(0.4, 0.6))

                if is_stopped_func and is_stopped_func():  # Kiểm tra lại sau khi thoát khỏi pause
                    break

            try:
                # Format tin nhắn
                message = template.format(
                    name=customer.get('name', ''),
                    phone=customer.get('phone', ''),
                    address=customer.get('address', ''),
                    cccd=customer.get('cccd', ''),
                    dob=customer.get('dob', ''),
                    contract_id=customer.get('contract_id', ''),
                    gender=customer.get('gender', '')
                )

                phone = customer.get('phone', '').strip()
                name = customer.get('name', 'N/A')

                if not phone:
                    if callback:
                        callback(f"⚠️ [{idx}/{len(customer_list)}] Bỏ qua: {name} (không có SĐT)")
                    result['failed'] += 1
                    result['details'].append({
                        'phone': phone,
                        'name': name,
                        'status': 'no_phone'
                    })
                    continue

                if callback:
                    callback(f"📤 [{idx}/{len(customer_list)}] Đang gửi đến: {name} ({phone})")

                # Gửi tin nhắn
                if self.send_message_to_phone(phone, message):
                    result['success'] += 1
                    if callback:
                        callback(f"✅ [{idx}/{len(customer_list)}] Thành công: {phone}")
                    result['details'].append({
                        'phone': phone,
                        'name': name,
                        'status': 'success'
                    })
                else:
                    result['failed'] += 1
                    result['errors'].append(f"{phone}: Không thể gửi tin nhắn")
                    if callback:
                        callback(f"❌ [{idx}/{len(customer_list)}] Thất bại: {phone}")
                    result['details'].append({
                        'phone': phone,
                        'name': name,
                        'status': 'failed'
                    })

                # Delay giữa các tin nhắn (thêm random vào delay)
                if idx < len(customer_list):
                    # Thêm biến động ±20% vào delay
                    random_delay = delay * random.uniform(0.8, 1.2)

                    # Chia nhỏ delay để có thể dừng nhanh hơn
                    delay_steps = int(random_delay * 10)  # Chia thành các bước 0.1s
                    for _ in range(delay_steps):
                        if is_stopped_func and is_stopped_func():
                            if callback:
                                callback("\n🛑 Đã dừng theo yêu cầu người dùng")
                            break
                        time.sleep(0.1)

                    if is_stopped_func and is_stopped_func():
                        break

            except Exception as e:
                result['failed'] += 1
                result['errors'].append(f"{customer.get('phone', 'N/A')}: {str(e)}")
                if callback:
                    callback(f"❌ [{idx}/{len(customer_list)}] Lỗi: {str(e)}")
                result['details'].append({
                    'phone': customer.get('phone', ''),
                    'name': customer.get('name', 'N/A'),
                    'status': 'error'
                })

        return result

