"""
Google Drive Cloud Roaming & Auto-Sync Engine for Google AI / Google One 2TB Subscribers.
Allows cross-device memory synchronization and automated cloud snapshots.
"""

from __future__ import annotations
import shutil
import hashlib
import socket
import time
from pathlib import Path
from typing import Any

from gemini_mem.config import config


class DriveSyncManager:
    def __init__(self, drive_root: Path | None = None, local_db_path: Path | None = None):
        self.drive_root = drive_root or config.google_drive_path
        self.local_db_path = local_db_path or config.db_path
        self.hostname = socket.gethostname().lower()

    @property
    def is_available(self) -> bool:
        return self.drive_root is not None and self.drive_root.exists() and self.drive_root.is_dir()

    @property
    def remote_dir(self) -> Path | None:
        if not self.is_available or self.drive_root is None:
            return None
        target = self.drive_root / "GeminiMem"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _file_hash(self, path: Path) -> str:
        if not path.exists():
            return ""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def sync_to_drive(self) -> bool:
        """Upload local memory database and snapshot to user's 2TB Google Drive."""
        if not self.is_available:
            return False

        r_dir = self.remote_dir
        if r_dir is None or not self.local_db_path.exists():
            return False

        # Machine-specific replica
        remote_file = r_dir / f"brain_{self.hostname}.db"
        master_file = r_dir / "brain_master.db"

        try:
            shutil.copy2(str(self.local_db_path), str(remote_file))
            shutil.copy2(str(self.local_db_path), str(master_file))

            # Weekly snapshot
            snapshot_dir = r_dir / "snapshots"
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            snapshot_file = snapshot_dir / f"brain_{time.strftime('%Y%m%d')}.db"
            if not snapshot_file.exists():
                shutil.copy2(str(self.local_db_path), str(snapshot_file))

            return True
        except Exception:
            return False

    def sync_from_drive(self, prefer_master: bool = True) -> bool:
        """Pull memory updates from user's Google Drive onto this machine."""
        if not self.is_available:
            return False

        r_dir = self.remote_dir
        if r_dir is None:
            return False

        target_remote = r_dir / "brain_master.db" if prefer_master else r_dir / f"brain_{self.hostname}.db"
        if not target_remote.exists():
            return False

        # Compare hashes
        local_hash = self._file_hash(self.local_db_path)
        remote_hash = self._file_hash(target_remote)

        if local_hash != remote_hash:
            # Backup local first
            if self.local_db_path.exists():
                backup = self.local_db_path.parent / f"brain_pre_sync_{int(time.time())}.db"
                shutil.copy2(str(self.local_db_path), str(backup))

            shutil.copy2(str(target_remote), str(self.local_db_path))
            return True

        return True

    def get_status(self) -> dict[str, Any]:
        return {
            "available": self.is_available,
            "drive_path": str(self.drive_root) if self.drive_root else "Not detected",
            "hostname": self.hostname,
            "synced_files": [f.name for f in self.remote_dir.glob("*.db")] if self.is_available and self.remote_dir else []
        }
