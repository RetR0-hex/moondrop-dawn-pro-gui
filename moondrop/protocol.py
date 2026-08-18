"""Wire protocol for MOONDROP Dawn Pro (USB 2FC6:F06A).

The Dawn Pro is a USB Audio Class device -- audio itself needs no driver. Its
gain/filter/LED settings live behind a vendor channel exposed on the device's
HID interface (MI_02), which also carries the consumer media keys.

The HID report descriptor declares, in a single unnumbered top-level collection:

    Output: 7 bytes   (host -> device command)
    Input : 1 byte media-key bitmap + 7 bytes payload  (device -> host reply)

so on Windows a written buffer is ``[0x00 report-id] + 7 command bytes`` (8) and
a read buffer is ``[0x00 report-id] + 8 payload bytes`` (9).

Every command starts with the magic ``C0 A5``. Replies echo it as ``A0 A5``
followed by the command byte, then the payload.
"""

VENDOR_ID = 0x2FC6
PRODUCT_ID = 0xF06A

MAGIC_REQUEST = (0xC0, 0xA5)
MAGIC_REPLY = (0xA0, 0xA5)

# Command bytes (third byte of a request).
CMD_SET_FILTER = 0x01
CMD_SET_GAIN = 0x02
CMD_SET_VOLUME = 0x04
CMD_SET_LED = 0x06
CMD_GET_STATUS = 0xA3
CMD_REFRESH_VOLUME = 0xA2

OUTPUT_REPORT_SIZE = 8   # report id + 7 payload bytes
INPUT_REPORT_SIZE = 9    # report id + 8 payload bytes

# Offsets into the 9-byte buffer returned by a CMD_GET_STATUS read.
OFF_MAGIC_HI = 1
OFF_MAGIC_LO = 2
OFF_COMMAND = 3
OFF_FILTER = 4
OFF_GAIN = 5
OFF_LED = 6

# Offset into the buffer returned by a CMD_REFRESH_VOLUME read. Note that the
# two replies have different layouts: this byte is the gain in a status reply.
OFF_VOLUME = 5

GAIN_BY_VALUE = {0: "low", 1: "high"}
GAIN_BY_NAME = {name: value for value, name in GAIN_BY_VALUE.items()}

FILTER_BY_VALUE = {
    0: "fast-low-latency",
    1: "fast-phase-compensated",
    2: "slow-low-latency",
    3: "slow-phase-compensated",
    4: "non-oversampling",
}
FILTER_BY_NAME = {name: value for value, name in FILTER_BY_VALUE.items()}

FILTER_LABELS = {
    0: "Fast Roll-Off, Low Latency",
    1: "Fast Roll-Off, Phase Compensated",
    2: "Slow Roll-Off, Low Latency",
    3: "Slow Roll-Off, Phase Compensated",
    4: "Non-Oversampling",
}

# Short aliases accepted on the command line.
FILTER_ALIASES = {
    "fast": 0,
    "fast-low": 0,
    "fast-phase": 1,
    "slow": 2,
    "slow-low": 2,
    "slow-phase": 3,
    "nos": 4,
    "non-oversampling": 4,
}

LED_BY_VALUE = {0: "on", 1: "temporarily-off", 2: "off"}
LED_BY_NAME = {name: value for value, name in LED_BY_VALUE.items()}
LED_ALIASES = {"temp-off": 1, "temp": 1}


def build_command(command: int, *args: int) -> bytes:
    """Build one 7-byte output report payload (without the HID report id)."""
    body = [*MAGIC_REQUEST, command, *args]
    if len(body) > 7:
        raise ValueError(f"command {command:#04x} payload too long: {body}")
    return bytes(body + [0] * (7 - len(body)))


def parse_gain(value: str) -> int:
    key = value.strip().lower()
    if key in GAIN_BY_NAME:
        return GAIN_BY_NAME[key]
    if key.isdigit() and int(key) in GAIN_BY_VALUE:
        return int(key)
    raise ValueError(f"unknown gain {value!r}; expected one of: {', '.join(GAIN_BY_NAME)}")


