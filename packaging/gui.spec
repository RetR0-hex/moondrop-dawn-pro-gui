# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the GUI.

``--exclude-module`` only drops Python bindings; PyInstaller's PySide6 hook
still copies the matching Qt DLLs and QML modules, and Qt6WebEngineCore.dll
alone is 195 MB. So the collected file lists are filtered here instead, which is
the difference between a ~185 MB binary and a ~45 MB one.
"""

from pathlib import Path

ROOT = Path(SPECPATH).parent

# Qt libraries this app never loads. It uses QtCore/Gui/Qml/Quick/QuickControls2
# plus the Shapes and Effects QML modules -- nothing else.
DROP_BINARIES = (
    "Qt6WebEngine", "Qt6Quick3D", "Qt6Pdf", "Qt6Designer", "Qt6Charts",
    "Qt63D", "Qt6DataVisualization", "Qt6Graphs", "Qt6Multimedia",
    "Qt6SpatialAudio", "Qt6Sensors", "Qt6Bluetooth", "Qt6Nfc", "Qt6Sql",
    "Qt6Test", "Qt6Location", "Qt6Positioning", "Qt6RemoteObjects",
    "Qt6Scxml", "Qt6StateMachine", "Qt6SerialPort", "Qt6SerialBus",
    "Qt6TextToSpeech", "Qt6WebSockets", "Qt6WebChannel", "Qt6WebView",
    "Qt6Help", "Qt6UiTools", "Qt6Quick3DRuntimeRender", "Qt6ShaderTools",
    "Qt6Concurrent", "Qt6NetworkAuth",
    # The bundled FFmpeg set exists only for QtMultimedia.
    "avcodec", "avformat", "avutil", "swscale", "swresample",
    # Software OpenGL fallback; Qt Quick renders through Direct3D 11 here.
    "opengl32sw",
)

# QML modules and resource blobs belonging to the same removed features.
DROP_DATA_PARTS = (
    "QtWebEngine", "QtQuick3D", "QtMultimedia", "QtCharts", "QtDataVisualization",
    "QtGraphs", "QtSensors", "QtPositioning", "QtLocation", "QtTextToSpeech",
    "QtWebSockets", "QtWebView", "QtRemoteObjects", "QtScxml", "QtBluetooth",
    "QtNfc", "Qt3D", "qtwebengine",
)


def _keep(entry, needles):
    path = str(entry[0]).replace("\\", "/")
    name = path.rsplit("/", 1)[-1]
    return not (name.startswith(needles) or any(n in path for n in needles))


datas = [(str(ROOT / "moondrop" / "ui" / "qml"), "moondrop/ui/qml")]
assets = ROOT / "moondrop" / "ui" / "assets"
if assets.is_dir() and any(assets.iterdir()):
    datas.append((str(assets), "moondrop/ui/assets"))

a = Analysis(
    [str(ROOT / "packaging" / "gui_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["hid", "comtypes", "winsdk"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PIL", "tkinter", "PySide6.QtWebEngineCore", "PySide6.QtMultimedia"],
    noarchive=False,
)

a.binaries = [b for b in a.binaries if _keep(b, DROP_BINARIES)]
a.datas = [d for d in a.datas if _keep(d, DROP_DATA_PARTS)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MoondropDawnPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
