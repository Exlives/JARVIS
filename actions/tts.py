"""
TTS (Text-to-Speech) - Windows SAPI kullanir.
"""

from __future__ import annotations

import subprocess
import threading


VOICE = ""


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def speak_text(text: str, on_done=None, blocking: bool = False):
    if not text or not text.strip():
        if on_done:
            on_done()
        return

    max_len = 500
    if len(text) > max_len:
        text = text[:max_len] + "..."

    def _run():
        try:
            select_voice = ""
            if VOICE:
                select_voice = f"$s.SelectVoice({_ps_quote(VOICE)}); "
            script = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"{select_voice}$s.Speak({_ps_quote(text)});"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
        if on_done:
            on_done()

    if blocking:
        _run()
    else:
        threading.Thread(target=_run, daemon=True).start()


def get_available_voices() -> list[str]:
    try:
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []
