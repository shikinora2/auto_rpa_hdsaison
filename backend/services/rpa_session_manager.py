"""
RPA Session Manager
Quản lý session đăng nhập HPO với persistent browser context

⚠️ QUAN TRỌNG: Sử dụng sync_playwright trong thread pool executor thay vì async_playwright.
Lý do: async_playwright dùng asyncio.create_subprocess_exec() nội bộ, trên Windows với
SelectorEventLoop (mặc định của uvicorn) sẽ raise NotImplementedError.
sync_playwright chạy trong thread pool không phụ thuộc vào event loop type.
"""
import os
import asyncio
import shutil
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright

from config.settings import APP_DATA_DIR, SESSION_CACHE_TTL_SECONDS

# Thư mục lưu session RPA theo user
RPA_SESSION_ROOT_DIR = APP_DATA_DIR / "rpa_sessions"

# URLs
LOGIN_URL = "https://hpo.hdsaison.com.vn/login"
DASHBOARD_URL = "https://hpo.hdsaison.com.vn/dashboard"

# Selectors
USERNAME_SELECTOR = "[formcontrolname='username']"
PASSWORD_SELECTOR = "[formcontrolname='password']"
LOGIN_BUTTON_SELECTOR = "text=Đăng nhập"

# Thread pool riêng cho Playwright operations (max 1 thread vì persistent context)
_playwright_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rpa_playwright")


