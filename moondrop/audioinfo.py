"""Reads what Windows is actually sending to the Dawn Pro, and how loud.

Two things come from the audio endpoint rather than from the DAC itself:

* the **stream format** -- sample rate, bit depth and channel count, as
  configured on the endpoint (Sound settings -> Device properties -> Advanced);
* the **peak level**, which drives the level meter.

Both are read through the Core Audio COM interfaces. Everything degrades to
``None`` when the endpoint or ``comtypes``/``pycaw`` are unavailable.
"""

from __future__ import annotations

import ctypes
import struct
import uuid
from ctypes import wintypes
from dataclasses import dataclass
from typing import Optional, Sequence

try:  # pragma: no cover - import guard is platform dependent
    import comtypes
    from comtypes import GUID
    from pycaw.pycaw import IAudioMeterInformation
    from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
    from pycaw.api.mmdeviceapi.depend.structures import PROPERTYKEY
    from pycaw.constants import CLSID_MMDeviceEnumerator

    AVAILABLE = True
except Exception:  # pragma: no cover
    AVAILABLE = False

E_RENDER = 0
DEVICE_STATE_ACTIVE = 1
STGM_READ = 0

# Subformat GUIDs found in a WAVEFORMATEXTENSIBLE.
_SUBTYPE_PCM = "00000001-0000-0010-8000-00AA00389B71"
_SUBTYPE_FLOAT = "00000003-0000-0010-8000-00AA00389B71"

DEFAULT_NAME_HINTS = ("dawn", "moondrop")


class _BLOB(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.ULONG), ("pBlobData", ctypes.POINTER(ctypes.c_byte))]


class _PROPVARIANT(ctypes.Structure):
    """Minimal PROPVARIANT -- pycaw's own definition has no blob member."""

    class _U(ctypes.Union):
        _fields_ = [
            ("blob", _BLOB),
            ("pwszVal", ctypes.c_wchar_p),
            ("uhVal", ctypes.c_ulonglong),
        ]

    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("reserved1", ctypes.c_ushort),
        ("reserved2", ctypes.c_ushort),
        ("reserved3", ctypes.c_ushort),
        ("union", _U),
    ]


VT_BLOB = 65


def _key(fmtid: str, pid: int):
    key = PROPERTYKEY()
    key.fmtid = GUID(fmtid)
    key.pid = pid
    return key


def _pkey_device_format():
    return _key("{f19f064d-082c-4e27-bc73-6882a1bb8e4c}", 0)


def _pkey_friendly_name():
    return _key("{a45c254e-df1c-4efd-8020-67d146a850e0}", 14)


@dataclass
class AudioFormat:
    device_name: str
    sample_rate: int
    bit_depth: int
    channels: int
    encoding: str  # "PCM", "Float" or "PCM/Float"

    @property
    def summary(self) -> str:
        khz = self.sample_rate / 1000.0
        rate = f"{khz:g} kHz"
        channels = {1: "Mono", 2: "Stereo"}.get(self.channels, f"{self.channels}ch")
        return f"{rate} · {self.bit_depth}-bit {self.encoding} · {channels}"


def _enumerator():
    return comtypes.CoCreateInstance(
        CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, comtypes.CLSCTX_INPROC_SERVER
    )


def find_endpoint(name_hints: Sequence[str] = DEFAULT_NAME_HINTS):
    """Return ``(device, friendly_name)`` for the first render endpoint matching a hint."""
    if not AVAILABLE:
        return None, ""
    try:
        collection = _enumerator().EnumAudioEndpoints(E_RENDER, DEVICE_STATE_ACTIVE)
        for index in range(collection.GetCount()):
            device = collection.Item(index)
            name = device.OpenPropertyStore(STGM_READ).GetValue(_pkey_friendly_name()).GetValue()
            lowered = (name or "").lower()
            if any(hint in lowered for hint in name_hints):
                return device, name
    except Exception:
        pass
    return None, ""


def read_format(name_hints: Sequence[str] = DEFAULT_NAME_HINTS) -> Optional[AudioFormat]:
    """Read the endpoint's configured stream format."""
    device, name = find_endpoint(name_hints)
    if device is None:
        return None
    try:
        value = device.OpenPropertyStore(STGM_READ).GetValue(_pkey_device_format())
        variant = ctypes.cast(ctypes.byref(value), ctypes.POINTER(_PROPVARIANT)).contents
        if variant.vt != VT_BLOB:
            return None
        data = bytes(ctypes.string_at(variant.union.blob.pBlobData, variant.union.blob.cbSize))
    except Exception:
        return None

    if len(data) < 16:
        return None
    tag, channels, rate, _avg, _align, bits = struct.unpack("<HHIIHH", data[:16])

    encoding = {1: "PCM", 3: "Float"}.get(tag, "PCM")
    if tag == 0xFFFE and len(data) >= 40:  # WAVEFORMATEXTENSIBLE
        valid_bits = struct.unpack("<H", data[18:20])[0]
        if valid_bits:
            bits = valid_bits
        subformat = str(uuid.UUID(bytes_le=data[24:40])).upper()
        encoding = {_SUBTYPE_PCM: "PCM", _SUBTYPE_FLOAT: "Float"}.get(subformat, "PCM")

    return AudioFormat(
        device_name=name, sample_rate=rate, bit_depth=bits, channels=channels, encoding=encoding
    )


class PeakMeter:
    """Live output level of the endpoint, 0.0 - 1.0.

    Activated lazily and re-activated if the device goes away, so unplugging
    the DAC does not take the meter down permanently.
    """

    def __init__(self, name_hints: Sequence[str] = DEFAULT_NAME_HINTS) -> None:
        self._name_hints = name_hints
        self._meter = None

    def _activate(self) -> None:
        device, _name = find_endpoint(self._name_hints)
        if device is None:
            self._meter = None
            return
        interface = device.Activate(IAudioMeterInformation._iid_, comtypes.CLSCTX_ALL, None)
        self._meter = interface.QueryInterface(IAudioMeterInformation)

    def read(self) -> float:
        if not AVAILABLE:
            return 0.0
        if self._meter is None:
            try:
                self._activate()
            except Exception:
                self._meter = None
                return 0.0
        if self._meter is None:
            return 0.0
        try:
            return float(self._meter.GetPeakValue())
        except Exception:
            self._meter = None
            return 0.0
