"""The QObject the QML front end talks to.

All device I/O happens on a worker thread: a HID round trip takes ~100 ms and a
full status read costs two of them, which would visibly stutter the UI if it ran
on the Qt thread. Writes are queued as callables; status is polled on an
interval and pushed back through Qt signals, which marshal onto the GUI thread
automatically.
"""

from __future__ import annotations

import base64
import queue
import threading
import time
from typing import Callable, Optional

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from pathlib import Path

from .. import protocol as p
from ..device import DawnPro, DeviceNotFound, ProtocolError
from ..deviceinfo import (
    PUBLISHED_SPECS,
    format_rate_list,
    probe_supported_formats,
    read_driver_bindings,
    read_usb_info,
)
from ..nowplaying import NowPlayingPoller, Track

ASSETS = Path(__file__).parent / "assets"

try:
    import comtypes

    from ..audioinfo import PeakMeter, read_format

    AUDIO_INFO = True
except Exception:  # pragma: no cover - optional dependency
    AUDIO_INFO = False

STATUS_POLL_SECONDS = 2.0
METER_INTERVAL_MS = 40
FORMAT_INTERVAL_MS = 2000


class _DeviceWorker(threading.Thread):
    """Serialises all access to the DAC onto one thread."""

    def __init__(self, on_status, on_connection) -> None:
        super().__init__(name="dawn-pro-io", daemon=True)
        self._commands: "queue.Queue[Optional[Callable[[DawnPro], None]]]" = queue.Queue()
        self._on_status = on_status
        self._on_connection = on_connection
        self._stop = threading.Event()
        self._dac = DawnPro()
        self._connected = False

    def submit(self, command: Callable[[DawnPro], None]) -> None:
        self._commands.put(command)

    def stop(self) -> None:
        self._stop.set()
        self._commands.put(None)

    def _set_connected(self, connected: bool, message: str) -> None:
        if connected != self._connected:
            self._connected = connected
            self._on_connection(connected, message)

    def _ensure_open(self) -> bool:
        if self._connected:
            return True
        try:
            self._dac.close()
            self._dac.open()
        except (DeviceNotFound, OSError) as exc:
            self._set_connected(False, str(exc))
            return False
        self._set_connected(True, "Connected")
        return True

    def run(self) -> None:  # pragma: no cover - thread body
        next_poll = 0.0
        while not self._stop.is_set():
            try:
                command = self._commands.get(timeout=0.05)
            except queue.Empty:
                command = None
            else:
                if command is None:
                    break

            if not self._ensure_open():
                self._stop.wait(1.0)
                continue

            # Idle ticks only read on the poll interval; a write always reads
            # back, so the UI reflects what the device actually accepted.
            if command is None and time.monotonic() < next_poll:
                continue

            try:
                if command is not None:
                    command(self._dac)
                self._on_status(self._dac.get_status())
                next_poll = time.monotonic() + STATUS_POLL_SECONDS
            except (DeviceNotFound, ProtocolError, OSError, RuntimeError) as exc:
                self._set_connected(False, str(exc))

        self._dac.close()


