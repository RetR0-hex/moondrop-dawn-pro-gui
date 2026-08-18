"""A level meter that actually moves.

The obvious source for a meter is ``IAudioMeterInformation.GetPeakValue`` on the
endpoint, but measuring it against real material shows why that reads as broken:

    peak dBFS: min -8.7  median 0.0  p90 0.0

Modern masters are limited hard enough that the *peak* sits at full scale
essentially all the time, so no amount of rescaling makes the bar move -- it is
faithfully reporting a signal that really is pinned at 0 dBFS.

Loudness is what a listener perceives as "how loud is this right now", and that
is RMS, which needs the samples themselves. So this captures the render stream
through a WASAPI loopback client and computes RMS over short blocks. Typical
material lands around -18 to -8 dBFS RMS and moves several dB with the music,
which is exactly what a meter should show.

Falls back to the peak meter if loopback cannot be opened.
"""

from __future__ import annotations

import ctypes
import math
import threading
from array import array
from ctypes import POINTER, c_uint32, c_uint64
from ctypes.wintypes import DWORD

try:  # pragma: no cover - platform dependent
    import comtypes
    from comtypes import COMMETHOD, GUID, IUnknown, HRESULT
    from pycaw.api.audioclient import IAudioClient
    from pycaw.api.audioclient.depend import WAVEFORMATEX

    from .audioinfo import find_endpoint

    AVAILABLE = True
except Exception:  # pragma: no cover
    AVAILABLE = False

AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
REFTIMES_PER_SEC = 10_000_000

# Meter scale. RMS below FLOOR_DB reads empty, at CEILING_DB reads full.
# Full scale is 0 dBFS RMS, which no real material reaches, so the bar has
# headroom instead of sitting against the end.
FLOOR_DB = -36.0
CEILING_DB = 0.0

BLOCK_SECONDS = 0.05      # RMS integration window
POLL_SECONDS = 0.02
SAMPLE_STRIDE = 4         # every Nth frame is plenty for a meter


if AVAILABLE:

    class IAudioCaptureClient(IUnknown):
        _iid_ = GUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")
        _methods_ = (
            COMMETHOD(
                [],
                HRESULT,
                "GetBuffer",
                (["out"], POINTER(POINTER(ctypes.c_byte)), "ppData"),
                (["out"], POINTER(c_uint32), "pNumFramesToRead"),
                (["out"], POINTER(DWORD), "pdwFlags"),
                (["out"], POINTER(c_uint64), "pu64DevicePosition"),
                (["out"], POINTER(c_uint64), "pu64QPCPosition"),
            ),
            COMMETHOD([], HRESULT, "ReleaseBuffer", (["in"], c_uint32, "NumFramesRead")),
            COMMETHOD(
                [],
                HRESULT,
                "GetNextPacketSize",
                (["out"], POINTER(c_uint32), "pNumFramesInNextPacket"),
            ),
        )


def _rms_to_level(rms: float) -> float:
    if rms <= 1e-7:
        return 0.0
    db = 20.0 * math.log10(rms)
    return max(0.0, min(1.0, (db - FLOOR_DB) / (CEILING_DB - FLOOR_DB)))


class LoopbackMeter(threading.Thread):
    """Captures the render stream and publishes a smoothed RMS level."""

    def __init__(self, name_hints=None) -> None:
        super().__init__(name="level-meter", daemon=True)
        self._name_hints = name_hints
        self._stop = threading.Event()
        self._level = 0.0
        self._opened = False
        self.failed = not AVAILABLE

    @property
    def level(self) -> float:
        return self._level

    def stop(self) -> None:
        self._stop.set()

    # -- capture ----------------------------------------------------------

    def _open(self):
        device, _name = (
            find_endpoint(self._name_hints) if self._name_hints else find_endpoint()
        )
        if device is None:
            raise RuntimeError("no matching render endpoint")

        client = device.Activate(IAudioClient._iid_, comtypes.CLSCTX_ALL, None).QueryInterface(
            IAudioClient
        )
        mix_format = client.GetMixFormat()
        client.Initialize(
            AUDCLNT_SHAREMODE_SHARED,
            AUDCLNT_STREAMFLAGS_LOOPBACK,
            REFTIMES_PER_SEC // 2,
            0,
            mix_format,
            None,
        )
        capture = client.GetService(IAudioCaptureClient._iid_).QueryInterface(
            IAudioCaptureClient
        )
        client.Start()
        return client, capture, mix_format.contents

    @staticmethod
    def _sum_squares(data: bytes, fmt: WAVEFORMATEX, frames: int):
        """Return (sum of squares, count) over one channel, sampled sparsely."""
        channels = max(1, fmt.nChannels)
        bits = fmt.wBitsPerSample

        if bits == 32:
            # The shared-mode mix format is float32 in practice.
            samples = array("f")
            samples.frombytes(data[: frames * channels * 4])
            scale = 1.0
        elif bits == 16:
            samples = array("h")
            samples.frombytes(data[: frames * channels * 2])
            scale = 1.0 / 32768.0
        else:
            return 0.0, 0

        total = 0.0
        count = 0
        step = channels * SAMPLE_STRIDE
        for index in range(0, len(samples), step):
            value = samples[index] * scale
            total += value * value
            count += 1
        return total, count

    def run(self) -> None:  # pragma: no cover - thread body
        if not AVAILABLE:
            return
        try:
            comtypes.CoInitialize()
            client, capture, fmt = self._open()
            self._opened = True
        except Exception:
            self.failed = True
            return

        rate = fmt.nSamplesPerSec or 48000
        block_frames = max(1, int(rate * BLOCK_SECONDS))
        total = 0.0
        count = 0
        frames_seen = 0

        try:
            while not self._stop.is_set():
                packet = capture.GetNextPacketSize()
                if not packet:
                    self._stop.wait(POLL_SECONDS)
                    continue

                while packet and not self._stop.is_set():
                    data_ptr, frames, flags, _pos, _qpc = capture.GetBuffer()
                    try:
                        if frames:
                            # AUDCLNT_BUFFERFLAGS_SILENT
                            if flags & 0x2:
                                count += frames // SAMPLE_STRIDE
                            else:
                                raw = ctypes.string_at(
                                    data_ptr, frames * fmt.nBlockAlign
                                )
                                block_total, block_count = self._sum_squares(raw, fmt, frames)
                                total += block_total
                                count += block_count
                            frames_seen += frames
                    finally:
                        capture.ReleaseBuffer(frames)

                    if frames_seen >= block_frames:
                        rms = math.sqrt(total / count) if count else 0.0
                        target = _rms_to_level(rms)
                        # Rise quickly, fall gently -- a meter, not a strobe.
                        coefficient = 0.6 if target > self._level else 0.18
                        self._level += (target - self._level) * coefficient
                        total, count, frames_seen = 0.0, 0, 0

                    packet = capture.GetNextPacketSize()
        except Exception:
            self.failed = True
        finally:
            try:
                client.Stop()
            except Exception:
                pass
