"""Launches the Qt/QML control panel."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from .bridge import Controller

QML_DIR = Path(__file__).parent / "qml"


def main(argv=None) -> int:
    app = QGuiApplication(list(sys.argv if argv is None else argv))
    app.setApplicationName("Dawn Pro")
    app.setOrganizationName("moondrop-driver")

    controller = Controller()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))

    if not engine.rootObjects():
        print("failed to load the QML interface", file=sys.stderr)
        return 1

    app.aboutToQuit.connect(controller.shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
