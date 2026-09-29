"""py2app build config. Use ./build.sh rather than running this directly."""

from setuptools import setup

setup(
    app=["app.py"],
    name="Stumpbar",
    options={
        "py2app": {
            "iconfile": "assets/Stumpbar.icns",
            "resources": ["LICENSE", "THIRD_PARTY_NOTICES.md"],
            "packages": ["rumps", "requests", "certifi", "UserNotifications"],
            "plist": {
                "CFBundleName": "Stumpbar",
                "CFBundleDisplayName": "Stumpbar",
                "CFBundleIdentifier": "com.calmac.stumpbar",
                "CFBundleShortVersionString": "1.0.0",
                "CFBundleVersion": "1.0.0",
                "LSUIElement": True,  # menu bar only: no Dock icon
                "LSMinimumSystemVersion": "11.0",
            },
        }
    },
)
