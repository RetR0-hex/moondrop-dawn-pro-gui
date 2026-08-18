"""Everything factual we can learn about the attached Dawn Pro.

Three sources, kept apart so the UI can say where a number came from:

* **USB/HID** -- read from the device itself (ids, strings, report descriptor).
* **Windows audio** -- what the OS negotiates with it (current format, and the
  formats it accepts in exclusive mode, probed one by one).
* **Published specs** -- MOONDROP's own figures, which we cannot measure.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import hid

from . import protocol as p

# --- published specifications ------------------------------------------------
# From moondroplab.com/en/products/dawn-pro. Figures we cannot verify locally.
PUBLISHED_SPECS: List[Tuple[str, str]] = [
    # The first two are engraved on the device itself.
    ("DAC", "Dual Cirrus Logic CS43131"),
    ("Decoding", "32-bit / 384 kHz PCM · DSD256"),
    ("Frequency response", "5 Hz – 82 kHz (±1 dB)"),
    ("THD+N", "0.00014% (AES17 20 kHz, no load)"),
    ("SNR", "131 dB A-wt (4.4 mm) · 123 dB A-wt (3.5 mm)"),
    ("Dynamic range", "132 dB A-wt (4.4 mm)"),
    ("Noise floor", "1.3 µV (4.4 mm) · 1.5 µV (3.5 mm)"),
    ("Line output", "4 Vrms (4.4 mm) · 2 Vrms (3.5 mm)"),
    ("Outputs", "3.5 mm single-ended · 4.4 mm balanced"),
    ("Size", "42 × 22.45 × 12.39 mm"),
    ("Weight", "13 g"),
]

SAMPLE_RATES = (44100, 48000, 88200, 96000, 176400, 192000, 352800, 384000)
BIT_DEPTHS = (16, 24, 32)


# --- USB / HID ---------------------------------------------------------------


class _HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", ctypes.c_ushort),
        ("UsagePage", ctypes.c_ushort),
        ("InputReportByteLength", ctypes.c_ushort),
        ("OutputReportByteLength", ctypes.c_ushort),
        ("FeatureReportByteLength", ctypes.c_ushort),
        ("Reserved", ctypes.c_ushort * 17),
        ("NumberLinkCollectionNodes", ctypes.c_ushort),
        ("NumberInputButtonCaps", ctypes.c_ushort),
        ("NumberInputValueCaps", ctypes.c_ushort),
        ("NumberInputDataIndices", ctypes.c_ushort),
        ("NumberOutputButtonCaps", ctypes.c_ushort),
        ("NumberOutputValueCaps", ctypes.c_ushort),
        ("NumberOutputDataIndices", ctypes.c_ushort),
        ("NumberFeatureButtonCaps", ctypes.c_ushort),
        ("NumberFeatureValueCaps", ctypes.c_ushort),
        ("NumberFeatureDataIndices", ctypes.c_ushort),
    ]


@dataclass
class UsbInfo:
    present: bool = False
    vendor_id: int = p.VENDOR_ID
    product_id: int = p.PRODUCT_ID
    manufacturer: str = ""
    product: str = ""
    serial: str = ""
    release: int = 0
    interface_number: int = -1
    usage_page: int = 0
    usage: int = 0
    path: str = ""
    input_report_len: int = 0
    output_report_len: int = 0
    feature_report_len: int = 0
    report_descriptor: bytes = field(default=b"", repr=False)

    @property
    def ids(self) -> str:
        return f"{self.vendor_id:04X}:{self.product_id:04X}"

    @property
    def release_text(self) -> str:
        """bcdDevice, shown the way USB spells it."""
        return f"{self.release >> 8:x}.{self.release & 0xFF:02x}"


def _report_lengths(path: bytes) -> Tuple[int, int, int]:
    """Ask Windows for the interface's report sizes."""
    hidd = ctypes.WinDLL("hid.dll")
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = k32.CreateFileW(ctypes.c_wchar_p(path.decode()), 0, 3, None, 3, 0, None)
    if handle in (0, -1, 0xFFFFFFFF):
        return 0, 0, 0
    handle = wintypes.HANDLE(handle)
    try:
        preparsed = ctypes.c_void_p()
        if not hidd.HidD_GetPreparsedData(handle, ctypes.byref(preparsed)):
            return 0, 0, 0
        caps = _HIDP_CAPS()
        hidd.HidP_GetCaps(preparsed, ctypes.byref(caps))
        return (
            caps.InputReportByteLength,
            caps.OutputReportByteLength,
            caps.FeatureReportByteLength,
        )
    finally:
        k32.CloseHandle(handle)