class RPASessionManager:
    """Quản lý phiên đăng nhập RPA với persistent context"""

    def __init__(self, user_id: int | str):
        self.user_id = str(user_id)
        self.session_dir = RPA_SESSION_ROOT_DIR / f"user_{self.user_id}"
        self.session_info_file = self.session_dir / "session_info.json"
        self.is_logged_in = False
        self._lock = asyncio.Lock()
        self._load_cached_login_state()

    def _ensure_session_dir(self):
        """Đảm bảo thư mục session tồn tại"""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        return str(self.session_dir)

    def _read_session_info(self) -> dict:
        try:
            if not self.session_info_file.exists():
                return {}
            with open(self.session_info_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_session_info(self, info: dict):
        try:
            self._ensure_session_dir()
            with open(self.session_info_file, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _is_cache_active(self, session_info: dict) -> bool:
        if not session_info:
            return False
        if session_info.get("status") != "active":
            return False
        expires_at_ts = float(session_info.get("expires_at_ts") or 0)
        if expires_at_ts <= 0:
            return False
        return time.time() < expires_at_ts

    @staticmethod
    def _normalize_hpo_username(username: str | None) -> str:
        return str(username or "").strip().lower()

    def _get_cached_hpo_username(self) -> str:
        session_info = self._read_session_info()
        return self._normalize_hpo_username(session_info.get("hpo_username"))

    def _set_cache_active(self, hpo_username: str | None = None):
        now_ts = time.time()
        current_info = self._read_session_info()
        to_save = {
            "status": "active",
            "last_login_ts": now_ts,
            "expires_at_ts": now_ts + SESSION_CACHE_TTL_SECONDS,
            "ttl_seconds": SESSION_CACHE_TTL_SECONDS,
        }

        # Giữ hpo_username hiện có nếu không truyền vào (hữu ích cho đường check session)
        normalized_username = self._normalize_hpo_username(hpo_username)
        if normalized_username:
            to_save["hpo_username"] = normalized_username
        elif self._normalize_hpo_username(current_info.get("hpo_username")):
            to_save["hpo_username"] = self._normalize_hpo_username(current_info.get("hpo_username"))

        self._write_session_info(to_save)

    def _set_cache_inactive(self, reason: str = "inactive", hpo_username: str | None = None):
        current_info = self._read_session_info()
        to_save = {
            "status": reason,
            "expires_at_ts": 0,
            "ttl_seconds": SESSION_CACHE_TTL_SECONDS,
        }

        normalized_username = self._normalize_hpo_username(hpo_username)
        if normalized_username:
            to_save["hpo_username"] = normalized_username
        elif self._normalize_hpo_username(current_info.get("hpo_username")):
            to_save["hpo_username"] = self._normalize_hpo_username(current_info.get("hpo_username"))

        self._write_session_info(to_save)

    def _load_cached_login_state(self):
        try:
            if not self.session_dir.exists():
                self.is_logged_in = False
                return
            session_info = self._read_session_info()
            self.is_logged_in = self._is_cache_active(session_info)
        except Exception:
            self.is_logged_in = False

    def _clear_stale_session(self):
        """
        Xóa session dir khi phát hiện session hết hạn (stale).
        Lần đăng nhập tiếp theo sẽ bắt đầu fresh — không load lại session hỏng.
        """
        try:
            if self.session_dir.exists():
                shutil.rmtree(self.session_dir, ignore_errors=True)
                print(f"[RPA][user={self.user_id}] 🗑️  Đã xóa session cũ bị hết hạn: {self.session_dir}")
                self.is_logged_in = False
                self._set_cache_inactive("expired")
        except Exception as e:
            print(f"[RPA] Không thể xóa session cũ: {e}")

    def _log_from_thread(self, loop, callback, message):
        """
        Log message an toàn từ trong thread (không có running loop).
        Dùng run_coroutine_threadsafe để schedule async callback vào event loop.
        """
        print(f"[RPA] {message}")
        if callback and loop:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.run_coroutine_threadsafe(callback(message), loop)
                else:
                    callback(message)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # Sync methods (chạy trong thread pool, không dùng asyncio)
    # ─────────────────────────────────────────────────────────────────────────

    def _check_session_valid_sync(self, loop, status_callback) -> bool:
        """Kiểm tra session bằng sync Playwright (chạy trong thread)"""
        context = None
        try:
            session_dir = self._ensure_session_dir()
            self._log_from_thread(loop, status_callback, "Đang kiểm tra phiên đăng nhập...")

            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=session_dir,
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )
                page = context.pages[0] if context.pages else context.new_page()

                page.goto(DASHBOARD_URL, timeout=15000)
                page.wait_for_load_state('networkidle', timeout=10000)

                current_url = page.url
                if DASHBOARD_URL in current_url or 'dashboard' in current_url.lower():
                    self._log_from_thread(loop, status_callback, "✅ Session còn hợp lệ! Đã đăng nhập sẵn.")
                    self._set_cache_active()
                    context.close()
                    return True
                else:
                    # Session đã hết hạn (bị văng về trang Login)
                    self._log_from_thread(
                        loop, status_callback,
                        "⚠ Session hết hạn (bị chuyển về trang login). Đang xóa session cũ để force re-login..."
                    )
                    context.close()
                    # Xóa session dir cũ — tránh load lại session hỏng vòng vòng
                    self._clear_stale_session()
                    return False

        except Exception as e:
            self._log_from_thread(loop, status_callback, f"⚠ Lỗi kiểm tra session: {e}")
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            return False

    def _login_sync(self, username: str, password: str, headless: bool, loop, status_callback) -> bool:
        """Đăng nhập bằng sync Playwright (chạy trong thread)"""
        context = None
        try:
            session_dir = self._ensure_session_dir()
            normalized_input_username = self._normalize_hpo_username(username)
            self._log_from_thread(loop, status_callback, "Đang mở trình duyệt...")

            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=session_dir,
                    headless=headless,
                    slow_mo=0 if headless else 250,
                    args=['--disable-blink-features=AutomationControlled']
                )
                page = context.pages[0] if context.pages else context.new_page()

                # Kiểm tra session cũ còn hợp lệ không
                self._log_from_thread(loop, status_callback, "Đang kiểm tra session cũ...")

                cached_username = self._get_cached_hpo_username()
                if cached_username and cached_username != normalized_input_username:
                    self._log_from_thread(
                        loop,
                        status_callback,
                        f"⚠ Phát hiện đổi tài khoản HPO ({cached_username} -> {normalized_input_username}), xóa session cũ để đăng nhập lại..."
                    )
                    try:
                        context.close()
                    except Exception:
                        pass
                    self._clear_stale_session()

                    # Re-open context sau khi xóa session để login tài khoản mới
                    context = playwright.chromium.launch_persistent_context(
                        user_data_dir=session_dir,
                        headless=headless,
                        slow_mo=0 if headless else 250,
                        args=['--disable-blink-features=AutomationControlled']
                    )
                    page = context.pages[0] if context.pages else context.new_page()

                try:
                    page.goto(DASHBOARD_URL, timeout=15000)
                    page.wait_for_load_state('networkidle', timeout=10000)
                    current_url = page.url
                    can_reuse_existing_session = (
                        (DASHBOARD_URL in current_url or 'dashboard' in current_url.lower())
                        and cached_username
                        and cached_username == normalized_input_username
                    )

                    if can_reuse_existing_session:
                        self._log_from_thread(loop, status_callback, "✅ Đã có session hợp lệ! Không cần đăng nhập lại.")
                        self._set_cache_active(hpo_username=username)
                        context.close()
                        return True
                except Exception as e:
                    self._log_from_thread(loop, status_callback, f"Lỗi check session cũ (không nghiêm trọng): {e}")

                # Thực hiện login mới
                self._log_from_thread(loop, status_callback, "Đang mở trang đăng nhập...")
                page.goto(LOGIN_URL)
                page.wait_for_load_state('networkidle', timeout=10000)

                self._log_from_thread(loop, status_callback, "Đang điền thông tin đăng nhập...")
                page.fill(USERNAME_SELECTOR, username)
                page.fill(PASSWORD_SELECTOR, password)

                self._log_from_thread(loop, status_callback, "Đang nhấn nút đăng nhập...")
                page.click(LOGIN_BUTTON_SELECTOR)

                self._log_from_thread(loop, status_callback, "Đang chờ chuyển đến Dashboard...")
                page.wait_for_url("**/dashboard**", timeout=30000)

                self._log_from_thread(loop, status_callback, "✅ Đăng nhập thành công! Session đã được lưu.")
                self._set_cache_active(hpo_username=username)
                context.close()
                return True

        except Exception as e:
            import traceback
            print(f"=== LOGIN ERROR ===")
            print(f"Error: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            print(f"===================")
            self._log_from_thread(loop, status_callback, f"❌ Lỗi đăng nhập: {e}")
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Async public API (gọi sync methods qua run_in_executor)
    # ─────────────────────────────────────────────────────────────────────────

    async def check_session_valid(self, status_callback=None) -> bool:
        """
        Kiểm tra session còn hợp lệ không.
        Chạy sync Playwright trong thread pool để tránh vấn đề event loop trên Windows.
        """
        async with self._lock:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                _playwright_executor,
                lambda: self._check_session_valid_sync(loop, status_callback)
            )
            self.is_logged_in = result
            if result:
                self._set_cache_active()
            else:
                self._set_cache_inactive("expired")
            return result

    def get_cached_session_valid(self) -> bool:
        """Fast path: đọc cache TTL từ disk, không mở browser."""
        session_info = self._read_session_info()
        valid = self._is_cache_active(session_info)
        self.is_logged_in = valid
        return valid

    async def login(self, username: str, password: str, headless: bool = False, status_callback=None) -> bool:
        """
        Đăng nhập HPO với persistent context.
        Chạy sync Playwright trong thread pool để tránh vấn đề event loop trên Windows.
        """
        async with self._lock:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                _playwright_executor,
                lambda: self._login_sync(username, password, headless, loop, status_callback)
            )
            self.is_logged_in = result
            if result:
                self._set_cache_active()
            else:
                self._set_cache_inactive("inactive")
            return result

    async def logout(self, status_callback=None) -> bool:
        """Đăng xuất và xóa session"""
        async with self._lock:
            try:
                if status_callback:
                    if asyncio.iscoroutinefunction(status_callback):
                        await status_callback("Đang xóa session HPO...")
                    else:
                        status_callback("Đang xóa session HPO...")

                if self.session_dir.exists():
                    # Retry logic for Windows file locking
                    for _ in range(3):
                        try:
                            shutil.rmtree(self.session_dir, ignore_errors=False)
                            break
                        except Exception:
                            await asyncio.sleep(0.5)
                            shutil.rmtree(self.session_dir, ignore_errors=True)

                self.is_logged_in = False
                self._set_cache_inactive("logged_out")
                print("[RPA] ✅ Đã đăng xuất!")

                if status_callback:
                    if asyncio.iscoroutinefunction(status_callback):
                        await status_callback("✅ Đã đăng xuất!")
                    else:
                        status_callback("✅ Đã đăng xuất!")

                return True
            except Exception as e:
                import traceback
                print(f"[RPA] Lỗi logout: {e}")
                print(f"Logout Error Traceback: {traceback.format_exc()}")
                return False


# Per-user global instances
_rpa_session_manager_by_user: dict[str, RPASessionManager] = {}


def get_rpa_session_manager(user_id: int | str = "default") -> RPASessionManager:
    """Lấy RPA session manager theo user_id."""
    key = str(user_id)
    manager = _rpa_session_manager_by_user.get(key)
    if manager is None:
        manager = RPASessionManager(user_id=key)
        _rpa_session_manager_by_user[key] = manager
    return manager
