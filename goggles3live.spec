# PyInstaller spec for SkyFeed Studio. Build with build_mac_app.command (or build_windows_app.bat).
import os
import sys
from PyInstaller.utils.hooks import collect_all

APP = "SkyFeed Studio"
VERSION = "0.4.0"
datas = [("assets/icon.png", "assets")]
binaries = []
hiddenimports = ["usb.backend.libusb1", "g3.helper", "g3.app", "segno", "certifi"]
for pkg in ("libusb_package", "certifi"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
if sys.platform == "darwin":
    hiddenimports += ["keyring.backends.macOS"]
elif sys.platform.startswith("win"):
    hiddenimports += ["keyring.backends.Windows"]
for lib in ("/opt/homebrew/lib/libusb-1.0.0.dylib", "/usr/local/lib/libusb-1.0.0.dylib"):
    if os.path.exists(lib):             # fallback copy next to the app's own libraries
        binaries.append((lib, "."))
        break

a = Analysis(
    ["app_main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtSql", "PySide6.QtTest",
              "PySide6.QtXml", "PySide6.QtConcurrent", "PySide6.QtDBus", "PySide6.QtOpenGL",
              "PySide6.QtOpenGLWidgets", "PySide6.QtPrintSupport", "PySide6.QtSvg", "PIL", "matplotlib", "gi"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SkyFeedStudio", console=False,
          argv_emulation=False, icon="assets/icon.png")
coll = COLLECT(exe, a.binaries, a.datas, name="SkyFeedStudio")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=APP + ".app",
        icon="assets/icon.png",
        bundle_identifier="io.github.skyfeedstudio",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": APP,
            "CFBundleShortVersionString": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "14.0",
            "NSLocalNetworkUsageDescription": "Lets phones and other computers on your network watch the live view.",
            "NSHumanReadableCopyright": "Not affiliated with DJI.",
        },
    )
