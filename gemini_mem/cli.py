"""
Command Line Interface for gemini-mem.
"""

from __future__ import annotations
import argparse
import sys
import os
import json
from pathlib import Path

from gemini_mem import __version__
from gemini_mem.config import config
from gemini_mem.core.store import MemoryStore
from gemini_mem.cloud.drive_sync import DriveSyncManager
from gemini_mem.web.server import run_dashboard
from gemini_mem.hooks.antigravity import install_antigravity_hooks, safe_post_tool_use, safe_session_start, safe_session_end


def main() -> None:
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        prog="gemini-mem",
        description="Persistent Agent Memory & Knowledge Graph for Google AI & Gemini Advanced subscribers."
    )
    parser.add_argument("-v", "--version", action="version", version=f"gemini-mem v{__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 1. install
    install_p = subparsers.add_parser("install", help="Install gemini-mem hooks into Antigravity or Gemini CLI")
    install_p.add_argument("--ide", default="antigravity", choices=["antigravity", "gemini-cli", "cursor"], help="Target IDE")

    # 2. start
    start_p = subparsers.add_parser("start", help="Start the Web Dashboard in foreground")
    start_p.add_argument("--port", type=int, default=config.port, help="Port to bind dashboard")
    start_p.add_argument("--host", default=config.host, help="Host to bind dashboard")

    # 2.1 daemon
    daemon_p = subparsers.add_parser("daemon", help="Manage background OS daemon (independent of chat/terminal)")
    daemon_p.add_argument("action", choices=["start", "stop", "status"], help="Daemon action")
    daemon_p.add_argument("--port", type=int, default=config.port, help="Port to bind dashboard")

    # 3. status
    subparsers.add_parser("status", help="Check memory store status, statistics, and Google Drive sync")

    # 4. search
    search_p = subparsers.add_parser("search", help="Search memory database via full-text search (FTS5)")
    search_p.add_argument("query", help="Keywords or query terms")
    search_p.add_argument("--project", default="", help="Project filter")
    search_p.add_argument("--limit", type=int, default=10, help="Max results")

    # 5. graph
    graph_p = subparsers.add_parser("graph", help="Show Knowledge Graph entities and relations")
    graph_p.add_argument("--project", default="", help="Project filter")

    # 6. context
    ctx_p = subparsers.add_parser("context", help="Output Markdown memory block for agent prompt injection")
    ctx_p.add_argument("--project", default="", help="Project filter")

    # 7. sync
    subparsers.add_parser("sync", help="Trigger manual synchronization to 2TB Google Drive")

    # 8. hook (internal)
    hook_p = subparsers.add_parser("hook", help="Internal lifecycle hook execution")
    hook_p.add_argument("event", choices=["post-tool", "context", "session-end"], help="Hook event")
    hook_p.add_argument("--tool", default="", help="Tool name")
    hook_p.add_argument("--input", default="", help="Tool input")
    hook_p.add_argument("--output", default="", help="Tool output")
    hook_p.add_argument("--project", default="", help="Project name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    store = MemoryStore()
    drive = DriveSyncManager()

    if args.command == "install":
        print(f"📦 Installing gemini-mem for {args.ide}...")
        ok = install_antigravity_hooks()
        if ok:
            print("✅ Successfully installed gemini-mem crash-proof hooks!")
            print(f"🧠 Database initialized at: {config.db_path}")
            if drive.is_available:
                print(f"☁️ Google Drive 2TB Roaming detected at: {drive.drive_root}")
            else:
                print("ℹ️ Google Drive local folder not auto-detected; memories will be stored locally.")
        else:
            print("⚠️ Hook registration finished with local fallback.")

    elif args.command == "start":
        run_dashboard(port=args.port, host=args.host)

    elif args.command == "daemon":
        pid_file = config.data_dir / "daemon.pid"
        if args.action == "start":
            import subprocess
            py = sys.executable
            cmd = [py, "-m", "gemini_mem.cli", "start", "--port", str(args.port)]
            if sys.platform == "win32":
                # DETACHED_PROCESS = 0x00000008, CREATE_NEW_PROCESS_GROUP = 0x00000200
                flags = 0x00000008 | 0x00000200
                p = subprocess.Popen(cmd, creationflags=flags, close_fds=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                p = subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            config.ensure_dirs()
            pid_file.write_text(str(p.pid), encoding="utf-8")
            print(f"🚀 gemini-mem daemon started in background (PID: {p.pid}) on http://{config.host}:{args.port}")

        elif args.action == "stop":
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text("utf-8").strip())
                    import signal
                    os.kill(pid, signal.SIGTERM)
                    print(f"🛑 Stopped gemini-mem daemon (PID: {pid}).")
                except Exception as e:
                    print(f"⚠️ Could not stop process: {e}")
                pid_file.unlink(missing_ok=True)
            else:
                print("ℹ️ No daemon PID file found.")

        elif args.action == "status":
            if pid_file.exists():
                pid = pid_file.read_text("utf-8").strip()
                print(f"🟢 gemini-mem daemon is running in background (PID: {pid}).")
            else:
                print("⚪ gemini-mem daemon is not running.")

    elif args.command == "status":
        stats = {
            "version": __version__,
            "database_path": str(config.db_path),
            "observations": len(store.get_timeline(limit=10000)),
            "entities": len(store.get_graph().entities),
            "relations": len(store.get_graph().relations),
            "summaries": len(store.get_recent_summaries(limit=100)),
            "google_drive_sync": drive.get_status()
        }
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif args.command == "search":
        results = store.search_observations(args.query, project=args.project or None, limit=args.limit)
        print(f"🔍 Found {len(results)} observation(s) matching '{args.query}':\n")
        for r in results:
            print(f"#{r.id} [{r.type.upper()}] {r.title} ({r.created_at})")
            if r.narrative:
                print(f"   {r.narrative}")
            if r.facts:
                for f in r.facts:
                    print(f"   - {f}")
            print()

    elif args.command == "graph":
        g = store.get_graph(project=args.project or None)
        print(f"🕸️ Knowledge Graph ({len(g.entities)} Entities, {len(g.relations)} Synapses):\n")
        print("Entities:")
        for e in g.entities:
            print(f"  • [{e.entity_type}] {e.name}")
        if g.relations:
            print("\nRelations:")
            for r in g.relations:
                print(f"  • {r.source} ──({r.relation_type})──► {r.target}")

    elif args.command == "context":
        print(store.generate_context_block(project=args.project or None))

    elif args.command == "sync":
        print("☁️ Syncing memory database to Google Drive (2TB)...")
        ok = drive.sync_to_drive()
        if ok:
            print("✅ Sync complete! Snapshot saved.")
        else:
            print("⚠️ Sync failed or Google Drive path not accessible.")

    elif args.command == "hook":
        try:
            if args.event == "post-tool":
                safe_post_tool_use(args.tool, args.input, args.output, args.project)
            elif args.event == "context":
                print(safe_session_start(args.project))
            elif args.event == "session-end":
                transcript = sys.stdin.read() if not sys.stdin.isatty() else ""
                safe_session_end(transcript, args.project)
        except Exception:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
