"""
Takvim islemleri - Windows fallback (yerel JSON depolama).
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CALENDAR_STORE = BASE_DIR / "memory" / "calendar_events.json"


def _load_events() -> list[dict]:
    try:
        if CALENDAR_STORE.exists():
            data = json.loads(CALENDAR_STORE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save_events(events: list[dict]):
    CALENDAR_STORE.parent.mkdir(parents=True, exist_ok=True)
    CALENDAR_STORE.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_dt(value: str) -> dt.datetime:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Tarih bos")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = dt.datetime.strptime(raw, fmt)
            if fmt == "%Y-%m-%d":
                return parsed.replace(hour=9, minute=0)
            return parsed
        except ValueError:
            continue
    return dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)


def _fmt_event(event: dict) -> str:
    start = dt.datetime.fromisoformat(event["start_iso"])
    end = dt.datetime.fromisoformat(event["end_iso"])
    base = f"{start.strftime('%d.%m %H:%M')}-{end.strftime('%H:%M')} - {event['title']}"
    if event.get("location"):
        base += f" @ {event['location']}"
    if event.get("calendar_name"):
        base += f" [{event['calendar_name']}]"
    return base


def get_calendar_events(query: str = "today", limit: int = 6) -> str:
    now = dt.datetime.now()
    q = (query or "today").lower().strip()
    events = sorted(_load_events(), key=lambda x: x.get("start_iso", ""))
    parsed = []
    for event in events:
        try:
            start = dt.datetime.fromisoformat(event["start_iso"])
            end = dt.datetime.fromisoformat(event["end_iso"])
            parsed.append((start, end, event))
        except Exception:
            continue

    if q in {"today", "bugun"}:
        selected = [e for s, _, e in parsed if s.date() == now.date()]
    elif q in {"tomorrow", "yarin"}:
        selected = [e for s, _, e in parsed if s.date() == (now.date() + dt.timedelta(days=1))]
    elif q in {"next", "siradaki"}:
        selected = [e for s, end, e in parsed if end >= now][:1]
    elif q in {"week", "agenda", "upcoming"}:
        horizon = now + dt.timedelta(days=7)
        selected = [e for s, end, e in parsed if end >= now and s <= horizon]
    else:
        selected = [e for _, end, e in parsed if end >= now]

    if not selected:
        return "Takvimde uygun etkinlik bulunmadi."

    selected = selected[: max(1, min(60, int(limit or 6)))]
    if q in {"next", "siradaki"}:
        return f"Siradaki etkinlik: {_fmt_event(selected[0])}"
    lines = [f"{len(selected)} etkinlik buldum:"]
    lines.extend(f"- {_fmt_event(event)}" for event in selected)
    return "\n".join(lines)


def add_calendar_event(
    title: str,
    start_iso: str,
    end_iso: str = "",
    notes: str = "",
    location: str = "",
    calendar_name: str = "",
    all_day: bool = False,
) -> str:
    title = (title or "").strip()
    if not title:
        return "Takvime eklemek icin etkinlik basligi gerekli."
    try:
        start = _parse_dt(start_iso)
    except Exception:
        return "Takvime eklemek icin gecerli bir baslangic tarihi gerekli."

    if end_iso and end_iso.strip():
        try:
            end = _parse_dt(end_iso)
        except Exception:
            return "Bitis tarihi gecersiz."
    else:
        end = start + dt.timedelta(days=1 if all_day else 1 / 24)

    event = {
        "id": str(uuid.uuid4()),
        "title": title,
        "start_iso": start.isoformat(timespec="minutes"),
        "end_iso": end.isoformat(timespec="minutes"),
        "notes": (notes or "").strip(),
        "location": (location or "").strip(),
        "calendar_name": (calendar_name or "").strip(),
        "all_day": bool(all_day),
    }
    events = _load_events()
    events.append(event)
    _save_events(events)
    return f"Takvime eklendi: {_fmt_event(event)}"


def delete_calendar_event(
    title: str,
    start_iso: str = "",
    calendar_name: str = "",
    delete_all_matches: bool = False,
) -> str:
    title_norm = (title or "").strip().casefold()
    if not title_norm:
        return "Takvimden silmek icin etkinlik basligi gerekli."

    target_start = None
    if start_iso and start_iso.strip():
        try:
            target_start = _parse_dt(start_iso).replace(second=0, microsecond=0)
        except Exception:
            return "Etkinlik tarihi gecersiz."

    events = _load_events()
    kept = []
    matched = []
    for event in events:
        e_title = str(event.get("title", "")).strip().casefold()
        if title_norm not in e_title:
            kept.append(event)
            continue
        if calendar_name and str(event.get("calendar_name", "")).strip() != calendar_name.strip():
            kept.append(event)
            continue
        if target_start:
            try:
                start = dt.datetime.fromisoformat(event["start_iso"]).replace(second=0, microsecond=0)
            except Exception:
                kept.append(event)
                continue
            if start != target_start:
                kept.append(event)
                continue
        matched.append(event)
        if not delete_all_matches:
            kept.extend(events[events.index(event) + 1 :])
            break

    if not matched:
        return "Silinecek etkinlik bulunamadi."
    _save_events(kept)
    return f"Takvimden silindi: {_fmt_event(matched[0])}"
