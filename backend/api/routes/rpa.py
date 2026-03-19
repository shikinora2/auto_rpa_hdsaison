"""
RPA API Routes
API endpoints cho các tính năng RPA
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import threading
import asyncio
import concurrent.futures

from api.websocket.connection_manager import manager, log_to_ws
from api.routes.config import load_config

# Thread pool cho việc chạy sync callbacks
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

router = APIRouter()

# Global state để quản lý RPA tasks
rpa_state = {
    "is_running": False,
    "is_paused": False,
    "current_task": None,
    "pause_event": threading.Event(),
    "stop_event": threading.Event()
}

# Set pause_event để mặc định không pause
rpa_state["pause_event"].set()


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


@router.get("/status")
async def get_status():
    """Lấy trạng thái hiện tại của RPA"""
    return {
        "is_running": rpa_state["is_running"],
        "is_paused": rpa_state["is_paused"],
        "current_task": rpa_state["current_task"]
    }


@router.post("/check-contracts")
async def check_contracts(request: RPARequest, background_tasks: BackgroundTasks):
    """
    Kiểm tra số lượng hợp đồng trong khoảng thời gian
    Chạy trong background task
    """
    if rpa_state["is_running"]:
        raise HTTPException(status_code=400, detail="Another RPA task is already running")
    
    # Lấy credentials từ config nếu không có trong request
    config = load_config()
    username = request.username or config.get("username", "")
    password = request.password or config.get("password", "")
    headless = request.headless if request.headless is not None else config.get("headless", False)
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    
    # Reset events
    rpa_state["stop_event"].clear()
    rpa_state["pause_event"].set()
    rpa_state["is_running"] = True
    rpa_state["is_paused"] = False
    rpa_state["current_task"] = "check_contracts"
    
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
        
        def callback(message):
            # Schedule coroutine trong event loop đang chạy
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
        
        await log_to_ws(f"Hoàn thành kiểm tra: {result}", "success")
        await manager.broadcast_status("completed", {"task": "check_contracts", "result": result})
        
    except Exception as e:
        await log_to_ws(f"Lỗi: {str(e)}", "error")
        await manager.broadcast_status("error", {"task": "check_contracts", "error": str(e)})
    finally:
        rpa_state["is_running"] = False
        rpa_state["current_task"] = None


@router.post("/download-files")
async def download_files(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    Tải file PDF/JSON từ hệ thống
    Chạy trong background task
    """
    if rpa_state["is_running"]:
        raise HTTPException(status_code=400, detail="Another RPA task is already running")
    
    config = load_config()
    username = request.username or config.get("username", "")
    password = request.password or config.get("password", "")
    headless = request.headless if request.headless is not None else config.get("headless", False)
    save_directory = request.save_directory or config.get("save_directory", "")
    save_format = request.save_format or config.get("save_format", "PDF")
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    
    if not save_directory:
        raise HTTPException(status_code=400, detail="Save directory is required")
    
    # Reset events
    rpa_state["stop_event"].clear()
    rpa_state["pause_event"].set()
    rpa_state["is_running"] = True
    rpa_state["is_paused"] = False
    rpa_state["current_task"] = "download_files"
    
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
        
        def callback(message):
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
        
        await log_to_ws("Hoàn thành tải file", "success")
        await manager.broadcast_status("completed", {"task": "download_files"})
        
    except Exception as e:
        await log_to_ws(f"Lỗi: {str(e)}", "error")
        await manager.broadcast_status("error", {"task": "download_files", "error": str(e)})
    finally:
        rpa_state["is_running"] = False
        rpa_state["current_task"] = None


