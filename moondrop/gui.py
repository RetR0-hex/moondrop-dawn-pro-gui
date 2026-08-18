"""Entry point for the graphical control panel.

The UI itself lives in :mod:`moondrop.ui` (PySide6 + QML); this module stays as
the stable import path used by ``python -m moondrop gui`` and the packaged
executable.
"""

from __future__ import annotations


def main(argv=None) -> int:
    from .ui.app import main as qt_main

    return qt_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
