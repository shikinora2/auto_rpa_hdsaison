"""
RPA API Routes
API endpoints cho các tính năng RPA
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional
import threading
import asyncio
import concurrent.futures
from pathlib import Path
import shutil
from datetime import datetime
import re

from api.websocket.connection_manager import manager, log_to_ws
from api.routes.config import load_config
from config.settings import DOWNLOADS_DIR
from api.deps.auth import require_roles

# Thread pool cho việc chạy sync callbacks
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

router = APIRouter(dependencies=[Depends(require_roles("admin", "user"))])

# Global state để quản lý RPA tasks
rpa_state = {
    "is_running": False,
    "is_paused": False,
    "current_task": None,
    "pause_event": threading.Event(),
    "stop_event": threading.Event()
}

_rpa_state_lock = threading.Lock()

# Set pause_event để mặc định không pause
rpa_state["pause_event"].set()


def _start_rpa_task(task_name: str):
    with _rpa_state_lock:
        if rpa_state["is_running"]:
            raise HTTPException(status_code=400, detail="Another RPA task is already running")
        rpa_state["stop_event"].clear()
        rpa_state["pause_event"].set()
        rpa_state["is_running"] = True
        rpa_state["is_paused"] = False
        rpa_state["current_task"] = task_name


def _finish_rpa_task():
    with _rpa_state_lock:
        rpa_state["is_running"] = False
        rpa_state["is_paused"] = False
        rpa_state["current_task"] = None


class RPARequest(BaseModel):
    """Schema cho RPA request"""
    username: Optional[str] = None
    password: Optional[str] = None
    start_date: str  # Format: dd/mm/yyyy
    end_date: str    # Format: dd/mm/yyyy
    headless: Optional[bool] = None


class DownloadRequest(RPARequest):
    """Schema cho download request"""
    save_directory: Optional[str] = None
    save_format: Optional[str] = "PDF"  # PDF hoặc JSON


def _resolve_save_directory(raw_path: Optional[str]) -> str:
    """Lấy thư mục lưu hợp lệ; fallback về DOWNLOADS_DIR khi không có cấu hình."""
    path = (raw_path or "").strip()
    if not path:
        path = str(DOWNLOADS_DIR)

    resolved = Path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return str(resolved)


def _make_month_folder_name(start_date_ddmmyyyy: str) -> str:
    return f"{start_date_ddmmyyyy[2:4]}{start_date_ddmmyyyy[4:8]}"


def _create_task_zip_artifact(save_directory: str, start_date_ddmmyyyy: str, task_prefix: str) -> Optional[str]:
    """Nén thư mục kết quả theo tháng thành 1 file zip trong DOWNLOADS_DIR để FE auto-download."""
    try:
        month_folder = _make_month_folder_name(start_date_ddmmyyyy)
        source_dir = Path(save_directory) / month_folder
        if not source_dir.exists() or not source_dir.is_dir():
            return None

        # Không tạo artifact nếu thư mục rỗng
        if not any(source_dir.iterdir()):
            return None

        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_stem = f"{task_prefix}_{month_folder}_{ts}"
        zip_path_no_ext = DOWNLOADS_DIR / zip_stem

        shutil.make_archive(str(zip_path_no_ext), "zip", root_dir=str(source_dir.parent), base_dir=source_dir.name)
        return f"{zip_stem}.zip"
    except Exception:
        return None


def _new_progress_tracker(task_name: str) -> dict:
    return {
        "task": task_name,
        "total": 0,
        "current": 0,
        "last_key": None,
    }


def _broadcast_progress_from_thread(loop, tracker: dict, current: int, total: int, message: str):
    if total <= 0:
        return

    normalized_current = max(0, min(current, total))
    key = (normalized_current, total, message)
    if tracker.get("last_key") == key:
        return

    tracker["total"] = total
    tracker["current"] = normalized_current
    tracker["last_key"] = key

    asyncio.run_coroutine_threadsafe(
        manager.broadcast_progress(normalized_current, total, message),
        loop,
    )


def _track_rpa_progress(loop, tracker: dict, message: str):
    text = str(message or "").strip()
    if not text:
        return

    total = int(tracker.get("total") or 0)

    # Mốc tổng số hợp đồng
    total_match = (
        re.search(r"Tìm thấy\s+(\d+)\s+ID hợp đồng", text, flags=re.IGNORECASE)
        or re.search(r"TỔNG CỘNG\s+(\d+)\s+HỢP ĐỒNG", text, flags=re.IGNORECASE)
        or re.search(r"BẮT ĐẦU\s+(?:XỬ LÝ|CÀO).*?(\d+)\s+HỢP ĐỒNG", text, flags=re.IGNORECASE)
    )
    if total_match:
        total = int(total_match.group(1))
        _broadcast_progress_from_thread(loop, tracker, 0, total, f"Tổng số hợp đồng: {total}")

    # Mốc đang quét hợp đồng thứ bao nhiêu
    current_match = re.search(r"HĐ\s*#\s*(\d+)\s*/\s*(\d+)", text, flags=re.IGNORECASE)
    if current_match:
        current = int(current_match.group(1))
        total_from_message = int(current_match.group(2))
        total = total_from_message if total_from_message > 0 else total
        _broadcast_progress_from_thread(
            loop,
            tracker,
            current,
            total,
            f"Đang quét hợp đồng {current}/{total}",
        )

    # Mốc hoàn tất
    done_match = (
        re.search(r"HOÀN TẤT!\s*ĐÃ\s*XỬ\s*LÝ\s*TẤT\s*CẢ\s*(\d+)\s*HỢP\s*ĐỒNG", text, flags=re.IGNORECASE)
        or re.search(r"KIỂM TRA\s*HOÀN\s*TẤT:\s*TÌM\s*THẤY\s*TỔNG\s*CỘNG\s*(\d+)\s*HỢP\s*ĐỒNG", text, flags=re.IGNORECASE)
    )
    if done_match:
        done_total = int(done_match.group(1))
        _broadcast_progress_from_thread(
            loop,
            tracker,
            done_total,
            done_total,
            f"Hoàn tất quét {done_total}/{done_total} hợp đồng",
        )


def _build_progress_summary(tracker: dict) -> Optional[dict]:
    total = int(tracker.get("total") or 0)
    current = int(tracker.get("current") or 0)
    if total <= 0:
        return None

    normalized_current = max(0, min(current, total))
    return {
        "current": normalized_current,
        "total": total,
        "percentage": round((normalized_current / total) * 100, 1) if total else 0,
        "message": (
            f"Hoàn tất quét {normalized_current}/{total} hợp đồng"
            if normalized_current >= total
            else f"Đang quét hợp đồng {normalized_current}/{total}"
        ),
    }


@router.get("/status")
async def get_status():
    """Lấy trạng thái hiện tại của RPA"""
    with _rpa_state_lock:
        state = {
            "is_running": rpa_state["is_running"],
            "is_paused": rpa_state["is_paused"],
            "current_task": rpa_state["current_task"],
        }
    return {
        "is_running": state["is_running"],
        "is_paused": state["is_paused"],
        "current_task": state["current_task"]
    }


@router.post("/check-contracts")
async def check_contracts(request: RPARequest, background_tasks: BackgroundTasks):
    """
    Kiểm tra số lượng hợp đồng trong khoảng thời gian
    Chạy trong background task
    """
    # Lấy credentials từ config nếu không có trong request
    config = load_config()
    username = request.username or config.get("username", "")
    password = request.password or config.get("password", "")
    headless = request.headless if request.headless is not None else config.get("headless", False)
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    
    _start_rpa_task("check_contracts")
    
    # Chạy trong background
    background_tasks.add_task(
        run_check_contracts_task,
        username, password,
        request.start_date, request.end_date,
        headless
    )
    
    return {
        "status": "started",
        "message": "Contract check task started",
        "task": "check_contracts"
    }


async def run_check_contracts_task(username, password, start_date, end_date, headless):
    """Background task để chạy check_contract_count"""
    try:
        await log_to_ws(f"Bắt đầu kiểm tra hợp đồng từ {start_date} đến {end_date}", "info")
        await manager.broadcast_status("running", {"task": "check_contracts"})
        
        # Import và chạy logic
        from logic.rpa_logic import check_contract_count
        
        # Lấy event loop hiện tại
        loop = asyncio.get_running_loop()
        progress_tracker = _new_progress_tracker("check_contracts")
        
        def callback(message):
            # Schedule coroutine trong event loop đang chạy
            _track_rpa_progress(loop, progress_tracker, message)
            asyncio.run_coroutine_threadsafe(log_to_ws(message, "info"), loop)
        
        # Chạy sync function trong thread pool để không block event loop
        result = await loop.run_in_executor(
            _executor,
            lambda: check_contract_count(
                username, password,
                start_date, end_date,
                rpa_state["pause_event"],
                rpa_state["stop_event"],
                status_callback=callback,
                headless=headless
            )
        )

        progress_summary = _build_progress_summary(progress_tracker)
        if progress_summary and progress_summary["current"] < progress_summary["total"]:
            _broadcast_progress_from_thread(
                loop,
                progress_tracker,
                progress_summary["total"],
                progress_summary["total"],
                f"Hoàn tất quét {progress_summary['total']}/{progress_summary['total']} hợp đồng",
            )
            progress_summary = _build_progress_summary(progress_tracker)
        
        await log_to_ws(f"Hoàn thành kiểm tra: {result}", "success")
        await manager.broadcast_status("completed", {
            "task": "check_contracts",
            "result": result,
            "progress_summary": progress_summary,
        })
        
    except Exception as e:
        await log_to_ws(f"Lỗi: {str(e)}", "error")
        await manager.broadcast_status("error", {"task": "check_contracts", "error": str(e)})
    finally:
        _finish_rpa_task()


@router.post("/download-files")
async def download_files(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    Tải file PDF/JSON từ hệ thống
    Chạy trong background task
    """
    config = load_config()
    username = request.username or config.get("username", "")
    password = request.password or config.get("password", "")
    headless = request.headless if request.headless is not None else config.get("headless", False)
    save_directory = _resolve_save_directory(request.save_directory)
    save_format = request.save_format or config.get("save_format", "PDF")
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    
    _start_rpa_task("download_files")
    
    background_tasks.add_task(
        run_download_files_task,
        username, password,
        request.start_date, request.end_date,
        save_directory, save_format,
        headless
    )
    
    return {
        "status": "started",
        "message": "Download files task started",
        "task": "download_files"
    }


