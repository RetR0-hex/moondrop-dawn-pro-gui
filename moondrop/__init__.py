"""Userspace driver for the MOONDROP Dawn Pro USB DAC/amp."""

from .device import DawnPro, DeviceNotFound, ProtocolError, Status, list_devices
from .protocol import (
    FILTER_BY_NAME,
    FILTER_BY_VALUE,
    FILTER_LABELS,
    GAIN_BY_NAME,
    GAIN_BY_VALUE,
    LED_BY_VALUE,
    PRODUCT_ID,
    VENDOR_ID,
)

__version__ = "1.0.0"

__all__ = [
    "DawnPro",
    "DeviceNotFound",
    "ProtocolError",
    "Status",
    "list_devices",
    "FILTER_BY_NAME",
    "FILTER_BY_VALUE",
    "FILTER_LABELS",
    "GAIN_BY_NAME",
    "GAIN_BY_VALUE",
    "LED_BY_VALUE",
    "VENDOR_ID",
    "PRODUCT_ID",
    "__version__",
]
