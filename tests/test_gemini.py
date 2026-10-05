"""
Unit tests for Gemini observer and Drive sync manager.
"""

import tempfile
import shutil
from pathlib import Path
from gemini_mem.providers.gemini import GeminiObserver
from gemini_mem.cloud.drive_sync import DriveSyncManager


def test_heuristic_fallback_offline():
    observer = GeminiObserver(api_key="")
    obs = observer.synthesize_observation(
        tool_name="replace_file_content",
        tool_input='TargetFile: "src/main.rs", ReplacementContent: "fn main() {}"',
        tool_output="File updated cleanly.",
        session_id="test-session",
        project="demo"
    )
    assert obs.type == "feature"
    assert "Modified files" in obs.title or "replace_file_content" in obs.title


def test_drive_sync_local_simulation():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        drive_fake = temp_dir / "GoogleDrive"
        drive_fake.mkdir()
        local_db = temp_dir / "brain.db"
        local_db.write_text("dummy database bytes")

        sync_mgr = DriveSyncManager(drive_root=drive_fake, local_db_path=local_db)
        assert sync_mgr.is_available is True

        # Test sync to drive
        ok = sync_mgr.sync_to_drive()
        assert ok is True
        assert (drive_fake / "GeminiMem" / "brain_master.db").exists()

        status = sync_mgr.get_status()
        assert status["available"] is True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