async def run_download_files_task(username, password, start_date, end_date, 
                                   save_directory, save_format, headless):
    """Background task để chạy run_scrape_and_download_files"""
    try:
        await log_to_ws(f"Bắt đầu tải file từ {start_date} đến {end_date}", "info")
        await manager.broadcast_status("running", {"task": "download_files"})
        
        from logic.rpa_logic import run_scrape_and_download_files
        
        loop = asyncio.get_running_loop()
        progress_tracker = _new_progress_tracker("download_files")
        
        def callback(message):
            _track_rpa_progress(loop, progress_tracker, message)
            asyncio.run_coroutine_threadsafe(log_to_ws(message, "info"), loop)
        
        result = await loop.run_in_executor(
            _executor,
            lambda: run_scrape_and_download_files(
                username, password,
                start_date, end_date,
                save_directory,
                save_format,
                rpa_state["pause_event"],
                rpa_state["stop_event"],
                status_callback=callback,
                headless=headless
            )
        )

        progress_summary = _build_progress_summary(progress_tracker)
        if progress_summary and progress_summary["current"] < progress_summary["total"]:
            _broadcast_progress_from_thread(
                loop,
                progress_tracker,
                progress_summary["total"],
                progress_summary["total"],
                f"Hoàn tất quét {progress_summary['total']}/{progress_summary['total']} hợp đồng",
            )
            progress_summary = _build_progress_summary(progress_tracker)

        artifact_filename = _create_task_zip_artifact(save_directory, start_date, "rpa_downloads")
        if artifact_filename:
            await log_to_ws(f"Đã tạo file tải tự động: {artifact_filename}", "success")

        await log_to_ws("Hoàn thành tải file", "success")
        await manager.broadcast_status("completed", {
            "task": "download_files",
            "artifact_filename": artifact_filename,
            "result": result,
            "progress_summary": progress_summary,
        })
        
    except Exception as e:
        await log_to_ws(f"Lỗi: {str(e)}", "error")
        await manager.broadcast_status("error", {"task": "download_files", "error": str(e)})
    finally:
        _finish_rpa_task()


