from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture Claude statusLine JSON for the monitor dashboard."
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        help="Where to write the latest statusLine payload.",
    )
    return parser


def format_status(payload: dict[str, Any]) -> str:
    model = (payload.get("model") or {}).get("display_name", "Claude")
    limits = payload.get("rate_limits") or {}
    five_hour = limits.get("five_hour") or {}
    seven_day = limits.get("seven_day") or {}
    five_used = five_hour.get("used_percentage")
    seven_used = seven_day.get("used_percentage")
    if five_used is None and seven_used is None:
        return f"[{model}] limits unavailable"
    return f"[{model}] 5h {five_used or 0}% | 7d {seven_used or 0}%"


def main() -> int:
    args = build_parser().parse_args()
    payload = json.load(sys.stdin)
    payload["captured_at"] = datetime.now(UTC).isoformat()
    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    args.snapshot.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(format_status(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
