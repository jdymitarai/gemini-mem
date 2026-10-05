"""
Model Context Protocol (MCP) Server for gemini-mem.
Exposes progressive disclosure search, Knowledge Graph querying, and Drive sync tools over JSON-RPC 2.0 stdio.
"""

from __future__ import annotations
import sys
import json
from typing import Any

from gemini_mem.core.store import MemoryStore
from gemini_mem.core.schema import Observation, Entity, Relation
from gemini_mem.cloud.drive_sync import DriveSyncManager


TOOLS = [
    {
        "name": "gemini_mem_search",
        "description": "Search agent memory index using full-text search (FTS5). Returns matching observation IDs and titles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms or keywords"},
                "project": {"type": "string", "description": "Optional project filter"},
                "limit": {"type": "integer", "description": "Max results to return (default: 10)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "gemini_mem_get_observations",
        "description": "Retrieve full facts, files modified, and narratives for specific memory observation IDs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of observation IDs to fetch"
                }
            },
            "required": ["ids"]
        }
    },
    {
        "name": "gemini_mem_get_graph",
        "description": "Inspect the Knowledge Graph concept map and relational dependencies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Optional project filter"}
            }
        }
    },
    {
        "name": "gemini_mem_save_observation",
        "description": "Manually save a critical decision, architectural insight, or bugfix lesson into memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title"},
                "narrative": {"type": "string", "description": "Detailed description or root cause"},
                "type": {
                    "type": "string",
                    "enum": ["bugfix", "feature", "decision", "lesson", "architecture", "security"],
                    "description": "Category of memory"
                },
                "project": {"type": "string", "description": "Project identifier"}
            },
            "required": ["title", "narrative"]
        }
    },
    {
        "name": "gemini_mem_sync_drive",
        "description": "Trigger synchronization of the memory database to user's 2TB Google Drive.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


class McpServer:
    def __init__(self):
        self.store = MemoryStore()
        self.drive = DriveSyncManager()

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "gemini-mem", "version": "0.1.0"}
                }
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS}
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            try:
                res = self._call_tool(tool_name, args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(res, indent=2, ensure_ascii=False)}]
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)}
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method {method} not found"}
        }

    def _call_tool(self, name: str, args: dict[str, Any]) -> Any:
        if name == "gemini_mem_search":
            query = args.get("query", "")
            project = args.get("project")
            limit = args.get("limit", 10)
            results = self.store.search_observations(query, project=project, limit=limit)
            return [
                {
                    "id": o.id,
                    "type": o.type,
                    "title": o.title,
                    "created_at": o.created_at,
                    "project": o.project
                }
                for o in results
            ]

        elif name == "gemini_mem_get_observations":
            ids = args.get("ids", [])
            output = []
            for obs_id in ids:
                obs = self.store.get_observation_by_id(obs_id)
                if obs:
                    output.append(obs.to_dict())
            return output

        elif name == "gemini_mem_get_graph":
            project = args.get("project")
            return self.store.get_graph(project=project).to_dict()

        elif name == "gemini_mem_save_observation":
            obs = Observation(
                title=args.get("title", ""),
                narrative=args.get("narrative", ""),
                type=args.get("type", "general"),
                project=args.get("project", "")
            )
            obs_id = self.store.add_observation(obs)
            return {"status": "success", "observation_id": obs_id}

        elif name == "gemini_mem_sync_drive":
            ok = self.drive.sync_to_drive()
            return {"synced": ok, "status": self.drive.get_status()}

        raise ValueError(f"Unknown tool: {name}")

    def run_stdio(self) -> None:
        """Run the JSON-RPC stdio event loop."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self.handle_request(req)
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
            except Exception:
                pass


if __name__ == "__main__":
    McpServer().run_stdio()
