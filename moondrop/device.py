"""Userspace control interface for the MOONDROP Dawn Pro."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

import hid

from . import protocol as p

# The device needs a moment to settle between reports; the vendor tooling uses
# the same 100 ms spacing and shorter gaps produce stale reads.
TRANSFER_DELAY = 0.1

# How many read/re-ask rounds before giving up on matching a reply to its request.
QUERY_ATTEMPTS = 6


class DeviceNotFound(RuntimeError):
    """No Dawn Pro HID interface is present."""


class ProtocolError(RuntimeError):
    """The device replied with something we do not understand."""


@dataclass(frozen=True)
class Status:
    """A decoded snapshot of the device's settings."""

    gain: int
    filter: int
    led: int
    raw: List[int]
    volume_raw: Optional[int] = None

    @property
    def volume(self) -> Optional[int]:
        """The volume as a 0-60 step, or None if it was not read."""
        return None if self.volume_raw is None else p.raw_to_step(self.volume_raw)

    @property
    def gain_name(self) -> str:
        return p.GAIN_BY_VALUE.get(self.gain, f"unknown({self.gain})")

    @property
    def filter_name(self) -> str:
        return p.FILTER_BY_VALUE.get(self.filter, f"unknown({self.filter})")

    @property
    def filter_label(self) -> str:
        return p.FILTER_LABELS.get(self.filter, self.filter_name)

    @property
    def led_name(self) -> str:
        return p.LED_BY_VALUE.get(self.led, f"unknown({self.led})")


def list_devices() -> List[dict]:
    """Return the HID interface descriptors belonging to a Dawn Pro."""
    return [
        d
        for d in hid.enumerate()
        if d["vendor_id"] == p.VENDOR_ID and d["product_id"] == p.PRODUCT_ID
    ]