def parse_filter(value: str) -> int:
    key = value.strip().lower()
    if key in FILTER_BY_NAME:
        return FILTER_BY_NAME[key]
    if key in FILTER_ALIASES:
        return FILTER_ALIASES[key]
    if key.isdigit() and int(key) in FILTER_BY_VALUE:
        return int(key)
    raise ValueError(
        f"unknown filter {value!r}; expected 0-4 or one of: {', '.join(FILTER_BY_NAME)}"
    )


def parse_led(value: str) -> int:
    key = value.strip().lower()
    if key in LED_BY_NAME:
        return LED_BY_NAME[key]
    if key in LED_ALIASES:
        return LED_ALIASES[key]
    if key.isdigit() and int(key) in LED_BY_VALUE:
        return int(key)
    raise ValueError(f"unknown LED mode {value!r}; expected one of: {', '.join(LED_BY_NAME)}")


# The vendor app exposes 61 volume steps. Step 0 is quietest, step 60 loudest;
# the byte written to the device is an attenuation code where 0x00 is full
# output and larger values are quieter, so the table runs downwards. Steps are
# coarse at the bottom and settle to 1-code increments near the top.
VOLUME_TABLE = (
    0xFF, 0xC8, 0xB4, 0xAA, 0xA0, 0x96, 0x8C, 0x82, 0x7A, 0x74,
    0x6E, 0x6A, 0x66, 0x62, 0x5E, 0x5A, 0x58, 0x56, 0x54, 0x52,
    0x50, 0x4E, 0x4C, 0x4A, 0x48, 0x46, 0x44, 0x42, 0x40, 0x3E,
    0x3C, 0x3A, 0x38, 0x36, 0x34, 0x32, 0x30, 0x2E, 0x2C, 0x2A,
    0x28, 0x26, 0x24, 0x22, 0x20, 0x1E, 0x1C, 0x1A, 0x18, 0x16,
    0x14, 0x12, 0x10, 0x0E, 0x0C, 0x0A, 0x08, 0x06, 0x04, 0x02,
    0x00,
)

VOLUME_MIN_STEP = 0
VOLUME_MAX_STEP = len(VOLUME_TABLE) - 1  # 60


def step_to_raw(step: int) -> int:
    """Map a 0-60 volume step to the device's attenuation code."""
    if not VOLUME_MIN_STEP <= step <= VOLUME_MAX_STEP:
        raise ValueError(f"volume step must be {VOLUME_MIN_STEP}-{VOLUME_MAX_STEP}, got {step}")
    return VOLUME_TABLE[step]


def raw_to_step(raw: int) -> int:
    """Map an attenuation code back to the nearest 0-60 volume step.

    The device accepts codes that are not in the table (the front-panel buttons
    and other tools can leave one set), so this rounds rather than failing.
    """
    return min(range(len(VOLUME_TABLE)), key=lambda i: abs(VOLUME_TABLE[i] - raw))


def parse_volume(value: str) -> int:
    """Parse a 0-60 step, or a percentage written like ``75%``."""
    text = value.strip().lower()
    if text.endswith("%"):
        percent = float(text[:-1])
        if not 0.0 <= percent <= 100.0:
            raise ValueError(f"volume percentage must be 0-100, got {text}")
        return round(percent / 100.0 * VOLUME_MAX_STEP)
    try:
        step = int(text, 0)
    except ValueError:
        raise ValueError(f"unknown volume {value!r}; expected 0-{VOLUME_MAX_STEP} or a percentage") from None
    if not VOLUME_MIN_STEP <= step <= VOLUME_MAX_STEP:
        raise ValueError(f"volume step must be {VOLUME_MIN_STEP}-{VOLUME_MAX_STEP}, got {step}")
    return step
