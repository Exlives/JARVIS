"""
Uygulama acma - Windows ShellExecute/os.startfile ile calisir.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from memory.memory_manager import load_memory


APP_ALIASES = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "terminal": "wt",
    "cmd": "cmd",
    "powershell": "powershell",
    "explorer": "explorer",
    "finder": "explorer",
    "spotify": "spotify:",
    "youtube music": "https://music.youtube.com",
    "youtube müzik": "https://music.youtube.com",
    "yt music": "https://music.youtube.com",
    "ytmusic": "https://music.youtube.com",
    "vscode": "code",
    "vs code": "code",
    "code": "code",
    "notion": "Notion",
    "slack": "Slack",
    "discord": "Discord",
    "whatsapp": "whatsapp:",
    "telegram": "Telegram",
    "zoom": "Zoom",
    "mail": "outlookmail:",
    "calendar": "outlookcal:",
    "takvim": "outlookcal:",
    "notes": "onenote:",
    "notlar": "onenote:",
    "music": "spotify:",
    "muzik": "spotify:",
    "müzik": "spotify:",
    "photos": "ms-photos:",
    "fotograflar": "ms-photos:",
    "fotoğraflar": "ms-photos:",
    "maps": "bingmaps:",
    "haritalar": "bingmaps:",
    "calculator": "calc",
    "hesap makinesi": "calc",
    "system preferences": "ms-settings:",
    "system settings": "ms-settings:",
    "ayarlar": "ms-settings:",
    "activity monitor": "taskmgr",
    "aktivite monitoru": "taskmgr",
    "aktivite monitörü": "taskmgr",
    "figma": "Figma",
    "postman": "Postman",
    "docker": "Docker",
    "tableplus": "TablePlus",
}


def _try_startfile(target: str) -> bool:
    try:
        os.startfile(target)  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


def _try_command(command: str) -> bool:
    executable = shutil.which(command)
    if not executable:
        return False
    subprocess.Popen([executable], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def _try_shell_command(command_line: str) -> bool:
    cmd = (command_line or "").strip()
    if not cmd:
        return False
    try:
        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def _resolve_memory_launch_command(app_name: str) -> str:
    normalized = (app_name or "").strip().lower()
    if not normalized:
        return ""
    try:
        mem = load_memory()
        bucket = mem.get("app_launch_commands", {})
        if not isinstance(bucket, dict):
            return ""
        raw = bucket.get(normalized, {})
        if isinstance(raw, dict):
            return str(raw.get("value", "") or "").strip()
        return str(raw or "").strip()
    except Exception:
        return ""


def _search_program_files(name: str) -> str | None:
    exe_name = name if name.lower().endswith(".exe") else f"{name}.exe"
    roots = [
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"),
    ]
    for root in roots:
        if not root or not Path(root).exists():
            continue
        try:
            for match in Path(root).rglob(exe_name):
                return str(match)
        except Exception:
            continue
    return None


def open_app(app_name: str) -> str:
    """Uygulamayi acar, basari/hata mesaji dondurur."""
    if not app_name:
        return "Uygulama adi belirtilmedi."

    normalized = app_name.lower().strip()
    resolved = APP_ALIASES.get(normalized, app_name.strip())
    memory_cmd = _resolve_memory_launch_command(normalized)

    try:
        if memory_cmd and _try_shell_command(memory_cmd):
            return f"{app_name} açıldı."

        if resolved.startswith(("http://", "https://")):
            webbrowser.open(resolved)
            return f"{app_name} acildi."

        if resolved.endswith(":"):
            if _try_startfile(resolved):
                return f"{app_name} acildi."
            subprocess.Popen(["cmd", "/c", "start", "", resolved], shell=False)
            return f"{app_name} acildi."

        if _try_command(resolved):
            return f"{app_name} acildi."

        if _try_startfile(resolved):
            return f"{app_name} acildi."

        found = _search_program_files(resolved)
        if found and _try_startfile(found):
            return f"{app_name} acildi."

        return f"'{app_name}' bulunamadi veya acilamadi."
    except Exception as exc:
        return f"Hata: {exc}"
