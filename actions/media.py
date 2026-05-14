"""
Medya oynatma - Windows uyumlu.
"""

from __future__ import annotations

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
