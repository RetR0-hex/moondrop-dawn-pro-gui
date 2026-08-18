"""Reads the Windows "now playing" media session.

Uses the same GlobalSystemMediaTransportControls session manager that the
Windows volume flyout uses, so it sees whatever app is playing -- Spotify, a
browser tab, a local player -- without any per-app integration.

Everything here degrades to ``None`` when the WinRT projection is unavailable
(non-Windows, or ``winsdk`` not installed) so the UI can run without it.
"""

from __future__ import annotations

import asyncio
import io
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

try:  # pragma: no cover - import guard is platform dependent
    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as SessionManager,
    )
    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )
    from winsdk.windows.storage.streams import DataReader

    AVAILABLE = True
except Exception:  # pragma: no cover
    AVAILABLE = False

_STATUS_NAMES = {
    0: "closed",
    1: "opened",
    2: "changing",
    3: "stopped",
    4: "playing",
    5: "paused",
}


@dataclass
class Track:
    title: str = ""
    artist: str = ""
    album: str = ""
    app_id: str = ""
    status: str = "stopped"
    art: Optional[bytes] = field(default=None, repr=False)

    @property
    def key(self) -> str:
        """Identity of the track, used to avoid re-fetching artwork."""
        return f"{self.app_id}|{self.artist}|{self.title}"

    @property
    def is_playing(self) -> bool:
        return self.status == "playing"

    @property
    def app_name(self) -> str:
        """A human-readable app name from the model id (``Spotify.exe`` -> ``Spotify``)."""
        name = self.app_id.rsplit("!", 1)[-1]
        if name.lower().endswith(".exe"):
            name = name[:-4]
        return name


async def _read_art(properties) -> Optional[bytes]:
    reference = properties.thumbnail
    if reference is None:
        return None
    stream = await reference.open_read_async()
    size = stream.size
    if not size:
        return None
    reader = DataReader(stream.get_input_stream_at(0))
    await reader.load_async(size)
    return bytes(reader.read_buffer(size))


async def _read_session(want_art: bool) -> Optional[Track]:
    manager = await SessionManager.request_async()
    session = manager.get_current_session()
    if session is None:
        return None

    properties = await session.try_get_media_properties_async()
    playback = session.get_playback_info()
    status = _STATUS_NAMES.get(int(playback.playback_status), "stopped")

    track = Track(
        title=properties.title or "",
        artist=properties.artist or "",
        album=properties.album_title or "",
        app_id=session.source_app_user_model_id or "",
        status=status,
    )
    if want_art:
        try:
            track.art = await _read_art(properties)
        except Exception:
            track.art = None
    return track


def read_now_playing(want_art: bool = True) -> Optional[Track]:
    """Read the current session once. Returns None when nothing is playing."""
    if not AVAILABLE:
        return None
    try:
        return asyncio.run(_read_session(want_art))
    except Exception:
        return None


class NowPlayingPoller(threading.Thread):
    """Polls the media session and calls back only when something changed.

    Artwork is only fetched when the track identity changes -- decoding a
    300x300 PNG every tick would be wasteful.
    """

    def __init__(self, on_change: Callable[[Optional[Track]], None], interval: float = 1.0) -> None:
        super().__init__(name="now-playing", daemon=True)
        self._on_change = on_change
        self._interval = interval
        self._stop = threading.Event()
        self._last_key: Optional[str] = None
        self._last_status: Optional[str] = None
        self._art: Optional[bytes] = None

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:  # pragma: no cover - thread body
        while not self._stop.is_set():
            track = read_now_playing(want_art=False)
            key = track.key if track else None
            status = track.status if track else None

            if key != self._last_key:
                fresh = read_now_playing(want_art=True)
                self._art = fresh.art if fresh else None
                if fresh is not None:
                    track = fresh
            if track is not None:
                track.art = self._art

            if key != self._last_key or status != self._last_status:
                self._last_key, self._last_status = key, status
                try:
                    self._on_change(track)
                except Exception:
                    pass

            self._stop.wait(self._interval)
