from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ccmonitor.collector import UsageCollector
from ccmonitor.server import serve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local dashboard for Codex and Claude usage."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=14,
        help="Number of days of daily totals to keep in charts.",
    )
    parser.add_argument(
        "--statusline-snapshot",
        type=Path,
        default=ROOT / "data" / "claude_statusline_snapshot.json",
        help="Path to the optional Claude statusLine snapshot file.",
    )
    parser.add_argument(
        "--once-json",
        action="store_true",
        help="Print a single JSON payload and exit.",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the dashboard in the default browser after starting the server.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    collector = UsageCollector(
        codex_root=Path.home() / ".codex",
        claude_root=Path.home() / ".claude",
        statusline_snapshot=args.statusline_snapshot,
        lookback_days=args.lookback_days,
    )

    if args.once_json:
        payload = collector.collect()
        print(json.dumps(payload, indent=2))
        return 0

    url = f"http://{args.host}:{args.port}"
    print(f"Serving Codex/Claude monitor at {url}")
    print("Press Ctrl+C to stop.")

    if args.open_browser:
        webbrowser.open(url)

    serve(
        collector=collector,
        static_dir=ROOT / "static",
        host=args.host,
        port=args.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
