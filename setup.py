"""py2app build config. Use ./build.sh rather than running this directly."""

from setuptools import setup

setup(
    app=["app.py"],
    name="Cricket Tray",
    options={
        "py2app": {
            "iconfile": "assets/CricketTray.icns",
            "packages": ["rumps", "requests", "certifi"],
            "plist": {
                "CFBundleName": "Cricket Tray",
                "CFBundleDisplayName": "Cricket Tray",
                "CFBundleIdentifier": "com.calmac.cricket-tray",
                "CFBundleShortVersionString": "1.0.0",
                "CFBundleVersion": "1.0.0",
                "LSUIElement": True,  # menu bar only: no Dock icon
                "LSMinimumSystemVersion": "11.0",
            },
        }
    },
)
