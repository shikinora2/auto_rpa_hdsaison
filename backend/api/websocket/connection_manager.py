"""
WebSocket Connection Manager
Quản lý các kết nối WebSocket và broadcast log messages
"""
from typing import List, Dict, Any
from fastapi import WebSocket
import asyncio
import json
from datetime import datetime


class ConnectionManager:
    """
    Singleton class để quản lý tất cả các kết nối WebSocket
    Thay thế function log_to_gui trong code cũ
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.active_connections: List[WebSocket] = []
            cls._instance.log_history: List[Dict[str, Any]] = []
            cls._instance.max_history = 1000  # Giữ tối đa 1000 log gần nhất
        return cls._instance
    
    async def connect(self, websocket: WebSocket):
        """Chấp nhận kết nối WebSocket mới"""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Gửi log history cho client mới
        if self.log_history:
            await websocket.send_json({
                "type": "history",
                "data": self.log_history[-100:]  # Gửi 100 log gần nhất
            })
    
    def disconnect(self, websocket: WebSocket):
        """Ngắt kết nối WebSocket"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: str, level: str = "info"):
        """
        Broadcast log message đến tất cả clients
        
        Args:
            message: Nội dung log
            level: Cấp độ log (info, warning, error, success)
        """
        log_entry = {
            "type": "log",
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        }
        
        # Lưu vào history
        self.log_history.append(log_entry)
        if len(self.log_history) > self.max_history:
            self.log_history = self.log_history[-self.max_history:]
        
        # Broadcast đến tất cả clients
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(log_entry)
            except Exception:
                disconnected.append(connection)
        
        # Xóa các kết nối đã ngắt
        for conn in disconnected:
            self.disconnect(conn)
    
    async def broadcast_progress(self, current: int, total: int, message: str = ""):
        """
        Broadcast tiến độ xử lý
        
        Args:
            current: Số lượng đã xử lý
            total: Tổng số lượng
            message: Thông báo kèm theo
        """
        progress_entry = {
            "type": "progress",
            "timestamp": datetime.now().isoformat(),
            "current": current,
            "total": total,
            "percentage": round((current / total) * 100, 1) if total > 0 else 0,
            "message": message
        }
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(progress_entry)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)
    
    async def broadcast_qr(self, qr_base64: str, account_id: str = None):
        """Broadcast QR code image (base64) cho tất cả clients"""
        entry = {
            "type": "qr_image",
            "timestamp": datetime.now().isoformat(),
            "qr_base64": qr_base64,
            "account_id": account_id,
        }
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(entry)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_status(self, status: str, data: Dict[str, Any] = None):
        """
        Broadcast trạng thái hệ thống
        
        Args:
            status: Trạng thái (running, paused, stopped, completed, error)
            data: Dữ liệu bổ sung
        """
        status_entry = {
            "type": "status",
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "data": data or {}
        }
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(status_entry)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)
    
    def clear_history(self):
        """Xóa log history"""
        self.log_history = []
    
    @property
    def connection_count(self) -> int:
        """Số lượng kết nối đang hoạt động"""
        return len(self.active_connections)


# Singleton instance
manager = ConnectionManager()


def get_log_callback():
    """
    Tạo callback function để thay thế log_to_gui
    Sử dụng trong các hàm logic cũ (sync)
    """
    def log_callback(message: str, level: str = "info"):
        """Callback sync để gọi từ code sync"""
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(manager.broadcast(message, level), loop)
        except RuntimeError:
            # Không có event loop đang chạy, bỏ qua (hoặc print)
            print(f"[{level.upper()}] {message}")
    
    return log_callback


async def log_to_ws(message: str, level: str = "info"):
    """
    Async function để log trực tiếp qua WebSocket
    Sử dụng trong các async functions
    """
    await manager.broadcast(message, level)
