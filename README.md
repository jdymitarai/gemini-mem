<div align="center">

# ✦ gemini-mem

### Persistent Agent Memory & Knowledge Graph Engine for Google AI & Gemini Advanced Subscribers

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](https://www.python.org/)
[![Google AI](https://img.shields.io/badge/Google%20AI-Gemini%202.5%20Flash%20%2F%20Pro-4285F4.svg)](https://ai.google.dev/)
[![Google One](https://img.shields.io/badge/Cloud%20Roaming-2TB%20Google%20Drive-34A853.svg)](https://one.google.com/)
[![Zero External Deps](https://img.shields.io/badge/dependencies-0%20mandatory-orange.svg)](#zero-dependency-architecture)

<br/>

**Preserve context, architectural decisions, and technical lessons across coding agent sessions without monthly third-party subscriptions.**

Built specifically for engineers subscribing to **Google One AI Premium**, **Gemini Advanced**, and **Google Cloud AI**.

[Quick Start](#-quick-start) •
[Why gemini-mem?](#-why-gemini-mem-vs-claude-mem) •
[Architecture](#-architecture) •
[Web Dashboard](#-material-3-web-dashboard) •
[MCP Integration](#-mcp-integration) •
[CLI Commands](#-cli-commands)

</div>

---

## ⚡ The Problem & The Solution

AI coding agents (Antigravity, Gemini CLI, Cursor, Claude Code) suffer from **amnesia**: when a session closes or resets, all hard-earned context, bugfix root causes, and architectural lessons vanish.

Existing solutions like `claude-mem` force developers into Anthropic Claude Pro (\$20/mo) subscriptions and rely on brittle shell hooks that can lock up the developer's IDE when credential tokens expire.

**`gemini-mem` changes this:**
1. **Designed for Google AI Subscribers**: Seamlessly uses your Google AI Studio or Gemini Advanced API.
2. **2TB Google Drive Cloud Roaming**: Automatically backs up and syncs your agent's brain across all your developer machines using the 2TB storage included with Google One AI.
3. **Crash-Proof Karpathy Architecture**: 100% non-blocking. If offline or disconnected, hooks fail-safe in `< 5ms` with zero IDE interference.
4. **Relational Knowledge Graph**: Beyond flat text notes—maintains an evolving concept graph of components, dependencies, and bug root causes.
5. **Zero Mandatory Dependencies**: Runs entirely on standard Python 3.10+ (SQLite FTS5 + WAL mode + native HTTPS).

---

## 🥊 Why gemini-mem? vs claude-mem

| Feature | `thedotmack/claude-mem` | `gemini-mem` (This Project) |
| :--- | :--- | :--- |
| **Subscription Barrier** | Mandatory Anthropic Claude Pro (\$20/mo) | **Native Google AI** (Works with Google One / AI Studio free & paid tiers) |
| **Cloud Roaming** | Third-party vendor cloud lock-in | **Your Own 2TB Google Drive** (Cross-machine auto-sync) |
| **Context Synthesis** | Limited context windows | **Up to 2,000,000 Tokens** via Gemini 2.5 Pro / Flash |
| **Hook Reliability** | Fragile multi-line Bash hooks (blocks IDE on failure) | **Crash-Proof Karpathy Design** (Guaranteed non-blocking, exit 0 safety) |
| **Memory Structure** | Flat text records with keyword search | **Knowledge Graph** (Entities, Synapses, Relations) + **FTS5 Full-Text** |
| **Runtime Footprint** | Heavy Node.js + Bun daemon (~200MB) | **Zero-Dependency Python Standard Library** (< 15MB) |
| **Visual Dashboard** | Basic plain text viewer | **Google Material 3 Dark UI** with real-time dynamic graph physics |

---

## 🚀 Quick Start

### 1. Installation

Clone and install with pip:

```bash
git clone https://github.com/jdymitarai/gemini-mem.git
cd gemini-mem
pip install -e .
```

### 2. Auto-configure Antigravity / Gemini CLI

```bash
gemini-mem install --ide antigravity
```

### 3. Launch the Background OS Daemon (or Web Dashboard)

```bash
# Start as a detached background daemon (runs silently, never blocks chat or terminal)
gemini-mem daemon start

# Or run interactively in the foreground
gemini-mem start
```

Visit [`http://127.0.0.1:38888`](http://127.0.0.1:38888) to explore your agent's neural knowledge graph in real time!

---

## 🏛️ Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │          Google AI / Gemini Advanced         │
                    │       (Google One AI Premium 2TB Drive)      │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 gemini-mem Core Engine                                 │
├────────────────────────────┬───────────────────────────────┬───────────────────────────┤
│  1. Knowledge Graph Store  │  2. Google Drive 2TB Roaming  │  3. Gemini 2.5 Synthesizer │
│  - SQLite WAL Mode         │  - Multi-machine sync         │  - High-precision digest  │
│  - FTS5 Full-Text Index    │  - Timestamped cloud backups  │  - Context generation     │
│  - Entities & Relations    │  - Google Drive auto-detect   │  - Offline heuristic rule │
├────────────────────────────┴───────────────────────────────┴───────────────────────────┤
│  4. Crash-Proof Lifecycle Hooks (Antigravity, Gemini CLI, Cursor, Claude Code)         │
│  - 100% non-blocking async execution • Guaranteed zero IDE lockups                     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  5. Material 3 Neural Dashboard (http://127.0.0.1:38888)                               │
│  - Real-time HTML5 Canvas force-directed graph • Instant memory search                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 Material 3 Web Dashboard

`gemini-mem` includes a built-in, lightweight web UI on port `38888`:

* **Live Knowledge Graph**: Dynamic spring-physics canvas visualizing entities and relational synapses.
* **Instant FTS5 Search**: Search through months of observations, bugfixes, and technical decisions.
* **Google One Sync Monitor**: One-click manual sync or real-time status of your 2TB Google Drive replica.

---

## 🔌 MCP Integration

`gemini-mem` includes a native Model Context Protocol (MCP) server for Antigravity, Cursor, and VS Code.

Add this to your MCP configuration (`mcp_config.json`):

```json
{
  "mcpServers": {
    "gemini-mem": {
      "command": "python",
      "args": ["-m", "gemini_mem.mcp.server"]
    }
  }
}
```

### Available MCP Tools:

1. **`gemini_mem_search`**: Fast keyword & semantic lookup (`query`, `project`, `limit`).
2. **`gemini_mem_get_observations`**: Fetch full technical facts and modified files by IDs.
3. **`gemini_mem_get_graph`**: Retrieve the project's entity-relationship map.
4. **`gemini_mem_save_observation`**: Manually record architectural decisions and lessons.
5. **`gemini_mem_sync_drive`**: Trigger immediate sync to 2TB Google Drive.

---

## 💻 CLI Commands

```bash
# Manage background OS daemon (independent of chat/terminal)
gemini-mem daemon start
gemini-mem daemon status
gemini-mem daemon stop

# Check memory database stats and Google Drive sync status
gemini-mem status

# Search past lessons and technical facts
gemini-mem search "memory allocation overflow"

# View Knowledge Graph entities and relations
gemini-mem graph

# Print context block ready for agent prompt injection
gemini-mem context

# Sync memory database to 2TB Google Drive
gemini-mem sync
```

---

## 🧪 Testing

`gemini-mem` is covered by standard library unit tests with 100% offline verification:

```bash
python -m unittest tests/test_all.py
```

---

## 📄 License

Distributed under the Apache 2.0 License. See [LICENSE](LICENSE) for details.
