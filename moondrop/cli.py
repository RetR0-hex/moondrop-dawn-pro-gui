"""Command line front end: ``python -m moondrop ...``"""

from __future__ import annotations

import argparse
import sys

from . import protocol as p
from .device import DawnPro, DeviceNotFound, ProtocolError, Status, list_devices


def _format_volume(step: int, raw_code: int) -> str:
    percent = round(step / p.VOLUME_MAX_STEP * 100)
    return f"{step}/{p.VOLUME_MAX_STEP} ({percent}%, code {raw_code:#04x})"


def _print_status(status: Status, raw: bool = False) -> None:
    if status.volume_raw is not None:
        print(f"volume  : {_format_volume(status.volume, status.volume_raw)}")
    print(f"gain    : {status.gain_name} ({status.gain})")
    print(f"filter  : {status.filter_label} [{status.filter_name}] ({status.filter})")
    print(f"led     : {status.led_name} ({status.led})")
    if raw:
        print("raw     : " + " ".join(f"{b:02X}" for b in status.raw))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="moondrop",
        description="Control the gain, filter and LED of a MOONDROP Dawn Pro.",
    )
    parser.add_argument("--raw", action="store_true", help="also print the raw reply bytes")

    # Repeated on the subcommands so ``moondrop status --raw`` works too.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--raw", action="store_true", help="also print the raw reply bytes")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", parents=[common], help="show the current settings (default)")
    sub.add_parser("list", help="list detected Dawn Pro HID interfaces")

    gain = sub.add_parser("gain", parents=[common], help="show or set the gain")
    gain.add_argument("value", nargs="?", choices=sorted(p.GAIN_BY_NAME), help="low or high")

    filt = sub.add_parser("filter", parents=[common], help="show or set the reconstruction filter")
    filt.add_argument(
        "value",
        nargs="?",
        help="0-4, a name (" + ", ".join(p.FILTER_BY_NAME) + ") or an alias (fast, slow, nos)",
    )

    led = sub.add_parser("led", parents=[common], help="show or set the LED mode")
    led.add_argument("value", nargs="?", help="on, temporarily-off or off")

    vol = sub.add_parser("volume", parents=[common], help="show or set the volume")
    vol.add_argument(
        "value",
        nargs="?",
        help=f"0-{p.VOLUME_MAX_STEP}, a percentage (75%%), or a relative step (+5, -5)",
    )
    vol.add_argument(
        "--code",
        type=lambda v: int(v, 0),
        help="write a raw attenuation code instead (0x00 loudest, 0xFF quietest)",
    )

    sub.add_parser("filters", help="list the available filters")
    sub.add_parser("gui", help="open the graphical control panel")
    return parser


def _volume(dac: DawnPro, args) -> int:
    if args.code is not None:
        raw_code = dac.set_volume_raw(args.code)
        print(_format_volume(p.raw_to_step(raw_code), raw_code))
        return 0

    value = args.value
    if value is None:
        pass
    elif value[0] in "+-":
        dac.adjust_volume(int(value))
    else:
        dac.set_volume(value)

    raw_code = dac.get_volume_raw()
    print(_format_volume(p.raw_to_step(raw_code), raw_code))
    return 0


def main(argv=None) -> int:
    parser = _build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    # ``volume -5`` reads as an option to argparse; keep the natural spelling.
    if "volume" in argv:
        index = argv.index("volume") + 1
        if index < len(argv) and argv[index][:1] == "-" and argv[index][1:].isdigit():
            argv.insert(index, "--")
    args = parser.parse_args(argv)
    command = args.command or "status"

    if command == "gui":
        from .gui import main as gui_main

        return gui_main()

    if command == "filters":
        for value, name in sorted(p.FILTER_BY_VALUE.items()):
            print(f"{value}  {name:<24} {p.FILTER_LABELS[value]}")
        return 0

    if command == "list":
        devices = list_devices()
        if not devices:
            print("no Dawn Pro found", file=sys.stderr)
            return 1
        for d in devices:
            print(
                f"interface {d.get('interface_number')}  usage_page={d['usage_page']:#06x}  "
                f"{d.get('manufacturer_string')} {d.get('product_string')}"
            )
            print(f"  path: {d['path'].decode(errors='replace')}")
        return 0

    try:
        with DawnPro() as dac:
            if command == "volume":
                return _volume(dac, args)

            if command == "status":
                _print_status(dac.get_status(), args.raw)
                return 0

            value = getattr(args, "value", None)
            if value is None:
                status = dac.get_status(with_volume=False)
                print({"gain": status.gain_name, "filter": status.filter_name, "led": status.led_name}[command])
                return 0

            setter = {"gain": dac.set_gain, "filter": dac.set_filter, "led": dac.set_led}[command]
            setter(value)
            _print_status(dac.get_status(), args.raw)
            return 0
    except (DeviceNotFound, ProtocolError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
