from __future__ import annotations

import argparse
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .collector import UsageCollector

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_widget_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Small Codex/Claude limit widget."
    )
    parser.add_argument(
        "--mode",
        choices=["gui", "cli"],
        default="gui",
        help="Run as a small GUI window or compact CLI output.",
    )
    parser.add_argument(
        "--provider",
        choices=["both", "codex", "claude"],
        default="both",
        help="Which providers to show.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Refresh interval in seconds.",
    )
    parser.add_argument(
        "--no-topmost",
        action="store_true",
        help="Disable always-on-top for the GUI window.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print one CLI snapshot and exit.",
    )
    parser.add_argument(
        "--statusline-snapshot",
        type=Path,
        default=REPO_ROOT / "data" / "claude_statusline_snapshot.json",
        help="Path to the optional Claude statusLine snapshot file.",
    )
    return parser


def _remaining_percent(limit: dict[str, Any] | None, key: str = "used_percent") -> str:
    if not limit:
        return "-"
    used = limit.get(key)
    if used is None:
        return "-"
    try:
        used_float = float(used)
    except (TypeError, ValueError):
        return "-"
    return f"{max(0.0, 100.0 - used_float):.0f}%"


def _format_reset(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%m-%d %H:%M")
    except ValueError:
        return value


def _build_provider_status(data: dict[str, Any], provider: str) -> dict[str, str]:
    current = data.get(provider, {}).get("current_limits")
    if provider == "codex":
        five_hour = (current or {}).get("primary")
        seven_day = (current or {}).get("secondary")
        return {
            "title": "Codex",
            "five_left": _remaining_percent(five_hour, "used_percent"),
            "five_reset": _format_reset((five_hour or {}).get("resets_at")),
            "week_left": _remaining_percent(seven_day, "used_percent"),
            "week_reset": _format_reset((seven_day or {}).get("resets_at")),
            "available": "yes" if current else "no",
        }

    five_hour = (current or {}).get("five_hour")
    seven_day = (current or {}).get("seven_day")
    return {
        "title": "Claude",
        "five_left": _remaining_percent(five_hour, "used_percentage"),
        "five_reset": _format_reset((five_hour or {}).get("resets_at")),
        "week_left": _remaining_percent(seven_day, "used_percentage"),
        "week_reset": _format_reset((seven_day or {}).get("resets_at")),
        "available": "yes" if current else "no",
    }


def _provider_order(selection: str) -> list[str]:
    if selection == "both":
        return ["codex", "claude"]
    return [selection]


def _print_cli_snapshot(collector: UsageCollector, provider: str) -> None:
    payload = collector.collect_limits_only()
    print(f"Updated {datetime.now().strftime('%H:%M:%S')}")
    print()
    for name in _provider_order(provider):
        status = _build_provider_status(payload, name)
        print(status["title"].upper())
        if status["available"] != "yes":
            print("  5h left : unavailable")
            print("  7d left : unavailable")
            print("  reset   : status snapshot needed")
            print()
            continue
        print(f"  5h left : {status['five_left']}")
        print(f"  5h reset: {status['five_reset']}")
        print(f"  7d left : {status['week_left']}")
        print(f"  7d reset: {status['week_reset']}")
        print()


def run_cli_widget(
    collector: UsageCollector,
    provider: str,
    interval: int,
    once: bool = False,
) -> int:
    if once:
        _print_cli_snapshot(collector, provider)
        return 0

    try:
        while True:
            os.system("cls")
            _print_cli_snapshot(collector, provider)
            time.sleep(max(3, interval))
    except KeyboardInterrupt:
        return 0


def run_gui_widget(
    collector: UsageCollector,
    provider: str,
    interval: int,
    topmost: bool,
) -> int:
    import tkinter as tk

    root = tk.Tk()
    root.title("Usage Limits")
    showing_both = provider == "both"
    root.geometry("720x220" if showing_both else "380x220")
    root.minsize(640 if showing_both else 340, 170)
    root.configure(bg="#101516")
    root.attributes("-topmost", topmost)

    outer = tk.Frame(root, bg="#101516", padx=12, pady=12)
    outer.pack(fill="both", expand=True)

    header = tk.Frame(outer, bg="#101516")
    header.pack(fill="x")

    title = tk.Label(
        header,
        text="Usage Limits",
        bg="#101516",
        fg="#f3f3ec",
        font=("Segoe UI Semibold", 12),
    )
    title.pack(side="left")

    meta = tk.Label(
        header,
        text="",
        bg="#101516",
        fg="#93a19a",
        font=("Segoe UI", 8),
    )
    meta.pack(side="right")

    cards_frame = tk.Frame(outer, bg="#101516")
    cards_frame.pack(fill="both", expand=True, pady=(10, 0))

    provider_cards: dict[str, dict[str, tk.Label]] = {}

    def build_card(parent: tk.Widget, accent: str, title_text: str) -> dict[str, tk.Label]:
        card = tk.Frame(
            parent,
            bg="#171d1f",
            highlightthickness=1,
            highlightbackground="#2b3437",
            padx=10,
            pady=10,
        )
        card.pack(
            side="left" if showing_both else "top",
            fill="both" if showing_both else "x",
            expand=True,
            padx=5 if showing_both else 0,
            pady=5,
        )

        title_row = tk.Frame(card, bg="#171d1f")
        title_row.pack(fill="x")
        tk.Label(
            title_row,
            text=title_text,
            bg="#171d1f",
            fg=accent,
            font=("Segoe UI Semibold", 11),
        ).pack(side="left")

        unavailable = tk.Label(
            title_row,
            text="",
            bg="#171d1f",
            fg="#b67373",
            font=("Segoe UI", 8),
        )
        unavailable.pack(side="right")

        grid = tk.Frame(card, bg="#171d1f")
        grid.pack(fill="x", pady=(8, 0))

        tk.Label(
            grid,
            text="5h left",
            bg="#171d1f",
            fg="#93a19a",
            font=("Segoe UI", 9),
        ).grid(row=0, column=0, sticky="w")
        five_left = tk.Label(
            grid,
            text="-",
            bg="#171d1f",
            fg="#f3f3ec",
            font=("Segoe UI Semibold", 13),
        )
        five_left.grid(row=0, column=1, sticky="e", padx=(8, 0))

        tk.Label(
            grid,
            text="reset",
            bg="#171d1f",
            fg="#93a19a",
            font=("Segoe UI", 9),
        ).grid(row=1, column=0, sticky="w")
        five_reset = tk.Label(
            grid,
            text="-",
            bg="#171d1f",
            fg="#d0d5cf",
            font=("Consolas", 9),
        )
        five_reset.grid(row=1, column=1, sticky="e", padx=(8, 0))

        tk.Label(
            grid,
            text="7d left",
            bg="#171d1f",
            fg="#93a19a",
            font=("Segoe UI", 9),
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))
        week_left = tk.Label(
            grid,
            text="-",
            bg="#171d1f",
            fg="#f3f3ec",
            font=("Segoe UI Semibold", 13),
        )
        week_left.grid(row=2, column=1, sticky="e", padx=(8, 0), pady=(6, 0))

        tk.Label(
            grid,
            text="reset",
            bg="#171d1f",
            fg="#93a19a",
            font=("Segoe UI", 9),
        ).grid(row=3, column=0, sticky="w")
        week_reset = tk.Label(
            grid,
            text="-",
            bg="#171d1f",
            fg="#d0d5cf",
            font=("Consolas", 9),
        )
        week_reset.grid(row=3, column=1, sticky="e", padx=(8, 0))

        grid.columnconfigure(0, weight=1)

        return {
            "five_left": five_left,
            "five_reset": five_reset,
            "week_left": week_left,
            "week_reset": week_reset,
            "unavailable": unavailable,
        }

    for name in _provider_order(provider):
        accent = "#58c7a7" if name == "codex" else "#f29b6d"
        provider_cards[name] = build_card(
            cards_frame,
            accent=accent,
            title_text="Codex" if name == "codex" else "Claude",
        )

    footer = tk.Frame(outer, bg="#101516")
    footer.pack(fill="x", pady=(10, 0))
    tk.Label(
        footer,
        text="R refresh  T topmost  Q close",
        bg="#101516",
        fg="#6e7a75",
        font=("Segoe UI", 8),
    ).pack(side="left")

    refresh_job: str | None = None

    def refresh(schedule_next: bool = True) -> None:
        nonlocal refresh_job
        payload = collector.collect_limits_only()
        meta.config(text=datetime.now().strftime("%H:%M:%S"))
        for name, card in provider_cards.items():
            status = _build_provider_status(payload, name)
            card["five_left"].config(text=status["five_left"])
            card["five_reset"].config(text=status["five_reset"])
            card["week_left"].config(text=status["week_left"])
            card["week_reset"].config(text=status["week_reset"])
            if status["available"] == "yes":
                card["unavailable"].config(text="")
            else:
                card["unavailable"].config(text="snapshot needed")
        if schedule_next:
            refresh_job = root.after(max(3000, interval * 1000), refresh)

    def toggle_topmost(_event: object | None = None) -> None:
        current = bool(root.attributes("-topmost"))
        root.attributes("-topmost", not current)

    def manual_refresh(_event: object | None = None) -> None:
        nonlocal refresh_job
        if refresh_job is not None:
            root.after_cancel(refresh_job)
            refresh_job = None
        refresh()

    root.bind("r", manual_refresh)
    root.bind("R", manual_refresh)
    root.bind("t", toggle_topmost)
    root.bind("T", toggle_topmost)
    root.bind("q", lambda _event: root.destroy())
    root.bind("Q", lambda _event: root.destroy())

    refresh()
    root.mainloop()
    return 0


def run_widget_from_args(args: argparse.Namespace) -> int:
    collector = UsageCollector(
        codex_root=Path.home() / ".codex",
        claude_root=Path.home() / ".claude",
        statusline_snapshot=args.statusline_snapshot,
        lookback_days=3,
    )

    if args.mode == "cli":
        return run_cli_widget(
            collector=collector,
            provider=args.provider,
            interval=args.interval,
            once=args.once,
        )

    return run_gui_widget(
        collector=collector,
        provider=args.provider,
        interval=args.interval,
        topmost=not args.no_topmost,
    )
