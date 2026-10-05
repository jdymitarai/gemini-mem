"""
SQLite Knowledge Graph and Full-Text Search Store for gemini-mem.
"""

from __future__ import annotations
import sqlite3
import json
import time
from pathlib import Path
from typing import Any

from gemini_mem.core.schema import Observation, Entity, Relation, SessionSummary, KnowledgeGraph
from gemini_mem.config import config


class MemoryStore:
    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            config.ensure_dirs()
            self.db_path = config.db_path
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            # 1. Observations
            conn.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                project TEXT NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                narrative TEXT NOT NULL,
                facts_json TEXT NOT NULL DEFAULT '[]',
                files_read_json TEXT NOT NULL DEFAULT '[]',
                files_modified_json TEXT NOT NULL DEFAULT '[]',
                discovery_tokens INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                created_at_epoch REAL NOT NULL
            )
            """)

            # FTS5 for full-text search
            conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
                title,
                narrative,
                facts_json,
                content='observations',
                content_rowid='id'
            )
            """)

            # Triggers to keep FTS in sync
            conn.execute("""
            CREATE TRIGGER IF NOT EXISTS observations_ai AFTER INSERT ON observations BEGIN
                INSERT INTO observations_fts(rowid, title, narrative, facts_json)
                VALUES (new.id, new.title, new.narrative, new.facts_json);
            END;
            """)
            conn.execute("""
            CREATE TRIGGER IF NOT EXISTS observations_ad AFTER DELETE ON observations BEGIN
                INSERT INTO observations_fts(observations_fts, rowid, title, narrative, facts_json)
                VALUES('delete', old.id, old.title, old.narrative, old.facts_json);
            END;
            """)
            conn.execute("""
            CREATE TRIGGER IF NOT EXISTS observations_au AFTER UPDATE ON observations BEGIN
                INSERT INTO observations_fts(observations_fts, rowid, title, narrative, facts_json)
                VALUES('delete', old.id, old.title, old.narrative, old.facts_json);
                INSERT INTO observations_fts(rowid, title, narrative, facts_json)
                VALUES (new.id, new.title, new.narrative, new.facts_json);
            END;
            """)

            # 2. Knowledge Graph Entities
            conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                name TEXT NOT NULL,
                project TEXT NOT NULL,
                entity_type TEXT NOT NULL DEFAULT 'Concept',
                observations_json TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (name, project)
            )
            """)

            # 3. Knowledge Graph Relations
            conn.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                project TEXT NOT NULL,
                relation_type TEXT NOT NULL DEFAULT 'relates_to',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source, target, project, relation_type)
            )
            """)

            # 4. Session Summaries
            conn.execute("""
            CREATE TABLE IF NOT EXISTS session_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                project TEXT NOT NULL,
                request TEXT NOT NULL,
                investigated TEXT NOT NULL,
                learned TEXT NOT NULL,
                completed TEXT NOT NULL,
                next_steps TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_at_epoch REAL NOT NULL
            )
            """)

            # 5. Cloud Sync Metadata
            conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """)
            conn.commit()

    def add_observation(self, obs: Observation) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute("""
            INSERT INTO observations (
                session_id, project, type, title, narrative,
                facts_json, files_read_json, files_modified_json,
                discovery_tokens, created_at, created_at_epoch
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                obs.session_id,
                obs.project,
                obs.type,
                obs.title,
                obs.narrative,
                json.dumps(obs.facts, ensure_ascii=False),
                json.dumps(obs.files_read, ensure_ascii=False),
                json.dumps(obs.files_modified, ensure_ascii=False),
                obs.discovery_tokens,
                obs.created_at,
                obs.created_at_epoch
            ))
            conn.commit()
            obs.id = cursor.lastrowid
            return cursor.lastrowid

    def search_observations(self, query: str, project: str | None = None, limit: int = 10) -> list[Observation]:
        with self._get_connection() as conn:
            cleaned_query = query.replace('"', '""').strip()
            if not cleaned_query:
                return self.get_timeline(project=project, limit=limit)

            sql = """
            SELECT o.*
            FROM observations_fts fts
            JOIN observations o ON o.id = fts.rowid
            WHERE observations_fts MATCH ?
            """
            params: list[Any] = [f'"{cleaned_query}"*']

            if project:
                sql += " AND (o.project = ? OR o.project = '')"
                params.append(project)

            sql += " ORDER BY rank, o.created_at_epoch DESC LIMIT ?"
            params.append(limit)

            try:
                rows = conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                # Fallback to LIKE if FTS syntax error
                like_sql = """
                SELECT * FROM observations
                WHERE (title LIKE ? OR narrative LIKE ? OR facts_json LIKE ?)
                """
                like_pattern = f"%{query}%"
                like_params: list[Any] = [like_pattern, like_pattern, like_pattern]
                if project:
                    like_sql += " AND (project = ? OR project = '')"
                    like_params.append(project)
                like_sql += " ORDER BY created_at_epoch DESC LIMIT ?"
                like_params.append(limit)
                rows = conn.execute(like_sql, like_params).fetchall()

            return [self._row_to_observation(r) for r in rows]

    def get_timeline(self, project: str | None = None, limit: int = 20) -> list[Observation]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM observations"
            params: list[Any] = []
            if project:
                sql += " WHERE (project = ? OR project = '')"
                params.append(project)
            sql += " ORDER BY created_at_epoch DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_observation(r) for r in rows]

    def get_observation_by_id(self, obs_id: int) -> Observation | None:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM observations WHERE id = ?", (obs_id,)).fetchone()
            if row:
                return self._row_to_observation(row)
            return None

    def upsert_entity(self, entity: Entity) -> None:
        with self._get_connection() as conn:
            existing = conn.execute(
                "SELECT observations_json FROM entities WHERE name = ? AND project = ?",
                (entity.name, entity.project)
            ).fetchone()

            obs_list = entity.observations
            if existing:
                try:
                    prior_obs = json.loads(existing["observations_json"])
                    obs_list = list(dict.fromkeys(prior_obs + entity.observations))
                except Exception:
                    pass

            conn.execute("""
            INSERT INTO entities (name, project, entity_type, observations_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name, project) DO UPDATE SET
                entity_type = excluded.entity_type,
                observations_json = excluded.observations_json,
                updated_at = excluded.updated_at
            """, (
                entity.name,
                entity.project,
                entity.entity_type,
                json.dumps(obs_list, ensure_ascii=False),
                entity.updated_at
            ))
            conn.commit()

    def add_relation(self, relation: Relation) -> None:
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO relations (source, target, project, relation_type, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source, target, project, relation_type) DO UPDATE SET
                updated_at = excluded.updated_at
            """, (
                relation.source,
                relation.target,
                relation.project,
                relation.relation_type,
                relation.updated_at
            ))
            conn.commit()

    def get_graph(self, project: str | None = None) -> KnowledgeGraph:
        with self._get_connection() as conn:
            e_sql = "SELECT * FROM entities"
            r_sql = "SELECT * FROM relations"
            params: list[Any] = []
            if project:
                e_sql += " WHERE (project = ? OR project = '')"
                r_sql += " WHERE (project = ? OR project = '')"
                params.append(project)

            e_rows = conn.execute(e_sql, params).fetchall()
            r_rows = conn.execute(r_sql, params).fetchall()

            entities = []
            for r in e_rows:
                try:
                    obs_list = json.loads(r["observations_json"])
                except Exception:
                    obs_list = []
                entities.append(Entity(
                    name=r["name"],
                    entity_type=r["entity_type"],
                    project=r["project"],
                    observations=obs_list,
                    updated_at=r["updated_at"]
                ))

            relations = [
                Relation(
                    source=r["source"],
                    target=r["target"],
                    relation_type=r["relation_type"],
                    project=r["project"],
                    updated_at=r["updated_at"]
                )
                for r in r_rows
            ]

            return KnowledgeGraph(entities=entities, relations=relations)

    def add_session_summary(self, summary: SessionSummary) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute("""
            INSERT INTO session_summaries (
                session_id, project, request, investigated, learned, completed, next_steps,
                created_at, created_at_epoch
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                summary.session_id,
                summary.project,
                summary.request,
                summary.investigated,
                summary.learned,
                summary.completed,
                summary.next_steps,
                summary.created_at,
                summary.created_at_epoch
            ))
            conn.commit()
            summary.id = cursor.lastrowid
            return cursor.lastrowid

    def get_recent_summaries(self, project: str | None = None, limit: int = 5) -> list[SessionSummary]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM session_summaries"
            params: list[Any] = []
            if project:
                sql += " WHERE (project = ? OR project = '')"
                params.append(project)
            sql += " ORDER BY created_at_epoch DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [
                SessionSummary(
                    id=r["id"],
                    session_id=r["session_id"],
                    project=r["project"],
                    request=r["request"],
                    investigated=r["investigated"],
                    learned=r["learned"],
                    completed=r["completed"],
                    next_steps=r["next_steps"],
                    created_at=r["created_at"],
                    created_at_epoch=r["created_at_epoch"]
                )
                for r in rows
            ]

    def generate_context_block(self, project: str | None = None) -> str:
        """
        Generate token-efficient context injection formatted as Markdown for Antigravity & Gemini agents.
        """
        observations = self.get_timeline(project=project, limit=config.max_context_observations)
        summaries = self.get_recent_summaries(project=project, limit=config.max_context_summaries)
        graph = self.get_graph(project=project)

        lines: list[str] = [
            "<gemini-mem-context>",
            f"# Gemini Agent Memory Context [{time.strftime('%Y-%m-%d %H:%M:%S')}]",
            f"Project: {project or 'Global'}",
            ""
        ]

        # 1. Recent Summaries (Learned Lessons)
        if summaries:
            lines.append("## Key Lessons from Past Sessions")
            for s in summaries:
                lines.append(f"- **Task**: {s.request or 'Previous Task'}")
                if s.learned:
                    lines.append(f"  - **Learned**: {s.learned}")
                if s.completed:
                    lines.append(f"  - **Completed**: {s.completed}")
                if s.next_steps:
                    lines.append(f"  - **Next Steps**: {s.next_steps}")
            lines.append("")

        # 2. Knowledge Graph Entities & Relations
        if graph.entities:
            lines.append("## Knowledge Graph Concept Map")
            for e in graph.entities[:15]:
                obs_summary = "; ".join(e.observations[:2]) if e.observations else ""
                lines.append(f"- `[{e.entity_type}]` **{e.name}**: {obs_summary}")
            if graph.relations:
                lines.append("### Key Concept Relations")
                for r in graph.relations[:12]:
                    lines.append(f"- `{r.source}` ──({r.relation_type})──► `{r.target}`")
            lines.append("")

        # 3. Compact Observations Index (Progressive Disclosure)
        if observations:
            lines.append("## Recent Memory Index (Use `gemini_mem_search` for full facts)")
            for o in observations[:20]:
                lines.append(f"- `#{o.id}` [{o.type.upper()}] **{o.title}** ({o.created_at})")
            lines.append("")

        if not observations and not summaries and not graph.entities:
            lines.append("*No previous memories recorded for this workspace yet. Active sessions will automatically synthesize lessons here.*")

        lines.append("</gemini-mem-context>")
        return "\n".join(lines)

    def _row_to_observation(self, r: sqlite3.Row) -> Observation:
        try:
            facts = json.loads(r["facts_json"])
        except Exception:
            facts = []
        try:
            files_read = json.loads(r["files_read_json"])
        except Exception:
            files_read = []
        try:
            files_modified = json.loads(r["files_modified_json"])
        except Exception:
            files_modified = []

        return Observation(
            id=r["id"],
            session_id=r["session_id"],
            project=r["project"],
            type=r["type"],
            title=r["title"],
            narrative=r["narrative"],
            facts=facts,
            files_read=files_read,
            files_modified=files_modified,
            discovery_tokens=r["discovery_tokens"],
            created_at=r["created_at"],
            created_at_epoch=r["created_at_epoch"]
        )
