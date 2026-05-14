"""
Sistem bilgisi - Windows uyumlu psutil + ipconfig.
"""

from __future__ import annotations

import datetime
import socket
import subprocess

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def sys_info(query: str) -> str:
    query = (query or "all").lower().strip()
    results = []

    if query in ("battery", "pil", "all"):
        results.append(_battery())
    if query in ("cpu", "islemci", "işlemci", "all"):
        results.append(_cpu())
    if query in ("ram", "bellek", "memory", "all"):
        results.append(_ram())
    if query in ("disk", "depolama", "all"):
        results.append(_disk())
    if query in ("time", "saat", "zaman", "all"):
        now = datetime.datetime.now()
        results.append(f"Saat: {now.strftime('%H:%M:%S')}")
    if query in ("date", "tarih", "all"):
        now = datetime.datetime.now()
        results.append(f"Tarih: {now.strftime('%d.%m.%Y, %A')}")
    if query in ("network", "ag", "ağ", "wifi", "all"):
        results.append(_network())

    if not results:
        results.append(f"Bilinmeyen sorgu: {query}. battery/cpu/ram/disk/time/date/network/all kullanin.")

    return "\n".join(r for r in results if r)


def _battery() -> str:
    if HAS_PSUTIL:
        bat = psutil.sensors_battery()
        if bat:
            status = "Sarj oluyor" if bat.power_plugged else "Pilde"
            return f"Pil: %{bat.percent:.0f} - {status}"
    return "Pil bilgisi alinamadi veya bu cihazda pil yok."


def _cpu() -> str:
    if HAS_PSUTIL:
        usage = psutil.cpu_percent(interval=0.5)
        count = psutil.cpu_count(logical=True)
        freq = psutil.cpu_freq()
        freq_str = f", {freq.current:.0f} MHz" if freq else ""
        return f"CPU: %{usage:.1f} kullanim - {count} cekirdek{freq_str}"
    return "CPU bilgisi alinamadi."


def _ram() -> str:
    if HAS_PSUTIL:
        vm = psutil.virtual_memory()
        total = vm.total / (1024**3)
        used = vm.used / (1024**3)
        return f"RAM: {used:.1f}GB / {total:.1f}GB kullanimda (%{vm.percent:.0f})"
    return "RAM bilgisi alinamadi."


def _disk() -> str:
    if HAS_PSUTIL:
        du = psutil.disk_usage("C:\\")
        total = du.total / (1024**3)
        used = du.used / (1024**3)
        free = du.free / (1024**3)
        return f"Disk (C:): {used:.1f}GB kullanildi, {free:.1f}GB bos (toplam {total:.1f}GB)"
    return "Disk bilgisi alinamadi."


def _network() -> str:
    if HAS_PSUTIL:
        for name, addrs in psutil.net_if_addrs().items():
            if "loopback" in name.lower():
                continue
            for addr in addrs:
                if getattr(addr, "family", None) == socket.AF_INET and not addr.address.startswith("127."):
                    return f"Ag: {name} - IP {addr.address}"
    try:
        out = subprocess.check_output(["ipconfig"], text=True, timeout=5, errors="ignore")
        for line in out.splitlines():
            if "IPv4" in line and ":" in line:
                ip = line.split(":", 1)[1].strip()
                if ip:
                    return f"Ag: IP {ip}"
    except Exception:
        pass
    return "Ag baglantisi bulunamadi."
