from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ccmonitor.widget import build_widget_parser, run_widget_from_args


def main() -> int:
    parser = build_widget_parser()
    args = parser.parse_args()
    return run_widget_from_args(args)


if __name__ == "__main__":
    raise SystemExit(main())
