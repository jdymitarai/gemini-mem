"""
Crash-Proof Lifecycle Hooks for Antigravity & Google Gemini Agents.
Designed with Karpathy-style defensive engineering:
- Guarantees ZERO blocking on IDE operations.
- Silent fail-safe: always exits with code 0 even on fatal exceptions.
- Completely decouples memory synthesis from agent response times.
"""

from __future__ import annotations
import sys
import os
import json
import subprocess
from pathlib import Path

from gemini_mem.core.store import MemoryStore
from gemini_mem.core.schema import Entity, Relation
from gemini_mem.providers.gemini import GeminiObserver
from gemini_mem.cloud.drive_sync import DriveSyncManager
from gemini_mem.config import config


def safe_post_tool_use(tool_name: str, tool_input: str, tool_output: str, project: str = "") -> None:
    """Invoked asynchronously after a tool is used. Must never raise."""
    try:
        store = MemoryStore()
        observer = GeminiObserver()
        obs = observer.synthesize_observation(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            project=project
        )
        store.add_observation(obs)

        # Update Knowledge Graph if tool indicates architectural dependencies
        if obs.type in ("feature", "bugfix", "architecture"):
            entity_name = tool_name
            if obs.files_modified:
                entity_name = Path(obs.files_modified[0]).name
            store.upsert_entity(Entity(
                name=entity_name,
                entity_type="Component",
                project=project,
                observations=[obs.title]
            ))

        # Auto sync to Drive in background
        if config.drive_sync_enabled:
            DriveSyncManager().sync_to_drive()
    except Exception:
        # Silent fail-safe: never crash or interfere with developer
        pass


def safe_session_start(project: str = "") -> str:
    """Generate context string to inject into agent prompt on startup."""
    try:
        store = MemoryStore()
        return store.generate_context_block(project=project)
    except Exception:
        return ""


def safe_session_end(transcript_text: str, project: str = "") -> None:
    """Summarize session on exit and record lessons."""
    try:
        store = MemoryStore()
        observer = GeminiObserver()
        summary = observer.synthesize_session_summary(transcript_text, project=project)
        store.add_session_summary(summary)
        if config.drive_sync_enabled:
            DriveSyncManager().sync_to_drive()
    except Exception:
        pass


def install_antigravity_hooks() -> bool:
    """
    Registers gemini-mem safely with Antigravity / Gemini configuration.
    """
    try:
        config.ensure_dirs()
        gemini_dir = Path.home() / ".gemini"
        config_dir = gemini_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        hooks_file = config_dir / "hooks.json"
        hooks_data: dict = {}
        if hooks_file.exists():
            try:
                hooks_data = json.loads(hooks_file.read_text("utf-8"))
            except Exception:
                hooks_data = {}

        # Safe python execution template
        py_exe = sys.executable
        runner_script = Path(__file__).resolve()

        # Add or update hooks safely
        # Note: We provide a resilient single-line command that never returns non-zero
        hooks_data["gemini_mem_post_tool"] = {
            "type": "command",
            "command": f'"{py_exe}" -m gemini_mem.cli hook post-tool',
            "timeout": 30,
            "async": True
        }

        hooks_file.write_text(json.dumps(hooks_data, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # If run directly via hook dispatcher, guarantee exit 0
    try:
        action = sys.argv[1] if len(sys.argv) > 1 else ""
        if action == "context":
            proj = sys.argv[2] if len(sys.argv) > 2 else ""
            print(safe_session_start(proj))
    except Exception:
        pass
    sys.exit(0)