def read_usb_info() -> UsbInfo:
    entry = next(
        (
            d
            for d in hid.enumerate()
            if d["vendor_id"] == p.VENDOR_ID and d["product_id"] == p.PRODUCT_ID
        ),
        None,
    )
    if entry is None:
        return UsbInfo()

    info = UsbInfo(
        present=True,
        manufacturer=entry.get("manufacturer_string") or "",
        product=entry.get("product_string") or "",
        serial=entry.get("serial_number") or "",
        release=entry.get("release_number") or 0,
        interface_number=entry.get("interface_number", -1),
        usage_page=entry.get("usage_page", 0),
        usage=entry.get("usage", 0),
        path=entry["path"].decode(errors="replace"),
    )
    try:
        info.input_report_len, info.output_report_len, info.feature_report_len = _report_lengths(
            entry["path"]
        )
    except Exception:
        pass
    try:
        device = hid.device()
        device.open_path(entry["path"])
        try:
            info.report_descriptor = bytes(device.get_report_descriptor())
        finally:
            device.close()
    except Exception:
        pass
    return info


# --- Windows audio -----------------------------------------------------------


def probe_supported_formats() -> Dict[int, List[int]]:
    """Ask the endpoint which PCM formats it accepts in exclusive mode.

    This is measured, not claimed: each combination is offered to WASAPI and
    only an exact match (S_OK, no "closest match" returned) counts.
    """
    try:
        import comtypes
        from pycaw.api.audioclient import IAudioClient
        from pycaw.api.audioclient.depend import WAVEFORMATEX

        from .audioinfo import find_endpoint
    except Exception:
        return {}

    class WAVEFORMATEXTENSIBLE(ctypes.Structure):
        _fields_ = [
            ("wFormatTag", ctypes.c_ushort),
            ("nChannels", ctypes.c_ushort),
            ("nSamplesPerSec", wintypes.DWORD),
            ("nAvgBytesPerSec", wintypes.DWORD),
            ("nBlockAlign", ctypes.c_ushort),
            ("wBitsPerSample", ctypes.c_ushort),
            ("cbSize", ctypes.c_ushort),
            ("wValidBitsPerSample", ctypes.c_ushort),
            ("dwChannelMask", wintypes.DWORD),
            ("SubFormat", ctypes.c_byte * 16),
        ]

    subtype_pcm = bytes.fromhex("0100000000001000800000aa00389b71")

    try:
        comtypes.CoInitialize()
        device, _name = find_endpoint()
        if device is None:
            return {}
        client = device.Activate(IAudioClient._iid_, comtypes.CLSCTX_ALL, None).QueryInterface(
            IAudioClient
        )
    except Exception:
        return {}

    def accepts(rate: int, bits: int) -> bool:
        fmt = WAVEFORMATEXTENSIBLE()
        fmt.wFormatTag = 0xFFFE
        fmt.nChannels = 2
        fmt.nSamplesPerSec = rate
        fmt.wBitsPerSample = bits
        fmt.nBlockAlign = 2 * bits // 8
        fmt.nAvgBytesPerSec = rate * fmt.nBlockAlign
        fmt.cbSize = 22
        fmt.wValidBitsPerSample = bits
        fmt.dwChannelMask = 3
        ctypes.memmove(fmt.SubFormat, subtype_pcm, 16)
        try:
            closest = client.IsFormatSupported(
                1, ctypes.cast(ctypes.byref(fmt), ctypes.POINTER(WAVEFORMATEX))
            )
            return not bool(closest)
        except Exception:
            return False

    return {bits: [r for r in SAMPLE_RATES if accepts(r, bits)] for bits in BIT_DEPTHS}


def format_rate_list(rates: List[int]) -> str:
    if not rates:
        return "—"
    return " · ".join(f"{r / 1000:g}".rstrip("0").rstrip(".") + "k" for r in rates)


# --- bound Windows drivers ---------------------------------------------------


@dataclass
class InterfaceBinding:
    instance: str
    description: str
    device_class: str
    service: str


def read_driver_bindings() -> List[InterfaceBinding]:
    """Which Windows driver is bound to each USB interface of the device.

    Read straight from the PnP enumerator in the registry, so it reflects what
    is actually loaded -- the audio interface is not always on Microsoft's
    usbaudio2.sys.
    """
    try:
        import winreg
    except ImportError:
        return []

    root = r"SYSTEM\CurrentControlSet\Enum\USB"
    prefix = f"VID_{p.VENDOR_ID:04X}&PID_{p.PRODUCT_ID:04X}"
    found: List[InterfaceBinding] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root) as usb:
            for index in range(winreg.QueryInfoKey(usb)[0]):
                name = winreg.EnumKey(usb, index)
                if not name.upper().startswith(prefix):
                    continue
                with winreg.OpenKey(usb, name) as device:
                    for child in range(winreg.QueryInfoKey(device)[0]):
                        instance = winreg.EnumKey(device, child)
                        with winreg.OpenKey(device, instance) as node:
                            values = {}
                            for value in range(winreg.QueryInfoKey(node)[1]):
                                key, data, _kind = winreg.EnumValue(node, value)
                                values[key] = data
                            found.append(
                                InterfaceBinding(
                                    instance=name + "\\" + instance,
                                    description=str(values.get("DeviceDesc", "")).split(";")[-1],
                                    device_class=str(values.get("Class", "")),
                                    service=str(values.get("Service", "")),
                                )
                            )
    except OSError:
        return []
    return sorted(found, key=lambda b: b.instance)
