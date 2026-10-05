"""
Configuration and settings management for gemini-mem.
"""

from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass, field


def get_default_data_dir() -> Path:
    override = os.environ.get("GEMINI_MEM_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".gemini-mem").resolve()


def detect_google_drive_path() -> Path | None:
    """Auto-detect user's Google Drive local sync directory (for Google One 2TB subscribers)."""
    env_path = os.environ.get("GEMINI_MEM_DRIVE_PATH")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.exists():
            return p

    home = Path.home()
    candidates = [
        Path("G:/My Drive"),
        Path("G:/"),
        home / "Google Drive" / "My Drive",
        home / "Google Drive",
        home / "My Drive",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return None


@dataclass
class GeminiMemConfig:
    data_dir: Path = field(default_factory=get_default_data_dir)
    db_name: str = "brain.db"
    port: int = 38888
    host: str = "127.0.0.1"
    model: str = "gemini-2.5-flash"
    api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", "")))
    google_drive_path: Path | None = field(default_factory=detect_google_drive_path)
    drive_sync_enabled: bool = True
    max_context_observations: int = 40
    max_context_summaries: int = 5

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "backups").mkdir(parents=True, exist_ok=True)


config = GeminiMemConfig()
