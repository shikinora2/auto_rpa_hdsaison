"""
Background cleanup service.

Runs periodic garbage-collection for:
- Auth token tables (refresh/password reset)
- Stale upload/download files
- Stale RPA/Zalo session folders
- In-memory QR cache in Zalo route
"""
import asyncio
import json
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_

from config.settings import (
    APP_DATA_DIR,
    CLEANUP_AUTH_TOKEN_RETENTION_DAYS,
    CLEANUP_DOWNLOAD_RETENTION_HOURS,
    CLEANUP_ENABLED,
    CLEANUP_INTERVAL_SECONDS,
    CLEANUP_SESSION_RETENTION_HOURS,
    CLEANUP_UPLOAD_RETENTION_HOURS,
    DOWNLOADS_DIR,
)
from db.database import SessionLocal
from db.models import PasswordResetToken, RefreshToken

UPLOADS_DIR = APP_DATA_DIR / "uploads"
RPA_SESSIONS_DIR = APP_DATA_DIR / "rpa_sessions"


class CleanupService:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self._run_lock: asyncio.Lock | None = None
        self._last_summary: dict[str, Any] | None = None

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self):
        if not CLEANUP_ENABLED or self.is_running():
            return
        self._stop_event = asyncio.Event()
        self._run_lock = asyncio.Lock()
        self._task = asyncio.create_task(self._run_loop(), name="cleanup_service_loop")

    async def stop(self):
        if not self._task:
            return
        if self._stop_event:
            self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    def get_last_summary(self) -> dict[str, Any] | None:
        return self._last_summary

    def get_runtime_config(self) -> dict[str, Any]:
        return {
            "enabled": CLEANUP_ENABLED,
            "interval_seconds": CLEANUP_INTERVAL_SECONDS,
            "upload_retention_hours": CLEANUP_UPLOAD_RETENTION_HOURS,
            "download_retention_hours": CLEANUP_DOWNLOAD_RETENTION_HOURS,
            "session_retention_hours": CLEANUP_SESSION_RETENTION_HOURS,
            "auth_token_retention_days": CLEANUP_AUTH_TOKEN_RETENTION_DAYS,
            "uploads_dir": str(UPLOADS_DIR),
            "downloads_dir": str(DOWNLOADS_DIR),
            "rpa_sessions_dir": str(RPA_SESSIONS_DIR),
            "app_data_dir": str(APP_DATA_DIR),
        }

    async def run_once(self, trigger: str = "manual") -> dict[str, Any]:
        if self._run_lock is None:
            self._run_lock = asyncio.Lock()

        async with self._run_lock:
            started_at = datetime.utcnow()
            now_ts = time.time()

            auth_stats = self._cleanup_auth_tokens(started_at)
            file_stats = self._cleanup_files(now_ts)
            session_stats = self._cleanup_sessions(now_ts)
            qr_stats = self._cleanup_zalo_qr_cache()

            summary = {
                "trigger": trigger,
                "started_at": started_at.isoformat(),
                "finished_at": datetime.utcnow().isoformat(),
                "auth": auth_stats,
                "files": file_stats,
                "sessions": session_stats,
                "qr_cache": qr_stats,
            }
            self._last_summary = summary
            return summary

    async def _run_loop(self):
        while self._stop_event and not self._stop_event.is_set():
            try:
                await self.run_once(trigger="scheduled")
            except Exception as exc:
                self._last_summary = {
                    "trigger": "scheduled",
                    "started_at": datetime.utcnow().isoformat(),
                    "finished_at": datetime.utcnow().isoformat(),
                    "error": str(exc),
                }

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=max(5, CLEANUP_INTERVAL_SECONDS))
            except asyncio.TimeoutError:
                continue

    def _cleanup_auth_tokens(self, now: datetime) -> dict[str, int]:
        cutoff = now - timedelta(days=CLEANUP_AUTH_TOKEN_RETENTION_DAYS)
        db = SessionLocal()
        try:
            refresh_deleted = (
                db.query(RefreshToken)
                .filter(
                    or_(
                        RefreshToken.expires_at < cutoff,
                        and_(RefreshToken.revoked_at.isnot(None), RefreshToken.revoked_at < cutoff),
                    )
                )
                .delete(synchronize_session=False)
            )

            reset_deleted = (
                db.query(PasswordResetToken)
                .filter(
                    or_(
                        PasswordResetToken.expires_at < cutoff,
                        and_(PasswordResetToken.used_at.isnot(None), PasswordResetToken.used_at < cutoff),
                    )
                )
                .delete(synchronize_session=False)
            )

            db.commit()
            return {
                "refresh_tokens_deleted": int(refresh_deleted or 0),
                "password_reset_tokens_deleted": int(reset_deleted or 0),
            }
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _cleanup_files(self, now_ts: float) -> dict[str, int]:
        upload_cutoff_ts = now_ts - (CLEANUP_UPLOAD_RETENTION_HOURS * 3600)
        download_cutoff_ts = now_ts - (CLEANUP_DOWNLOAD_RETENTION_HOURS * 3600)

        uploads_deleted, uploads_bytes = self._delete_old_files(UPLOADS_DIR, upload_cutoff_ts)
        downloads_deleted, downloads_bytes = self._delete_old_files(DOWNLOADS_DIR, download_cutoff_ts)

        return {
            "uploads_deleted": uploads_deleted,
            "uploads_reclaimed_bytes": uploads_bytes,
            "downloads_deleted": downloads_deleted,
            "downloads_reclaimed_bytes": downloads_bytes,
        }

    def _cleanup_sessions(self, now_ts: float) -> dict[str, int]:
        cutoff_ts = now_ts - (CLEANUP_SESSION_RETENTION_HOURS * 3600)

        rpa_deleted = self._delete_stale_session_dirs(
            parent=RPA_SESSIONS_DIR,
            prefix="user_",
            cutoff_ts=cutoff_ts,
            now_ts=now_ts,
        )
        zalo_deleted = self._delete_stale_session_dirs(
            parent=APP_DATA_DIR,
            prefix="zalo_session",
            cutoff_ts=cutoff_ts,
            now_ts=now_ts,
        )

        return {
            "rpa_session_dirs_deleted": rpa_deleted,
            "zalo_session_dirs_deleted": zalo_deleted,
        }

    def _cleanup_zalo_qr_cache(self) -> dict[str, int]:
        try:
            from api.routes.zalo import cleanup_expired_qr_cache

            removed = cleanup_expired_qr_cache()
            return {"entries_removed": int(removed)}
        except Exception:
            return {"entries_removed": 0}

    @staticmethod
    def _delete_old_files(target_dir: Path, cutoff_ts: float) -> tuple[int, int]:
        if not target_dir.exists() or not target_dir.is_dir():
            return 0, 0

        deleted = 0
        reclaimed_bytes = 0

        for path in target_dir.iterdir():
            if not path.is_file():
                continue
            try:
                mtime = path.stat().st_mtime
                if mtime > cutoff_ts:
                    continue
                reclaimed_bytes += path.stat().st_size
                path.unlink(missing_ok=True)
                deleted += 1
            except Exception:
                continue

        return deleted, reclaimed_bytes

    @staticmethod
    def _delete_stale_session_dirs(parent: Path, prefix: str, cutoff_ts: float, now_ts: float) -> int:
        if not parent.exists() or not parent.is_dir():
            return 0

        deleted = 0

        for item in parent.iterdir():
            if not item.is_dir() or not item.name.startswith(prefix):
                continue

            try:
                session_info_file = item / "session_info.json"
                delete_it = False

                if session_info_file.exists():
                    try:
                        with open(session_info_file, "r", encoding="utf-8") as fp:
                            info = json.load(fp)
                        expires_at_ts = float(info.get("expires_at_ts") or 0)
                        if expires_at_ts > 0 and now_ts >= expires_at_ts:
                            delete_it = True
                    except Exception:
                        delete_it = False

                if not delete_it:
                    mtime = item.stat().st_mtime
                    delete_it = mtime <= cutoff_ts

                if delete_it:
                    shutil.rmtree(item, ignore_errors=True)
                    deleted += 1
            except Exception:
                continue

        return deleted


_cleanup_service_singleton = CleanupService()


def get_cleanup_service() -> CleanupService:
    return _cleanup_service_singleton
