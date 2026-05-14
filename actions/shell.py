"""
PowerShell/cmd komutu calistirma - Windows.
"""

from __future__ import annotations

import subprocess


BLOCKED = [
    "rm -rf /",
    "sudo rm -rf",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
    "shutdown",
    "reboot",
    "halt",
    "format ",
    "diskpart",
    "bcdedit",
    "reg delete",
    "remove-item -recurse -force c:\\",
    "del /s /q c:\\",
]


def shell_run(command: str, timeout: int = 30) -> str:
    if not command:
        return "Komut belirtilmedi."

    cmd_lower = command.lower()
    stripped = command.strip().lower()

    if stripped.startswith(("rm ", "mv ", "cp ", "chmod ", "chown ", "sudo ")):
        return (
            "Guvenlik: Dosya veya yetki degistiren komutlar dogrudan calistirilmiyor. "
            "Daha guvenli ve dar kapsamli bir komut dene."
        )

    for blocked in BLOCKED:
        if blocked in cmd_lower:
            return f"Guvenlik: Bu komut engellendi -> {blocked}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            timeout=timeout,
        )
        stdout = result.stdout or b""
        stderr = result.stderr or b""
        if isinstance(stdout, str):
            stdout_text = stdout
        else:
            try:
                stdout_text = stdout.decode("utf-8", errors="replace")
            except Exception:
                stdout_text = stdout.decode("cp1254", errors="replace")
        if isinstance(stderr, str):
            stderr_text = stderr
        else:
            try:
                stderr_text = stderr.decode("utf-8", errors="replace")
            except Exception:
                stderr_text = stderr.decode("cp1254", errors="replace")

        output = (stdout_text + stderr_text).strip()
        if not output:
            return "Komut başarıyla çalıştı (çıktı yok)."
        if len(output) > 800:
            output = output[:800] + "\n... (çıktı kısaltıldı)"
        return output
    except subprocess.TimeoutExpired:
        return f"Komut zaman aşımına uğradı ({timeout}s)."
    except Exception as exc:
        return f"Hata: {exc}"
