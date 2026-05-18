"""
Zalo Automation - Tự động hóa gửi tin nhắn và kết bạn hàng loạt
Sử dụng Playwright để tương tác với Zalo Web
"""
import time
import random
import logging
import unicodedata
import os
import subprocess
import base64
import mimetypes
from pathlib import Path
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from config.settings import ZALO_CHAT_URL

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BrowserClosedError(RuntimeError):
    """Raised when the Playwright page/context/browser is closed during automation."""


class ZaloRateLimitError(RuntimeError):
    """Raised when Zalo blocks phone search/add-friend due to anti-spam limits."""


def is_browser_closed_error(error) -> bool:
    """Detect Playwright errors caused by a closed page/context/browser."""
    text = str(error).lower()
    return any(
        marker in text
        for marker in [
            "target page, context or browser has been closed",
            "page has been closed",
            "browser has been closed",
            "context has been closed",
            "trang web đã bị đóng",
            "trình duyệt đã bị đóng",
            "browser_closed",
        ]
    )


def is_rate_limit_error(error) -> bool:
    """Detect Zalo anti-spam/rate-limit errors from exception text."""
    text = str(error).lower()
    return any(
        marker in text
        for marker in [
            "tìm số điện thoại quá nhiều lần trong 1 giờ",
            "hoạt động bất thường",
            "bạn hãy thử lại vào",
            "zalo_rate_limit",
        ]
    )


def to_gender_pronoun(value) -> str:
    """Convert raw gender values from Excel/data sources to anh/chị."""
    raw_text = str(value or '').strip()
    if not raw_text:
        return 'anh/chị'

    normalized = unicodedata.normalize('NFKD', raw_text)
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower().strip()

    male_markers = {'nam', 'male', 'm', 'mr', 'anh', 'boy'}
    female_markers = {'nu', 'female', 'f', 'ms', 'mrs', 'chi', 'girl'}

    if normalized in male_markers or 'nam' in normalized or 'male' in normalized:
        return 'anh'
    if normalized in female_markers or 'nu' in normalized or 'female' in normalized:
        return 'chị'
    return 'anh/chị'


