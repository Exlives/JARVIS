from __future__ import annotations

import io
import time
from pathlib import Path

from google import genai
from google.genai import errors, types
from PIL import Image, ImageGrab, ImageStat

from app_config import get_app_config_value


BASE_DIR = Path(__file__).resolve().parent.parent
VISION_MODELS = (
    "models/gemini-2.0-flash",
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.5-flash",
)
VISION_MAX_DIMENSION = 1800
VISION_MAX_INLINE_BYTES = 5_500_000


def _screen_permission_message() -> str:
    return (
        "Ekran analizi icin Windows ekran yakalama izni gerekiyor. "
        "Ayarlar > Gizlilik ve guvenlik > Ekran goruntuleri veya ilgili izinleri kontrol et."
    )


def _capture_screen() -> tuple[bool, str, Path | None]:
    image_path = BASE_DIR / "memory" / "latest_screen_capture.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        image = ImageGrab.grab(all_screens=True)
        image.save(image_path, format="PNG")
        return True, "", image_path
    except Exception as exc:
        return False, str(exc), None


def _image_looks_blank(image_path: Path) -> bool:
    try:
        with Image.open(image_path) as img:
            sample = img.convert("RGB")
            stat = ImageStat.Stat(sample)
            means = stat.mean
            extrema = stat.extrema
            max_seen = max(channel[1] for channel in extrema)
            mean_total = sum(means) / max(1, len(means))
            return max_seen <= 8 or mean_total <= 3
    except Exception:
        return False


def _build_image_part(image_path: Path) -> types.Part:
    with Image.open(image_path) as img:
        work = img.copy()
    if work.mode not in {"RGB", "L"}:
        work = work.convert("RGB")
    if max(work.size) > VISION_MAX_DIMENSION:
        work.thumbnail((VISION_MAX_DIMENSION, VISION_MAX_DIMENSION), Image.Resampling.LANCZOS)

    png_buffer = io.BytesIO()
    work.save(png_buffer, format="PNG", optimize=True)
    png_bytes = png_buffer.getvalue()
    if len(png_bytes) <= VISION_MAX_INLINE_BYTES:
        return types.Part.from_bytes(data=png_bytes, mime_type="image/png")

    jpg_buffer = io.BytesIO()
    rgb = work.convert("RGB") if work.mode != "RGB" else work
    rgb.save(jpg_buffer, format="JPEG", quality=88, optimize=True)
    return types.Part.from_bytes(data=jpg_buffer.getvalue(), mime_type="image/jpeg")


def _vision_prompt(query: str) -> str:
    user_query = (query or "Ekranda ne var?").strip()
    return (
        "Sen Windows uzerinde JARVIS icin ekran analizi yapan bir goruntu yorumlayicisisin.\n"
        "1. Ekranin amacini kisaca acikla.\n"
        "2. Gorunen metin, hata ve onemli butonlari ozetle.\n"
        "3. Kullanici sorusunu bu goruntuye gore cevapla.\n"
        "4. Emin olmadigin kisimlarda bunu belirt.\n\n"
        f"Kullanici sorusu: {user_query}\n"
        "Yaniti Turkce ve net ver."
    )


def _extract_response_text(response) -> str:
    text = str(getattr(response, "text", "") or "").strip()
    if text:
        return text
    candidates = getattr(response, "candidates", None) or []
    chunks = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            part_text = str(getattr(part, "text", "") or "").strip()
            if part_text:
                chunks.append(part_text)
    return "\n".join(chunks).strip()


def _is_transient_vision_error(exc: Exception) -> bool:
    if isinstance(exc, (errors.ServerError, TimeoutError)):
        return True
    message = str(exc or "").lower()
    return any(
        marker in message
        for marker in (
            "503",
            "429",
            "deadline",
            "timed out",
            "timeout",
            "unavailable",
            "service unavailable",
            "busy",
            "resource exhausted",
        )
    )


def _analyze_with_gemini(query: str, image_path: Path) -> str:
    api_key = str(get_app_config_value("gemini_api_key", "") or "").strip()
    if not api_key:
        return "Gemini API anahtari eksik oldugu icin ekran analizi yapilamadi."

    prompt = _vision_prompt(query)
    client = genai.Client(api_key=api_key)
    image_part = _build_image_part(image_path)
    retry_delays = (0.9, 1.8, 3.0)
    last_error = None

    for model_name in VISION_MODELS:
        for attempt, delay in enumerate(retry_delays, start=1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[types.Part.from_text(text=prompt), image_part],
                    config=types.GenerateContentConfig(temperature=0.2),
                )
                merged = _extract_response_text(response)
                if merged:
                    return merged
                raise RuntimeError("Gemini gecerli bir ekran analizi metni dondurmedi.")
            except Exception as exc:
                last_error = exc
                if attempt < len(retry_delays) and _is_transient_vision_error(exc):
                    time.sleep(delay)
                    continue
                if _is_transient_vision_error(exc):
                    break
                raise
    if last_error:
        raise RuntimeError(f"Gemini vision istegi basarisiz oldu: {last_error}")
    raise RuntimeError("Gemini vision istegi basarisiz oldu.")


def analyze_screen(query: str, target: str = "active_window") -> str:
    _ = target
    ok, detail, image_path = _capture_screen()
    if not ok or not image_path:
        if "permission" in detail.lower():
            return _screen_permission_message()
        return f"Ekran goruntusu alinamadi: {detail}"

    try:
        if not image_path.exists() or image_path.stat().st_size <= 0:
            return "Ekran goruntusu bos geldi. " + _screen_permission_message()
        if _image_looks_blank(image_path):
            return "Ekran goruntusu siyah veya bos gorunuyor. " + _screen_permission_message()
        return _analyze_with_gemini(query, image_path)
    except Exception as exc:
        return f"Ekran analizi tamamlanamadi: {exc}"