class Controller(QObject):
    """Everything the QML front end can see and do."""

    changed = Signal()
    levelChanged = Signal()
    trackChanged = Signal()
    infoChanged = Signal()
    toast = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._connected = False
        self._message = "Connecting…"
        self._volume = 0
        self._gain = 0
        self._filter = 0
        self._led = 0
        self._raw = ""
        self._level = 0.0
        self._level_peak = 0.0
        self._format = ""
        self._device_name = ""
        self._track = Track()
        self._art_uri = ""
        self._info_groups: list = []

        # Probing formats means ~24 WASAPI round trips; keep it off the UI thread.
        threading.Thread(target=self._build_info, daemon=True, name="device-info").start()

        self._worker = _DeviceWorker(self._on_status, self._on_connection)
        self._worker.start()

        self._media = NowPlayingPoller(self._on_track, interval=1.0)
        self._media.start()

        self._meter = None
        if AUDIO_INFO:
            comtypes.CoInitialize()
            self._meter = PeakMeter()

            self._meter_timer = QTimer(self)
            self._meter_timer.timeout.connect(self._tick_meter)
            self._meter_timer.start(METER_INTERVAL_MS)

            self._format_timer = QTimer(self)
            self._format_timer.timeout.connect(self._tick_format)
            self._format_timer.start(FORMAT_INTERVAL_MS)
            self._tick_format()

    # -- callbacks from worker threads -------------------------------------

    def _on_status(self, status) -> None:
        if status.volume is not None:
            self._volume = status.volume
        self._gain = status.gain
        self._filter = status.filter
        self._led = status.led
        self._raw = " ".join(f"{b:02X}" for b in status.raw)
        self.changed.emit()

    def _on_connection(self, connected: bool, message: str) -> None:
        self._connected = connected
        self._message = message
        self.changed.emit()

    def _on_track(self, track: Optional[Track]) -> None:
        self._track = track or Track()
        art = self._track.art
        self._art_uri = (
            "data:image/png;base64," + base64.b64encode(art).decode("ascii") if art else ""
        )
        self.trackChanged.emit()

    def _tick_meter(self) -> None:
        value = self._meter.read()
        # Fast attack, slow release: a raw peak reading flickers badly.
        self._level = value if value > self._level else self._level * 0.82 + value * 0.18
        self._level_peak = max(value, self._level_peak * 0.97)
        self.levelChanged.emit()

    def _tick_format(self) -> None:
        fmt = read_format()
        summary = fmt.summary if fmt else ""
        name = fmt.device_name if fmt else ""
        if summary != self._format or name != self._device_name:
            self._format, self._device_name = summary, name
            self.changed.emit()

    # -- device info -------------------------------------------------------

    def _build_info(self) -> None:
        usb = read_usb_info()
        groups = []

        groups.append(
            {
                "title": "Device",
                "note": "read from the device",
                "rows": [
                    {"label": "Model", "value": usb.serial or "Dawn Pro"},
                    {"label": "Manufacturer", "value": usb.manufacturer or "MOONDROP"},
                    {"label": "USB ID", "value": usb.ids},
                    {"label": "Device release", "value": "bcdDevice " + usb.release_text},
                    {"label": "Connection", "value": "USB composite device"},
                ],
            }
        )

        descriptor = " ".join(f"{b:02X}" for b in usb.report_descriptor)
        groups.append(
            {
                "title": "Control channel",
                "note": "the vendor HID interface this app drives",
                "rows": [
                    {"label": "Interface", "value": f"MI_{usb.interface_number:02d} (HID)"},
                    {
                        "label": "Usage",
                        "value": f"page {usb.usage_page:#06x} / usage {usb.usage:#06x} (consumer)",
                    },
                    {
                        "label": "Report sizes",
                        "value": (
                            f"in {usb.input_report_len} · out {usb.output_report_len} · "
                            f"feature {usb.feature_report_len}"
                        ),
                    },
                    {"label": "Descriptor", "value": f"{len(usb.report_descriptor)} bytes"},
                    {"label": "Command prefix", "value": "C0 A5 · replies A0 A5"},
                    {"label": "Commands", "value": "01 filter · 02 gain · 04 volume · 06 LED · A2/A3 read"},
                    {"label": "Descriptor bytes", "value": descriptor},
                ],
            }
        )

        formats = probe_supported_formats()
        audio_rows = []
        if self._device_name:
            audio_rows.append({"label": "Endpoint", "value": self._device_name})
        if self._format:
            audio_rows.append({"label": "Current format", "value": self._format})
        for bits in sorted(formats):
            audio_rows.append(
                {"label": f"{bits}-bit rates", "value": format_rate_list(formats[bits])}
            )
        for binding in read_driver_bindings():
            audio_rows.append(
                {
                    "label": binding.description or "Driver",
                    "value": binding.service,
                }
            )
        if audio_rows:
            groups.append(
                {
                    "title": "Windows audio",
                    "note": "measured against the endpoint · exclusive mode",
                    "rows": audio_rows,
                }
            )

        groups.append(
            {
                "title": "Published specifications",
                "note": "MOONDROP figures · not measured here",
                "rows": [{"label": label, "value": value} for label, value in PUBLISHED_SPECS],
            }
        )

        self._info_groups = groups
        self.infoChanged.emit()

    # -- properties --------------------------------------------------------

    connected = Property(bool, lambda self: self._connected, notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)
    volume = Property(int, lambda self: self._volume, notify=changed)
    volumeMax = Property(int, lambda self: p.VOLUME_MAX_STEP, constant=True)
    volumePercent = Property(
        int, lambda self: round(self._volume / p.VOLUME_MAX_STEP * 100), notify=changed
    )
    gain = Property(int, lambda self: self._gain, notify=changed)
    filterIndex = Property(int, lambda self: self._filter, notify=changed)
    filterLabel = Property(str, lambda self: p.FILTER_LABELS.get(self._filter, ""), notify=changed)
    led = Property(int, lambda self: self._led, notify=changed)
    rawStatus = Property(str, lambda self: self._raw, notify=changed)
    formatSummary = Property(str, lambda self: self._format, notify=changed)
    deviceName = Property(str, lambda self: self._device_name, notify=changed)

    level = Property(float, lambda self: self._level, notify=levelChanged)
    levelPeak = Property(float, lambda self: self._level_peak, notify=levelChanged)

    trackTitle = Property(str, lambda self: self._track.title, notify=trackChanged)
    trackArtist = Property(str, lambda self: self._track.artist, notify=trackChanged)
    trackAlbum = Property(str, lambda self: self._track.album, notify=trackChanged)
    trackApp = Property(str, lambda self: self._track.app_name, notify=trackChanged)
    trackPlaying = Property(bool, lambda self: self._track.is_playing, notify=trackChanged)
    artUri = Property(str, lambda self: self._art_uri, notify=trackChanged)

    infoGroups = Property("QVariantList", lambda self: self._info_groups, notify=infoChanged)

    def _product_image(self) -> str:
        """A photo of the device, if the user dropped one next to the QML."""
        for name in ("dawnpro.png", "dawnpro.jpg", "dawnpro.webp"):
            candidate = ASSETS / name
            if candidate.exists():
                return candidate.as_uri()
        return ""

    productImage = Property(str, lambda self: self._product_image(), constant=True)

    # -- slots called from QML ---------------------------------------------

    @Slot(int)
    def setVolume(self, step: int) -> None:
        step = max(0, min(p.VOLUME_MAX_STEP, int(step)))
        if step == self._volume:
            return
        # Optimistic: update locally so the slider does not snap back while the
        # write is in flight, then let the read-back confirm it.
        self._volume = step
        self.changed.emit()
        self._worker.submit(lambda dac: dac.set_volume(step))

    @Slot(int)
    def nudgeVolume(self, delta: int) -> None:
        self.setVolume(self._volume + delta)

    @Slot(int)
    def setGain(self, value: int) -> None:
        self._gain = value
        self.changed.emit()
        self._worker.submit(lambda dac: dac.set_gain(value))
        self.toast.emit("Gain: " + p.GAIN_BY_VALUE.get(value, str(value)).capitalize())

    @Slot(int)
    def setFilter(self, value: int) -> None:
        self._filter = value
        self.changed.emit()
        self._worker.submit(lambda dac: dac.set_filter(value))
        self.toast.emit(p.FILTER_LABELS.get(value, ""))

    @Slot(int)
    def setLed(self, value: int) -> None:
        self._led = value
        self.changed.emit()
        self._worker.submit(lambda dac: dac.set_led(value))
        self.toast.emit("LED: " + p.LED_BY_VALUE.get(value, str(value)))

    @Slot()
    def reconnect(self) -> None:
        self._worker.submit(lambda dac: None)

    @Slot()
    def shutdown(self) -> None:
        self._media.stop()
        self._worker.stop()
