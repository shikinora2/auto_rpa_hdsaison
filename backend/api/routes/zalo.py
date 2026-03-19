"""
Zalo API Routes
API endpoints cho các tính năng Zalo automation
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import concurrent.futures
import time
from playwright.sync_api import sync_playwright

from config.settings import ZALO_SESSION_DIR
from api.websocket.connection_manager import manager, log_to_ws
from api.routes.config import load_config

# Thread pool cho việc chạy sync Playwright (max 1 vì persistent context)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

router = APIRouter()

# Cache QR code duy nhất để FE có thể fetch ngay khi reload trang
_qr_cache: dict | None = None
_QR_TTL = 600  # giây


def _cache_qr(qr_b64: str):
    global _qr_cache
    _qr_cache = {"qr_base64": qr_b64, "ts": time.time()}


def _get_cached_qr() -> str | None:
    entry = _qr_cache
    if not entry:
        return None

    # Khi task login đang chạy, luôn giữ QR cache để FE không mất ảnh giữa chừng
    if zalo_state.get("is_running") and zalo_state.get("current_task") == "login":
        return entry["qr_base64"]

    if time.time() - entry["ts"] < _QR_TTL:
        return entry["qr_base64"]
    return None


def _clear_qr_cache():
    global _qr_cache
    _qr_cache = None

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



class SendMessageRequest(BaseModel):
    """Schema cho gửi tin nhắn"""
    customers: List[dict]  # List of {phone, name, contract_id, ...}
    message_template: str
    check_friend_status: Optional[bool] = True


class AddFriendRequest(BaseModel):
    """Schema cho kết bạn"""
    customers: List[dict]
    greeting_template: Optional[str] = ""


# ============== Session Helpers ==============

def get_session_manager():
    """Tạo ZaloSessionManager với thư mục mặc định duy nhất."""
    from logic.zalo_logic import ZaloSessionManager
    return ZaloSessionManager(session_dir=str(ZALO_SESSION_DIR))


def persist_session_snapshot(session_manager, existing_info: Optional[dict] = None, zalo_name: str = "") -> dict:
    """Đảm bảo metadata session tồn tại mỗi khi phát hiện session đang active."""
    session_info = dict(existing_info or {})
    session_info["status"] = "active"
    session_info.setdefault("last_login", time.strftime('%Y-%m-%d %H:%M:%S'))
    if zalo_name:
        session_info["zalo_name"] = zalo_name
    session_manager.save_session_info(session_info)
    return session_info


def sync_session_state() -> dict:
    """Đồng bộ session Zalo từ dữ liệu lưu trên disk thay vì chỉ dựa vào RAM."""
    session_manager = get_session_manager()
    session_info = session_manager.get_session_info() or {}
    has_session = session_manager.has_session()
    session_active = has_session and session_info.get("status") == "active"
    zalo_name = session_info.get("zalo_name", "")

    zalo_state["session_active"] = session_active
    zalo_state["zalo_name"] = zalo_name

    return {
        "session_manager": session_manager,
        "session_info": session_info,
        "session_active": session_active,
        "zalo_name": zalo_name,
    }


async def resolve_session_state(verify: bool = False) -> dict:
    """Lấy trạng thái session Zalo và có thể xác thực session thật bằng browser headless."""
    session_state = sync_session_state()

    if not verify:
        return session_state

    session_manager = session_state["session_manager"]
    session_info = dict(session_state["session_info"] or {})
    has_session = session_manager.has_session()

    # Tránh đụng session directory khi bất kỳ task nào đang chạy browser trên cùng account.
    # Nếu đang login (QR), send_messages, hay add_friends — không mở thêm browser verify
    # vì sẽ bị data race với persistent context đang hoạt động.
    if zalo_state["is_running"]:
        return session_state

    if not has_session:
        session_info["status"] = "inactive"
        session_manager.save_session_info(session_info)
        return sync_session_state()

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

    return sync_session_state()


# ============== Session Management ==============

@router.get("/session")
async def get_session_status(verify: bool = False):
    """Kiểm tra trạng thái session Zalo.
    - verify=False (mặc định): trả về trạng thái nhanh từ disk, không mở browser.
    - verify=True: mở headless browser để xác thực session thực tế (chậm hơn).
    """
    session_state = await resolve_session_state(verify=verify)

    return {
        "is_active": session_state["session_active"],
        "is_running": zalo_state["is_running"],
        "current_task": zalo_state["current_task"],
        "zalo_name": session_state["zalo_name"],
    }


@router.post("/login")
async def login_zalo(background_tasks: BackgroundTasks):
    """
    Mở trình duyệt để đăng nhập Zalo (quét QR)
    Browser sẽ mở ở chế độ headful để người dùng quét QR
    """
    if zalo_state["is_running"]:
        raise HTTPException(status_code=400, detail="Another Zalo task is running")
    
    zalo_state["is_running"] = True
    zalo_state["current_task"] = "zalo_login"
    zalo_state["stop_requested"] = False
    
    background_tasks.add_task(run_zalo_login_task)
    
    return {
        "status": "started",
        "message": "Đang mở trình duyệt Zalo, vui lòng quét mã QR"
    }


async def run_zalo_login_task():
    """Background task để login Zalo.
    Mở browser headful cho user quét QR.
    Sau khi login thành công: lưu session vào disk, đóng browser.
    Browser KHÔNG được giữ mở — các task automation sau dùng headless per-task.
    """
    try:
        await log_to_ws("Đang mở trình duyệt Zalo...", "info")
        await manager.broadcast_status("running", {"task": "zalo_login"})

        loop = asyncio.get_running_loop()

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
            _cache_qr(qr_base64)
            asyncio.run_coroutine_threadsafe(
                manager.broadcast_qr(qr_base64),
                loop
            )

        def do_login():
            from logic.zalo_automation import ZaloAutomation

            session_manager = get_session_manager()

            # ── Mở browser HIỂN THỊ để lấy QR ổn định hơn ──────────────────
            p = sync_playwright().start()
            context = session_manager.create_persistent_context(p, headless=False)
            page = context.pages[0] if context.pages else context.new_page()

            # Xóa cookie cũ để buộc hiện QR mới
            context.clear_cookies()
            try:
                page.goto("about:blank")
                page.evaluate("localStorage.clear(); sessionStorage.clear();")
            except Exception:
                pass

            try:
                page.goto("https://id.zalo.me/account?continue=https%3A%2F%2Fchat.zalo.me%2F", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass

            # Đợi QR canvas/img xuất hiện rồi broadcast
            qr_selectors = [
                "div.qrcode img",
                "div.qr-container img",
                "img[src*='data:image/png;base64']",
                "canvas#qrcode", 
                "canvas[class*='qrcode']", 
                "div[class*='qr'] canvas"
            ]

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
                        qr_bytes = el.screenshot()
                        import base64
                        qr_b64 = base64.b64encode(qr_bytes).decode()
                        broadcast_qr(qr_b64)
                        return True
                    except Exception:
                        continue

                # Fallback: chụp toàn trang login để FE vẫn có hình quét (tránh kẹt không ra QR)
                try:
                    current_url = page.url
                    if "id.zalo.me" in current_url or "chat.zalo.me" in current_url:
                        page_bytes = page.screenshot(full_page=True)
                        import base64 as _b64
                        broadcast_qr(_b64.b64encode(page_bytes).decode())
                        return True
                except Exception:
                    pass
                return False

            # Thử bắt QR nhanh trong ~20s đầu, tránh block lâu từng selector
            first_qr_deadline = time.time() + 20
            while time.time() < first_qr_deadline:
                if _try_capture_qr():
                    break
                time.sleep(0.8)

            # ── Chờ đăng nhập (polling URL mỗi 1.5s) ──────────────────────
            import time as _time
            start = _time.time()
            max_wait = 300
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
                        break
                    # Refresh QR đều đặn nếu user chưa quét
                    elapsed = int(_time.time() - start)
                    if elapsed > 0 and elapsed % 3 == 0:
                        _try_capture_qr()

                    # Làm mới trang login định kỳ để tránh QR bị treo/expired mà không render lại
                    if elapsed > 0 and elapsed % 45 == 0 and "chat.zalo.me" not in page.url:
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
            try:
                automation = ZaloAutomation(page)
                zalo_name = automation.get_my_zalo_name(session_manager)
                persist_session_snapshot(session_manager, session_manager.get_session_info() or {}, zalo_name=zalo_name)
            except Exception:
                zalo_name = ""

            try:
                context.close()
                p.stop()
            except Exception:
                pass

            return True, zalo_name

        success, zalo_name = await loop.run_in_executor(_executor, do_login)

        if success:
            zalo_state["session_active"] = True
            zalo_state["zalo_name"] = zalo_name
            await log_to_ws(f"Đăng nhập thành công! Tài khoản: {zalo_name or '(không xác định)'}", "success")
            await manager.broadcast_status("completed", {"task": "zalo_login", "success": True})
        else:
            zalo_state["session_active"] = False
            zalo_state["zalo_name"] = ""
            await log_to_ws("Đăng nhập thất bại hoặc timeout", "error")
            await manager.broadcast_status("error", {"task": "zalo_login"})

    except Exception as e:
        await log_to_ws(f"Lỗi: {str(e)}", "error")
        await manager.broadcast_status("error", {"task": "zalo_login", "error": str(e)})
    finally:
        zalo_state["is_running"] = False
        zalo_state["current_task"] = None
        await manager.broadcast_status("session_state", {
            "task": "zalo_session",
            "session_active": zalo_state["session_active"],
            "zalo_name": zalo_state["zalo_name"],
        })


@router.post("/logout")
async def logout_zalo():
    """Xóa session Zalo (logout).
    Browser không còn tồn tại trong memory — chỉ cần reset state và xóa session disk.
    """
    try:
        # Xóa session trên disk để buộc QR lần sau
        session_manager = get_session_manager()
        session_manager.delete_session()
    except Exception:
        pass

    zalo_state["session_active"] = False
    zalo_state["zalo_name"] = ""
    _clear_qr_cache()
    return {"status": "success", "message": "Logged out"}


@router.get("/qr")
async def get_qr_image():
    """Trả về QR code đã cache (nếu còn hợp lệ) để FE hiện ngay khi reload trang.
    FE nên gọi endpoint này sau khi xác nhận session chưa đăng nhập.
    """
    qr_b64 = _get_cached_qr()
    return {
        "qr_base64": qr_b64,
        "is_running": zalo_state["is_running"],
        "current_task": zalo_state["current_task"],
    }


# ============== Automation ==============

@router.post("/send-messages")
async def send_messages(request: SendMessageRequest, background_tasks: BackgroundTasks):
    """Gửi tin nhắn hàng loạt"""
    if zalo_state["is_running"]:
        raise HTTPException(status_code=400, detail="Another Zalo task is running")

    session_state = await resolve_session_state(verify=False)
    if not session_state["session_active"]:
        raise HTTPException(status_code=400, detail="Please login to Zalo first")
    
    if not request.customers:
        raise HTTPException(status_code=400, detail="Customer list is empty")

    valid_customers = [customer for customer in request.customers if str(customer.get("phone", "")).strip()]
    if not valid_customers:
        raise HTTPException(status_code=400, detail="Danh sách hiện tại không còn khách hàng nào có số điện thoại hợp lệ")
    
    zalo_state["is_running"] = True
    zalo_state["is_paused"] = False
    zalo_state["stop_requested"] = False
    zalo_state["current_task"] = "send_messages"
    
    background_tasks.add_task(
        run_send_messages_task,
        valid_customers,
        request.message_template,
        request.check_friend_status
    )
    
    return {
        "status": "started",
        "message": f"Bắt đầu gửi tin nhắn cho {len(valid_customers)} khách hàng"
    }


async def run_send_messages_task(customers, message_template, check_friend_status):
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
            session_manager = get_session_manager()
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
                    check_friend_status=check_friend_status
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
        zalo_state["is_running"] = False
        zalo_state["current_task"] = None


@router.post("/add-friends")
async def add_friends(request: AddFriendRequest, background_tasks: BackgroundTasks):
    """Kết bạn hàng loạt"""
    if zalo_state["is_running"]:
        raise HTTPException(status_code=400, detail="Another Zalo task is running")

    session_state = await resolve_session_state(verify=False)
    if not session_state["session_active"]:
        raise HTTPException(status_code=400, detail="Please login to Zalo first")
    
    if not request.customers:
        raise HTTPException(status_code=400, detail="Customer list is empty")

    valid_customers = [customer for customer in request.customers if str(customer.get("phone", "")).strip()]
    if not valid_customers:
        raise HTTPException(status_code=400, detail="Danh sách hiện tại không còn khách hàng nào có số điện thoại hợp lệ")
    
    zalo_state["is_running"] = True
    zalo_state["is_paused"] = False
    zalo_state["stop_requested"] = False
    zalo_state["current_task"] = "add_friends"
    
    background_tasks.add_task(
        run_add_friends_task,
        valid_customers,
        request.greeting_template
    )
    
    return {
        "status": "started",
        "message": f"Bắt đầu kết bạn với {len(valid_customers)} khách hàng"
    }


async def run_add_friends_task(customers, greeting_template):
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
            from logic.zalo_automation import ZaloAutomation, BrowserClosedError, is_browser_closed_error, to_gender_pronoun

            mode_text = "ẩn" if headless else "hiện"
            asyncio.run_coroutine_threadsafe(
                log_to_ws(f"🌐 Đang mở Zalo để kết bạn (chế độ {mode_text})...", "info"), loop
            )
            session_manager = get_session_manager()
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
        await log_to_ws(f"Lỗi: {str(e)}", "error")
        await manager.broadcast_status("error", {"task": "add_friends", "error": str(e)})
    finally:
        zalo_state["is_running"] = False
        zalo_state["current_task"] = None


@router.post("/stop")
async def stop_zalo():
    """Dừng hẳn Zalo task đang chạy"""
    if not zalo_state["is_running"]:
        raise HTTPException(status_code=400, detail="No Zalo task is running")

    zalo_state["stop_requested"] = True
    zalo_state["is_paused"] = False  # Mở khóa pause loop nếu đang pause
    await log_to_ws("Đang dừng tác vụ Zalo...", "warning")
    await manager.broadcast_status("stopping", {"task": zalo_state["current_task"]})

    return {"status": "stopping", "message": "Zalo task is being stopped"}


@router.post("/pause")
async def pause_zalo():
    """Tạm dừng Zalo task"""
    if not zalo_state["is_running"]:
        raise HTTPException(status_code=400, detail="No Zalo task is running")
    
    zalo_state["is_paused"] = True
    await log_to_ws("Đã tạm dừng", "warning")
    await manager.broadcast_status("paused", {"task": zalo_state["current_task"]})
    
    return {"status": "paused"}


@router.post("/resume")
async def resume_zalo():
    """Tiếp tục Zalo task"""
    if not zalo_state["is_running"]:
        raise HTTPException(status_code=400, detail="No Zalo task is running")
    
    zalo_state["is_paused"] = False
    await log_to_ws("Đã tiếp tục", "info")
    await manager.broadcast_status("running", {"task": zalo_state["current_task"]})
    
    return {"status": "resumed"}
