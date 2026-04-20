from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value).astimezone(UTC)
    except ValueError:
        return None


def _epoch_to_iso(epoch_seconds: int | None) -> str | None:
    if not epoch_seconds:
        return None
    try:
        return datetime.fromtimestamp(int(epoch_seconds), tz=UTC).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _display_name(path: Path, anchor: Path) -> str:
    try:
        return str(path.relative_to(anchor))
    except ValueError:
        return str(path)


@dataclass
class _CacheEntry:
    mtime_ns: int
    size: int
    data: Any


class UsageCollector:
    def __init__(
        self,
        codex_root: Path,
        claude_root: Path,
        statusline_snapshot: Path,
        lookback_days: int = 14,
    ) -> None:
        self.codex_root = codex_root
        self.claude_root = claude_root
        self.statusline_snapshot = statusline_snapshot
        self.lookback_days = max(3, lookback_days)
        self._cache: dict[Path, _CacheEntry] = {}

    def collect(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        codex = self._collect_codex(now)
        claude = self._collect_claude(now)
        return {
            "generated_at": now.isoformat(),
            "paths": {
                "codex_root": str(self.codex_root),
                "claude_root": str(self.claude_root),
                "claude_statusline_snapshot": str(self.statusline_snapshot),
            },
            "codex": codex,
            "claude": claude,
        }

    def collect_limits_only(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        return {
            "generated_at": now.isoformat(),
            "codex": self._collect_codex_limits_only(),
            "claude": {
                "current_limits": self._load_claude_statusline_snapshot(),
            },
        }

    def _collect_codex_limits_only(self) -> dict[str, Any]:
        latest_path = self._latest_modified_path(self._iter_codex_session_paths())
        if latest_path is None:
            return {"current_limits": None}

        parsed = self._read_cached(latest_path, self._parse_codex_session)
        if parsed is None:
            return {"current_limits": None}

        summary, events, _daily = parsed
        return {
            "current_limits": events[-1] if events else None,
            "latest_session": summary,
        }

    def _collect_codex(self, now: datetime) -> dict[str, Any]:
        daily_totals: dict[str, dict[str, int]] = defaultdict(self._blank_daily_totals)
        rate_events: list[dict[str, Any]] = []
        recent_sessions: list[dict[str, Any]] = []
        session_histories: list[tuple[str, list[dict[str, Any]]]] = []

        for path in self._iter_codex_session_paths():
            parsed = self._read_cached(path, self._parse_codex_session)
            if parsed is None:
                continue
            summary, events, daily = parsed
            if summary:
                recent_sessions.append(summary)
                if events and summary.get("updated_at"):
                    session_histories.append((summary["updated_at"], events))
            rate_events.extend(events)
            self._merge_daily(daily_totals, daily)

        recent_sessions.sort(
            key=lambda item: item.get("updated_at") or "",
            reverse=True,
        )
        rate_events.sort(key=lambda item: item["timestamp"])
        session_histories.sort(key=lambda item: item[0], reverse=True)

        current_limits = rate_events[-1] if rate_events else None
        history = session_histories[0][1][-120:] if session_histories else []
        daily_series = self._daily_series(daily_totals, now)

        seven_day_total = sum(
            item["total_tokens"] for item in daily_series[-7:]
        ) if daily_series else 0

        return {
            "current_limits": current_limits,
            "daily_tokens": daily_series,
            "rate_limit_history": history,
            "recent_sessions": recent_sessions[:8],
            "seven_day_total_tokens": seven_day_total,
            "session_count": len(recent_sessions),
        }

    def _collect_claude(self, now: datetime) -> dict[str, Any]:
        daily_totals: dict[str, dict[str, int]] = defaultdict(self._blank_daily_totals)
        recent_sessions: list[dict[str, Any]] = []

        for path in self._iter_claude_project_paths():
            parsed = self._read_cached(path, self._parse_claude_session)
            if parsed is None:
                continue
            summary, daily = parsed
            if summary:
                recent_sessions.append(summary)
            self._merge_daily(daily_totals, daily)

        recent_sessions.sort(
            key=lambda item: item.get("updated_at") or "",
            reverse=True,
        )

        live_limits = self._load_claude_statusline_snapshot()
        daily_series = self._daily_series(daily_totals, now)
        seven_day_total = sum(
            item["total_tokens"] for item in daily_series[-7:]
        ) if daily_series else 0

        return {
            "current_limits": live_limits,
            "daily_tokens": daily_series,
            "recent_sessions": recent_sessions[:8],
            "seven_day_total_tokens": seven_day_total,
            "session_count": len(recent_sessions),
            "statusline_snapshot_detected": live_limits is not None,
            "statusline_help": {
                "supported": True,
                "snapshot_path": str(self.statusline_snapshot),
                "note": (
                    "Claude 5h/7d limits require a statusLine snapshot. "
                    "Token totals work without it."
                ),
            },
        }

    def _load_claude_statusline_snapshot(self) -> dict[str, Any] | None:
        if not self.statusline_snapshot.exists():
            return None

        try:
            payload = json.loads(self.statusline_snapshot.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        rate_limits = payload.get("rate_limits") or {}
        five_hour = rate_limits.get("five_hour") or {}
        seven_day = rate_limits.get("seven_day") or {}
        if not five_hour and not seven_day:
            return None

        return {
            "captured_at": payload.get("captured_at"),
            "session_id": payload.get("session_id"),
            "session_name": payload.get("session_name"),
            "model": (payload.get("model") or {}).get("display_name"),
            "five_hour": {
                "used_percentage": _safe_int(five_hour.get("used_percentage")),
                "resets_at": _epoch_to_iso(five_hour.get("resets_at")),
            },
            "seven_day": {
                "used_percentage": _safe_int(seven_day.get("used_percentage")),
                "resets_at": _epoch_to_iso(seven_day.get("resets_at")),
            },
        }

    def _iter_codex_session_paths(self) -> list[Path]:
        paths: list[Path] = []
        sessions_dir = self.codex_root / "sessions"
        if sessions_dir.exists():
            paths.extend(sessions_dir.rglob("*.jsonl"))

        archived_dir = self.codex_root / "archived_sessions"
        if archived_dir.exists():
            paths.extend(archived_dir.glob("*.jsonl"))
        return paths

    def _iter_claude_project_paths(self) -> list[Path]:
        projects_dir = self.claude_root / "projects"
        if not projects_dir.exists():
            return []
        return [
            path
            for path in projects_dir.rglob("*.jsonl")
            if not path.name.endswith(".meta.json")
        ]

    def _latest_modified_path(self, paths: list[Path]) -> Path | None:
        latest_path: Path | None = None
        latest_mtime = -1
        for path in paths:
            try:
                mtime = path.stat().st_mtime_ns
            except OSError:
                continue
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_path = path
        return latest_path

    def _read_cached(
        self,
        path: Path,
        parser: Callable[[Path], Any],
    ) -> Any:
        try:
            stat = path.stat()
        except OSError:
            return None

        cached = self._cache.get(path)
        if (
            cached is not None
            and cached.mtime_ns == stat.st_mtime_ns
            and cached.size == stat.st_size
        ):
            return cached.data

        data = parser(path)
        self._cache[path] = _CacheEntry(
            mtime_ns=stat.st_mtime_ns,
            size=stat.st_size,
            data=data,
        )
        return data

    def _parse_codex_session(
        self,
        path: Path,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, dict[str, int]]]:
        meta: dict[str, Any] = {}
        daily: dict[str, dict[str, int]] = defaultdict(self._blank_daily_totals)
        rate_events: list[dict[str, Any]] = []
        latest_event: dict[str, Any] | None = None

        try:
            handle = path.open("r", encoding="utf-8")
        except OSError:
            return None, [], {}

        with handle:
            for line in handle:
                if not line.strip():
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if obj.get("type") == "session_meta":
                    payload = obj.get("payload") or {}
                    meta = {
                        "session_id": payload.get("id") or path.stem,
                        "cwd": payload.get("cwd"),
                        "source": payload.get("source"),
                        "model_provider": payload.get("model_provider"),
                    }
                    continue

                if obj.get("type") != "event_msg":
                    continue

                payload = obj.get("payload") or {}
                if payload.get("type") != "token_count":
                    continue

                timestamp = _parse_timestamp(obj.get("timestamp"))
                if timestamp is None:
                    continue

                info = payload.get("info") or {}
                total_usage = info.get("total_token_usage") or {}
                last_usage = info.get("last_token_usage") or {}
                rate_limits = payload.get("rate_limits") or {}

                last_total = _safe_int(last_usage.get("total_tokens"))
                date_key = timestamp.date().isoformat()
                bucket = daily[date_key]
                bucket["input_tokens"] += _safe_int(last_usage.get("input_tokens"))
                bucket["cached_input_tokens"] += _safe_int(
                    last_usage.get("cached_input_tokens")
                )
                bucket["output_tokens"] += _safe_int(last_usage.get("output_tokens"))
                bucket["reasoning_output_tokens"] += _safe_int(
                    last_usage.get("reasoning_output_tokens")
                )
                bucket["total_tokens"] += last_total

                candidate_event = {
                    "timestamp": timestamp.isoformat(),
                    "total_usage": {
                        "input_tokens": _safe_int(total_usage.get("input_tokens")),
                        "cached_input_tokens": _safe_int(
                            total_usage.get("cached_input_tokens")
                        ),
                        "output_tokens": _safe_int(total_usage.get("output_tokens")),
                        "reasoning_output_tokens": _safe_int(
                            total_usage.get("reasoning_output_tokens")
                        ),
                        "total_tokens": _safe_int(total_usage.get("total_tokens")),
                    },
                    "last_usage": {
                        "total_tokens": last_total,
                    },
                    "rate_limits": rate_limits,
                }
                if latest_event is None or candidate_event["timestamp"] > latest_event["timestamp"]:
                    latest_event = candidate_event

                primary = rate_limits.get("primary") or {}
                secondary = rate_limits.get("secondary") or {}
                if primary or secondary:
                    rate_events.append(
                        {
                            "timestamp": timestamp.isoformat(),
                            "plan_type": rate_limits.get("plan_type"),
                            "primary": {
                                "used_percent": float(primary.get("used_percent") or 0),
                                "window_minutes": _safe_int(
                                    primary.get("window_minutes")
                                ),
                                "resets_at": _epoch_to_iso(primary.get("resets_at")),
                            },
                            "secondary": {
                                "used_percent": float(
                                    secondary.get("used_percent") or 0
                                ),
                                "window_minutes": _safe_int(
                                    secondary.get("window_minutes")
                                ),
                                "resets_at": _epoch_to_iso(secondary.get("resets_at")),
                            },
                        }
                    )

        if latest_event is None and not meta:
            return None, [], {}

        summary = {
            "session_id": meta.get("session_id") or path.stem,
            "cwd": meta.get("cwd"),
            "source": meta.get("source"),
            "model_provider": meta.get("model_provider"),
            "updated_at": latest_event["timestamp"] if latest_event else None,
            "total_tokens": (
                latest_event["total_usage"]["total_tokens"] if latest_event else 0
            ),
            "path": _display_name(path, self.codex_root),
        }
        return summary, rate_events, daily

    def _parse_claude_session(
        self,
        path: Path,
    ) -> tuple[dict[str, Any] | None, dict[str, dict[str, int]]]:
        daily: dict[str, dict[str, int]] = defaultdict(self._blank_daily_totals)
        latest_message: dict[str, Any] | None = None
        latest_real_model: str | None = None
        totals = self._blank_daily_totals()

        try:
            handle = path.open("r", encoding="utf-8")
        except OSError:
            return None, {}

        with handle:
            for line in handle:
                if not line.strip():
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                message = obj.get("message") or {}
                usage = message.get("usage") or {}
                if not usage:
                    continue

                timestamp = _parse_timestamp(obj.get("timestamp"))
                if timestamp is None:
                    continue

                input_tokens = _safe_int(usage.get("input_tokens"))
                output_tokens = _safe_int(usage.get("output_tokens"))
                cache_creation = _safe_int(usage.get("cache_creation_input_tokens"))
                cache_read = _safe_int(usage.get("cache_read_input_tokens"))
                reasoning = _safe_int(usage.get("reasoning_output_tokens"))
                total_tokens = (
                    input_tokens
                    + output_tokens
                    + cache_creation
                    + cache_read
                    + reasoning
                )

                date_key = timestamp.date().isoformat()
                bucket = daily[date_key]
                bucket["input_tokens"] += input_tokens + cache_creation + cache_read
                bucket["cached_input_tokens"] += cache_creation + cache_read
                bucket["output_tokens"] += output_tokens
                bucket["reasoning_output_tokens"] += reasoning
                bucket["total_tokens"] += total_tokens

                totals["input_tokens"] += input_tokens + cache_creation + cache_read
                totals["cached_input_tokens"] += cache_creation + cache_read
                totals["output_tokens"] += output_tokens
                totals["reasoning_output_tokens"] += reasoning
                totals["total_tokens"] += total_tokens

                candidate_message = {
                    "timestamp": timestamp.isoformat(),
                    "session_id": obj.get("sessionId") or path.stem,
                    "session_name": obj.get("slug"),
                    "cwd": obj.get("cwd"),
                    "model": message.get("model"),
                    "entrypoint": obj.get("entrypoint"),
                    "version": obj.get("version"),
                }
                model_name = candidate_message.get("model")
                if model_name and model_name != "<synthetic>":
                    latest_real_model = model_name
                if (
                    latest_message is None
                    or candidate_message["timestamp"] > latest_message["timestamp"]
                ):
                    latest_message = candidate_message

        if latest_message is None:
            return None, {}

        summary = {
            "session_id": latest_message["session_id"],
            "session_name": latest_message.get("session_name"),
            "cwd": latest_message.get("cwd"),
            "model": latest_real_model or latest_message.get("model"),
            "entrypoint": latest_message.get("entrypoint"),
            "updated_at": latest_message["timestamp"],
            "total_tokens": totals["total_tokens"],
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
            "path": _display_name(path, self.claude_root),
        }
        return summary, daily

    def _blank_daily_totals(self) -> dict[str, int]:
        return {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_output_tokens": 0,
            "total_tokens": 0,
        }

    def _merge_daily(
        self,
        target: dict[str, dict[str, int]],
        source: dict[str, dict[str, int]],
    ) -> None:
        for day, bucket in source.items():
            target_bucket = target[day]
            for key, value in bucket.items():
                target_bucket[key] += value

    def _daily_series(
        self,
        daily_map: dict[str, dict[str, int]],
        now: datetime,
    ) -> list[dict[str, Any]]:
        start_day = now.date() - timedelta(days=self.lookback_days - 1)
        series: list[dict[str, Any]] = []
        for offset in range(self.lookback_days):
            current_day = start_day + timedelta(days=offset)
            key = current_day.isoformat()
            bucket = daily_map.get(key, self._blank_daily_totals())
            series.append(
                {
                    "date": key,
                    "label": current_day.strftime("%b %d"),
                    "input_tokens": bucket["input_tokens"],
                    "cached_input_tokens": bucket["cached_input_tokens"],
                    "output_tokens": bucket["output_tokens"],
                    "reasoning_output_tokens": bucket["reasoning_output_tokens"],
                    "total_tokens": bucket["total_tokens"],
                }
            )
        return series
