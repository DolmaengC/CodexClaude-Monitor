# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Local monitor for OpenAI Codex and Anthropic Claude usage limits (5-hour and 7-day windows). Reads session logs from `~/.codex/sessions` and `~/.claude/projects`, and optionally reads a Claude `statusLine` snapshot for live limit percentages.

## Running the tools

```bash
# Always-on-top GUI widget (default, auto-refreshes every 15s)
python run_widget.py
python run_widget.py --provider codex
python run_widget.py --provider claude
python run_widget.py --no-topmost

# CLI mode
python run_widget.py --mode cli
python run_widget.py --mode cli --once

# Web dashboard at http://127.0.0.1:8765
python run_monitor.py
python run_monitor.py --open-browser
python run_monitor.py --once-json   # dump JSON and exit

# Install Claude statusLine hook (PowerShell, one-time setup)
powershell -ExecutionPolicy Bypass -File .\tools\install_claude_statusline.ps1
```

## Architecture

There is no build step. `src/` is added to `sys.path` at runtime by the two entry-point scripts.

```
run_widget.py          → src/ccmonitor/widget.py   (tkinter GUI + CLI)
run_monitor.py         → src/ccmonitor/server.py   (ThreadingHTTPServer)
                       → static/index.html + app.js + styles.css
Both entry points use  → src/ccmonitor/collector.py (all data parsing)
```

### `collector.py` — `UsageCollector`

Central data layer. Two public methods:
- `collect()` — full payload for the web dashboard (daily token series, session lists, rate-limit history)
- `collect_limits_only()` — lightweight snapshot for the widget (current limit percentages only)

File reads are memoized by `(mtime_ns, size)` so re-polls are cheap. Codex sessions are `.jsonl` files under `~/.codex/sessions/**` and `~/.codex/archived_sessions/`. Claude sessions are `.jsonl` files under `~/.claude/projects/**`.

**Codex limits** come from `token_count` events inside session `.jsonl` files — each event carries `rate_limits.primary` (5h window) and `rate_limits.secondary` (7d window).

**Claude limits** are not present in the regular JSONL logs. They come from `data/claude_statusline_snapshot.json`, written by `tools/claude_statusline_capture.py` which is invoked as a Claude `statusLine` hook command after each interaction.

### `widget.py` — dual-mode display

GUI uses plain `tkinter` with `overrideredirect(True)` (frameless window). Drag, resize, maximize, minimize, and keyboard shortcuts (`R`, `T`, `Q`) are all implemented manually. The widget calls `collect_limits_only()` on a timer and updates labels + canvas gauge bars in place.

CLI mode calls `os.system("cls")` to redraw in a loop.

### `server.py` — web dashboard backend

Minimal `ThreadingHTTPServer` with two routes: `GET /api/data` (calls `collector.collect()`) and everything else served from `static/`. Path traversal is blocked by checking `static_root not in candidate.parents`.

## Data flow for Claude live limits

`install_claude_statusline.ps1` writes a `statusLine` hook into `~/.claude/settings.json`. After each Claude interaction, Claude Code pipes the session's statusLine JSON to `tools/claude_statusline_capture.py`, which writes it to `data/claude_statusline_snapshot.json`. The collector reads that file on every poll.

## Key field name differences between providers

| Concept | Codex field | Claude field |
|---|---|---|
| 5h usage | `primary.used_percent` | `five_hour.used_percentage` |
| 7d usage | `secondary.used_percent` | `seven_day.used_percentage` |

These are handled in `widget.py:_build_provider_status` with explicit per-provider branches.
