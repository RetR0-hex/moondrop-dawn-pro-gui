#!/usr/bin/env python
"""Build standalone Windows executables with PyInstaller.

    python build.py

Produces two single-file executables in ``dist/``:

    MoondropDawnPro.exe   the GUI, no console window
    moondrop.exe          the command line tool

Neither needs Python or hidapi installed on the target machine.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()

COMMON = [
    "--onefile",
    "--noconfirm",
    "--clean",
    "--paths", str(ROOT),
    "--hidden-import", "hid",
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(ROOT / "build"),
    "--specpath", str(ROOT / "build"),
]

# The CLI never touches Qt or the audio/media extras. It reaches them only
# through the lazy `from .gui import main` inside cli.main(), which PyInstaller
# follows anyway, so they have to be excluded explicitly.
CLI_EXTRA = [
    "--console",
    "--icon", str(ROOT / "packaging" / "icon.ico"),
    "--exclude-module", "PySide6",
    "--exclude-module", "shiboken6",
    "--exclude-module", "winsdk",
    "--exclude-module", "pycaw",
    "--exclude-module", "comtypes",
    "--exclude-module", "PIL",
]

TARGETS = [
    # The GUI is built from a spec so the Qt collection can be filtered; see
    # packaging/gui.spec for why that is necessary.
    ("MoondropDawnPro", ROOT / "packaging" / "gui.spec", []),
    ("moondrop", ROOT / "packaging" / "cli_entry.py", CLI_EXTRA),
]


def main() -> int:
    for name, entry, extra in TARGETS:
        if entry.suffix == ".spec":
            # A spec carries its own name, entry point and options.
            cmd = [
                sys.executable, "-m", "PyInstaller",
                "--noconfirm", "--clean",
                "--distpath", str(ROOT / "dist"),
                "--workpath", str(ROOT / "build"),
                str(entry),
            ]
        else:
            cmd = [sys.executable, "-m", "PyInstaller", "--name", name, *COMMON, *extra, str(entry)]
        print(f"\n=== building {name}.exe ===")
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            print(f"build of {name}.exe failed", file=sys.stderr)
            return result.returncode

    shutil.rmtree(ROOT / "build", ignore_errors=True)
    print("\nBuilt:")
    for exe in sorted((ROOT / "dist").glob("*.exe")):
        print(f"  {exe}  ({exe.stat().st_size / 1_048_576:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
