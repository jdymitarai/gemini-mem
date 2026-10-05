"""
Complete unittest test suite for gemini-mem.
Uses Python's standard library unittest so it runs everywhere with zero extra pip packages!
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from gemini_mem.core.store import MemoryStore
from gemini_mem.core.schema import Observation, Entity, Relation, SessionSummary
from gemini_mem.providers.gemini import GeminiObserver
from gemini_mem.cloud.drive_sync import DriveSyncManager
from gemini_mem.hooks.antigravity import safe_post_tool_use, safe_session_start, safe_session_end


class TestGeminiMem(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test_brain.db"
        self.store = MemoryStore(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_observations_add_and_fts_search(self):
        obs = Observation(
            session_id="sess-001",
            project="draco",
            type="bugfix",
            title="Fix mesh face index bounds check",
            narrative="Prevented heap buffer overflow in ObjDecoder by clamping point indices",
            facts=["Validated corner indices in ObjDecoder::ParseFace", "Returns DRACO_ERROR status on invalid index"],
            files_modified=["src/draco/io/obj_decoder.cc"]
        )
        obs_id = self.store.add_observation(obs)
        self.assertIsNotNone(obs_id)
        self.assertGreater(obs_id, 0)

        # Full Text Search via FTS5
        results = self.store.search_observations("clamping", project="draco")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].title, "Fix mesh face index bounds check")
        self.assertIn("src/draco/io/obj_decoder.cc", results[0].files_modified)

    def test_knowledge_graph_mesh(self):
        e1 = Entity(name="ObjDecoder", entity_type="Component", project="draco", observations=["Decodes Wavefront OBJ meshes"])
        e2 = Entity(name="MeshValidation", entity_type="Rule", project="draco", observations=["Guards indices"])
        self.store.upsert_entity(e1)
        self.store.upsert_entity(e2)

        rel = Relation(source="ObjDecoder", target="MeshValidation", relation_type="enforces", project="draco")
        self.store.add_relation(rel)

        graph = self.store.get_graph(project="draco")
        self.assertEqual(len(graph.entities), 2)
        self.assertEqual(len(graph.relations), 1)
        self.assertEqual(graph.relations[0].source, "ObjDecoder")
        self.assertEqual(graph.relations[0].target, "MeshValidation")

    def test_session_summaries_and_context_block(self):
        summary = SessionSummary(
            session_id="sess-003",
            project="sandboxed-api",
            request="Implement Landlock LSM support",
            investigated="Investigated Linux 5.13+ Landlock syscalls",
            learned="Landlock ABI versions must be probed with LANDLOCK_CREATE_RULESET_VERSION",
            completed="Added Landlock ruleset builder and filesystem flags",
            next_steps="Test with unprivileged sandboxes"
        )
        self.store.add_session_summary(summary)

        summaries = self.store.get_recent_summaries(project="sandboxed-api")
        self.assertEqual(len(summaries), 1)
        self.assertIn("Landlock ABI", summaries[0].learned)

        # Generate Context Markdown for Agent Prompt
        ctx = self.store.generate_context_block(project="sandboxed-api")
        self.assertIn("<gemini-mem-context>", ctx)
        self.assertIn("Landlock ABI", ctx)
        self.assertIn("## Key Lessons from Past Sessions", ctx)

    def test_gemini_observer_offline_fallback(self):
        observer = GeminiObserver(api_key="")
        obs = observer.synthesize_observation(
            tool_name="run_command",
            tool_input="ctest -R draco_tests",
            tool_output="100% tests passed, 0 errors.",
            session_id="s1",
            project="draco"
        )
        self.assertIsNotNone(obs)
        self.assertEqual(obs.project, "draco")

    def test_google_drive_sync_simulation(self):
        fake_drive = self.temp_dir / "GoogleDrive"
        fake_drive.mkdir()
        local_db = self.temp_dir / "local_brain.db"
        local_db.write_text("sqlite mock payload")

        sync_mgr = DriveSyncManager(drive_root=fake_drive, local_db_path=local_db)
        self.assertTrue(sync_mgr.is_available)

        ok = sync_mgr.sync_to_drive()
        self.assertTrue(ok)
        self.assertTrue((fake_drive / "GeminiMem" / "brain_master.db").exists())

    def test_crash_proof_hooks(self):
        # Ensure safe hook methods NEVER raise
        safe_post_tool_use("test_tool", "input", "output", "proj")
        ctx = safe_session_start("proj")
        self.assertIsInstance(ctx, str)
        safe_session_end("dialogue transcript", "proj")


if __name__ == "__main__":
    unittest.main()
