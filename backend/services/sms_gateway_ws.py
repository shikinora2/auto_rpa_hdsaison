"""
WebSocket hub for Android SMS Gateway devices.
Devices keep an outbound WebSocket connection to VPS and receive commands.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import WebSocket


class SmsGatewayWsHub:
    """Tracks connected devices and supports request/response messaging."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._connection_meta: dict[str, dict[str, Any]] = {}
        self._ws_to_device: dict[int, str] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self._pending_owner: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()

    async def authenticate_device(
        self,
        websocket: WebSocket,
        *,
        device_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        device_id = str(device_id or "").strip()
        if not device_id:
            raise ValueError("device_id is required")

        ws_key = id(websocket)
        meta = dict(metadata or {})
        meta["device_id"] = device_id
        meta["last_seen"] = datetime.now().isoformat()

        async with self._lock:
            existing_ws = self._connections.get(device_id)
            if existing_ws and existing_ws is not websocket:
                try:
                    await existing_ws.close(code=1012, reason="Replaced by newer session")
                except Exception:
                    pass
                old_ws_key = id(existing_ws)
                self._ws_to_device.pop(old_ws_key, None)

            self._connections[device_id] = websocket
            self._connection_meta[device_id] = meta
            self._ws_to_device[ws_key] = device_id

        return meta

    async def disconnect(self, websocket: WebSocket) -> None:
        ws_key = id(websocket)

        async with self._lock:
            device_id = self._ws_to_device.pop(ws_key, None)
            if device_id:
                self._connections.pop(device_id, None)
                self._connection_meta.pop(device_id, None)

            to_fail = [req_id for req_id, owner in self._pending_owner.items() if owner == ws_key]
            for req_id in to_fail:
                future = self._pending.pop(req_id, None)
                self._pending_owner.pop(req_id, None)
                if future and not future.done():
                    future.set_exception(ConnectionError("Device disconnected before response"))

    async def refresh_heartbeat(self, websocket: WebSocket) -> None:
        ws_key = id(websocket)
        async with self._lock:
            device_id = self._ws_to_device.get(ws_key)
            if not device_id:
                return
            meta = self._connection_meta.get(device_id, {})
            meta["last_seen"] = datetime.now().isoformat()
            self._connection_meta[device_id] = meta

    def list_devices(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for device_id, meta in self._connection_meta.items():
            rows.append(
                {
                    "device_id": device_id,
                    "device_name": meta.get("device_name"),
                    "platform": meta.get("platform"),
                    "app_version": meta.get("app_version"),
                    "last_seen": meta.get("last_seen"),
                }
            )
        rows.sort(key=lambda x: str(x.get("last_seen") or ""), reverse=True)
        return rows

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def request_device(
        self,
        command: str,
        payload: dict[str, Any] | None = None,
        *,
        device_id: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> dict[str, Any]:
        selected_device_id, websocket = self._pick_connection(device_id)
        if not websocket:
            raise RuntimeError("No SMS Gateway device connected via WebSocket")

        request_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        ws_key = id(websocket)

        async with self._lock:
            self._pending[request_id] = future
            self._pending_owner[request_id] = ws_key

        try:
            await websocket.send_json(
                {
                    "type": "command",
                    "request_id": request_id,
                    "command": command,
                    "payload": payload or {},
                    "timestamp": datetime.now().isoformat(),
                }
            )
            response = await asyncio.wait_for(future, timeout=timeout_seconds)
            if isinstance(response, dict):
                response.setdefault("device_id", selected_device_id)
            return response
        finally:
            async with self._lock:
                self._pending.pop(request_id, None)
                self._pending_owner.pop(request_id, None)

    async def resolve_response(self, websocket: WebSocket, message: dict[str, Any]) -> bool:
        request_id = str(message.get("request_id") or "").strip()
        if not request_id:
            return False

        ws_key = id(websocket)
        async with self._lock:
            owner = self._pending_owner.get(request_id)
            future = self._pending.get(request_id)

        if owner != ws_key or future is None:
            return False

        if not future.done():
            future.set_result(message)
        await self.refresh_heartbeat(websocket)
        return True

    def _pick_connection(self, preferred_device_id: str | None) -> tuple[str | None, WebSocket | None]:
        preferred_device_id = str(preferred_device_id or "").strip()
        if preferred_device_id:
            return preferred_device_id, self._connections.get(preferred_device_id)

        if not self._connections:
            return None, None

        # Select most recently active device.
        latest_device_id = None
        latest_seen = ""
        for device_id, meta in self._connection_meta.items():
            seen = str(meta.get("last_seen") or "")
            if seen >= latest_seen:
                latest_seen = seen
                latest_device_id = device_id

        if not latest_device_id:
            latest_device_id = next(iter(self._connections.keys()))

        return latest_device_id, self._connections.get(latest_device_id)


sms_gateway_ws_hub = SmsGatewayWsHub()


def parse_ws_json(raw_text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw_text)
    except Exception:
        return None
    return data if isinstance(data, dict) else None
