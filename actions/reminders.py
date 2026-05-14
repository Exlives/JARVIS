"""
Animsatici islemleri - Windows fallback (yerel JSON depolama).
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REMINDERS_STORE = BASE_DIR / "memory" / "reminders.json"


def _load_reminders() -> list[dict]:
    try:
        if REMINDERS_STORE.exists():
            data = json.loads(REMINDERS_STORE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save_reminders(reminders: list[dict]):
    REMINDERS_STORE.parent.mkdir(parents=True, exist_ok=True)
    REMINDERS_STORE.write_text(json.dumps(reminders, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_due_iso(due_iso: str) -> tuple[str, bool]:
    raw = (due_iso or "").strip()
    if not raw:
        return "", False
    for fmt, is_all_day in (
        ("%Y-%m-%dT%H:%M:%S", False),
        ("%Y-%m-%dT%H:%M", False),
        ("%Y-%m-%d %H:%M", False),
        ("%Y-%m-%d", True),
    ):
        try:
            parsed = dt.datetime.strptime(raw, fmt)
            if is_all_day:
                return parsed.date().isoformat(), True
            return parsed.isoformat(timespec="minutes"), False
        except ValueError:
            continue
    parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=None).isoformat(timespec="minutes"), False


def _format_due(item: dict) -> str:
    due_iso = str(item.get("due_iso", "")).strip()
    if not due_iso:
        return "zaman atanmamis"
    if item.get("all_day", False) and len(due_iso) == 10:
        return f"{due_iso} tum gun"
    try:
        due = dt.datetime.fromisoformat(due_iso)
        return due.strftime("%d.%m %H:%M")
    except Exception:
        return due_iso


def get_reminders(query: str = "upcoming", limit: int = 8, list_name: str = "") -> str:
    mode = (query or "upcoming").strip().lower()
    now = dt.datetime.now()
    reminders = _load_reminders()
    rows = []
    for item in reminders:
        if list_name and str(item.get("list_name", "")).strip() != list_name.strip():
            continue
        due_iso = str(item.get("due_iso", "")).strip()
        due_dt = None
        if due_iso and len(due_iso) > 10:
            try:
                due_dt = dt.datetime.fromisoformat(due_iso)
            except Exception:
                due_dt = None
        rows.append((due_dt, item))
    rows.sort(key=lambda x: (x[0] is None, x[0] or dt.datetime.max))

    if mode in {"today", "bugun"}:
        rows = [r for r in rows if r[0] and r[0].date() == now.date()]
    elif mode in {"overdue", "geciken"}:
        rows = [r for r in rows if r[0] and r[0] < now]
    elif mode in {"next", "siradaki"}:
        rows = [r for r in rows if r[0] and r[0] >= now][:1]
    elif mode in {"upcoming", "agenda"}:
        rows = [r for r in rows if not r[0] or r[0] >= now]

    if not rows:
        return "Uygun animsatici bulunmuyor."

    selected = [item for _, item in rows[: max(1, min(20, int(limit or 8)))]]
    if mode in {"next", "siradaki"}:
        item = selected[0]
        return f"Siradaki animsatici: {_format_due(item)} - {item['title']}"
    lines = [f"{len(selected)} animsatici buldum:"]
    for item in selected:
        list_suffix = f" [{item['list_name']}]" if item.get("list_name") else ""
        lines.append(f"- {_format_due(item)} - {item['title']}{list_suffix}")
    return "\n".join(lines)


def add_reminder(
    title: str,
    due_iso: str = "",
    notes: str = "",
    list_name: str = "",
    priority: str = "",
    all_day: bool = False,
) -> str:
    if not title or not title.strip():
        return "Animsatici basligi bos olamaz."
    normalized_due = ""
    normalized_all_day = bool(all_day)
    if due_iso and due_iso.strip():
        try:
            normalized_due, inferred_all_day = _parse_due_iso(due_iso)
            normalized_all_day = normalized_all_day or inferred_all_day
        except Exception:
            return "Animsatici tarihi gecersiz. due_iso icin YYYY-MM-DD veya YYYY-MM-DDTHH:MM kullan."

    item = {
        "id": str(uuid.uuid4()),
        "title": title.strip(),
        "due_iso": normalized_due,
        "notes": (notes or "").strip(),
        "list_name": (list_name or "").strip(),
        "priority": (priority or "").strip().lower(),
        "all_day": normalized_all_day,
    }
    reminders = _load_reminders()
    reminders.append(item)
    _save_reminders(reminders)
    suffix = f" [{item['list_name']}]" if item["list_name"] else ""
    return f"Animsatici eklendi: {_format_due(item)} - {item['title']}{suffix}"