class DawnPro:
    """Talks to a Dawn Pro over its HID control interface.

    Usage::

        with DawnPro() as dac:
            print(dac.get_status())
            dac.set_gain("high")
            dac.set_filter("slow-phase-compensated")
    """

    def __init__(self, path: Optional[bytes] = None) -> None:
        self._path = path
        self._handle: Optional[hid.device] = None

    # -- lifecycle ---------------------------------------------------------

    def open(self) -> "DawnPro":
        if self._handle is not None:
            return self
        path = self._path
        if path is None:
            devices = list_devices()
            if not devices:
                raise DeviceNotFound(
                    f"no MOONDROP Dawn Pro found (USB {p.VENDOR_ID:04X}:{p.PRODUCT_ID:04X}); "
                    "check that it is plugged in"
                )
            # The control channel is the only HID interface the device exposes;
            # prefer an explicit interface 2 match when several are present.
            path = next(
                (d["path"] for d in devices if d.get("interface_number") == 2),
                devices[0]["path"],
            )
        handle = hid.device()
        handle.open_path(path)
        handle.set_nonblocking(0)
        self._handle = handle
        self._path = path
        return self

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "DawnPro":
        return self.open()

    def __exit__(self, *_exc) -> None:
        self.close()

    @property
    def _device(self) -> hid.device:
        if self._handle is None:
            raise RuntimeError("device is not open; call open() or use it as a context manager")
        return self._handle

    # -- transport ---------------------------------------------------------

    def _send(self, command: int, *args: int) -> None:
        payload = p.build_command(command, *args)
        self._device.write(b"\x00" + payload)
        time.sleep(TRANSFER_DELAY)

    def _read(self) -> List[int]:
        """Read the pending 8-byte reply payload (plus its report id).

        Windows never delivers this interface's input report through ReadFile,
        so it has to be pulled with a HID GET_REPORT of the interface's exact
        input length. Other platforms fall back to the interrupt endpoint.
        """
        try:
            data = list(self._device.get_input_report(0x00, p.INPUT_REPORT_SIZE))
        except (OSError, ValueError):
            data = list(self._device.read(p.INPUT_REPORT_SIZE - 1, 500))
            if data:
                data = [0x00] + data
        if len(data) < p.INPUT_REPORT_SIZE:
            raise ProtocolError(f"short reply from device: {data}")
        return data

    def _query(self, command: int, *args: int) -> List[int]:
        """Send a request and read the reply that belongs to it.

        The device exposes a single latest-reply buffer with no queue, but it
        can lag a beat behind a preceding write -- a read issued too early
        returns the previous command's reply. So re-read, and re-ask, until the
        reply's command byte matches.
        """
        data: List[int] = []
        for attempt in range(QUERY_ATTEMPTS):
            if attempt % 2 == 0:
                self._send(command, *args)
            else:
                time.sleep(TRANSFER_DELAY)
            data = self._read()
            if (
                (data[p.OFF_MAGIC_HI], data[p.OFF_MAGIC_LO]) == p.MAGIC_REPLY
                and data[p.OFF_COMMAND] == command
            ):
                return data

        if (data[p.OFF_MAGIC_HI], data[p.OFF_MAGIC_LO]) != p.MAGIC_REPLY:
            raise ProtocolError(f"unexpected reply header in {data}")
        raise ProtocolError(
            f"reply is for command {data[p.OFF_COMMAND]:#04x}, expected {command:#04x}"
        )

    # -- public API --------------------------------------------------------

    def get_status(self, with_volume: bool = True) -> Status:
        """Read the device's settings.

        Volume lives behind a second command, so it costs one extra round trip;
        pass ``with_volume=False`` to skip it.
        """
        data = self._query(p.CMD_GET_STATUS)
        return Status(
            gain=data[p.OFF_GAIN],
            filter=data[p.OFF_FILTER],
            led=data[p.OFF_LED],
            raw=data,
            volume_raw=self.get_volume_raw() if with_volume else None,
        )

    def refresh_volume(self) -> None:
        """Ask the device to re-apply its volume curve.

        A gain change rescales the analogue output, and the vendor tool issues
        this immediately afterwards so the current volume is re-latched.
        """
        self._send(p.CMD_REFRESH_VOLUME)

    def get_volume_raw(self) -> int:
        """Return the device's raw attenuation code (0x00 loudest, 0xFF quietest)."""
        data = self._query(p.CMD_REFRESH_VOLUME)
        return data[p.OFF_VOLUME]

    def get_volume(self) -> int:
        """Return the current volume as a 0-60 step."""
        return p.raw_to_step(self.get_volume_raw())

    def set_volume_raw(self, raw: int) -> int:
        """Write a raw attenuation code and return what the device reports back.

        Beware the direction: 0x00 is *full output*. Prefer :meth:`set_volume`
        unless you specifically need a code that is not on the 61-step curve.
        """
        if not 0 <= raw <= 0xFF:
            raise ValueError(f"raw volume must be 0-255, got {raw}")
        self._send(p.CMD_SET_VOLUME, raw)
        actual = self.get_volume_raw()
        if actual != raw:
            raise ProtocolError(f"device did not apply volume: wrote {raw:#04x}, read back {actual:#04x}")
        return actual

    def set_volume(self, volume) -> int:
        """Set the volume by 0-60 step (or a string such as ``"45"`` / ``"75%"``).

        Returns the step actually in effect.
        """
        step = volume if isinstance(volume, int) else p.parse_volume(volume)
        if not p.VOLUME_MIN_STEP <= step <= p.VOLUME_MAX_STEP:
            raise ValueError(
                f"volume step must be {p.VOLUME_MIN_STEP}-{p.VOLUME_MAX_STEP}, got {step}"
            )
        self.set_volume_raw(p.step_to_raw(step))
        return step

    def adjust_volume(self, delta: int) -> int:
        """Move the volume by ``delta`` steps, clamped to the 0-60 range."""
        step = max(p.VOLUME_MIN_STEP, min(p.VOLUME_MAX_STEP, self.get_volume() + delta))
        return self.set_volume(step)

    def set_gain(self, gain) -> Status:
        value = gain if isinstance(gain, int) else p.parse_gain(gain)
        if value not in p.GAIN_BY_VALUE:
            raise ValueError(f"gain must be one of {sorted(p.GAIN_BY_VALUE)}, got {value}")
        self._send(p.CMD_SET_GAIN, value)
        self.refresh_volume()
        return self._verify("gain", value)

    def set_filter(self, filter_type) -> Status:
        value = filter_type if isinstance(filter_type, int) else p.parse_filter(filter_type)
        if value not in p.FILTER_BY_VALUE:
            raise ValueError(f"filter must be one of {sorted(p.FILTER_BY_VALUE)}, got {value}")
        self._send(p.CMD_SET_FILTER, value)
        return self._verify("filter", value)

    def set_led(self, mode) -> Status:
        value = mode if isinstance(mode, int) else p.parse_led(mode)
        if value not in p.LED_BY_VALUE:
            raise ValueError(f"LED mode must be one of {sorted(p.LED_BY_VALUE)}, got {value}")
        self._send(p.CMD_SET_LED, value)
        return self._verify("led", value)

    def _verify(self, field: str, expected: int) -> Status:
        """Read back after a write -- the device accepts writes silently."""
        status = self.get_status(with_volume=False)
        actual = getattr(status, field)
        if actual != expected:
            raise ProtocolError(
                f"device did not apply {field}: wrote {expected}, read back {actual}"
            )
        return status
