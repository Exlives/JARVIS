"""
Uygulama kapatma - Windows.
"""

from __future__ import annotations

import subprocess


PROCESS_ALIASES = {
    "calculator": ["CalculatorApp.exe", "calc.exe"],
    "hesap makinesi": ["CalculatorApp.exe", "calc.exe"],
    "calc": ["calc.exe", "CalculatorApp.exe"],
    "discord": ["Discord.exe", "Update.exe"],
    "steam": ["steam.exe"],
    "spotify": ["Spotify.exe"],
    "chrome": ["chrome.exe"],
    "google chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "microsoft edge": ["msedge.exe"],
    "firefox": ["firefox.exe"],
}


def _taskkill(image_name: str) -> bool:
    try:
        res = subprocess.run(
            ["taskkill", "/F", "/IM", image_name],
            capture_output=True,
            text=True,
            timeout=8,
        )
        msg = ((res.stdout or "") + " " + (res.stderr or "")).lower()
        if "success" in msg or "başarı" in msg or "sonlandırıldı" in msg:
            return True
        return res.returncode == 0
    except Exception:
        return False


def close_app(app_name: str) -> str:
    if not app_name:
        return "Kapatılacak uygulama adı belirtilmedi."

    normalized = app_name.strip().lower()
    process_names = PROCESS_ALIASES.get(normalized, [])
    if not process_names:
        candidate = app_name.strip()
        if not candidate.lower().endswith(".exe"):
            candidate = f"{candidate}.exe"
        process_names = [candidate]

    killed_any = False
    for name in process_names:
        if _taskkill(name):
            killed_any = True

    if killed_any:
        return f"{app_name} kapatıldı."
    return f"{app_name} zaten kapalı görünüyor veya kapatılamadı."

