# moondrop-dawn-pro-gui

Control the **volume**, **gain**, **reconstruction filter** and **LED** of a
MOONDROP Dawn Pro from Windows — with a native desktop app, a CLI, and a Python
API. No kernel driver, no Zadig, no driver replacement.

The Dawn Pro is USB Audio Class compliant, so Windows already handles the audio.
Everything the vendor app exposes lives behind an undocumented vendor protocol on
the device's HID interface — this project speaks it, and the protocol is
[documented below](#protocol-notes) so you do not have to rediscover it.

Built and verified against real hardware (USB `2FC6:F06A`).

## Download

**[⬇ Get the latest release](https://github.com/RetR0-hex/moondrop-dawn-pro-gui/releases/latest)**

| File | What it is |
|------|------------|
| `MoondropDawnPro-GUI.exe` | The GUI. Double-click and go. |
| `MoondropDawnPro-CLI.exe` | The command line tool. |

Both are single-file executables: **no Python, no dependencies, no installer.**
Windows 10 or later, 64-bit.

## Screenshots

| Control | Device info |
|---------|-------------|
| ![Control page](docs/screenshot-control.png) | ![Device info page](docs/screenshot-info.png) |

The control page reads what Windows is currently sending to the DAC — track,
artist, album art, live output level and the negotiated stream format. The
device info page reports everything factual about the attached hardware,
labelled by where each fact came from.

## Features

- **Volume** — 61 steps, percentages, relative nudges, or a raw attenuation code.
- **Gain** — low / high.
- **Filter** — all five reconstruction filters.
- **LED** — on / temporarily off / off.
- **Reads back every write**, so a successful command means the device really
  applied it.
- **Now playing + level meter + stream format**, read from Windows itself.
- **No driver installation.** Nothing is replaced, nothing is unsigned.

## Install

```powershell
pip install -r requirements.txt
```

The driver and CLI need only `hidapi`. The GUI adds `PySide6` (the interface),
`winsdk` (the Windows now-playing session) and `pycaw`/`comtypes` (audio endpoint
format and level meter). Installing the package itself, `pip install .`, takes
just the driver; `pip install .[gui]` takes the GUI extras too.

Or install the package itself, which also puts a `moondrop` command on PATH:

```powershell
pip install .
```

## Standalone executables

Prebuilt executables are attached to every
[release](https://github.com/RetR0-hex/moondrop-dawn-pro-gui/releases/latest) and need **no Python and no dependencies** on
the target machine. `build.py` reproduces them locally into `dist/`:

* `dist\MoondropDawnPro-GUI.exe` — the GUI, opens with no console window. It
  carries Qt, so it is the larger of the two.
* `dist\MoondropDawnPro-CLI.exe` — the command line tool
  (`MoondropDawnPro-CLI.exe status`, `… gain high`, …). Qt is excluded from this
  one, so it stays small. Rename it to `moondrop.exe` if you want shorter
  commands — the examples below assume you have.

Double-click `MoondropDawnPro.exe` and it just runs. Both are portable — copy
them anywhere, or pin `MoondropDawnPro.exe` to the taskbar.

To rebuild them after a code change:

```powershell
pip install pyinstaller
python build.py
```

`build.py` drives PyInstaller for both targets, bundles the QML at the path the
package expects, cleans up its scratch directory and prints the resulting
sizes.

## GUI

```powershell
python -m moondrop gui
```

A native desktop app: PySide6 + QML, no web runtime and no Electron. Two pages,
switched from the tabs under the title bar.

**Control** — volume slider, gain and filter and LED as segmented pills, plus a
now-playing panel showing what Windows is currently sending to the DAC: track,
artist, source app, album art, and a live output level meter. A row of chips
reports the negotiated stream format (sample rate, bit depth, channels). All of
it updates on its own; changes made from the device buttons or another app show
up within a couple of seconds.

**Device info** — a vector diagram of the Dawn Pro (drawn, not photographed, so
it scales cleanly and carries no licensing baggage; its status LED mirrors the
real one), followed by everything factual about the attached device, grouped by
where the fact came from:

* *Device* — USB ids, strings and release, read from the device.
* *Control channel* — HID interface, usage page, report sizes and the raw report
  descriptor bytes.
* *Windows audio* — the endpoint, its current format, the PCM formats it accepts
  in exclusive mode (probed one by one, not claimed), and which driver Windows
  has bound to each USB interface.
* *Published specifications* — MOONDROP's own figures, labelled as not measured.

The window is frameless and drag-moves from anywhere in the header.

## Command line

```powershell
python -m moondrop status            # everything at once
python -m moondrop status --raw      # ... plus the raw reply bytes

python -m moondrop volume            # -> 45/60 (75%, code 0x1e)
python -m moondrop volume 45         # 0-60 steps
python -m moondrop volume 75%        # or a percentage
python -m moondrop volume +5         # relative, clamped to 0-60
python -m moondrop volume -5
python -m moondrop volume --code 0x20   # raw attenuation code

python -m moondrop gain              # -> low | high
python -m moondrop gain high

python -m moondrop filter            # -> current filter name
python -m moondrop filter slow-phase-compensated
python -m moondrop filter 2          # index also works
python -m moondrop filter nos        # so do the aliases

python -m moondrop led off           # on | temporarily-off | off

python -m moondrop filters           # list the filter names
python -m moondrop list              # show the detected HID interface
python -m moondrop gui               # open the control panel
```

Every write is read back from the device before the command returns, so a
successful exit really means the setting was applied. Example:

```
> python -m moondrop status
volume  : 60/60 (100%, code 0x00)
gain    : high (1)
filter  : Fast Roll-Off, Phase Compensated [fast-phase-compensated] (1)
led     : off (2)
```

### Filters

| # | Name | Meaning |
|---|------|---------|
| 0 | `fast-low-latency` | Fast Roll-Off, Low Latency |
| 1 | `fast-phase-compensated` | Fast Roll-Off, Phase Compensated |
| 2 | `slow-low-latency` | Slow Roll-Off, Low Latency |
| 3 | `slow-phase-compensated` | Slow Roll-Off, Phase Compensated |
| 4 | `non-oversampling` | Non-Oversampling |

Aliases: `fast` = 0, `fast-phase` = 1, `slow` = 2, `slow-phase` = 3, `nos` = 4.

### Volume

The device carries 61 volume steps (0 quietest, 60 loudest), the same scale the
vendor app shows. Underneath, the device takes an **attenuation code**: `0x00`
is full output and larger values are quieter, which is why the step→code table
in `protocol.py` runs downwards. The steps are coarse at the bottom and settle
into single-code increments near the top.

`--code` writes an arbitrary code, which the device accepts even when it is not
on the 61-step curve — useful for finer adjustment than the steps allow. Codes
read back off the curve are rounded to the nearest step for display.

Two things worth knowing:

* **This is not the Windows volume.** The device's attenuator and the Windows
  endpoint volume are independent stages in series — verified by moving each and
  reading the other: taking Windows from 5% to 70% left the device code at
  `0x00`, and moving the device from step 30 to 45 left Windows at 5%. Your
  actual output level is the product of the two, so a quiet result can mean
  either one is turned down.
* **Mind your ears.** `0x00` / step 60 is full output on the device's own stage.
  The driver refuses nothing, so a jump from step 10 to step 60 happens
  immediately.

### Gain

`low` (0) or `high` (1). After a gain change the driver issues the device's
volume-refresh command, matching what the vendor tool does, so the current
volume is re-latched against the new output scaling.

## Python API

```python
from moondrop import DawnPro

with DawnPro() as dac:
    status = dac.get_status()
    print(status.gain_name, status.filter_label, status.led_name)

    print(status.volume, "of", 60)      # volume step

    dac.set_volume(45)                  # 0-60 step
    dac.set_volume("75%")
    dac.adjust_volume(-5)               # relative, clamped
    dac.set_volume_raw(0x20)            # raw attenuation code
    dac.set_gain("low")
    dac.set_filter(4)                 # non-oversampling
    dac.set_led("temporarily-off")
```

The GUI in `moondrop/gui.py` is a thin layer over exactly this API.

`set_*` returns the re-read `Status` and raises `ProtocolError` if the device
did not apply the value. `DeviceNotFound` is raised when no Dawn Pro is
attached; `ValueError` on an unknown gain/filter/LED name.

## Protocol notes

Recorded here because the device is undocumented and these details were
established by probing the hardware directly.

The Dawn Pro exposes one HID interface (`MI_02`, consumer-control usage page)
whose report descriptor declares, in a single **unnumbered** top-level
collection:

* an **Output** report of 7 bytes — the host's command;
* an **Input** report of 1 byte (media-key bitmap) + 7 bytes — the device's reply.

Because there are no report IDs, on Windows the buffers carry a leading `0x00`:
writes are 8 bytes, reads are 9.

Commands begin with the magic `C0 A5`; replies echo it back as `A0 A5` followed
by the command byte.

| Command | Bytes | Effect |
|---------|-------|--------|
| Set filter | `C0 A5 01 <0-4>` | reconstruction filter |
| Set gain | `C0 A5 02 <0-1>` | 0 = low, 1 = high |
| Set volume | `C0 A5 04 <code>` | attenuation code, `0x00` loudest |
| Set LED | `C0 A5 06 <0-2>` | 0 = on, 1 = temporarily off, 2 = off |
| Refresh volume | `C0 A5 A2` | re-latch the volume curve |
| Get status | `C0 A5 A3` | returns the settings |

A `C0 A5 A3` request produces this 9-byte read buffer:

```
index : 0    1    2    3    4       5     6    7    8
value : 00   A0   A5   A3   filter  gain  led  --   --
```

Volume lives behind a separate command. `C0 A5 A2` replies with:

```
index : 0    1    2    3    4    5     6    7    8
value : 00   A0   A5   A2   00   code  00   --   --
```

so the same offset means *gain* in one reply and *volume* in the other — read
the command byte at index 3 before trusting index 5.

**Reply timing:** there is no reply queue; index 0-8 is a single latest-reply
buffer that repeats until the next command lands. But the device can lag a beat
after a write, so a read issued immediately afterwards returns the *previous*
command's reply. `_query()` therefore re-reads and re-asks until the reply's
command byte matches the request. Writes do get their own acknowledgement — a
`set volume` is answered with `00 A5 04 <code>`, note the `00 A5` header rather
than the `A0 A5` of a read reply.

**Windows read quirk:** this interface never delivers its input report through
`ReadFile`, so `hid.read()` always times out. The reply has to be pulled with a
HID `GET_REPORT` (`HidD_GetInputReport`) using the interface's *exact* input
report length of 9 bytes — anything shorter fails. `device.py` does this, and
on non-Windows platforms falls back to reading the interrupt endpoint — an
untested path, and one that may well not work: the input report is marked
Constant in the descriptor, which is likely why `ReadFile` fails on Windows in
the first place. On Linux, prefer the libusb control-transfer route used by
DawnPro-GUI.

Writes are silent: the device acknowledges nothing, which is why this driver
always reads back after a write.

## Contributing

Issues and pull requests are welcome — especially reports from other Dawn Pro
units, other Windows versions, or the Dawn Pro 2 (which speaks a different,
PEQ-capable protocol this project does not implement).

If you extend the protocol, please keep the "read it back and verify" habit: the
device accepts writes silently, so verification is the only way to know a command
landed.

## Licence

MIT — see [LICENSE](LICENSE). Not affiliated with or endorsed by MOONDROP.

## Credits

The device illustration is vector art drawn from MOONDROP's product photography;
no copyrighted image is redistributed here.

Command bytes and value mappings cross-checked against
[shaypower/DawnPro-GUI](https://github.com/shaypower/DawnPro-GUI), which drives
the same device over libusb control transfers (that route needs Zadig on
Windows). The HID transport and the Windows `GET_REPORT` workaround here were
derived from the device's own report descriptor and confirmed on hardware.
