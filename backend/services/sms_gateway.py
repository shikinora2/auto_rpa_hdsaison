"""
SMS Gateway Service
Dịch vụ giao tiếp với Android SMS Gateway app (Local mode only)
"""
import json
import uuid
import asyncio
import aiohttp
from aiohttp import BasicAuth
from datetime import datetime
from typing import Optional

from config.settings import SMS_GATEWAY_CONFIG_FILE, SMS_HISTORY_FILE


DEFAULT_CONFIG = {
    "connection_mode": "local",
    "device_ip": "",
    "device_port": 8080,
    "username": "",
    "password": "",
    "enabled": False,
    "use_specific_sim": False,
    "sim_number": 1,
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
                merged = {**DEFAULT_CONFIG, **cfg}
                # Force local-only mode, bỏ logic cloud/self-hosted cũ.
                merged["connection_mode"] = "local"
                merged.pop("custom_base_url", None)
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
        current["connection_mode"] = "local"
        current.pop("custom_base_url", None)
        with open(SMS_GATEWAY_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)

    # ---------- Gateway URL ----------

    @staticmethod
    def _base_url(config: Optional[dict] = None) -> str:
        cfg = config or SmsGatewayService.load_config()
        ip = str(cfg.get("device_ip", "")).strip()
        port = cfg.get("device_port", 8080)
        return f"http://{ip}:{port}"

    @staticmethod
    def _auth(config: Optional[dict] = None) -> BasicAuth:
        cfg = config or SmsGatewayService.load_config()
        return BasicAuth(
            login=cfg.get("username", ""),
            password=cfg.get("password", ""),
        )

    @staticmethod
    def _build_message_payload(cfg: dict, phones: list[str], text: str) -> dict:
        payload = {
            "message": text,
            "phoneNumbers": phones,
        }

        if cfg.get("use_specific_sim"):
            try:
                sim_number = int(cfg.get("sim_number", 1))
                if 1 <= sim_number <= 2:
                    payload["simNumber"] = sim_number
            except (TypeError, ValueError):
                pass

        return payload

    # ---------- Health Check ----------

    @staticmethod
    async def check_health(config: Optional[dict] = None) -> dict:
        """Ping gateway để kiểm tra kết nối Local."""
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

                            # /health có thể vẫn 200 dù auth gửi tin sai.
                            # Probe thêm endpoint yêu cầu auth để phát hiện lỗi sớm.
                            try:
                                async with session.get(f"{base_url}/messages", auth=auth) as auth_probe:
                                    if auth_probe.status == 401:
                                        return {
                                            "status": "error",
                                            "message": "Sai username/password cho API gửi SMS (HTTP 401). Vui lòng kiểm tra lại tài khoản trên app Android.",
                                        }
                            except Exception:
                                # Nếu endpoint probe không khả dụng ở bản app này thì bỏ qua,
                                # vẫn dựa vào /health để đánh giá kết nối.
                                pass

                            return {
                                "status": "ok" if gw_status == "pass" else "warn",
                                "message": f"Đã kết nối Local tới {base_url} | " + " · ".join(parts),
                                "device_info": {
                                    "version": version,
                                    "battery": battery,
                                    "charging": bool(charging),
                                    "internet": bool(internet),
                                    "gateway_status": gw_status,
                                },
                            }
                        except Exception:
                            return {"status": "ok", "message": f"Đã kết nối tới {base_url}"}
                    elif resp.status == 401:
                        return {
                            "status": "error",
                            "message": "Sai username/password (HTTP 401) - Hãy kiểm tra lại",
                        }
                    else:
                        return {
                            "status": "error",
                            "message": f"Gateway phản hồi HTTP {resp.status}",
                        }
        except aiohttp.ClientConnectorError:
            return {
                "status": "error",
                "message": "Không thể kết nối (Connection Error) — kiểm tra Gateway app đang chạy hoặc IP",
            }
        except asyncio.TimeoutError:
            return {
                "status": "error",
                "message": "Timeout khi thực hiện Check Health",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ---------- Status Polling ----------

    @staticmethod
    async def get_message_status(message_id: str, config: Optional[dict] = None) -> dict:
        """Kéo trạng thái mới nhất của SMS dựa vào message_id."""
        cfg = config or SmsGatewayService.load_config()
        base_url = SmsGatewayService._base_url(cfg)
        auth = SmsGatewayService._auth(cfg)

        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{base_url}/messages/{message_id}", auth=auth) as resp:
                    if resp.status == 200:
                        body = await resp.json(content_type=None)
                        state = body.get("state", "Unknown")
                        device_id = body.get("deviceId")
                        error_msg = None
                        recipients = body.get("recipients", [])
                        if recipients and isinstance(recipients, list):
                            first_rep = recipients[0]
                            if first_rep.get("state") == "Failed":
                                error_msg = first_rep.get("error")

                        return {
                            "success": True,
                            "state": state,
                            "error": error_msg,
                            "device_id": device_id,
                        }
                    elif resp.status == 404:
                        return {"success": False, "error": "Message not found"}
                    else:
                        return {"success": False, "error": f"HTTP {resp.status}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------- Send SMS ----------

    @staticmethod
    async def send_sms(
        phone_numbers: list[str],
        text: str,
        config: Optional[dict] = None,
    ) -> dict:
        """
        Gửi SMS qua Android Gateway (Local).
        Trả về dict gồm: success (bool), message_id, response hoặc error, step.
        """
        cfg = config or SmsGatewayService.load_config()
        base_url = SmsGatewayService._base_url(cfg)
        auth = SmsGatewayService._auth(cfg)

        if not cfg.get("device_ip"):
            return {"success": False, "step": "validate_config", "error": "Chưa cấu hình IP thiết bị Android"}

        if not cfg.get("username") or not cfg.get("password"):
            return {"success": False, "step": "validate_config", "error": "Chưa cấu hình username/password của SMS Gateway"}

        phones = [str(p).strip() for p in phone_numbers if str(p).strip()]
        if not phones:
            return {"success": False, "step": "validate_input", "error": "Không có số điện thoại hợp lệ"}

        payload = SmsGatewayService._build_message_payload(cfg, phones, text)
        message_id = str(uuid.uuid4())[:8]

        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{base_url}/messages",
                    json=payload,
                    auth=auth,
                ) as resp:
                    resp_text = await resp.text()
                    try:
                        resp_body = json.loads(resp_text) if resp_text else {}
                    except Exception:
                        resp_body = {"raw": resp_text}

                    if resp.status in (200, 201, 202):
                        location = resp.headers.get("Location", "")
                        location_id = location.rsplit("/", 1)[-1] if location else ""
                        resolved_id = resp_body.get("id") or location_id or message_id

                        return {
                            "success": True,
                            "step": "gateway_send",
                            "message_id": resolved_id,
                            "response": resp_body,
                        }

                    if resp.status == 401:
                        return {
                            "success": False,
                            "step": "gateway_auth",
                            "http_status": 401,
                            "error": "Gateway từ chối xác thực (401). Vui lòng kiểm tra lại Username/Password trên app Android.",
                        }

                    if isinstance(resp_body, dict):
                        err_msg = resp_body.get("message") or resp_body.get("error") or str(resp_body)
                    else:
                        err_msg = str(resp_body)

                    if len(str(err_msg)) > 180:
                        err_msg = str(err_msg)[:177] + "..."

                    return {
                        "success": False,
                        "step": "gateway_send",
                        "http_status": resp.status,
                        "error": f"Lỗi gửi SMS (HTTP {resp.status}): {err_msg}",
                    }
        except aiohttp.ClientConnectorError:
            return {
                "success": False,
                "step": "gateway_connect",
                "error": f"Không thể kết nối tới {base_url} — kiểm tra Gateway app đang chạy",
            }
        except asyncio.TimeoutError:
            return {"success": False, "step": "gateway_timeout", "error": "Timeout khi gửi SMS"}
        except Exception as e:
            return {"success": False, "step": "gateway_exception", "error": str(e)}

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
        history.insert(0, entry)
        history = history[:500]
        SMS_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SMS_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    @staticmethod
    async def sync_history_statuses(limit: int = 50, config: Optional[dict] = None) -> dict:
        """Đồng bộ trạng thái từ gateway về lịch sử theo message_id."""
        cfg = config or SmsGatewayService.load_config()
        history = SmsGatewayService.load_history()

        refreshable_statuses = {"pending", "processed", "sent"}
        synced_count = 0
        checked_count = 0

        for item in history:
            if checked_count >= max(1, int(limit)):
                break

            message_id = str(item.get("id") or "").strip()
            status = str(item.get("status") or "").lower()
            if not message_id or status not in refreshable_statuses:
                continue

            checked_count += 1
            status_result = await SmsGatewayService.get_message_status(message_id, config=cfg)
            item["last_checked_at"] = datetime.now().isoformat()

            if not status_result.get("success"):
                continue

            new_state = str(status_result.get("state") or "").lower()
            if new_state:
                item["status"] = new_state
            item["error"] = status_result.get("error")
            if status_result.get("device_id"):
                item["device_id"] = status_result.get("device_id")
            synced_count += 1

        SMS_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SMS_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

        return {
            "checked": checked_count,
            "synced": synced_count,
            "total": len(history),
        }

    @staticmethod
    def clear_history() -> None:
        """Xóa toàn bộ lịch sử."""
        if SMS_HISTORY_FILE.exists():
            SMS_HISTORY_FILE.write_text("[]", encoding="utf-8")
