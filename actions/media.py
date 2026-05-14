"""
Medya oynatma - Windows uyumlu.
"""

from __future__ import annotations

import ctypes
import os
import urllib.parse
import webbrowser

from actions.browser import browser_control


def _play_youtube(query: str) -> str:
    return browser_control("play_youtube", query=query)


def _play_spotify(query: str, autoplay: bool = True) -> str:
    encoded_query = urllib.parse.quote(query.strip())
    uri = f"spotify:search:{encoded_query}"
    try:
        os.startfile(uri)  # type: ignore[attr-defined]
        if autoplay:
            return f"Spotify acildi ve '{query}' aramasi baslatildi."
        return f"Spotify icinde '{query}' aramasi acildi."
    except Exception:
        webbrowser.open(f"https://open.spotify.com/search/{encoded_query}", new=2)
        return f"Spotify web aramasi acildi: {query}"


def _play_apple_music(query: str) -> str:
    webbrowser.open(
        f"https://music.apple.com/search?term={urllib.parse.quote(query.strip())}",
        new=2,
    )
    return f"Apple Music web aramasi acildi: {query}"


def play_media(query: str, provider: str = "auto", autoplay: bool = True) -> str:
    if not query or not query.strip():
        return "Calinacak icerik belirtilmedi."

    normalized_provider = (provider or "auto").strip().lower()
    if normalized_provider in {"yt", "youtube music"}:
        normalized_provider = "youtube"
    elif normalized_provider in {"apple music", "music", "apple_music"}:
        normalized_provider = "apple_music"

    if normalized_provider == "spotify":
        return _play_spotify(query, autoplay=autoplay)
    if normalized_provider == "apple_music":
        return _play_apple_music(query)
    if normalized_provider == "youtube":
        return _play_youtube(query)

    # auto
    spotify = _play_spotify(query, autoplay=autoplay)
    if "web aramasi" not in spotify.lower():
        return spotify
    return _play_youtube(query)


def stop_media(provider: str = "auto") -> str:
    """
    Windows genel medya Play/Pause tusunu gonderir.
    Bircok uygulamada (YouTube/Spotify tarayici/masaustu) calan medyayi durdurur.
    """
    try:
        # VK_MEDIA_PLAY_PAUSE = 0xB3
        VK_MEDIA_PLAY_PAUSE = 0xB3
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_KEYUP, 0)
        if provider and provider != "auto":
            return f"{provider} için durdur/oynat komutu gönderildi."
        return "Medya durdur/oynat komutu gönderildi."
    except Exception as exc:
        return f"Hata: Medya durdurulamadi - {exc}"
