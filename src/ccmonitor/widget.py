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


def _remaining_ratio(limit: dict[str, Any] | None, key: str = "used_percent") -> float:
    if not limit:
        return 0.0
    used = limit.get(key)
    try:
        used_float = float(used)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, (100.0 - used_float) / 100.0))


def _format_reset(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%m-%d %H:%M")
    except ValueError:
        return value


def _build_provider_status(data: dict[str, Any], provider: str) -> dict[str, Any]:
    current = data.get(provider, {}).get("current_limits")
    if provider == "codex":
        five_hour = (current or {}).get("primary")
        seven_day = (current or {}).get("secondary")
        return {
            "title": "Codex",
            "five_left": _remaining_percent(five_hour, "used_percent"),
            "five_ratio": _remaining_ratio(five_hour, "used_percent"),
            "five_reset": _format_reset((five_hour or {}).get("resets_at")),
            "week_left": _remaining_percent(seven_day, "used_percent"),
            "week_ratio": _remaining_ratio(seven_day, "used_percent"),
            "week_reset": _format_reset((seven_day or {}).get("resets_at")),
            "available": "yes" if current else "no",
        }

    five_hour = (current or {}).get("five_hour")
    seven_day = (current or {}).get("seven_day")
    return {
        "title": "Claude",
        "five_left": _remaining_percent(five_hour, "used_percentage"),
        "five_ratio": _remaining_ratio(five_hour, "used_percentage"),
        "five_reset": _format_reset((five_hour or {}).get("resets_at")),
        "week_left": _remaining_percent(seven_day, "used_percentage"),
        "week_ratio": _remaining_ratio(seven_day, "used_percentage"),
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
    root.overrideredirect(True)

    drag_state = {"x": 0, "y": 0, "resizing": False}
    window_state = {"maximized": False, "pre_max_geometry": root.geometry()}

    outer = tk.Frame(root, bg="#101516", padx=12, pady=12)
    outer.pack(fill="both", expand=True)
    outer.grid_columnconfigure(0, weight=1)
    outer.grid_rowconfigure(1, weight=1)

    header = tk.Frame(outer, bg="#0c1112", height=34, padx=10, pady=6)
    header.grid(row=0, column=0, sticky="ew")
    header.grid_columnconfigure(1, weight=1)

    title = tk.Label(
        header,
        text="Usage Limits",
        bg="#0c1112",
        fg="#f3f3ec",
        font=("Segoe UI Semibold", 12),
    )
    title.grid(row=0, column=0, sticky="w")

    meta = tk.Label(
        header,
        text="",
        bg="#0c1112",
        fg="#93a19a",
        font=("Segoe UI", 8),
    )
    meta.grid(row=0, column=1, sticky="e", padx=(0, 10))

    controls = tk.Frame(header, bg="#0c1112")
    controls.grid(row=0, column=2, sticky="e")

    def style_button(text: str, command: Any, danger: bool = False) -> tk.Button:
        return tk.Button(
            controls,
            text=text,
            command=command,
            width=3,
            relief="flat",
            bd=0,
            highlightthickness=0,
            bg="#0c1112",
            activebackground="#b54848" if danger else "#223033",
            fg="#f6f6ef",
            activeforeground="#ffffff",
            font=("Segoe UI Symbol", 10),
            cursor="hand2",
        )

    cards_frame = tk.Frame(outer, bg="#101516")
    cards_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

    if showing_both:
        cards_frame.grid_columnconfigure(0, weight=1, uniform="provider")
        cards_frame.grid_columnconfigure(1, weight=1, uniform="provider")
        cards_frame.grid_rowconfigure(0, weight=1)
    else:
        cards_frame.grid_columnconfigure(0, weight=1)
        cards_frame.grid_rowconfigure(0, weight=1)

    provider_cards: dict[str, dict[str, Any]] = {}

    def set_gauge(canvas: tk.Canvas, fill_id: int, ratio: float) -> None:
        canvas.update_idletasks()
        width = max(1, canvas.winfo_width())
        inset = 2
        fill_width = inset + max(0.0, min(1.0, ratio)) * max(0, width - inset * 2)
        canvas.coords(fill_id, inset, inset, fill_width, 14)

    def build_card(
        parent: tk.Widget,
        accent: str,
        title_text: str,
        column: int = 0,
    ) -> dict[str, Any]:
        card = tk.Frame(
            parent,
            bg="#171d1f",
            highlightthickness=1,
            highlightbackground="#2b3437",
            padx=10,
            pady=10,
        )
        if showing_both:
            padx = (0, 5) if column == 0 else (5, 0)
            card.grid(row=0, column=column, sticky="nsew", padx=padx, pady=5)
        else:
            card.grid(row=0, column=0, sticky="nsew", pady=5)

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

        five_gauge = tk.Canvas(
            grid,
            height=16,
            bg="#171d1f",
            highlightthickness=0,
            bd=0,
        )
        five_gauge.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        five_gauge.create_rectangle(
            2, 2, 238, 14, fill="#263033", outline=""
        )
        five_fill = five_gauge.create_rectangle(
            2, 2, 2, 14, fill=accent, outline=""
        )

        tk.Label(
            grid,
            text="reset",
            bg="#171d1f",
            fg="#93a19a",
            font=("Segoe UI", 9),
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))
        five_reset = tk.Label(
            grid,
            text="-",
            bg="#171d1f",
            fg="#d0d5cf",
            font=("Consolas", 9),
        )
        five_reset.grid(row=2, column=1, sticky="e", padx=(8, 0), pady=(6, 0))

        tk.Label(
            grid,
            text="7d left",
            bg="#171d1f",
            fg="#93a19a",
            font=("Segoe UI", 9),
        ).grid(row=3, column=0, sticky="w", pady=(10, 0))
        week_left = tk.Label(
            grid,
            text="-",
            bg="#171d1f",
            fg="#f3f3ec",
            font=("Segoe UI Semibold", 13),
        )
        week_left.grid(row=3, column=1, sticky="e", padx=(8, 0), pady=(10, 0))

        week_gauge = tk.Canvas(
            grid,
            height=16,
            bg="#171d1f",
            highlightthickness=0,
            bd=0,
        )
        week_gauge.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        week_gauge.create_rectangle(
            2, 2, 238, 14, fill="#263033", outline=""
        )
        week_fill = week_gauge.create_rectangle(
            2, 2, 2, 14, fill=accent, outline=""
        )

        tk.Label(
            grid,
            text="reset",
            bg="#171d1f",
            fg="#93a19a",
            font=("Segoe UI", 9),
        ).grid(row=5, column=0, sticky="w", pady=(6, 0))
        week_reset = tk.Label(
            grid,
            text="-",
            bg="#171d1f",
            fg="#d0d5cf",
            font=("Consolas", 9),
        )
        week_reset.grid(row=5, column=1, sticky="e", padx=(8, 0), pady=(6, 0))

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=0)

        return {
            "five_left": five_left,
            "five_gauge": five_gauge,
            "five_fill": five_fill,
            "five_reset": five_reset,
            "week_left": week_left,
            "week_gauge": week_gauge,
            "week_fill": week_fill,
            "week_reset": week_reset,
            "unavailable": unavailable,
        }

    for index, name in enumerate(_provider_order(provider)):
        accent = "#58c7a7" if name == "codex" else "#f29b6d"
        provider_cards[name] = build_card(
            cards_frame,
            accent=accent,
            title_text="Codex" if name == "codex" else "Claude",
            column=index,
        )

    footer = tk.Frame(outer, bg="#101516")
    footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
    tk.Label(
        footer,
        text="Drag header  Double-click maximize  R refresh  T topmost  Q close",
        bg="#101516",
        fg="#6e7a75",
        font=("Segoe UI", 8),
    ).pack(side="left")

    resize_grip = tk.Frame(footer, bg="#2b3437", width=16, height=16, cursor="size_nw_se")
    resize_grip.pack(side="right")

    refresh_job: str | None = None

    def start_drag(event: tk.Event[Any]) -> None:
        drag_state["x"] = event.x_root
        drag_state["y"] = event.y_root

    def drag_window(event: tk.Event[Any]) -> None:
        if window_state["maximized"]:
            return
        delta_x = event.x_root - drag_state["x"]
        delta_y = event.y_root - drag_state["y"]
        drag_state["x"] = event.x_root
        drag_state["y"] = event.y_root
        root.geometry(f"+{root.winfo_x() + delta_x}+{root.winfo_y() + delta_y}")

    def toggle_maximize(_event: object | None = None) -> None:
        if window_state["maximized"]:
            root.state("normal")
            root.geometry(window_state["pre_max_geometry"])
            window_state["maximized"] = False
            return
        window_state["pre_max_geometry"] = root.geometry()
        root.state("zoomed")
        window_state["maximized"] = True

    def minimize_window() -> None:
        root.overrideredirect(False)
        root.iconify()

    def on_map(_event: object | None = None) -> None:
        root.after(10, lambda: root.overrideredirect(True))

    def start_resize(event: tk.Event[Any]) -> None:
        drag_state["resizing"] = True
        drag_state["x"] = event.x_root
        drag_state["y"] = event.y_root
        window_state["pre_max_geometry"] = root.geometry()

    def resize_window(event: tk.Event[Any]) -> None:
        if window_state["maximized"]:
            return
        delta_x = event.x_root - drag_state["x"]
        delta_y = event.y_root - drag_state["y"]
        width = max(root.winfo_width() + delta_x, 640 if showing_both else 340)
        height = max(root.winfo_height() + delta_y, 170)
        root.geometry(f"{width}x{height}+{root.winfo_x()}+{root.winfo_y()}")
        drag_state["x"] = event.x_root
        drag_state["y"] = event.y_root

    def stop_resize(_event: object | None = None) -> None:
        drag_state["resizing"] = False

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
            set_gauge(card["five_gauge"], card["five_fill"], status["five_ratio"])
            set_gauge(card["week_gauge"], card["week_fill"], status["week_ratio"])
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

    for widget in (header, title, meta):
        widget.bind("<ButtonPress-1>", start_drag)
        widget.bind("<B1-Motion>", drag_window)
        widget.bind("<Double-Button-1>", toggle_maximize)

    resize_grip.bind("<ButtonPress-1>", start_resize)
    resize_grip.bind("<B1-Motion>", resize_window)
    resize_grip.bind("<ButtonRelease-1>", stop_resize)

    minimize_button = style_button("_", minimize_window)
    minimize_button.pack(side="left", padx=(0, 4))
    maximize_button = style_button("□", toggle_maximize)
    maximize_button.pack(side="left", padx=(0, 4))
    close_button = style_button("×", root.destroy, danger=True)
    close_button.pack(side="left")

    root.bind("r", manual_refresh)
    root.bind("R", manual_refresh)
    root.bind("t", toggle_topmost)
    root.bind("T", toggle_topmost)
    root.bind("q", lambda _event: root.destroy())
    root.bind("Q", lambda _event: root.destroy())
    root.bind("<Map>", on_map)

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
