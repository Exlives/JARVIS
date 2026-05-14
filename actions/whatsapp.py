"""
WhatsApp mesaj gonderme - Windows uyumlu.
Desktop otomasyonu yerine guvenli olarak sohbet/taslak acar.
"""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
import webbrowser
from pathlib import Path

from memory.memory_manager import load_memory, update_memory


BASE_DIR = Path(__file__).resolve().parent.parent
PHONEBOOK_FILE = BASE_DIR / "memory" / "phone_book.json"


def _normalize_phone(phone_number: str) -> str:
    digits = re.sub(r"\D+", "", phone_number or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = "90" + digits[1:]
    elif len(digits) == 10:
        digits = "90" + digits
    if len(digits) < 8 or len(digits) > 15:
        raise ValueError("Telefon numarasi uluslararasi formatta olmali. Ornek: +905551112233")
    return digits


def _normalize_lookup(text: str) -> str:
    text = (text or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ı", "i")
    text = re.sub(r"\s+", " ", text)
    return text


def _contact_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _normalize_lookup(name)).strip("_") or "contact"


def _load_contacts() -> dict:
    memory = load_memory()
    contacts = memory.get("whatsapp_contacts", {})
    return contacts if isinstance(contacts, dict) else {}


def _load_phone_book() -> dict:
    try:
        if PHONEBOOK_FILE.exists():
            return json.loads(PHONEBOOK_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_phone_book(phone_book: dict):
    PHONEBOOK_FILE.parent.mkdir(parents=True, exist_ok=True)
    PHONEBOOK_FILE.write_text(json.dumps(phone_book, indent=2, ensure_ascii=False), encoding="utf-8")


def _contact_candidates() -> list[dict]:
    candidates = []
    for source_name, source in (("whatsapp", _load_contacts()), ("phone_book", _load_phone_book())):
        if not isinstance(source, dict):
            continue
        for key, entry in source.items():
            if not isinstance(entry, dict):
                continue
            item = dict(entry)
            item.setdefault("display_name", key)
            item["_source"] = source_name
            item["_key"] = key
            candidates.append(item)
    return candidates


def _match_score(needle: str, candidate: str) -> int:
    candidate_norm = _normalize_lookup(candidate)
    if not candidate_norm:
        return 0
    if candidate_norm == needle:
        return 300
    if candidate_norm.startswith(needle) or needle.startswith(candidate_norm):
        return 220
    if needle in candidate_norm:
        return 160
    needle_parts = needle.split()
    if needle_parts and all(part in candidate_norm for part in needle_parts):
        return 120
    return 0


def _find_contact(recipient_name: str) -> dict | None:
    needle = _normalize_lookup(recipient_name)
    if not needle:
        return None
    best_match = None
    best_score = 0
    for entry in _contact_candidates():
        names = [entry.get("display_name", ""), entry.get("_key", "")]
        aliases = entry.get("aliases", [])
        if isinstance(aliases, list):
            names.extend(str(alias) for alias in aliases)
        elif aliases:
            names.append(str(aliases))
        for name in names:
            score = _match_score(needle, name)
            if score > best_score:
                best_score = score
                best_match = entry
    return best_match


def save_whatsapp_contact(display_name: str, phone_number: str, aliases: str = "") -> str:
    if not display_name or not display_name.strip():
        return "Kisi adi bos olamaz."
    try:
        normalized_phone = _normalize_phone(phone_number)
    except ValueError as exc:
        return str(exc)

    alias_list = [part.strip() for part in (aliases or "").split(",") if part.strip()]
    key = _contact_key(display_name)
    update_memory(
        {
            "whatsapp_contacts": {
                key: {
                    "value": f"+{normalized_phone}",
                    "display_name": display_name.strip(),
                    "aliases": alias_list,
                }
            }
        }
    )
    return f"{display_name.strip()} WhatsApp kisilerine kaydedildi."


def import_phone_book_from_vcf(vcf_path: str) -> str:
    source = Path(vcf_path).expanduser()
    if not source.exists():
        return f"Rehber dosyasi bulunamadi: {source}"

    try:
        text = source.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return f"Rehber dosyasi okunamadi: {exc}"

    entries = {}
    current_lines = []
    imported = 0
    skipped = 0

    def _flush_card(lines: list[str]):
        nonlocal imported, skipped
        display_name = ""
        numbers = []
        for line in lines:
            upper = line.upper()
            if upper.startswith("FN:"):
                display_name = line.split(":", 1)[1].strip()
            elif "TEL" in upper and ":" in line:
                number = line.split(":", 1)[1].strip()
                if number:
                    numbers.append(number)
        if not display_name or not numbers:
            skipped += 1
            return
        for raw in numbers:
            try:
                normalized = "+" + _normalize_phone(raw)
                key = _contact_key(display_name)
                entries[key] = {"display_name": display_name, "value": normalized, "source": "vcf_import"}
                imported += 1
                return
            except ValueError:
                continue
        skipped += 1

    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        if line.upper() == "BEGIN:VCARD":
            current_lines = []
        elif line.upper() == "END:VCARD":
            _flush_card(current_lines)
            current_lines = []
        else:
            current_lines.append(line)

    phone_book = _load_phone_book()
    phone_book.update(entries)
    _save_phone_book(phone_book)
    return f"{imported} rehber kisisi ice aktarildi, {skipped} kayit atlandi."


def _open_whatsapp(phone_number: str, message: str) -> None:
    encoded_message = urllib.parse.quote(message.strip())
    url = f"https://web.whatsapp.com/send?phone={phone_number}&text={encoded_message}"
    webbrowser.open(url, new=2)


def send_whatsapp_message(
    message: str,
    phone_number: str = "",
    recipient_name: str = "",
    send_now: bool = False,
    app_target: str = "auto",
) -> str:
    if not message or not message.strip():
        return "Mesaj bos olamaz."

    normalized_phone = ""
    if phone_number and phone_number.strip():
        try:
            normalized_phone = _normalize_phone(phone_number)
        except ValueError as exc:
            return str(exc)

    resolved_name = recipient_name.strip() if recipient_name else ""
    contact = _find_contact(resolved_name) if resolved_name else None
    contact_source = ""
    if contact and not normalized_phone:
        contact_source = str(contact.get("_source", ""))
        try:
            normalized_phone = _normalize_phone(str(contact.get("value", "")))
        except ValueError:
            normalized_phone = ""
        resolved_name = str(contact.get("display_name", resolved_name)).strip() or resolved_name

    if not normalized_phone:
        if resolved_name:
            return f"'{resolved_name}' icin kayitli bir telefon numarasi bulamadim."
        return "WhatsApp mesaji icin kisi adi veya telefon numarasi gerekli."

    _open_whatsapp(normalized_phone, message)
    label = resolved_name or f"+{normalized_phone}"
    source_note = " (rehberden bulundu)" if contact_source == "phone_book" else ""
    if send_now:
        return (
            f"WhatsApp Web acildi: {label}{source_note}. "
            "Windows'ta guvenlik nedeniyle otomatik Enter basmiyorum; mesaji gondermek icin Enter'a bas."
        )
    return f"WhatsApp sohbeti {label}{source_note} icin taslak mesajla acildi."
