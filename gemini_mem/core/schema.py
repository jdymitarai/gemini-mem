"""
Data schema definitions for gemini-mem memory models.
"""

from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Observation:
    id: int | None = None
    session_id: str = ""
    project: str = ""
    type: str = "general"  # bugfix, feature, decision, lesson, architecture, security
    title: str = ""
    narrative: str = ""
    facts: list[str] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    discovery_tokens: int = 0
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    created_at_epoch: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Entity:
    name: str
    entity_type: str = "Concept"  # Module, Service, Tool, Config, Vulnerability
    project: str = ""
    observations: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Relation:
    source: str
    target: str
    relation_type: str = "relates_to"  # depends_on, fixes, triggers, configures, uses
    project: str = ""
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SessionSummary:
    id: int | None = None
    session_id: str = ""
    project: str = ""
    request: str = ""
    investigated: str = ""
    learned: str = ""
    completed: str = ""
    next_steps: str = ""
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    created_at_epoch: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeGraph:
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
        }
