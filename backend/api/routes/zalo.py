"""
Zalo API Routes
API endpoints cho các tính năng Zalo automation
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
import asyncio
import concurrent.futures
import threading
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from datetime import datetime

from config.settings import APP_DATA_DIR, SESSION_CACHE_TTL_SECONDS
from api.websocket.connection_manager import manager, log_to_ws
from api.routes.config import load_config
from api.deps.auth import require_roles

# Thread pool cho việc chạy sync Playwright (max 1 vì persistent context)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

router = APIRouter(dependencies=[Depends(require_roles("admin", "user"))])

# Cache QR code theo user để FE có thể fetch ngay khi reload trang
_qr_cache_by_user: dict[int, dict] = {}
_QR_TTL = 600  # giây


def _is_zalo_login_task(task_name: str | None) -> bool:
    """Chuẩn hóa nhận diện task đăng nhập Zalo (hỗ trợ tên cũ và mới)."""
    return task_name in {"zalo_login", "login"}


def _cache_qr(user_id: int, qr_b64: str):
    _qr_cache_by_user[user_id] = {"qr_base64": qr_b64, "ts": time.time()}


def _get_cached_qr(user_id: int) -> str | None:
    entry = _qr_cache_by_user.get(user_id)
    if not entry:
        return None

    # Khi task login đang chạy, luôn giữ QR cache để FE không mất ảnh giữa chừng
    state = _snapshot_zalo_state()
    if state.get("is_running") and _is_zalo_login_task(state.get("current_task")):
        return entry["qr_base64"]

    if time.time() - entry["ts"] < _QR_TTL:
        return entry["qr_base64"]
    return None


def _clear_qr_cache(user_id: int | None = None):
    if user_id is None:
        _qr_cache_by_user.clear()
        return
    _qr_cache_by_user.pop(user_id, None)


def cleanup_expired_qr_cache() -> int:
    """Xóa các QR cache đã quá TTL; trả về số entry đã xóa."""
    state = _snapshot_zalo_state()
    if state.get("is_running") and _is_zalo_login_task(state.get("current_task")):
        return 0

    now_ts = time.time()
    stale_user_ids = [
        user_id
        for user_id, entry in _qr_cache_by_user.items()
        if now_ts - float(entry.get("ts") or 0) >= _QR_TTL
    ]
    for user_id in stale_user_ids:
        _qr_cache_by_user.pop(user_id, None)
    return len(stale_user_ids)

# Global state cho Zalo — KHÔNG lưu playwright/context/page ở đây.
# Mỗi task (login, send_messages, add_friends) tự mở/đóng browser riêng.
# Session được lưu trên disk (persistent context), không cần giữ browser sống mãi.
zalo_state = {
    "is_running": False,
    "is_paused": False,
    "stop_requested": False,
    "current_task": None,
    "session_active": False,   # True nếu đã login và session disk còn hợp lệ
    "zalo_name": "",
}

_zalo_state_lock = threading.Lock()


def _snapshot_zalo_state() -> dict:
    with _zalo_state_lock:
        return {
            "is_running": zalo_state["is_running"],
            "is_paused": zalo_state["is_paused"],
            "stop_requested": zalo_state["stop_requested"],
            "current_task": zalo_state["current_task"],
            "session_active": zalo_state["session_active"],
            "zalo_name": zalo_state["zalo_name"],
        }


def _start_zalo_task(task_name: str):
    with _zalo_state_lock:
        if zalo_state["is_running"]:
            raise HTTPException(status_code=400, detail="Another Zalo task is running")
        zalo_state["is_running"] = True
        zalo_state["is_paused"] = False
        zalo_state["stop_requested"] = False
        zalo_state["current_task"] = task_name


def _finish_zalo_task():
    with _zalo_state_lock:
        zalo_state["is_running"] = False
        zalo_state["is_paused"] = False
        zalo_state["current_task"] = None



class SendMessageRequest(BaseModel):
    """Schema cho gửi tin nhắn"""
    customers: List[dict]  # List of {phone, name, contract_id, ...}
    message_template: str
    check_friend_status: Optional[bool] = True
    attachment_filename: Optional[str] = None


class AddFriendRequest(BaseModel):
    """Schema cho kết bạn"""
    customers: List[dict]
    greeting_template: Optional[str] = Field(default="", max_length=150)


class AddFriendAndSendRequest(BaseModel):
    """Schema cho kết bạn rồi gửi tin nhắn"""
    customers: List[dict]
    greeting_template: Optional[str] = Field(default="", max_length=150)
    message_template: str
    attachment_filename: Optional[str] = None


_ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _resolve_uploaded_image_path(attachment_filename: Optional[str]) -> Optional[str]:
    """Resolve safe absolute path for an uploaded image in app_data/uploads."""
    raw_name = str(attachment_filename or "").strip()
    if not raw_name:
        return None

    safe_name = Path(raw_name).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Tên file ảnh đính kèm không hợp lệ")

    ext = Path(safe_name).suffix.lower()
    if ext not in _ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Ảnh đính kèm phải là PNG/JPG/JPEG/WEBP/GIF")

    upload_dir = APP_DATA_DIR / "uploads"
    resolved = (upload_dir / safe_name).resolve()
    if resolved.parent != upload_dir.resolve():
        raise HTTPException(status_code=400, detail="Đường dẫn ảnh đính kèm không hợp lệ")

    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=400, detail="Không tìm thấy ảnh đính kèm trên server")

    return str(resolved)


# ============== Session Helpers ==============

def get_session_manager(user_id: int):
    """Tạo ZaloSessionManager với thư mục session theo user."""
    from logic.zalo_logic import ZaloSessionManager
    session_dir = APP_DATA_DIR / f"zalo_session_{user_id}"
    return ZaloSessionManager(session_dir=str(session_dir))


def persist_session_snapshot(session_manager, existing_info: Optional[dict] = None, zalo_name: str = "") -> dict:
    """Đảm bảo metadata session tồn tại mỗi khi phát hiện session đang active."""
    session_info = dict(existing_info or {})
    now_ts = time.time()
    session_info["status"] = "active"
    session_info["last_login"] = time.strftime('%Y-%m-%d %H:%M:%S')
    session_info["last_login_ts"] = now_ts
    session_info["expires_at_ts"] = now_ts + SESSION_CACHE_TTL_SECONDS
    session_info["ttl_seconds"] = SESSION_CACHE_TTL_SECONDS
    if zalo_name:
        session_info["zalo_name"] = zalo_name
    session_manager.save_session_info(session_info)
    return session_info


def _resolve_session_expires_at_ts(session_info: dict) -> float:
    expires_at_ts = session_info.get("expires_at_ts")
    if expires_at_ts is not None:
        try:
            return float(expires_at_ts)
        except Exception:
            pass

    last_login_ts = session_info.get("last_login_ts")
    if last_login_ts is not None:
        try:
            return float(last_login_ts) + SESSION_CACHE_TTL_SECONDS
        except Exception:
            pass

    # Legacy migration: last_login dạng string '%Y-%m-%d %H:%M:%S'
    legacy_last_login = session_info.get("last_login")
    if isinstance(legacy_last_login, str) and legacy_last_login.strip():
        try:
            dt = datetime.strptime(legacy_last_login, "%Y-%m-%d %H:%M:%S")
            return dt.timestamp() + SESSION_CACHE_TTL_SECONDS
        except Exception:
            pass

    return 0.0


def _is_session_cache_active(session_info: dict) -> bool:
    if session_info.get("status") != "active":
        return False
    expires_at_ts = _resolve_session_expires_at_ts(session_info)
    return expires_at_ts > 0 and time.time() < expires_at_ts


def sync_session_state(user_id: int) -> dict:
    """Đồng bộ session Zalo từ dữ liệu lưu trên disk thay vì chỉ dựa vào RAM."""
    session_manager = get_session_manager(user_id)
    session_info = session_manager.get_session_info() or {}
    has_session = session_manager.has_session()
    session_active = has_session and _is_session_cache_active(session_info)

    if has_session and session_info.get("status") == "active" and not session_active:
        session_info["status"] = "expired"
        session_info["expires_at_ts"] = 0
        session_info["ttl_seconds"] = SESSION_CACHE_TTL_SECONDS
        session_manager.save_session_info(session_info)

    zalo_name = session_info.get("zalo_name", "")

    return {
        "session_manager": session_manager,
        "session_info": session_info,
        "session_active": session_active,
        "zalo_name": zalo_name,
    }


async def resolve_session_state(user_id: int, verify: bool = False) -> dict:
    """Lấy trạng thái session Zalo và có thể xác thực session thật bằng browser headless."""
    session_state = sync_session_state(user_id)

    if not verify:
        return session_state

    session_manager = session_state["session_manager"]
    session_info = dict(session_state["session_info"] or {})
    has_session = session_manager.has_session()

    # Tránh đụng session directory khi bất kỳ task nào đang chạy browser trên cùng account.
    # Nếu đang login (QR), send_messages, hay add_friends — không mở thêm browser verify
    # vì sẽ bị data race với persistent context đang hoạt động.
    if _snapshot_zalo_state()["is_running"]:
        return session_state

    if not has_session:
        session_info["status"] = "inactive"
        session_info["expires_at_ts"] = 0
        session_info["ttl_seconds"] = SESSION_CACHE_TTL_SECONDS
        session_manager.save_session_info(session_info)
        return sync_session_state(user_id)

    # Session đã biết là expired — không cần launch browser verify lại mỗi lần check.
    # Trạng thái chỉ thay đổi khi user login lại, lúc đó session_info được ghi lại.
    if session_info.get("status") == "expired":
        return session_state

    loop = asyncio.get_running_loop()

    def check_session_disk_state():
        success, p, context, page = session_manager.connect_headless_only()
        try:
            if context:
                context.close()
            if p:
                p.stop()
        except Exception:
            pass
        return success

    is_valid = await loop.run_in_executor(_executor, check_session_disk_state)

    if is_valid:
        persist_session_snapshot(
            session_manager,
            existing_info=session_info,
            zalo_name=session_info.get("zalo_name", "")
        )
    else:
        session_info["status"] = "expired"
        session_manager.save_session_info(session_info)

    return sync_session_state(user_id)


# ============== Session Management ==============

@router.get("/session")
async def get_session_status(verify: bool = False, current_user=Depends(require_roles("admin", "user"))):
    """Kiểm tra trạng thái session Zalo.
    - verify=False (mặc định): trả về trạng thái nhanh từ disk, không mở browser.
    - verify=True: mở headless browser để xác thực session thực tế (chậm hơn).
    """
    session_state = await resolve_session_state(current_user["id"], verify=verify)

    state = _snapshot_zalo_state()
    return {
        "is_active": session_state["session_active"],
        "is_running": state["is_running"],
        "current_task": state["current_task"],
        "zalo_name": session_state["zalo_name"],
    }


@router.post("/login")
async def login_zalo(background_tasks: BackgroundTasks, current_user=Depends(require_roles("admin", "user"))):
    """
    Mở trình duyệt để đăng nhập Zalo (quét QR)
    Browser sẽ mở ở chế độ headful để người dùng quét QR
    """
    # Mỗi lần yêu cầu đăng nhập mới phải xoá QR cũ để FE không hiển thị ảnh stale sau F5.
    _clear_qr_cache(current_user["id"])

    _start_zalo_task("zalo_login")
    
    background_tasks.add_task(run_zalo_login_task, current_user["id"])
    
    return {
        "status": "started",
        "message": "Đang khởi tạo đăng nhập Zalo chạy ngầm, vui lòng quét mã QR"
    }


async def run_zalo_login_task(user_id: int):
    """Background task để login Zalo.
    Chạy browser headless để lấy QR mà không hiển thị trang login.
    Sau khi login thành công: lưu session vào disk, đóng browser.
    Browser KHÔNG được giữ mở — các task automation sau dùng headless per-task.
    """
    try:
        await log_to_ws("Bắt đầu luồng đăng nhập Zalo chạy ngầm (không hiển thị trình duyệt)...", "info")
        await manager.broadcast_status("running", {"task": "zalo_login"})

        loop = asyncio.get_running_loop()

        def emit_step(message: str, level: str = "info"):
            try:
                asyncio.run_coroutine_threadsafe(log_to_ws(message, level), loop)
            except Exception:
                try:
                    print(f"[{level.upper()}] {message}")
                except Exception:
                    pass

        def on_login_detected():
            """Gọi ngay khi phát hiện avatar/icon sau QR"""
            zalo_state["session_active"] = True
            asyncio.run_coroutine_threadsafe(
                manager.broadcast_status("active", {"task": "zalo_session", "session_active": True}),
                loop
            )
            asyncio.run_coroutine_threadsafe(
                log_to_ws("✅ Đã phát hiện đăng nhập Zalo thành công!", "success"),
                loop
            )

        def broadcast_qr(qr_base64: str):
            _cache_qr(user_id, qr_base64)
            asyncio.run_coroutine_threadsafe(
                manager.broadcast_qr(qr_base64),
                loop
            )

        def do_login():
            from logic.zalo_automation import ZaloAutomation

            session_manager = get_session_manager(user_id)
            emit_step("[B1] Khởi tạo Playwright cho đăng nhập Zalo...", "info")

            # ── Mở browser ẨN để không hiển thị trang login ─────────────────
            p = sync_playwright().start()
            context = session_manager.create_persistent_context(p, headless=True)
            page = context.pages[0] if context.pages else context.new_page()
            emit_step("[B2] Đã tạo browser context headless thành công.", "success")

            # Xóa cookie cũ để buộc hiện QR mới
            emit_step("[B3] Xóa session/cookie cũ để yêu cầu QR mới...", "info")
            context.clear_cookies()
            try:
                page.goto("about:blank")
                page.evaluate("localStorage.clear(); sessionStorage.clear();")
            except Exception:
                pass

            emit_step("[B4] Điều hướng đến trang đăng nhập Zalo...", "info")
            try:
                page.goto("https://id.zalo.me/account?continue=https%3A%2F%2Fchat.zalo.me%2F", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass

            emit_step("[B5] Đang tìm và trích xuất QR từ DOM (không chụp full trang)...", "info")

            # Đợi QR canvas/img xuất hiện rồi broadcast
            qr_selectors = [
                "div.qrcode img",
                "div.qr-container img",
                "img[src*='data:image/png;base64']",
                "canvas#qrcode", 
                "canvas[class*='qrcode']", 
                "div[class*='qr'] canvas"
            ]

            def _extract_b64_from_element(el) -> str | None:
                try:
                    tag_name = (el.evaluate("e => (e.tagName || '').toLowerCase()") or "").strip()
                except Exception:
                    tag_name = ""

                # Ưu tiên lấy trực tiếp data URL để tránh lỗi screenshot trong headless
                if tag_name == "img":
                    try:
                        src = el.get_attribute("src") or ""
                        if src.startswith("data:image") and "," in src:
                            return src.split(",", 1)[1]
                    except Exception:
                        pass

                if tag_name == "canvas":
                    try:
                        data_url = el.evaluate("e => e.toDataURL('image/png')") or ""
                        if data_url.startswith("data:image") and "," in data_url:
                            return data_url.split(",", 1)[1]
                    except Exception:
                        pass

                # Fallback: screenshot element
                try:
                    qr_bytes = el.screenshot()
                    import base64
                    return base64.b64encode(qr_bytes).decode()
                except Exception:
                    return None

            def _try_capture_qr() -> bool:
                for selector in qr_selectors:
                    try:
                        el = page.query_selector(selector)
                        if not el:
                            continue
                        try:
                            page.evaluate(f"""
                                (function() {{
                                    var c = document.querySelector("{selector}");
                                    if (c) {{ c.style.width = '300px'; c.style.height = '300px'; }}
                                }})();
                            """)
                        except Exception:
                            pass
                        qr_b64 = _extract_b64_from_element(el)
                        if not qr_b64:
                            continue
                        broadcast_qr(qr_b64)
                        emit_step(f"[B5.1] Đã lấy QR thành công từ selector: {selector}", "success")
                        return True
                    except Exception:
                        continue

                # Fallback bổ sung: quét toàn bộ IMG có data URL trong DOM
                try:
                    dom_qr_b64 = page.evaluate("""
                        () => {
                            const img = document.querySelector("img[src^='data:image']");
                            if (!img) return null;
                            const src = img.getAttribute('src') || '';
                            if (!src.includes(',')) return null;
                            return src.split(',', 2)[1] || null;
                        }
                    """)
                    if dom_qr_b64:
                        broadcast_qr(dom_qr_b64)
                        emit_step("[B5.1] Đã lấy QR thành công từ fallback DOM image.", "success")
                        return True
                except Exception:
                    pass
                return False

            # Thử bắt QR nhanh trong tối đa 50s để đảm bảo tổng luồng dưới 1 phút
            first_qr_deadline = time.time() + 50
            first_qr_found = False
            qr_wait_tick = 0
            while time.time() < first_qr_deadline:
                if _try_capture_qr():
                    first_qr_found = True
                    break
                qr_wait_tick += 1
                if qr_wait_tick % 4 == 0:
                    try:
                        emit_step(f"[B5.wait] Đang chờ QR render... URL hiện tại: {page.url}", "info")
                    except Exception:
                        emit_step("[B5.wait] Đang chờ QR render...", "info")
                time.sleep(0.5)

            if not first_qr_found:
                emit_step("[B5.2] Không lấy được QR trong 50 giây đầu.", "warning")
                try:
                    context.close()
                    p.stop()
                except Exception:
                    pass
                try:
                    session_manager.delete_session()
                except Exception:
                    pass
                return False, ""

            # ── Chờ đăng nhập (polling URL mỗi 1.5s) ──────────────────────
            emit_step("[B6] Đã phát QR, bắt đầu chờ người dùng quét và xác nhận đăng nhập...", "info")
            import time as _time
            start = _time.time()
            max_wait = 60
            success_detected = False
            login_success_selectors = [
                "div.zavatar img",
                "i.fa.fa-Message_28_Filled",
                "div.mmi-icon-wr",
            ]

            def _is_logged_in_now() -> bool:
                try:
                    if "chat.zalo.me" not in page.url:
                        return False
                    for selector in login_success_selectors:
                        try:
                            if page.query_selector(selector):
                                return True
                        except Exception:
                            continue
                    return False
                except Exception:
                    return False

            while _time.time() - start < max_wait:
                if zalo_state.get("stop_requested"):
                    break
                try:
                    if _is_logged_in_now():
                        on_login_detected()
                        success_detected = True
                        emit_step("[B7] Phát hiện đăng nhập thành công sau khi quét QR.", "success")
                        break
                    # Refresh QR đều đặn nếu user chưa quét
                    elapsed = int(_time.time() - start)
                    if elapsed > 0 and elapsed % 3 == 0:
                        _try_capture_qr()
                    if elapsed > 0 and elapsed % 10 == 0:
                        emit_step(f"[B6.{elapsed // 10}] Vẫn đang chờ quét QR... ({elapsed}s/{max_wait}s)", "info")

                    # Làm mới trang login định kỳ để tránh QR bị treo/expired mà không render lại
                    if elapsed > 0 and elapsed % 45 == 0 and "chat.zalo.me" not in page.url:
                        emit_step("[B6.refresh] Làm mới trang login để lấy QR mới do QR cũ có thể hết hạn...", "warning")
                        try:
                            page.goto("https://id.zalo.me/account?continue=https%3A%2F%2Fchat.zalo.me%2F", wait_until="domcontentloaded", timeout=30000)
                            _try_capture_qr()
                        except Exception:
                            pass
                except Exception:
                    pass
                _time.sleep(1.5)

            if not success_detected and _is_logged_in_now():
                on_login_detected()
                success_detected = True

            if not success_detected:
                emit_step("[B8] Hết thời gian chờ quét QR (60s), kết thúc phiên login.", "error")
                try:
                    context.close()
                    p.stop()
                except Exception:
                    pass
                try:
                    session_manager.delete_session()
                except Exception:
                    pass
                return False, ""

            # ── Lấy tên Zalo, lưu session, đóng browser ───────────────────
            emit_step("[B9] Đang lấy thông tin tài khoản và lưu session...", "info")
            zalo_name = ""
            try:
                automation = ZaloAutomation(page)
                zalo_name = automation.get_my_zalo_name(session_manager)
            except Exception as name_err:
                emit_step(f"[B9.warn] Không lấy được tên Zalo: {name_err}", "warning")

            # Luôn persist session active sau khi đã xác nhận login thành công,
            # kể cả khi không lấy được tên tài khoản.
            persist_session_snapshot(
                session_manager,
                session_manager.get_session_info() or {},
                zalo_name=zalo_name,
            )

            try:
                context.close()
                p.stop()
            except Exception:
                pass

            emit_step("[B10] Hoàn tất đăng nhập nền, đã đóng browser headless.", "success")

            return True, zalo_name

        success, zalo_name = await loop.run_in_executor(_executor, do_login)

        if success:
            zalo_state["session_active"] = True
            zalo_state["zalo_name"] = zalo_name
            await log_to_ws(f"Đăng nhập Zalo thành công (chạy ngầm)! Tài khoản: {zalo_name or '(không xác định)'}", "success")
            await manager.broadcast_status("completed", {"task": "zalo_login", "success": True})
        else:
            zalo_state["session_active"] = False
            zalo_state["zalo_name"] = ""
            await log_to_ws("Đăng nhập thất bại hoặc timeout (không lấy được QR / chưa quét trong 60s)", "error")
            await manager.broadcast_status("error", {"task": "zalo_login"})

    except Exception as e:
        await log_to_ws(f"Lỗi: {str(e)}", "error")
        await manager.broadcast_status("error", {"task": "zalo_login", "error": str(e)})
    finally:
        _finish_zalo_task()
        state = _snapshot_zalo_state()
        await manager.broadcast_status("session_state", {
            "task": "zalo_session",
            "session_active": state["session_active"],
            "zalo_name": state["zalo_name"],
        })


@router.post("/logout")
async def logout_zalo(current_user=Depends(require_roles("admin", "user"))):
    """Xóa session Zalo (logout).
    Browser không còn tồn tại trong memory — chỉ cần reset state và xóa session disk.
    """
    try:
        # Xóa session trên disk để buộc QR lần sau
        session_manager = get_session_manager(current_user["id"])
        session_manager.delete_session()
    except Exception:
        pass

    zalo_state["session_active"] = False
    zalo_state["zalo_name"] = ""
    _clear_qr_cache(current_user["id"])
    return {"status": "success", "message": "Logged out"}


@router.get("/qr")
async def get_qr_image(current_user=Depends(require_roles("admin", "user"))):
    """Trả về QR code đã cache (nếu còn hợp lệ) để FE hiện ngay khi reload trang.
    FE nên gọi endpoint này sau khi xác nhận session chưa đăng nhập.
    """
    qr_b64 = _get_cached_qr(current_user["id"])
    state = _snapshot_zalo_state()
    return {
        "qr_base64": qr_b64,
        "is_running": state["is_running"],
        "current_task": state["current_task"],
    }


# ============== Automation ==============

@router.post("/send-messages")
async def send_messages(request: SendMessageRequest, background_tasks: BackgroundTasks, current_user=Depends(require_roles("admin", "user"))):
    """Gửi tin nhắn hàng loạt"""
    session_state = await resolve_session_state(current_user["id"], verify=False)
    if not session_state["session_active"]:
        raise HTTPException(status_code=400, detail="Please login to Zalo first")
    
    if not request.customers:
        raise HTTPException(status_code=400, detail="Customer list is empty")

    valid_customers = [customer for customer in request.customers if str(customer.get("phone", "")).strip()]
    if not valid_customers:
        raise HTTPException(status_code=400, detail="Danh sách hiện tại không còn khách hàng nào có số điện thoại hợp lệ")

    attachment_path = _resolve_uploaded_image_path(request.attachment_filename)
    
    _start_zalo_task("send_messages")
    
    background_tasks.add_task(
        run_send_messages_task,
        current_user["id"],
        valid_customers,
        request.message_template,
        request.check_friend_status,
        attachment_path,
    )
    
    return {
        "status": "started",
        "message": f"Bắt đầu gửi tin nhắn cho {len(valid_customers)} khách hàng"
    }


async def run_send_messages_task(user_id, customers, message_template, check_friend_status, attachment_path: Optional[str] = None):
    """Background task để gửi tin nhắn.
    Mỗi lần gọi tự mở browser theo cấu hình headless ở Trang Chủ,
    chạy xong đóng lại.
    """
    try:
        await log_to_ws(f"Bắt đầu gửi tin nhắn cho {len(customers)} khách hàng", "info")
        await manager.broadcast_status("running", {"task": "send_messages"})

        loop = asyncio.get_running_loop()
        headless = load_config().get("headless", False)

        def callback(msg):
            asyncio.run_coroutine_threadsafe(log_to_ws(str(msg), "info"), loop)

        def is_paused():
            return zalo_state["is_paused"]

        def is_stop():
            return zalo_state["stop_requested"]

        def do_send():
            from logic.zalo_automation import ZaloAutomation

            mode_text = "ẩn" if headless else "hiện"
            asyncio.run_coroutine_threadsafe(
                log_to_ws(f"🌐 Đang mở Zalo để gửi tin nhắn (chế độ {mode_text})...", "info"), loop
            )
            session_manager = get_session_manager(user_id)
            success, p, context, page = session_manager.connect_with_session(headless=headless)
            if not success:
                zalo_state["session_active"] = False
                asyncio.run_coroutine_threadsafe(
                    log_to_ws("⚠️ Session Zalo không còn hợp lệ khi bắt đầu gửi tin nhắn. Browser sẽ đóng và yêu cầu đăng nhập lại.", "warning"),
                    loop
                )
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast_status("session_state", {
                        "task": "zalo_session",
                        "session_active": False,
                        "zalo_name": "",
                    }),
                    loop
                )
                raise Exception("Session Zalo đã hết hạn — vui lòng đăng nhập lại")

            asyncio.run_coroutine_threadsafe(
                log_to_ws("✅ Đã kết nối Zalo, bắt đầu gửi tin nhắn...", "success"), loop
            )
            try:
                automation = ZaloAutomation(page)
                result = automation.send_bulk_messages(
                    customer_list=customers,
                    template=message_template,
                    callback=callback,
                    delay=3,
                    is_paused_func=is_paused,
                    is_stop_func=is_stop,
                    my_name=zalo_state.get("zalo_name", ""),
                    check_friend_status=check_friend_status,
                    attachment_path=attachment_path,
                )
            finally:
                try:
                    context.close()
                    p.stop()
                except Exception:
                    pass
            return result

        results = await loop.run_in_executor(_executor, do_send)

        success_count = results.get("success", 0) if isinstance(results, dict) else 0
        failed_count = results.get("failed", 0) if isinstance(results, dict) else 0
        await log_to_ws(
            f"✅ Hoàn thành gửi tin nhắn — Thành công: {success_count}, Thất bại: {failed_count}",
            "success"
        )
        await manager.broadcast_status("completed", {"task": "send_messages", "results": results})

    except Exception as e:
        await log_to_ws(f"Lỗi: {str(e)}", "error")
        await manager.broadcast_status("error", {"task": "send_messages", "error": str(e)})
    finally:
        _finish_zalo_task()


@router.post("/add-friends")
async def add_friends(request: AddFriendRequest, background_tasks: BackgroundTasks, current_user=Depends(require_roles("admin", "user"))):
    """Kết bạn hàng loạt"""
    session_state = await resolve_session_state(current_user["id"], verify=False)
    if not session_state["session_active"]:
        raise HTTPException(status_code=400, detail="Please login to Zalo first")
    
    if not request.customers:
        raise HTTPException(status_code=400, detail="Customer list is empty")

    valid_customers = [customer for customer in request.customers if str(customer.get("phone", "")).strip()]
    if not valid_customers:
        raise HTTPException(status_code=400, detail="Danh sách hiện tại không còn khách hàng nào có số điện thoại hợp lệ")
    
    _start_zalo_task("add_friends")
    
    background_tasks.add_task(
        run_add_friends_task,
        current_user["id"],
        valid_customers,
        request.greeting_template
    )
    
    return {
        "status": "started",
        "message": f"Bắt đầu kết bạn với {len(valid_customers)} khách hàng"
    }


async def run_add_friends_task(user_id, customers, greeting_template):
    """Background task để kết bạn.
    Mỗi lần gọi tự mở browser theo cấu hình headless ở Trang Chủ,
    chạy xong đóng lại.
    """
    try:
        await log_to_ws(f"Bắt đầu kết bạn với {len(customers)} khách hàng", "info")
        await manager.broadcast_status("running", {"task": "add_friends"})

        loop = asyncio.get_running_loop()
        headless = load_config().get("headless", False)

        def do_add_friends():
            import time
            import random
            from logic.zalo_automation import (
                ZaloAutomation,
                BrowserClosedError,
                ZaloRateLimitError,
                is_browser_closed_error,
                is_rate_limit_error,
                to_gender_pronoun,
            )

            mode_text = "ẩn" if headless else "hiện"
            asyncio.run_coroutine_threadsafe(
                log_to_ws(f"🌐 Đang mở Zalo để kết bạn (chế độ {mode_text})...", "info"), loop
            )
            session_manager = get_session_manager(user_id)
            success, p, context, page = session_manager.connect_with_session(headless=headless)
            if not success:
                zalo_state["session_active"] = False
                asyncio.run_coroutine_threadsafe(
                    log_to_ws("⚠️ Session Zalo không còn hợp lệ khi bắt đầu kết bạn. Browser sẽ đóng và yêu cầu đăng nhập lại.", "warning"),
                    loop
                )
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast_status("session_state", {
                        "task": "zalo_session",
                        "session_active": False,
                        "zalo_name": "",
                    }),
                    loop
                )
                raise Exception("Session Zalo đã hết hạn — vui lòng đăng nhập lại")

            asyncio.run_coroutine_threadsafe(
                log_to_ws("✅ Đã kết nối Zalo, bắt đầu kết bạn...", "success"), loop
            )

            try:
                automation = ZaloAutomation(page)
                my_name = automation.get_my_zalo_name(session_manager)
                asyncio.run_coroutine_threadsafe(
                    log_to_ws(f"👤 Tài khoản Zalo: {my_name}", "info"), loop
                )

                success_count = 0
                failed_count = 0
                already_sent_count = 0
                already_friend_count = 0
                results = []

                customers_with_phone = [c for c in customers if c.get("phone", "").strip()]

                for i, customer in enumerate(customers_with_phone):
                    # Kiểm tra dừng hẳn
                    if zalo_state["stop_requested"]:
                        asyncio.run_coroutine_threadsafe(
                            log_to_ws("🛑 Đã nhận lệnh dừng, thoát vòng kết bạn.", "warning"),
                            loop
                        )
                        break

                    # Tạm dừng nếu cần
                    while zalo_state["is_paused"] and not zalo_state["stop_requested"]:
                        time.sleep(random.uniform(0.4, 0.6))

                    if zalo_state["stop_requested"]:
                        break

                    phone = customer.get("phone", "").strip()
                    name = customer.get("name", "N/A")
                    contract_id = customer.get("contract_id", "")

                    # Format greeting với các biến (giống working app_ui.py)
                    gender_pronoun = to_gender_pronoun(customer.get("gender", ""))

                    if greeting_template:
                        try:
                            formatted_greeting = greeting_template.format(
                                name=name,
                                phone=phone,
                                contract_id=contract_id,
                                my_name=my_name,
                                gender=gender_pronoun,
                                address=customer.get("address", ""),
                                cccd=customer.get("cccd", ""),
                                dob=customer.get("dob", "")
                            )
                        except (KeyError, ValueError):
                            formatted_greeting = greeting_template
                    else:
                        formatted_greeting = ""

                    asyncio.run_coroutine_threadsafe(
                        log_to_ws(f"🤝 [{i+1}/{len(customers_with_phone)}] Đang kết bạn: {name} ({phone})", "info"),
                        loop
                    )
                    asyncio.run_coroutine_threadsafe(
                        manager.broadcast_progress(i + 1, len(customers_with_phone), f"Đang xử lý: {phone}"),
                        loop
                    )

                    try:
                        result, display_name = automation.add_friend_by_phone(
                            phone_number=phone,
                            contract_id=contract_id,
                            my_zalo_name=my_name,
                            greeting_template=formatted_greeting
                        )
                    except Exception as e:
                        err_str = str(e)
                        if isinstance(e, ZaloRateLimitError) or is_rate_limit_error(e):
                            asyncio.run_coroutine_threadsafe(
                                log_to_ws(
                                    f"🚫 Zalo đang giới hạn tìm kiếm/kết bạn do chống spam. {err_str}",
                                    "error"
                                ),
                                loop
                            )
                            results.append({
                                "phone": phone,
                                "name": name,
                                "status": "rate_limited",
                                "display_name": None,
                                "error": err_str,
                            })
                            raise ZaloRateLimitError(err_str) from e

                        if isinstance(e, BrowserClosedError) or is_browser_closed_error(e):
                            asyncio.run_coroutine_threadsafe(
                                log_to_ws("🛑 Trình duyệt đã bị đóng, dừng toàn bộ tác vụ kết bạn.", "error"),
                                loop
                            )
                            raise BrowserClosedError("Trình duyệt Zalo đã bị đóng trong khi kết bạn") from e
                        asyncio.run_coroutine_threadsafe(
                            log_to_ws(f"❌ [{i+1}/{len(customers_with_phone)}] Lỗi: {phone} — {err_str}", "error"),
                            loop
                        )
                        results.append({"phone": phone, "name": name, "status": "error", "display_name": None})
                        failed_count += 1
                        try:
                            automation.close_modal_after_add_friend()
                        except Exception:
                            pass
                        time.sleep(3)
                        continue

                    # Đóng modal sau mỗi lần (thành công hoặc thất bại)
                    try:
                        automation.close_modal_after_add_friend()
                    except Exception:
                        pass

                    if result == "already_sent":
                        already_sent_count += 1
                        msg = f"⚠️ [{i+1}/{len(customers_with_phone)}] Đã gửi lời mời trước đó: {phone}"
                        if display_name:
                            msg += f" — Zalo: {display_name}"
                        asyncio.run_coroutine_threadsafe(log_to_ws(msg, "warning"), loop)
                        results.append({"phone": phone, "name": name, "status": "already_sent", "display_name": display_name})
                    elif result == "already_friend":
                        already_friend_count += 1
                        msg = f"👥 [{i+1}/{len(customers_with_phone)}] Đã là bạn bè: {phone}"
                        if display_name:
                            msg += f" — Zalo: {display_name}"
                        asyncio.run_coroutine_threadsafe(log_to_ws(msg, "info"), loop)
                        results.append({"phone": phone, "name": name, "status": "already_friend", "display_name": display_name})
                    elif result:
                        success_count += 1
                        msg = f"✅ [{i+1}/{len(customers_with_phone)}] Kết bạn thành công: {phone}"
                        if display_name:
                            msg += f" — Zalo: {display_name}"
                        asyncio.run_coroutine_threadsafe(log_to_ws(msg, "success"), loop)
                        results.append({"phone": phone, "name": name, "status": "success", "display_name": display_name})
                    else:
                        failed_count += 1
                        asyncio.run_coroutine_threadsafe(
                            log_to_ws(f"❌ [{i+1}/{len(customers_with_phone)}] Thất bại: {phone}", "error"),
                            loop
                        )
                        results.append({"phone": phone, "name": name, "status": "failed", "display_name": None})

                    # Delay giữa các lần kết bạn (random 2.5-3.5s giống working code)
                    if i < len(customers_with_phone) - 1:
                        delay = random.uniform(2.5, 3.5)
                        time.sleep(delay)

                asyncio.run_coroutine_threadsafe(
                    log_to_ws(
                        f"📊 Kết quả: {success_count} thành công, "
                        f"{already_friend_count} đã là bạn, "
                        f"{already_sent_count} đã gửi trước, "
                        f"{failed_count} thất bại",
                        "info"
                    ),
                    loop
                )
                return results

            finally:
                try:
                    context.close()
                    p.stop()
                except Exception:
                    pass

        results = await loop.run_in_executor(_executor, do_add_friends)

        await log_to_ws("✅ Hoàn thành kết bạn hàng loạt", "success")
        await manager.broadcast_status("completed", {"task": "add_friends", "results": results})

    except Exception as e:
        error_text = str(e)
        if any(
            marker in error_text.lower()
            for marker in [
                "tìm số điện thoại quá nhiều lần trong 1 giờ",
                "hoạt động bất thường",
                "bạn hãy thử lại vào",
            ]
        ):
            await log_to_ws(
                f"🚫 Tác vụ đã dừng: Zalo giới hạn thao tác kết bạn/tìm kiếm. {error_text}",
                "error"
            )
        else:
            await log_to_ws(f"Lỗi: {error_text}", "error")

        await manager.broadcast_status("error", {"task": "add_friends", "error": error_text})
    finally:
        _finish_zalo_task()


@router.post("/add-friends-and-send")
async def add_friends_and_send(
    request: AddFriendAndSendRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(require_roles("admin", "user")),
):
    """Kết bạn rồi gửi tin nhắn ngay sau đó (nếu có thể)."""
    session_state = await resolve_session_state(current_user["id"], verify=False)
    if not session_state["session_active"]:
        raise HTTPException(status_code=400, detail="Please login to Zalo first")

    if not request.customers:
        raise HTTPException(status_code=400, detail="Customer list is empty")

    if not str(request.message_template or "").strip():
        raise HTTPException(status_code=400, detail="Message template is required")

    valid_customers = [customer for customer in request.customers if str(customer.get("phone", "")).strip()]
    if not valid_customers:
        raise HTTPException(status_code=400, detail="Danh sách hiện tại không còn khách hàng nào có số điện thoại hợp lệ")

    attachment_path = _resolve_uploaded_image_path(request.attachment_filename)

    _start_zalo_task("add_friends_and_send")

    background_tasks.add_task(
        run_add_friends_and_send_task,
        current_user["id"],
        valid_customers,
        request.greeting_template,
        request.message_template,
        attachment_path,
    )

    return {
        "status": "started",
        "message": f"Bắt đầu kết bạn rồi gửi tin nhắn cho {len(valid_customers)} khách hàng",
    }


async def run_add_friends_and_send_task(user_id, customers, greeting_template, message_template, attachment_path: Optional[str] = None):
    """Background task để kết bạn rồi gửi tin nhắn ngay sau đó.
    Quy tắc:
    - Nếu bị rate-limit chống spam kết bạn: dừng toàn bộ tác vụ ngay.
    - Nếu kết bạn được/đã là bạn/đã gửi lời mời trước đó: thử gửi tin nhắn.
    """
    try:
        await log_to_ws(f"Bắt đầu kết bạn rồi gửi tin nhắn cho {len(customers)} khách hàng", "info")
        await manager.broadcast_status("running", {"task": "add_friends_and_send"})

        loop = asyncio.get_running_loop()
        headless = load_config().get("headless", False)

        def do_add_and_send():
            import time
            import random
            from logic.zalo_automation import (
                ZaloAutomation,
                BrowserClosedError,
                ZaloRateLimitError,
                is_browser_closed_error,
                is_rate_limit_error,
                to_gender_pronoun,
            )

            mode_text = "ẩn" if headless else "hiện"
            asyncio.run_coroutine_threadsafe(
                log_to_ws(f"🌐 Đang mở Zalo để kết bạn + gửi tin (chế độ {mode_text})...", "info"), loop
            )
            session_manager = get_session_manager(user_id)
            success, p, context, page = session_manager.connect_with_session(headless=headless)
            if not success:
                zalo_state["session_active"] = False
                asyncio.run_coroutine_threadsafe(
                    log_to_ws("⚠️ Session Zalo không còn hợp lệ khi bắt đầu tác vụ. Browser sẽ đóng và yêu cầu đăng nhập lại.", "warning"),
                    loop
                )
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast_status("session_state", {
                        "task": "zalo_session",
                        "session_active": False,
                        "zalo_name": "",
                    }),
                    loop
                )
                raise Exception("Session Zalo đã hết hạn — vui lòng đăng nhập lại")

            asyncio.run_coroutine_threadsafe(
                log_to_ws("✅ Đã kết nối Zalo, bắt đầu kết bạn + gửi tin...", "success"), loop
            )

            try:
                automation = ZaloAutomation(page)
                my_name = automation.get_my_zalo_name(session_manager)
                asyncio.run_coroutine_threadsafe(
                    log_to_ws(f"👤 Tài khoản Zalo: {my_name}", "info"), loop
                )

                sent_after_add_count = 0
                add_success_count = 0
                failed_count = 0
                already_sent_count = 0
                already_friend_count = 0
                results = []

                customers_with_phone = [c for c in customers if c.get("phone", "").strip()]

                for i, customer in enumerate(customers_with_phone):
                    if zalo_state["stop_requested"]:
                        asyncio.run_coroutine_threadsafe(
                            log_to_ws("🛑 Đã nhận lệnh dừng, thoát vòng kết bạn + gửi tin.", "warning"),
                            loop
                        )
                        break

                    while zalo_state["is_paused"] and not zalo_state["stop_requested"]:
                        time.sleep(random.uniform(0.4, 0.6))

                    if zalo_state["stop_requested"]:
                        break

                    phone = customer.get("phone", "").strip()
                    name = customer.get("name", "N/A")
                    contract_id = customer.get("contract_id", "")
                    gender_pronoun = to_gender_pronoun(customer.get("gender", ""))

                    if greeting_template:
                        try:
                            formatted_greeting = greeting_template.format(
                                name=name,
                                phone=phone,
                                contract_id=contract_id,
                                my_name=my_name,
                                gender=gender_pronoun,
                                address=customer.get("address", ""),
                                cccd=customer.get("cccd", ""),
                                dob=customer.get("dob", "")
                            )
                        except (KeyError, ValueError):
                            formatted_greeting = greeting_template
                    else:
                        formatted_greeting = ""

                    try:
                        formatted_message = message_template.format(
                            name=name,
                            phone=phone,
                            contract_id=contract_id,
                            my_name=my_name,
                            gender=gender_pronoun,
                            address=customer.get("address", ""),
                            cccd=customer.get("cccd", ""),
                            dob=customer.get("dob", "")
                        )
                    except (KeyError, ValueError):
                        formatted_message = message_template

                    asyncio.run_coroutine_threadsafe(
                        log_to_ws(f"🤝💬 [{i+1}/{len(customers_with_phone)}] Kết bạn rồi gửi tin: {name} ({phone})", "info"),
                        loop
                    )
                    asyncio.run_coroutine_threadsafe(
                        manager.broadcast_progress(i + 1, len(customers_with_phone), f"Đang xử lý: {phone}"),
                        loop
                    )

                    try:
                        add_result, display_name = automation.add_friend_by_phone(
                            phone_number=phone,
                            contract_id=contract_id,
                            my_zalo_name=my_name,
                            greeting_template=formatted_greeting,
                        )
                    except Exception as e:
                        err_str = str(e)
                        if isinstance(e, ZaloRateLimitError) or is_rate_limit_error(e):
                            asyncio.run_coroutine_threadsafe(
                                log_to_ws(f"🚫 Zalo đang giới hạn tìm kiếm/kết bạn do chống spam. {err_str}", "error"),
                                loop
                            )
                            results.append({
                                "phone": phone,
                                "name": name,
                                "status": "rate_limited",
                                "display_name": None,
                                "error": err_str,
                            })
                            raise ZaloRateLimitError(err_str) from e

                        if isinstance(e, BrowserClosedError) or is_browser_closed_error(e):
                            asyncio.run_coroutine_threadsafe(
                                log_to_ws("🛑 Trình duyệt đã bị đóng, dừng toàn bộ tác vụ kết bạn + gửi tin.", "error"),
                                loop
                            )
                            raise BrowserClosedError("Trình duyệt Zalo đã bị đóng trong khi kết bạn + gửi tin") from e

                        asyncio.run_coroutine_threadsafe(
                            log_to_ws(f"❌ [{i+1}/{len(customers_with_phone)}] Lỗi kết bạn: {phone} — {err_str}", "error"),
                            loop
                        )
                        results.append({"phone": phone, "name": name, "status": "error", "display_name": None})
                        failed_count += 1
                        try:
                            automation.close_modal_after_add_friend()
                        except Exception:
                            pass
                        time.sleep(2)
                        continue

                    try:
                        automation.close_modal_after_add_friend()
                    except Exception:
                        pass

                    should_send_message = False
                    status_prefix = ""
                    if add_result == "already_sent":
                        already_sent_count += 1
                        status_prefix = "already_sent"
                        should_send_message = True
                    elif add_result == "already_friend":
                        already_friend_count += 1
                        status_prefix = "already_friend"
                        should_send_message = True
                    elif add_result:
                        add_success_count += 1
                        status_prefix = "success"
                        should_send_message = True
                    else:
                        failed_count += 1
                        asyncio.run_coroutine_threadsafe(
                            log_to_ws(f"❌ [{i+1}/{len(customers_with_phone)}] Kết bạn thất bại: {phone}", "error"),
                            loop
                        )
                        results.append({"phone": phone, "name": name, "status": "failed", "display_name": None})

                    if should_send_message:
                        try:
                            send_ok, _friend_status, send_error = automation.send_message_to_phone(
                                phone_number=phone,
                                message=formatted_message,
                                check_status=False,
                                image_path=attachment_path,
                            )
                        except Exception as e:
                            if isinstance(e, BrowserClosedError) or is_browser_closed_error(e):
                                asyncio.run_coroutine_threadsafe(
                                    log_to_ws("🛑 Trình duyệt đã bị đóng, dừng toàn bộ tác vụ kết bạn + gửi tin.", "error"),
                                    loop
                                )
                                raise BrowserClosedError("Trình duyệt Zalo đã bị đóng khi gửi tin sau kết bạn") from e
                            send_ok = False
                            send_error = str(e)

                        if send_ok:
                            sent_after_add_count += 1
                            final_status = (
                                "already_friend_sent" if status_prefix == "already_friend"
                                else "already_sent_and_sent" if status_prefix == "already_sent"
                                else "success_and_sent"
                            )
                            asyncio.run_coroutine_threadsafe(
                                log_to_ws(f"✅ [{i+1}/{len(customers_with_phone)}] Kết bạn + gửi tin thành công: {phone}", "success"),
                                loop
                            )
                            results.append({"phone": phone, "name": name, "status": final_status, "display_name": display_name})
                        else:
                            failed_count += 1
                            final_status = f"{status_prefix}_send_failed" if status_prefix else "send_failed"
                            asyncio.run_coroutine_threadsafe(
                                log_to_ws(f"⚠️ [{i+1}/{len(customers_with_phone)}] Kết bạn xong nhưng gửi tin thất bại: {phone} ({send_error or 'send_failed'})", "warning"),
                                loop
                            )
                            results.append({
                                "phone": phone,
                                "name": name,
                                "status": final_status,
                                "display_name": display_name,
                                "error": send_error,
                            })

                    if i < len(customers_with_phone) - 1:
                        delay = random.uniform(2.5, 3.5)
                        time.sleep(delay)

                asyncio.run_coroutine_threadsafe(
                    log_to_ws(
                        f"📊 Kết quả (kết bạn + gửi tin): "
                        f"{add_success_count} kết bạn mới, "
                        f"{already_friend_count} đã là bạn, "
                        f"{already_sent_count} đã gửi lời mời trước, "
                        f"{sent_after_add_count} gửi tin thành công, "
                        f"{failed_count} thất bại",
                        "info"
                    ),
                    loop
                )
                return results

            finally:
                try:
                    context.close()
                    p.stop()
                except Exception:
                    pass

        results = await loop.run_in_executor(_executor, do_add_and_send)

        await log_to_ws("✅ Hoàn thành kết bạn rồi gửi tin nhắn", "success")
        await manager.broadcast_status("completed", {"task": "add_friends_and_send", "results": results})

    except Exception as e:
        error_text = str(e)
        if any(
            marker in error_text.lower()
            for marker in [
                "tìm số điện thoại quá nhiều lần trong 1 giờ",
                "hoạt động bất thường",
                "bạn hãy thử lại vào",
            ]
        ):
            await log_to_ws(
                f"🚫 Tác vụ đã dừng: Zalo giới hạn thao tác kết bạn/tìm kiếm. {error_text}",
                "error"
            )
        else:
            await log_to_ws(f"Lỗi: {error_text}", "error")
        await manager.broadcast_status("error", {"task": "add_friends_and_send", "error": error_text})
    finally:
        _finish_zalo_task()


@router.post("/stop")
async def stop_zalo():
    """Dừng hẳn Zalo task đang chạy"""
    with _zalo_state_lock:
        if not zalo_state["is_running"]:
            raise HTTPException(status_code=400, detail="No Zalo task is running")
        zalo_state["stop_requested"] = True
        zalo_state["is_paused"] = False  # Mở khóa pause loop nếu đang pause
        current_task = zalo_state["current_task"]
    await log_to_ws("Đang dừng tác vụ Zalo...", "warning")
    await manager.broadcast_status("stopping", {"task": current_task})

    return {"status": "stopping", "message": "Zalo task is being stopped"}


@router.post("/pause")
async def pause_zalo():
    """Tạm dừng Zalo task"""
    with _zalo_state_lock:
        if not zalo_state["is_running"]:
            raise HTTPException(status_code=400, detail="No Zalo task is running")
        zalo_state["is_paused"] = True
        current_task = zalo_state["current_task"]
    await log_to_ws("Đã tạm dừng", "warning")
    await manager.broadcast_status("paused", {"task": current_task})
    
    return {"status": "paused"}


@router.post("/resume")
async def resume_zalo():
    """Tiếp tục Zalo task"""
    with _zalo_state_lock:
        if not zalo_state["is_running"]:
            raise HTTPException(status_code=400, detail="No Zalo task is running")
        zalo_state["is_paused"] = False
        current_task = zalo_state["current_task"]
    await log_to_ws("Đã tiếp tục", "info")
    await manager.broadcast_status("running", {"task": current_task})
    
    return {"status": "resumed"}
