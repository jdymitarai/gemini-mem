"""
Unit tests for gemini-mem MemoryStore and FTS5 search.
"""

import tempfile
import shutil
from pathlib import Path
import pytest

from gemini_mem.core.store import MemoryStore
from gemini_mem.core.schema import Observation, Entity, Relation, SessionSummary


@pytest.fixture
def temp_store():
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_brain.db"
    store = MemoryStore(db_path=db_path)
    yield store
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_add_and_search_observation(temp_store):
    obs = Observation(
        session_id="sess-001",
        project="leveldb",
        type="bugfix",
        title="Fix key size overflow in MemTable",
        narrative="Guarded against integer overflow in WriteBatch::Iterate when key exceeds uint32 max - 8",
        facts=["Key size check added", "Status::InvalidArgument returned on overflow"],
        files_modified=["db/write_batch.cc", "db/db_impl.cc"]
    )
    obs_id = temp_store.add_observation(obs)
    assert obs_id is not None
    assert obs_id > 0

    # Search with FTS
    results = temp_store.search_observations("overflow")
    assert len(results) >= 1
    assert results[0].title == "Fix key size overflow in MemTable"
    assert "db/write_batch.cc" in results[0].files_modified


def test_knowledge_graph_entities_and_relations(temp_store):
    e1 = Entity(name="WriteBatch", entity_type="Component", project="leveldb", observations=["Handles batch writes"])
    e2 = Entity(name="MemTable", entity_type="Component", project="leveldb", observations=["In-memory skiplist buffer"])
    temp_store.upsert_entity(e1)
    temp_store.upsert_entity(e2)

    rel = Relation(source="WriteBatch", target="MemTable", relation_type="inserts_into", project="leveldb")
    temp_store.add_relation(rel)

    graph = temp_store.get_graph(project="leveldb")
    assert len(graph.entities) == 2
    assert len(graph.relations) == 1
    assert graph.relations[0].source == "WriteBatch"
    assert graph.relations[0].target == "MemTable"


def test_session_summaries_and_context_injection(temp_store):
    summary = SessionSummary(
        session_id="sess-002",
        project="leveldb",
        request="Fix issue #1362 overflow",
        investigated="Inspected WriteBatch::Iterate encoding",
        learned="Varint32 key size requires careful boundary checking",
        completed="Patch applied and PR submitted",
        next_steps="Review CI tests"
    )
    temp_store.add_session_summary(summary)

    summaries = temp_store.get_recent_summaries(project="leveldb")
    assert len(summaries) == 1
    assert "Varint32" in summaries[0].learned

    # Test markdown context block generation
    context_block = temp_store.generate_context_block(project="leveldb")
    assert "<gemini-mem-context>" in context_block
    assert "</gemini-mem-context>" in context_block
    assert "Varint32" in context_block