@router.post("/scrape-details")
async def scrape_details(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    Cào chi tiết hợp đồng và xuất Excel
    """
    config = load_config()
    username = request.username or config.get("username", "")
    password = request.password or config.get("password", "")
    headless = request.headless if request.headless is not None else config.get("headless", False)
    save_directory = _resolve_save_directory(request.save_directory)
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    
    _start_rpa_task("scrape_details")
    
    background_tasks.add_task(
        run_scrape_details_task,
        username, password,
        request.start_date, request.end_date,
        save_directory, headless
    )
    
    return {
        "status": "started",
        "message": "Scrape details task started",
        "task": "scrape_details"
    }


async def run_scrape_details_task(username, password, start_date, end_date, 
                                   save_directory, headless):
    """Background task để chạy run_scrape_and_export_details"""
    try:
        await log_to_ws(f"Bắt đầu cào chi tiết từ {start_date} đến {end_date}", "info")
        await manager.broadcast_status("running", {"task": "scrape_details"})
        
        from logic.rpa_logic import run_scrape_and_export_details
        
        loop = asyncio.get_running_loop()
        progress_tracker = _new_progress_tracker("scrape_details")
        
        def callback(message):
            _track_rpa_progress(loop, progress_tracker, message)
            asyncio.run_coroutine_threadsafe(log_to_ws(message, "info"), loop)
        
        result = await loop.run_in_executor(
            _executor,
            lambda: run_scrape_and_export_details(
                username, password,
                start_date, end_date,
                save_directory,
                rpa_state["pause_event"],
                rpa_state["stop_event"],
                status_callback=callback,
                headless=headless
            )
        )

        progress_summary = _build_progress_summary(progress_tracker)
        if progress_summary and progress_summary["current"] < progress_summary["total"]:
            _broadcast_progress_from_thread(
                loop,
                progress_tracker,
                progress_summary["total"],
                progress_summary["total"],
                f"Hoàn tất quét {progress_summary['total']}/{progress_summary['total']} hợp đồng",
            )
            progress_summary = _build_progress_summary(progress_tracker)

        artifact_filename = _create_task_zip_artifact(save_directory, start_date, "rpa_details")
        if artifact_filename:
            await log_to_ws(f"Đã tạo file tải tự động: {artifact_filename}", "success")

        await log_to_ws("Hoàn thành cào chi tiết", "success")
        await manager.broadcast_status("completed", {
            "task": "scrape_details",
            "artifact_filename": artifact_filename,
            "result": result,
            "progress_summary": progress_summary,
        })
        
    except Exception as e:
        await log_to_ws(f"Lỗi: {str(e)}", "error")
        await manager.broadcast_status("error", {"task": "scrape_details", "error": str(e)})
    finally:
        _finish_rpa_task()


@router.post("/pause")
async def pause_rpa():
    """Tạm dừng RPA task đang chạy"""
    with _rpa_state_lock:
        if not rpa_state["is_running"]:
            raise HTTPException(status_code=400, detail="No RPA task is running")
        if rpa_state["is_paused"]:
            raise HTTPException(status_code=400, detail="Task is already paused")
        rpa_state["pause_event"].clear()
        rpa_state["is_paused"] = True
        current_task = rpa_state["current_task"]
    
    await log_to_ws("Đã tạm dừng tác vụ", "warning")
    await manager.broadcast_status("paused", {"task": current_task})
    
    return {"status": "paused", "message": "RPA task paused"}


@router.post("/resume")
async def resume_rpa():
    """Tiếp tục RPA task đang tạm dừng"""
    with _rpa_state_lock:
        if not rpa_state["is_running"]:
            raise HTTPException(status_code=400, detail="No RPA task is running")
        if not rpa_state["is_paused"]:
            raise HTTPException(status_code=400, detail="Task is not paused")
        rpa_state["pause_event"].set()
        rpa_state["is_paused"] = False
        current_task = rpa_state["current_task"]
    
    await log_to_ws("Đã tiếp tục tác vụ", "info")
    await manager.broadcast_status("running", {"task": current_task})
    
    return {"status": "resumed", "message": "RPA task resumed"}


@router.post("/stop")
async def stop_rpa():
    """Dừng hẳn RPA task đang chạy"""
    with _rpa_state_lock:
        if not rpa_state["is_running"]:
            raise HTTPException(status_code=400, detail="No RPA task is running")
        rpa_state["stop_event"].set()
        rpa_state["pause_event"].set()  # Đảm bảo không bị block
        current_task = rpa_state["current_task"]
    
    await log_to_ws("Đang dừng tác vụ...", "warning")
    await manager.broadcast_status("stopping", {"task": current_task})
    
    return {"status": "stopping", "message": "RPA task is being stopped"}


# ============== Session Management ==============

class LoginRequest(BaseModel):
    """Schema cho login request"""
    username: str
    password: str
    headless: Optional[bool] = False


@router.get("/session")
async def check_session(force: bool = False, current_user=Depends(require_roles("admin", "user"))):
    """
    Kiểm tra trạng thái session đăng nhập HPO.
    - force=False (mặc định): trả về trạng thái cache nhanh, không mở browser.
    - force=True: kiểm tra thực tế qua Playwright (chậm hơn, dành cho nút reload).
    """
    from services.rpa_session_manager import get_rpa_session_manager

    session_manager = get_rpa_session_manager(current_user["id"])

    if not force:
        # Fast path: trả về trạng thái đã lưu trong bộ nhớ, không launch browser
        cached_valid = session_manager.get_cached_session_valid()
        return {
            "is_logged_in": cached_valid,
            "message": "Session hợp lệ" if cached_valid else "Chưa đăng nhập hoặc session hết hạn"
        }

    # Slow path: kiểm tra thực tế qua Playwright (chỉ khi người dùng bấm nút kiểm tra)
    async def callback(msg):
        await log_to_ws(msg, "info")

    is_valid = await session_manager.check_session_valid(status_callback=callback)

    return {
        "is_logged_in": is_valid,
        "message": "Session hợp lệ" if is_valid else "Chưa đăng nhập hoặc session hết hạn"
    }


@router.post("/login")
async def login_hpo(request: LoginRequest, background_tasks: BackgroundTasks, current_user=Depends(require_roles("admin", "user"))):
    """
    Đăng nhập vào HPO và lưu session
    Session được lưu để các lần chạy sau không cần đăng nhập lại
    """
    _start_rpa_task("login")
    
    background_tasks.add_task(
        run_login_task,
        current_user["id"],
        request.username,
        request.password,
        request.headless
    )
    
    return {
        "status": "started",
        "message": "Đang thực hiện đăng nhập..."
    }


async def run_login_task(user_id: int, username: str, password: str, headless: bool):
    """Background task để login HPO"""
    try:
        await log_to_ws("Đang khởi tạo đăng nhập HPO...", "info")
        await manager.broadcast_status("running", {"task": "login"})
        
        from services.rpa_session_manager import get_rpa_session_manager
        
        session_manager = get_rpa_session_manager(user_id)
        
        async def callback(msg):
            await log_to_ws(msg, "info")
        
        success = await session_manager.login(
            username=username,
            password=password,
            headless=headless,
            status_callback=callback
        )
        
        if success:
            await log_to_ws("✅ Đăng nhập thành công! Session đã được lưu.", "success")
            await manager.broadcast_status("completed", {"task": "login", "success": True})
        else:
            await log_to_ws("❌ Đăng nhập thất bại!", "error")
            await manager.broadcast_status("error", {"task": "login"})
            
    except Exception as e:
        await log_to_ws(f"Lỗi: {str(e)}", "error")
        await manager.broadcast_status("error", {"task": "login", "error": str(e)})
    finally:
        _finish_rpa_task()


@router.post("/logout")
async def logout_hpo(current_user=Depends(require_roles("admin", "user"))):
    """Đăng xuất và xóa session HPO"""
    from services.rpa_session_manager import get_rpa_session_manager
    
    session_manager = get_rpa_session_manager(current_user["id"])
    
    async def callback(msg):
        await log_to_ws(msg, "info")
    
    success = await session_manager.logout(status_callback=callback)
    
    if success:
        await log_to_ws("Đã đăng xuất HPO", "info")
        return {"status": "success", "message": "Đã đăng xuất"}
    else:
        raise HTTPException(status_code=500, detail="Không thể đăng xuất")