@router.post("/scrape-details")
async def scrape_details(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    Cào chi tiết hợp đồng và xuất Excel
    """
    if rpa_state["is_running"]:
        raise HTTPException(status_code=400, detail="Another RPA task is already running")
    
    config = load_config()
    username = request.username or config.get("username", "")
    password = request.password or config.get("password", "")
    headless = request.headless if request.headless is not None else config.get("headless", False)
    save_directory = request.save_directory or config.get("save_directory", "")
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    
    rpa_state["stop_event"].clear()
    rpa_state["pause_event"].set()
    rpa_state["is_running"] = True
    rpa_state["is_paused"] = False
    rpa_state["current_task"] = "scrape_details"
    
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
        
        def callback(message):
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
        
        await log_to_ws("Hoàn thành cào chi tiết", "success")
        await manager.broadcast_status("completed", {"task": "scrape_details"})
        
    except Exception as e:
        await log_to_ws(f"Lỗi: {str(e)}", "error")
        await manager.broadcast_status("error", {"task": "scrape_details", "error": str(e)})
    finally:
        rpa_state["is_running"] = False
        rpa_state["current_task"] = None


@router.post("/pause")
async def pause_rpa():
    """Tạm dừng RPA task đang chạy"""
    if not rpa_state["is_running"]:
        raise HTTPException(status_code=400, detail="No RPA task is running")
    
    if rpa_state["is_paused"]:
        raise HTTPException(status_code=400, detail="Task is already paused")
    
    rpa_state["pause_event"].clear()
    rpa_state["is_paused"] = True
    
    await log_to_ws("Đã tạm dừng tác vụ", "warning")
    await manager.broadcast_status("paused", {"task": rpa_state["current_task"]})
    
    return {"status": "paused", "message": "RPA task paused"}


@router.post("/resume")
async def resume_rpa():
    """Tiếp tục RPA task đang tạm dừng"""
    if not rpa_state["is_running"]:
        raise HTTPException(status_code=400, detail="No RPA task is running")
    
    if not rpa_state["is_paused"]:
        raise HTTPException(status_code=400, detail="Task is not paused")
    
    rpa_state["pause_event"].set()
    rpa_state["is_paused"] = False
    
    await log_to_ws("Đã tiếp tục tác vụ", "info")
    await manager.broadcast_status("running", {"task": rpa_state["current_task"]})
    
    return {"status": "resumed", "message": "RPA task resumed"}


@router.post("/stop")
async def stop_rpa():
    """Dừng hẳn RPA task đang chạy"""
    if not rpa_state["is_running"]:
        raise HTTPException(status_code=400, detail="No RPA task is running")
    
    rpa_state["stop_event"].set()
    rpa_state["pause_event"].set()  # Đảm bảo không bị block
    
    await log_to_ws("Đang dừng tác vụ...", "warning")
    await manager.broadcast_status("stopping", {"task": rpa_state["current_task"]})
    
    return {"status": "stopping", "message": "RPA task is being stopped"}


# ============== Session Management ==============

class LoginRequest(BaseModel):
    """Schema cho login request"""
    username: str
    password: str
    headless: Optional[bool] = False


@router.get("/session")
async def check_session(force: bool = False):
    """
    Kiểm tra trạng thái session đăng nhập HPO.
    - force=False (mặc định): trả về trạng thái cache nhanh, không mở browser.
    - force=True: kiểm tra thực tế qua Playwright (chậm hơn, dành cho nút reload).
    """
    from services.rpa_session_manager import get_rpa_session_manager

    session_manager = get_rpa_session_manager()

    if not force:
        # Fast path: trả về trạng thái đã lưu trong bộ nhớ, không launch browser
        return {
            "is_logged_in": session_manager.is_logged_in,
            "message": "Session hợp lệ" if session_manager.is_logged_in else "Chưa đăng nhập hoặc session hết hạn"
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
async def login_hpo(request: LoginRequest, background_tasks: BackgroundTasks):
    """
    Đăng nhập vào HPO và lưu session
    Session được lưu để các lần chạy sau không cần đăng nhập lại
    """
    if rpa_state["is_running"]:
        raise HTTPException(status_code=400, detail="Có task RPA đang chạy")
    
    rpa_state["is_running"] = True
    rpa_state["current_task"] = "login"
    
    background_tasks.add_task(
        run_login_task,
        request.username,
        request.password,
        request.headless
    )
    
    return {
        "status": "started",
        "message": "Đang thực hiện đăng nhập..."
    }


async def run_login_task(username: str, password: str, headless: bool):
    """Background task để login HPO"""
    try:
        await log_to_ws("Đang khởi tạo đăng nhập HPO...", "info")
        await manager.broadcast_status("running", {"task": "login"})
        
        from services.rpa_session_manager import get_rpa_session_manager
        
        session_manager = get_rpa_session_manager()
        
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
        rpa_state["is_running"] = False
        rpa_state["current_task"] = None


@router.post("/logout")
async def logout_hpo():
    """Đăng xuất và xóa session HPO"""
    from services.rpa_session_manager import get_rpa_session_manager
    
    session_manager = get_rpa_session_manager()
    
    async def callback(msg):
        await log_to_ws(msg, "info")
    
    success = await session_manager.logout(status_callback=callback)
    
    if success:
        await log_to_ws("Đã đăng xuất HPO", "info")
        return {"status": "success", "message": "Đã đăng xuất"}
    else:
        raise HTTPException(status_code=500, detail="Không thể đăng xuất")
