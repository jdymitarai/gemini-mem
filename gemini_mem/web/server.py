"""
Built-in Web Dashboard HTTP Server for gemini-mem.
Powered by Python's standard library ThreadingHTTPServer. Zero external pip dependencies!
"""

from __future__ import annotations
import http.server
import json
import urllib.parse
from pathlib import Path

from gemini_mem.core.store import MemoryStore
from gemini_mem.cloud.drive_sync import DriveSyncManager
from gemini_mem.config import config


STATIC_DIR = Path(__file__).parent / "static"


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    store = MemoryStore()
    drive = DriveSyncManager()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            index_file = STATIC_DIR / "index.html"
            if index_file.exists():
                content = index_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.send_error(404, "Dashboard HTML not found")
                return

        elif path == "/api/stats":
            timeline = self.store.get_timeline(limit=1000)
            graph = self.store.get_graph()
            summaries = self.store.get_recent_summaries(limit=100)
            data = {
                "total_observations": len(timeline),
                "total_entities": len(graph.entities),
                "total_relations": len(graph.relations),
                "total_summaries": len(summaries),
                "drive_sync": self.drive.get_status()
            }
            self._send_json(data)
            return

        elif path == "/api/observations":
            query_params = urllib.parse.parse_qs(parsed.query)
            q = query_params.get("q", [""])[0]
            limit = int(query_params.get("limit", [50])[0])
            obs_list = self.store.search_observations(q, limit=limit) if q else self.store.get_timeline(limit=limit)
            self._send_json([o.to_dict() for o in obs_list])
            return

        elif path == "/api/graph":
            graph = self.store.get_graph()
            self._send_json(graph.to_dict())
            return

        elif path == "/api/summaries":
            summaries = self.store.get_recent_summaries(limit=20)
            self._send_json([s.to_dict() for s in summaries])
            return

        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/sync":
            ok = self.drive.sync_to_drive()
            self._send_json({"status": "success" if ok else "failed", "details": self.drive.get_status()})
            return
        self.send_error(404)

    def _send_json(self, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        # Mute normal HTTP access logs for clean CLI
        pass


def run_dashboard(port: int = 38888, host: str = "127.0.0.1") -> None:
    server = http.server.ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"✨ gemini-mem Web Dashboard running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
