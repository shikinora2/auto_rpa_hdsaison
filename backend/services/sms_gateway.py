"""
SMS Gateway Service
Dịch vụ giao tiếp với Android SMS Gateway app (Local Mode)
API docs: https://capcom6.github.io/android-sms-gateway/
"""
import json
import uuid
import asyncio
import aiohttp
from aiohttp import BasicAuth
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import SMS_GATEWAY_CONFIG_FILE, SMS_HISTORY_FILE


DEFAULT_CONFIG = {
    "device_ip": "",
    "device_port": 8080,
    "username": "",
    "password": "",
    "enabled": False,
}


class SmsGatewayService:
    """Service tương tác với Android SMS Gateway app qua Local Server mode."""

    # ---------- Config ----------

    @staticmethod
    def load_config() -> dict:
        """Đọc cấu hình gateway từ file JSON."""
        if SMS_GATEWAY_CONFIG_FILE.exists():
            try:
                with open(SMS_GATEWAY_CONFIG_FILE, encoding="utf-8") as f:
                    cfg = json.load(f)
                # Merge với default để đảm bảo đủ keys
                merged = {**DEFAULT_CONFIG, **cfg}
                return merged
            except Exception:
                pass
        return dict(DEFAULT_CONFIG)

    @staticmethod
    def save_config(config: dict) -> None:
        """Lưu cấu hình gateway ra file JSON."""
        SMS_GATEWAY_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        current = SmsGatewayService.load_config()
        current.update(config)
        with open(SMS_GATEWAY_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)

    # ---------- Gateway URL ----------

    @staticmethod
    def _base_url(config: Optional[dict] = None) -> str:
        cfg = config or SmsGatewayService.load_config()
        ip = cfg.get("device_ip", "").strip()
        port = cfg.get("device_port", 8080)
        return f"http://{ip}:{port}"

    @staticmethod
    def _auth(config: Optional[dict] = None) -> BasicAuth:
        cfg = config or SmsGatewayService.load_config()
        return BasicAuth(
            login=cfg.get("username", ""),
            password=cfg.get("password", ""),
        )

    # ---------- Health Check ----------

    @staticmethod
    async def check_health(config: Optional[dict] = None) -> dict:
        """Ping gateway để kiểm tra kết nối. Trả về metadata device nếu có."""
        cfg = config or SmsGatewayService.load_config()
        base_url = SmsGatewayService._base_url(cfg)
        auth = SmsGatewayService._auth(cfg)

        if not cfg.get("device_ip"):
            return {"status": "error", "message": "Chưa cấu hình IP thiết bị Android"}

        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{base_url}/health", auth=auth) as resp:
                    if resp.status == 200:
                        try:
                            body = await resp.json(content_type=None)
                            checks = body.get("checks", {})
                            # Parse metadata hữu ích từ gateway
                            battery = checks.get("battery:level", {}).get("observedValue")
                            charging = checks.get("battery:charging", {}).get("observedValue")
                            internet = checks.get("connection:status", {}).get("observedValue")
                            version = body.get("version", "?")
                            gw_status = body.get("status", "pass")

                            parts = [f"v{version}"]
                            if battery is not None:
                                charge_icon = "⚡" if charging else "🔋"
                                parts.append(f"{charge_icon} Pin {battery}%")
                            if internet is not None:
                                parts.append("🌐 Có mạng" if internet else "📵 Không có mạng")

                            return {
                                "status": "ok" if gw_status == "pass" else "warn",
                                "message": f"Đã kết nối tới {base_url} | " + " · ".join(parts),
                                "device_info": {
                                    "version": version,
                                    "battery": battery,
                                    "charging": bool(charging),
                                    "internet": bool(internet),
                                    "gateway_status": gw_status,
                                },
                            }
                        except Exception:
                            # Nếu không parse được JSON, vẫn coi là OK
                            return {"status": "ok", "message": f"Đã kết nối tới {base_url}"}
                    elif resp.status == 401:
                        return {
                            "status": "error",
                            "message": "Sai username/password (HTTP 401)"
                        }
                    else:
                        return {
                            "status": "error",
                            "message": f"Gateway phản hồi HTTP {resp.status}"
                        }
        except aiohttp.ClientConnectorError:
            return {
                "status": "error",
                "message": f"Không thể kết nối tới {base_url} — kiểm tra IP, port và Gateway app"
            }
        except asyncio.TimeoutError:
            return {
                "status": "error",
                "message": f"Timeout khi kết nối tới {base_url}"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ---------- Send SMS ----------

    @staticmethod
    async def send_sms(
        phone_numbers: list[str],
        text: str,
        config: Optional[dict] = None,
    ) -> dict:
        """
        Gửi SMS qua Android Gateway.
        Trả về dict gồm: success (bool), message_id, response hoặc error.
        """
        cfg = config or SmsGatewayService.load_config()
        base_url = SmsGatewayService._base_url(cfg)
        auth = SmsGatewayService._auth(cfg)

        if not cfg.get("device_ip"):
            return {"success": False, "error": "Chưa cấu hình IP thiết bị Android"}

        # Chuẩn hoá số điện thoại
        phones = [p.strip() for p in phone_numbers if p.strip()]
        if not phones:
            return {"success": False, "error": "Không có số điện thoại hợp lệ"}

        payload = {
            "message": text,
            "phoneNumbers": phones,
        }

        message_id = str(uuid.uuid4())[:8]

        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{base_url}/messages",
                    json=payload,
                    auth=auth,
                ) as resp:
                    resp_body = await resp.json(content_type=None)
                    if resp.status in (200, 201, 202):
                        return {
                            "success": True,
                            "message_id": resp_body.get("id", message_id),
                            "response": resp_body,
                        }
                    else:
                        if isinstance(resp_body, dict):
                            err_msg = resp_body.get('message') or resp_body.get('error') or str(resp_body)
                        else:
                            err_msg = str(resp_body)

                        # Rút gọn nếu quá dài
                        if len(str(err_msg)) > 150:
                            err_msg = str(err_msg)[:147] + "..."

                        return {
                            "success": False,
                            "error": f"Lỗi (HTTP {resp.status}): {err_msg}",
                        }
        except aiohttp.ClientConnectorError:
            return {
                "success": False,
                "error": f"Không thể kết nối tới {base_url} — kiểm tra Gateway app đang chạy"
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout khi gửi SMS"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------- History ----------

    @staticmethod
    def load_history() -> list:
        """Đọc lịch sử gửi SMS."""
        if SMS_HISTORY_FILE.exists():
            try:
                with open(SMS_HISTORY_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    @staticmethod
    def append_history(entry: dict) -> None:
        """Thêm một bản ghi vào lịch sử."""
        history = SmsGatewayService.load_history()
        history.insert(0, entry)  # Mới nhất lên đầu
        # Giữ tối đa 500 bản ghi
        history = history[:500]
        SMS_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SMS_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    @staticmethod
    def clear_history() -> None:
        """Xoá toàn bộ lịch sử."""
        if SMS_HISTORY_FILE.exists():
            SMS_HISTORY_FILE.write_text("[]", encoding="utf-8")