class ZaloAutomation:
    """Class xử lý tự động hóa Zalo"""

    CHAT_URL = ZALO_CHAT_URL

    # ==================== SELECTORS ====================
    # Nút "Phân loại" (Tag/Label button)
    SELECTOR_BTN_PHAN_LOAI = 'i.fa.fa-outline-tag.label-ico-header[data-translate-title="STR_LABEL_CLASS"]'

    # Thẻ "Khách hàng" (Customer label/tag)
    SELECTOR_THE_KHACH_HANG = 'div.zmenu-item:has-text("Khách hàng")'
    SELECTOR_THE_KHACH_HANG_ALT = '.zmenu-item:has(.fa.fa-Tag_24_Filled) .truncate:has-text("Khách hàng")'

    # Ô "Soạn tin nhắn" (Message input box)
    SELECTOR_O_SOAN_TIN = '#richInput.rich-input'
    SELECTOR_O_SOAN_TIN_ALT = 'div[contenteditable="true"]#richInput'
    SELECTOR_O_SOAN_TIN_CONTAINER = '.chat-input-container__left-layout'
    # ===================================================

    def __init__(self, page: Page):
        """
        Khởi tạo ZaloAutomation

        Args:
            page: Playwright Page instance đã đăng nhập Zalo
        """
        self.page = page

    def _focus_chat_input_box(self, timeout: int = 10000):
        input_selectors = [
            'div#richInput.rich-input[contenteditable="true"]',
            'div[contenteditable="true"]#richInput',
            'div[contenteditable="true"][data-placeholder*="Nhập @"]',
            'div[contenteditable="true"][placeholder*="Nhập @"]',
            "div[contenteditable='true'][class*='input']",
            "div[contenteditable='true'][role='textbox']",
            "div[class*='chat-input'] div[contenteditable='true']",
        ]

        for selector in input_selectors:
            try:
                input_box = self.page.wait_for_selector(selector, timeout=timeout, state="visible")
                if input_box:
                    input_box.click()
                    time.sleep(random.uniform(0.2, 0.45))
                    return input_box
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue
        return None

    @staticmethod
    def _set_windows_file_clipboard(file_path: str) -> bool:
        if os.name != "nt":
            return False
        try:
            cmd = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f"Set-Clipboard -Path '{str(file_path).replace("'", "''")}'",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False

    def _activate_image_caption_mode(self, timeout: int = 3000):
        preview_click_selectors = [
            'div.media-preview img',
            'div.media-preview-item img',
            'img[src^="blob:"]',
            'div[class*="image-preview"] img',
        ]
        for selector in preview_click_selectors:
            try:
                image_el = self.page.wait_for_selector(selector, timeout=timeout, state="visible")
                if image_el:
                    image_el.click()
                    time.sleep(random.uniform(0.2, 0.45))
                    break
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue

        return self._focus_chat_input_box(timeout=timeout) is not None

    def _dismiss_edit_caption_tip(self, timeout: int = 1500) -> bool:
        close_selectors = [
            'i.editCaptionTip-closeBtn',
            'div.editCaptionTip-content i.fa-close.clickable',
            'div.z-tooltip i.editCaptionTip-closeBtn',
        ]

        for selector in close_selectors:
            try:
                close_btn = self.page.wait_for_selector(selector, timeout=timeout, state="visible")
                if close_btn:
                    try:
                        close_btn.click()
                    except Exception:
                        close_btn.click(force=True)
                    time.sleep(random.uniform(0.12, 0.25))
                    logger.info("✓ Đã tắt tooltip 'Nhấn vào ảnh để thêm mô tả'")
                    return True
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue

        # Fallback nhẹ: ESC thường đóng popover/tooltip nổi
        try:
            self.page.keyboard.press("Escape")
            time.sleep(random.uniform(0.08, 0.15))
        except Exception:
            pass
        return False

    def _click_send_button_in_chat(self, timeout: int = 2500) -> bool:
        scoped_selectors = [
            '#chat-input-container-id .normal-buttons-group div.send-msg-btn[title="Gửi"]',
            '#chat-input-container-id .normal-buttons-group div[icon="Sent-msg_24_Line"].send-msg-btn',
            '#chat-input-container-id .normal-buttons-group div.send-msg-btn[data-translate-title="STR_SEND"]',
            '#chat-input-container-id div.send-msg-btn[title="Gửi"]',
        ]

        for selector in scoped_selectors:
            try:
                elements = self.page.query_selector_all(selector)
            except Exception:
                elements = []

            # Ưu tiên nút nằm thấp nhất (khung compose active thường ở dưới cùng)
            try:
                elements = sorted(
                    elements,
                    key=lambda node: (node.bounding_box() or {}).get("y", -1),
                    reverse=True,
                )
            except Exception:
                pass

            for el in elements:
                try:
                    if not el or not el.is_visible():
                        continue

                    bbox = el.bounding_box()
                    if not bbox or bbox.get("width", 0) < 8 or bbox.get("height", 0) < 8:
                        continue

                    try:
                        el.scroll_into_view_if_needed(timeout=timeout)
                    except Exception:
                        pass

                    # Click theo tọa độ thật và chỉ khi điểm giữa thuộc topmost send button
                    try:
                        center = {
                            "x": bbox["x"] + (bbox["width"] / 2),
                            "y": bbox["y"] + (bbox["height"] / 2),
                        }
                        is_topmost_send = self.page.evaluate(
                            """
                            (point) => {
                              const el = document.elementFromPoint(point.x, point.y);
                              if (!el) return false;
                              const sendBtn = el.closest('div.send-msg-btn');
                              return !!sendBtn;
                            }
                            """,
                            center,
                        )
                        if is_topmost_send:
                            self.page.mouse.click(center["x"], center["y"])
                            logger.info(f"📤 Đã click theo tọa độ nút gửi: {selector}")
                            return True
                    except Exception:
                        pass

                    try:
                        el.click(timeout=1000)
                        logger.info(f"📤 Đã click nút gửi trong chat: {selector}")
                        return True
                    except Exception:
                        pass

                    try:
                        icon = el.query_selector('i.fa-Sent-msg_24_Line')
                        if icon:
                            icon.click(timeout=1000)
                            logger.info(f"📤 Đã click icon gửi trong chat: {selector}")
                            return True
                    except Exception:
                        pass

                    try:
                        el.click(force=True, timeout=1000)
                        logger.info(f"📤 Đã force-click nút gửi trong chat: {selector}")
                        return True
                    except Exception:
                        pass

                    try:
                        self.page.evaluate(
                            "(node) => node.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }))",
                            el,
                        )
                        logger.info(f"📤 Đã JS-click nút gửi trong chat: {selector}")
                        return True
                    except Exception:
                        pass

                except Exception:
                    continue

        return False

    def _collect_send_diagnostics(self) -> dict:
        try:
            diagnostics = self.page.evaluate(
                """
                () => {
                    const isVisible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        if (!style) return false;
                        return style.visibility !== 'hidden' && style.display !== 'none' && (el.offsetWidth > 0 || el.offsetHeight > 0);
                    };

                    const active = document.activeElement;
                    const rich = document.querySelector('#chat-input-container-id #richInput');
                    const richText = rich ? (rich.innerText || '').trim() : '';
                    const richAlt = rich ? String(rich.getAttribute('alt') || '').trim() : '';
                    const sendBtns = Array.from(document.querySelectorAll('#chat-input-container-id .normal-buttons-group .send-msg-btn'));
                    const visibleSendBtns = sendBtns.filter(isVisible);
                    const previewCount = document.querySelectorAll('div.media-preview, div.media-preview-item, img[src^="blob:"]').length;
                    const tipClose = document.querySelector('i.editCaptionTip-closeBtn');
                    const clearAllNodes = Array.from(document.querySelectorAll('span,div,button,a')).filter((el) => {
                        const txt = (el.textContent || '').trim();
                        return txt === 'Xóa tất cả' && isVisible(el);
                    });

                    let topAtSend = '';
                    if (visibleSendBtns.length > 0) {
                        const target = visibleSendBtns.sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top)[0];
                        const rect = target.getBoundingClientRect();
                        const cx = rect.left + rect.width / 2;
                        const cy = rect.top + rect.height / 2;
                        const topEl = document.elementFromPoint(cx, cy);
                        topAtSend = topEl ? `${topEl.tagName.toLowerCase()}#${topEl.id || ''}.${topEl.className || ''}` : '';
                    }

                    return {
                        activeTag: active ? active.tagName : '',
                        activeId: active ? active.id : '',
                        activeClass: active ? String(active.className || '') : '',
                        richEditable: rich ? String(rich.getAttribute('contenteditable') || '') : '',
                        richTextLen: richText.length,
                        richAltLen: richAlt.length,
                        sendBtnCount: sendBtns.length,
                        visibleSendBtnCount: visibleSendBtns.length,
                        previewCount,
                        clearAllVisible: clearAllNodes.length > 0,
                        captionTipVisible: !!(tipClose && isVisible(tipClose)),
                        topElementAtSendCenter: topAtSend,
                    };
                }
                """
            )
            return diagnostics if isinstance(diagnostics, dict) else {"raw": diagnostics}
        except Exception as e:
            return {"error": str(e)}

    def _log_send_diagnostics(self, stage: str):
        diagnostics = self._collect_send_diagnostics()
        logger.info(f"🧪 SEND_DIAG [{stage}] {diagnostics}")

    def _confirm_send_effect(self, has_image: bool, timeout_ms: int = 3000) -> bool:
        start = time.time()
        timeout_seconds = max(0.5, timeout_ms / 1000)

        while (time.time() - start) < timeout_seconds:
            if self.page.is_closed():
                return False

            diagnostics = self._collect_send_diagnostics()
            preview_count = int(diagnostics.get("previewCount") or 0)
            rich_text_len = int(diagnostics.get("richTextLen") or 0)
            clear_all_visible = bool(diagnostics.get("clearAllVisible"))

            if has_image:
                if preview_count == 0 and not clear_all_visible:
                    return True
                if preview_count == 0 and rich_text_len == 0:
                    return True
            else:
                if rich_text_len == 0:
                    return True

            time.sleep(0.18)

        return False

    def _attach_image_via_clipboard(self, image_path: str, timeout: int = 10000) -> bool:
        path_obj = Path(image_path)
        if not path_obj.exists() or not path_obj.is_file():
            logger.error(f"❌ Ảnh đính kèm không tồn tại: {image_path}")
            return False

        input_box = self._focus_chat_input_box(timeout=timeout)
        if not input_box:
            logger.error("❌ Không tìm thấy khung chat để paste ảnh")
            return False

        clipboard_ready = self._set_windows_file_clipboard(str(path_obj))
        if not clipboard_ready:
            logger.warning("⚠️ Không thể đưa file vào clipboard hệ điều hành")
            return False

        self.page.keyboard.press("Control+V")
        time.sleep(random.uniform(0.8, 1.3))

        preview_selectors = [
            'div.media-preview',
            'div.media-preview-item',
            'img[src^="blob:"]',
            'button:has-text("Xóa tất cả")',
            'div[role="dialog"] button:has-text("Gửi")',
            'button:has-text("Gửi")',
            'div.z--btn--v2.btn-primary:has-text("Gửi")',
        ]
        for selector in preview_selectors:
            try:
                preview = self.page.wait_for_selector(selector, timeout=1800, state="visible")
                if preview:
                    logger.info("✓ Đã paste ảnh vào khung chat")
                    return True
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue

        return False

    def _wait_for_image_preview(self, timeout_ms: int = 4500) -> bool:
        preview_selectors = [
            'div.media-preview',
            'div.media-preview-item',
            'img[src^="blob:"]',
            'span:has-text("ảnh")',
            'div:has-text("Xóa tất cả")',
        ]
        for selector in preview_selectors:
            try:
                found = self.page.wait_for_selector(selector, timeout=timeout_ms, state="visible")
                if found:
                    return True
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue
        return False

    def _collect_attach_diagnostics(self) -> dict:
        try:
            diagnostics = self.page.evaluate(
                """
                () => {
                    const isVisible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        return style && style.display !== 'none' && style.visibility !== 'hidden' && (el.offsetWidth > 0 || el.offsetHeight > 0);
                    };

                    const rich = document.querySelector('#chat-input-container-id #richInput');
                    const previewNodes = document.querySelectorAll('div.media-preview, div.media-preview-item, img[src^="blob:"]');
                    const tooltipClose = document.querySelector('i.editCaptionTip-closeBtn');
                    const attachIcons = document.querySelectorAll('i.fa.fa-clip, div[icon*="attach"], .chat-box-input-button');

                    return {
                        richFound: !!rich,
                        richEditable: rich ? String(rich.getAttribute('contenteditable') || '') : '',
                        richPlaceholder: rich ? String(rich.getAttribute('placeholder') || '') : '',
                        richTextLen: rich ? String(rich.innerText || '').trim().length : 0,
                        previewCount: previewNodes.length,
                        captionTipVisible: !!(tooltipClose && isVisible(tooltipClose)),
                        attachIconCount: attachIcons.length,
                    };
                }
                """
            )
            return diagnostics if isinstance(diagnostics, dict) else {"raw": diagnostics}
        except Exception as e:
            return {"error": str(e)}

    def _log_attach_diagnostics(self, stage: str):
        logger.info(f"🧪 ATTACH_DIAG [{stage}] {self._collect_attach_diagnostics()}")

    def _attach_image_via_dom_paste(self, image_path: str, timeout: int = 10000) -> bool:
        path_obj = Path(image_path)
        if not path_obj.exists() or not path_obj.is_file():
            return False

        target = self._focus_chat_input_box(timeout=timeout)
        if not target:
            return False

        try:
            mime_type = mimetypes.guess_type(str(path_obj))[0] or "image/jpeg"
            with path_obj.open("rb") as stream:
                encoded = base64.b64encode(stream.read()).decode("ascii")

            dispatch_ok = self.page.evaluate(
                """
                ({ b64, filename, mimeType }) => {
                    const base64ToUint8 = (base64) => {
                        const binary = atob(base64);
                        const bytes = new Uint8Array(binary.length);
                        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
                        return bytes;
                    };

                    const target =
                        document.querySelector('#chat-input-container-id #richInput') ||
                        document.querySelector('#chat-input-content-id') ||
                        document.querySelector('#chat-input-container-id');
                    if (!target) return false;

                    const bytes = base64ToUint8(b64);
                    const file = new File([bytes], filename, { type: mimeType });
                    const dt = new DataTransfer();
                    dt.items.add(file);

                    const event = new Event('paste', { bubbles: true, cancelable: true });
                    Object.defineProperty(event, 'clipboardData', { value: dt });

                    target.dispatchEvent(event);
                    return true;
                }
                """,
                {
                    "b64": encoded,
                    "filename": path_obj.name,
                    "mimeType": mime_type,
                },
            )

            if not dispatch_ok:
                return False

            time.sleep(random.uniform(0.35, 0.75))
            return self._wait_for_image_preview(timeout_ms=3500)
        except Exception:
            return False

    def _attach_image_to_chat(self, image_path: str, timeout: int = 10000) -> bool:
        """Attach an image to current chat (clipboard first, file-input fallback)."""
        try:
            if not image_path:
                return True

            path_obj = Path(image_path)
            if not path_obj.exists() or not path_obj.is_file():
                logger.error(f"❌ Ảnh đính kèm không tồn tại: {image_path}")
                return False

            logger.info(f"🖼️ Đang đính kèm ảnh: {path_obj.name}")
            self._log_attach_diagnostics("before_attach")

            if self._attach_image_via_dom_paste(image_path=str(path_obj), timeout=timeout):
                self._log_attach_diagnostics("attached_by_dom_paste")
                logger.info("✓ Đã chèn ảnh bằng DOM paste event")
                return True

            if self._attach_image_via_clipboard(image_path=str(path_obj), timeout=timeout):
                self._log_attach_diagnostics("attached_by_os_clipboard")
                logger.info("✓ Đã chèn ảnh bằng cơ chế clipboard (Ctrl+V)")
                return True

            self._log_attach_diagnostics("clipboard_attach_failed")

            attach_trigger_selectors = [
                'i.fa.fa-clip',
                'div[icon*="attach"]',
                'button[aria-label*="đính kèm"]',
                'button[title*="Đính kèm"]',
            ]
            for selector in attach_trigger_selectors:
                try:
                    btn = self.page.query_selector(selector)
                    if btn:
                        btn.click()
                        time.sleep(random.uniform(0.15, 0.35))
                        break
                except Exception:
                    continue

            file_input_selectors = [
                'input[type="file"]',
                'input[type="file"][accept*="image"]',
            ]

            file_input = None
            for selector in file_input_selectors:
                try:
                    file_input = self.page.wait_for_selector(selector, timeout=timeout, state="attached")
                    if file_input:
                        break
                except PlaywrightTimeoutError:
                    continue

            if not file_input:
                self._log_attach_diagnostics("file_input_not_found")
                logger.error("❌ Không tìm thấy input file để đính kèm ảnh")
                return False

            file_input.set_input_files(str(path_obj))
            logger.info("✓ Đã chọn ảnh đính kèm")
            time.sleep(random.uniform(0.6, 1.1))

            media_send_selectors = [
                'button:has-text("Gửi")',
                'div.z--btn--v2.btn-primary:has-text("Gửi")',
                'div[data-id*="send"]',
            ]
            for selector in media_send_selectors:
                try:
                    send_btn = self.page.wait_for_selector(selector, timeout=1200, state="visible")
                    if send_btn:
                        self._log_attach_diagnostics("attached_by_file_input")
                        logger.info("✓ Đã chèn ảnh bằng fallback input file")
                        return True
                except PlaywrightTimeoutError:
                    continue
                except Exception:
                    continue

            logger.error("❌ Không thấy preview ảnh sau khi chèn")
            self._log_attach_diagnostics("attach_preview_missing")
            return False
        except Exception as e:
            logger.error(f"❌ Lỗi khi đính kèm ảnh: {str(e)}")
            self._log_attach_diagnostics("attach_exception")
            return False

    def _detect_add_friend_rate_limit(self, timeout: int = 2000) -> str | None:
        """Check if Zalo shows anti-spam search limit popup in add-friend flow."""
        selectors = [
            'div.error span.error__msg',
            'span.error__msg',
            'span[data-translate-inner*="Tìm số điện thoại quá nhiều lần"]',
            'div.error__msg',
        ]

        for selector in selectors:
            try:
                el = self.page.wait_for_selector(selector, timeout=timeout, state="visible")
                if not el:
                    continue
                raw_text = (el.inner_text() or "").strip()
                normalized = " ".join(raw_text.split())
                if (
                    "Tìm số điện thoại quá nhiều lần trong 1 giờ" in normalized
                    or ("hoạt động bất thường" in normalized and "Bạn hãy thử lại vào" in normalized)
                ):
                    return normalized
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue

        return None

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
        Tìm kiếm và mở chat với số điện thoại theo quy trình:
        1. Nhấn vào ô tìm kiếm
        2. Nhập số điện thoại
        3. Đợi thông tin khách hàng hiện lên
        4. Kiểm tra có thông báo lỗi không (số chưa đăng ký, không cho phép tìm kiếm)
        5. Nhấn vào thông tin khách hàng

        Args:
            phone_number: Số điện thoại cần tìm
            timeout: Thời gian chờ tối đa (milliseconds)

        Returns:
            tuple: (success: bool, error_message: str or None)
                - (True, None) nếu thành công
                - (False, "not_registered") nếu số chưa đăng ký
                - (False, "not_found") nếu không tìm thấy
                - (False, error_msg) nếu lỗi khác
        """
        try:
            logger.info(f"🔍 Đang tìm kiếm: {phone_number}")

            # Bước 1: Tìm ô search (id="contact-search-input")
            search_selectors = [
                "input#contact-search-input",  # Selector chính xác từ HTML
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
                return (False, "search_box_not_found")

            # Bước 2: Nhập số điện thoại
            logger.info(f"📝 Nhập số điện thoại: {phone_number}")
            search_box.click()
            time.sleep(random.uniform(0.2, 0.4))
            search_box.fill("")  # Clear
            time.sleep(random.uniform(0.2, 0.4))
            search_box.type(phone_number, delay=100)

            # Bước 3: Đợi thông tin khách hàng hiện lên
            logger.info("⏳ Đợi thông tin khách hàng hiện lên...")
            time.sleep(random.uniform(1.5, 2.5))  # Chờ kết quả tìm kiếm

            # Bước 4: Kiểm tra có thông báo lỗi không
            # Selector cho thông báo "Số điện thoại chưa đăng ký tài khoản hoặc không cho phép tìm kiếm"
            error_selectors = [
                'span[data-translate-inner="STR_UNVALID_SEARCH_NUM_PHONE"]',
                'i.fa.fa-outline-call-info',
            ]

            for error_selector in error_selectors:
                try:
                    error_element = self.page.wait_for_selector(error_selector, timeout=2000, state="visible")
                    if error_element:
                        logger.warning(f"⚠️ Số điện thoại {phone_number} chưa đăng ký hoặc không cho phép tìm kiếm")
                        return (False, "not_registered")
                except PlaywrightTimeoutError:
                    continue

            # Bước 5: Tìm và click vào kết quả đầu tiên (thông tin khách hàng)
            # Sử dụng selector từ HTML: div.conv-item với class chứa số điện thoại
            result_selectors = [
                # Selector chính xác từ HTML
                'div.conv-item.conv-rel',
                'div[class*="conv-item"][class*="lv-2"]',
                # Fallback selectors
                "div[class*='search-result'] div[class*='item']:first-child",
                "div[class*='result'] div[class*='conv-item']:first-child",
                "div[class*='contact-item']:first-child",
                # Selector tìm theo text số điện thoại
                f'span.txt-highlight:has-text("{phone_number}")',
            ]

            result_found = False
            for selector in result_selectors:
                try:
                    result = self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    if result:
                        logger.info(f"✓ Tìm thấy thông tin khách hàng: {selector}")

                        # Nhấn vào thông tin khách hàng
                        result.click()
                        logger.info("✓ Đã nhấn vào thông tin khách hàng")
                        time.sleep(random.uniform(0.8, 1.5))
                        result_found = True
                        break
                except PlaywrightTimeoutError:
                    continue

            if not result_found:
                logger.warning(f"⚠️ Không tìm thấy kết quả cho: {phone_number}")
                return (False, "not_found")

            logger.info("✅ Đã mở chat thành công")
            return (True, None)

        except Exception as e:
            if is_browser_closed_error(e):
                raise BrowserClosedError("Trình duyệt Zalo đã bị đóng trong khi tìm kiếm") from e
            logger.error(f"❌ Lỗi khi tìm kiếm: {str(e)}")
            return (False, str(e))
    
    def send_message(self, message: str, timeout: int = 10000, image_path: str | None = None):
        """
        Gửi tin nhắn trong chat đang mở theo quy trình:
        1. Kiểm tra page còn mở không
        2. Focus ô nhập tin nhắn
        3. Nhập nội dung text (nếu có)
        4. Dán/chèn ảnh đính kèm (nếu có)
        5. Nhấn Enter để gửi

        Args:
            message: Nội dung tin nhắn
            timeout: Thời gian chờ tối đa (milliseconds)

        Returns:
            bool: True nếu thành công, False nếu không
        """
        try:
            logger.info("📝 Đang gửi tin nhắn...")
            text = str(message or "")
            has_text = bool(text.strip())
            has_image = bool(str(image_path or "").strip())

            # Kiểm tra page còn mở không
            if self.page.is_closed():
                logger.error("❌ Trang web đã bị đóng")
                return False

            input_box = self._focus_chat_input_box(timeout=timeout)
            if not input_box:
                logger.error("❌ Không tìm thấy ô nhập tin nhắn")
                return False

            if not has_text and not has_image:
                logger.warning("⚠️ Không có nội dung text hoặc ảnh để gửi")
                return False

            if has_text:
                logger.info(f"📍 Nhập nội dung: {text[:50]}...")
                try:
                    if self.page.is_closed():
                        logger.error("❌ Trang web đã bị đóng trong khi nhập tin nhắn")
                        return False

                    for char in text:
                        if self.page.is_closed():
                            logger.error("❌ Trang web đã bị đóng trong khi nhập tin nhắn")
                            return False

                        if char == '\n':
                            self.page.keyboard.down("Shift")
                            self.page.keyboard.press("Enter")
                            self.page.keyboard.up("Shift")
                            time.sleep(random.uniform(0.05, 0.1))
                        else:
                            self.page.keyboard.type(char, delay=30)
                except Exception as e:
                    if "closed" in str(e).lower():
                        logger.error("❌ Trang web đã bị đóng khi nhập tin nhắn")
                        return False
                    raise

                time.sleep(random.uniform(0.2, 0.45))

            if has_image:
                if not self._attach_image_to_chat(image_path=image_path, timeout=timeout):
                    logger.error("❌ Không thể đính kèm/gửi ảnh")
                    return False

            if has_image and has_text:
                self._activate_image_caption_mode(timeout=3500)

            # Chờ một chút sau khi soạn xong
            logger.info("⏳ Đã soạn xong tin nhắn, chuẩn bị gửi...")
            time.sleep(random.uniform(0.5, 1.0))

            # Kiểm tra page trước khi gửi
            if self.page.is_closed():
                logger.error("❌ Trang web đã bị đóng trước khi gửi")
                return False

            # Gửi bằng phím tắt Ctrl+Enter theo yêu cầu
            try:
                if has_image:
                    self._dismiss_edit_caption_tip(timeout=1800)
                self._log_send_diagnostics("before_send")

                # Khi có ảnh, UI khung chat thường bị đổi layout; thử click nút gửi trước
                if has_image and self._click_send_button_in_chat(timeout=2500):
                    if self._confirm_send_effect(has_image=True, timeout_ms=3200):
                        self._log_send_diagnostics("sent_by_button")
                        logger.info("✅ Đã gửi tin nhắn thành công (click nút gửi)")
                        return True
                    self._log_send_diagnostics("button_click_no_effect")

                # Refocus ngay trước khi gửi để keybinding context của chat input luôn active
                self._focus_chat_input_box(timeout=2500)

                logger.info("📤 Gửi tin nhắn bằng tổ hợp Ctrl giữ + Enter...")
                self.page.keyboard.down("Control")
                time.sleep(random.uniform(0.04, 0.08))
                self.page.keyboard.press("Enter")
                time.sleep(random.uniform(0.04, 0.08))
                self.page.keyboard.up("Control")

                if self._confirm_send_effect(has_image=has_image, timeout_ms=2600):
                    self._log_send_diagnostics("sent_by_ctrl_enter_1")
                    logger.info("✅ Đã gửi tin nhắn thành công")
                    return True
                self._log_send_diagnostics("ctrl_enter_1_no_effect")

                # Thử thêm lần 2 nếu UI bỏ lỡ lần đầu (không dùng Enter đơn lẻ để tránh xuống dòng)
                time.sleep(random.uniform(0.12, 0.2))
                self.page.keyboard.down("Control")
                time.sleep(random.uniform(0.03, 0.06))
                self.page.keyboard.press("Enter")
                self.page.keyboard.up("Control")

                if self._confirm_send_effect(has_image=has_image, timeout_ms=2600):
                    self._log_send_diagnostics("sent_by_ctrl_enter_2")
                    logger.info("✅ Đã gửi tin nhắn thành công")
                    return True
                self._log_send_diagnostics("ctrl_enter_2_no_effect")

                # Hướng xử lý bổ sung: đóng tooltip lại và click nút gửi lần cuối
                if has_image:
                    self._dismiss_edit_caption_tip(timeout=1200)
                    if self._click_send_button_in_chat(timeout=2200) and self._confirm_send_effect(has_image=True, timeout_ms=3000):
                        self._log_send_diagnostics("sent_by_button_retry")
                        logger.info("✅ Đã gửi tin nhắn thành công (button retry)")
                        return True
                    self._log_send_diagnostics("button_retry_no_effect")

                # Chờ tin nhắn được gửi đi
                time.sleep(random.uniform(1.0, 1.5))
                logger.error("❌ Không xác nhận được trạng thái đã gửi sau tất cả phương án")
                return False

            except Exception as e:
                if "closed" in str(e).lower():
                    logger.error("❌ Trang web đã bị đóng khi nhấn Enter")
                    return False
                raise

        except Exception as e:
            logger.error(f"❌ Lỗi khi gửi tin nhắn: {str(e)}")
            return False
    
    def check_friend_status(self, timeout: int = 5000):
        """
        Kiểm tra trạng thái bạn bè/người lạ trong cửa sổ chat đang mở

        Returns:
            str: 'friend' nếu là bạn bè, 'stranger' nếu là người lạ, 'unknown' nếu không xác định được
        """
        try:
            logger.info("🔍 Đang kiểm tra trạng thái bạn bè...")

            # Chờ một chút để trang load
            time.sleep(random.uniform(0.5, 1.0))

            # Kiểm tra các dấu hiệu của người lạ
            stranger_indicators = [
                'div:has-text("Người lạ")',
                'div:has-text("Stranger")',
                'div[class*="stranger"]',
                'span:has-text("Chưa phải bạn bè")',
            ]

            for selector in stranger_indicators:
                try:
                    element = self.page.wait_for_selector(selector, timeout=2000, state="visible")
                    if element:
                        logger.info("👤 Trạng thái: Người lạ")
                        return 'stranger'
                except PlaywrightTimeoutError:
                    continue

            # Nếu không phải người lạ, coi như là bạn bè
            logger.info("👥 Trạng thái: Bạn bè")
            return 'friend'

        except Exception as e:
            logger.warning(f"⚠️ Không xác định được trạng thái: {str(e)}")
            return 'unknown'

    def send_message_to_phone(self, phone_number: str, message: str, check_status: bool = False, image_path: str | None = None):
        """
        Tìm kiếm và gửi tin nhắn đến số điện thoại

        Args:
            phone_number: Số điện thoại
            message: Nội dung tin nhắn
            check_status: Có kiểm tra trạng thái bạn bè/người lạ không

        Returns:
            tuple: (success: bool, friend_status: str or None, error_msg: str or None)
                   - success: True nếu gửi thành công
                   - friend_status: 'friend', 'stranger', 'unknown' hoặc None
                   - error_msg: Thông báo lỗi nếu có ('not_registered', 'not_found', etc.)
        """
        try:
            # Bước 1: Tìm và mở chat
            search_success, error_msg = self.search_and_open_chat(phone_number)
            if not search_success:
                if is_browser_closed_error(error_msg):
                    raise BrowserClosedError("Trình duyệt Zalo đã bị đóng trong khi mở chat")
                # Trả về lỗi cụ thể
                return False, None, error_msg

            # Bước 2: Kiểm tra trạng thái (nếu cần)
            friend_status = None
            if check_status:
                friend_status = self.check_friend_status()

            # Bước 3: Gửi tin nhắn
            if not self.send_message(message, image_path=image_path):
                if self.page.is_closed():
                    raise BrowserClosedError("Trình duyệt Zalo đã bị đóng trong khi gửi tin nhắn")
                return False, friend_status, "send_failed"

            logger.info(f"✅ Đã gửi tin nhắn đến {phone_number}")
            return True, friend_status, None

        except BrowserClosedError:
            raise
        except Exception as e:
            logger.error(f"Lỗi khi gửi tin nhắn đến {phone_number}: {str(e)}")
            return False, None, str(e)
    
    def add_friend_by_phone(self, phone_number: str, contract_id: str = "", my_zalo_name: str = "", greeting_template: str = "", timeout: int = 10000):
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
            greeting_template: Template lời chào tùy chỉnh (có thể dùng {my_name}, {contract_id})
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

            # Kiểm tra chặn anti-spam của Zalo (search quá nhiều trong 1 giờ)
            rate_limit_msg = self._detect_add_friend_rate_limit(timeout=2500)
            if rate_limit_msg:
                logger.warning(f"🚫 Zalo giới hạn tìm kiếm/kết bạn: {rate_limit_msg}")
                raise ZaloRateLimitError(rate_limit_msg)

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
                # Một số trường hợp popup anti-spam xuất hiện trễ sau khi search
                late_rate_limit_msg = self._detect_add_friend_rate_limit(timeout=1000)
                if late_rate_limit_msg:
                    logger.warning(f"🚫 Zalo giới hạn tìm kiếm/kết bạn: {late_rate_limit_msg}")
                    raise ZaloRateLimitError(late_rate_limit_msg)

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

            # Bước 6: Kiểm tra trạng thái kết bạn
            logger.info("📍 Bước 6: Kiểm tra trạng thái kết bạn...")

            # Kiểm tra 1: Đã gửi lời mời trước đó (có nút "Hủy kết bạn")
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

            # Kiểm tra 2: Đã là bạn bè (chỉ có nút "Nhắn tin", không có "Kết bạn" và "Hủy kết bạn")
            try:
                chat_btn = self.page.wait_for_selector(
                    'div.truncate[data-translate-inner="STR_CHAT"]:has-text("Nhắn tin")',
                    timeout=2000,
                    state="visible"
                )
                if chat_btn:
                    # Kiểm tra xem có nút "Kết bạn" không
                    try:
                        add_friend_check = self.page.wait_for_selector(
                            'div.z--btn--v2:has-text("Kết bạn")',
                            timeout=1000,
                            state="visible"
                        )
                        # Nếu có nút "Kết bạn" thì chưa phải bạn bè, tiếp tục bình thường
                    except PlaywrightTimeoutError:
                        # Không có nút "Kết bạn" và chỉ có nút "Nhắn tin" => Đã là bạn bè
                        logger.info(f"✅ Đã là bạn bè với {phone_number}")
                        logger.info("ℹ️ Bỏ qua khách hàng này và chuyển sang người tiếp theo")
                        return "already_friend", display_name  # Trả về trạng thái đặc biệt
            except PlaywrightTimeoutError:
                pass  # Không có nút "Nhắn tin" - OK, tiếp tục

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

            # Sử dụng template tùy chỉnh nếu có, nếu không dùng mặc định
            if greeting_template:
                # Template đã được format sẵn từ app_ui.py, sử dụng trực tiếp
                greeting_message = greeting_template
            else:
                # Lời chào mặc định
                if contract_id:
                    greeting_message = f"Xin chào, mình là {my_zalo_name} bên automation marketing, vui lòng đồng ý kết bạn để được hỗ trợ hợp đồng {contract_id}"
                else:
                    greeting_message = f"Xin chào, mình là {my_zalo_name} bên automation marketing, vui lòng đồng ý kết bạn để được hỗ trợ"

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

        except ZaloRateLimitError:
            raise
        except Exception as e:
            if is_browser_closed_error(e):
                raise BrowserClosedError("Trình duyệt Zalo đã bị đóng trong khi thêm bạn") from e
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
                          is_paused_func=None, is_stop_func=None, my_name: str = "", check_friend_status: bool = True,
                          attachment_path: str | None = None, row_callback=None):
        """
        Gửi tin nhắn hàng loạt theo quy trình:
        1. Tìm kiếm số điện thoại
        2. Đợi thông tin khách hàng hiện lên
        3. Nhấn vào thông tin khách hàng
        4. Kiểm tra trạng thái bạn bè/người lạ (để đối chiếu)
        5. Gửi tin nhắn (cho cả bạn bè và người lạ)

        Args:
            customer_list: Danh sách khách hàng (list of dict)
            template: Template tin nhắn với biến {name}, {phone}, etc.
            callback: Hàm callback để báo tiến trình
            delay: Thời gian chờ giữa các tin nhắn (giây)
            is_paused_func: Hàm kiểm tra trạng thái tạm dừng (trả về True/False)
            is_stop_func: Hàm kiểm tra dừng hẳn (trả về True/False)
            my_name: Tên tài khoản Zalo của người gửi (cho biến {my_name} trong template)
            check_friend_status: Có kiểm tra và ghi nhận trạng thái bạn bè/người lạ không

        Returns:
            dict: Kết quả {success: int, failed: int, errors: list, details: list}
        """
        result = {"success": 0, "failed": 0, "errors": [], "details": []}

        for idx, customer in enumerate(customer_list, 1):
            # Kiểm tra dừng hẳn
            if is_stop_func and is_stop_func():
                if callback:
                    callback("🛑 Đã nhận lệnh dừng, thoát vòng gửi tin nhắn.")
                break

            # Kiểm tra tạm dừng
            if is_paused_func:
                while is_paused_func() and not (is_stop_func and is_stop_func()):
                    time.sleep(random.uniform(0.4, 0.6))

            if is_stop_func and is_stop_func():
                if callback:
                    callback("🛑 Đã nhận lệnh dừng, thoát vòng gửi tin nhắn.")
                break

            try:
                gender_pronoun = to_gender_pronoun(customer.get('gender', ''))
                product_value = customer.get('product') or customer.get('products_joined') or customer.get('san_pham') or ''

                # Format tin nhắn
                message = template.format(
                    name=customer.get('name', ''),
                    my_name=my_name,
                    phone=customer.get('phone', ''),
                    address=customer.get('address', ''),
                    cccd=customer.get('cccd', ''),
                    dob=customer.get('dob', ''),
                    contract_id=customer.get('contract_id', ''),
                    gender=gender_pronoun,  # Sử dụng anh/chị thay vì Nam/Nữ
                    product=product_value,
                    san_pham=product_value,
                )

                phone = customer.get('phone', '').strip()
                name = customer.get('name', 'N/A')

                if not phone:
                    if callback:
                        callback(f"⚠️ [{idx}/{len(customer_list)}] Bỏ qua: {name} (không có SĐT)")
                    result['failed'] += 1
                    row_res = {
                        'phone': phone,
                        'name': name,
                        'status': 'no_phone',
                        'friend_status': None
                    }
                    result['details'].append(row_res)
                    if row_callback:
                        row_callback(row_res)
                    continue

                if callback:
                    callback(f"📤 [{idx}/{len(customer_list)}] Đang gửi đến: {name} ({phone})")

                # Gửi tin nhắn với kiểm tra trạng thái
                success, friend_status, error_msg = self.send_message_to_phone(
                    phone,
                    message,
                    check_status=check_friend_status,
                    image_path=attachment_path,
                )

                if is_browser_closed_error(error_msg):
                    raise BrowserClosedError("Trình duyệt Zalo đã bị đóng trong khi gửi tin nhắn")

                if success:
                    result['success'] += 1
                    status_text = ""
                    if friend_status == 'friend':
                        status_text = " [Bạn bè]"
                    elif friend_status == 'stranger':
                        status_text = " [Người lạ]"

                    if callback:
                        callback(f"✅ [{idx}/{len(customer_list)}] Thành công: {phone}{status_text}")
                    row_res = {
                        'phone': phone,
                        'name': name,
                        'status': 'success',
                        'friend_status': friend_status
                    }
                    result['details'].append(row_res)
                    if row_callback:
                        row_callback(row_res)
                else:
                    result['failed'] += 1

                    # Xử lý thông báo lỗi cụ thể
                    if error_msg == 'not_registered':
                        error_text = "Số điện thoại chưa đăng ký hoặc không cho phép tìm kiếm"
                        if callback:
                            callback(f"⚠️ [{idx}/{len(customer_list)}] {phone}: {error_text}")
                        result['errors'].append(f"{phone}: {error_text}")
                        row_res = {
                            'phone': phone,
                            'name': name,
                            'status': 'not_registered',
                            'friend_status': None
                        }
                        result['details'].append(row_res)
                        if row_callback:
                            row_callback(row_res)
                    elif error_msg == 'not_found':
                        error_text = "Không tìm thấy kết quả"
                        if callback:
                            callback(f"⚠️ [{idx}/{len(customer_list)}] {phone}: {error_text}")
                        result['errors'].append(f"{phone}: {error_text}")
                        row_res = {
                            'phone': phone,
                            'name': name,
                            'status': 'not_found',
                            'friend_status': None
                        }
                        result['details'].append(row_res)
                        if row_callback:
                            row_callback(row_res)
                    else:
                        error_text = error_msg or "Không thể gửi tin nhắn"
                        if callback:
                            callback(f"❌ [{idx}/{len(customer_list)}] Thất bại: {phone} - {error_text}")
                        result['errors'].append(f"{phone}: {error_text}")
                        row_res = {
                            'phone': phone,
                            'name': name,
                            'status': 'failed',
                            'friend_status': friend_status
                        }
                        result['details'].append(row_res)
                        if row_callback:
                            row_callback(row_res)

                # Delay giữa các tin nhắn (thêm random vào delay)
                if idx < len(customer_list):
                    # Thêm biến động ±20% vào delay
                    random_delay = delay * random.uniform(0.8, 1.2)
                    time.sleep(random_delay)

            except Exception as e:
                error_str = str(e)
                if is_browser_closed_error(e):
                    if callback:
                        callback("🛑 Trình duyệt đã bị đóng, dừng toàn bộ tác vụ gửi tin nhắn.")
                    raise BrowserClosedError("Trình duyệt Zalo đã bị đóng trong khi gửi tin nhắn") from e
                result['failed'] += 1
                result['errors'].append(f"{customer.get('phone', 'N/A')}: {error_str}")
                if callback:
                    callback(f"❌ [{idx}/{len(customer_list)}] Lỗi: {error_str}")
                result['details'].append({
                    'phone': customer.get('phone', ''),
                    'name': customer.get('name', 'N/A'),
                    'status': 'error',
                    'friend_status': None
                })
        return result

