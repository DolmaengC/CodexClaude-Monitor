# Codex Claude Monitor

Small local widget for checking only the remaining 5-hour and 7-day limits for
Codex and Claude.

## Mini window

```powershell
python .\run_widget.py
```

This opens a small always-on-top window that auto-refreshes every 15 seconds.

Useful options:

```powershell
python .\run_widget.py --provider codex
python .\run_widget.py --provider claude
python .\run_widget.py --no-topmost
```

Keyboard shortcuts in the window:

- `R` refresh now
- `T` toggle always-on-top
- `Q` close

## CLI mini mode

```powershell
python .\run_widget.py --mode cli
python .\run_widget.py --mode cli --once
```

## Claude live limits

Codex live limits are read directly from `~/.codex/sessions`. Claude's 5h/7d
limits are not present in the regular session logs, so the widget uses an
optional Claude `statusLine` snapshot if you enable it:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\install_claude_statusline.ps1
```

After that, interact with Claude once and the widget will start showing Claude
live limit remaining and reset times.

## Web dashboard

The earlier web dashboard is still available:

```powershell
python .\run_monitor.py
```
