# Cricket Tray

A tiny macOS menu bar app that shows cricket scores.

- Menu bar shows 🏏 plus the number of live matches, or the score of a match you pin.
- Menu lists **Live**, **Results** and **Upcoming** matches; each has a submenu to pin it or open it on ESPNcricinfo.
- "International only" hides domestic/A-team games.
- Refreshes every 15 seconds (⌘R to refresh now).

Scores come from ESPN's public (unofficial, undocumented) scoreboard feed — no API key needed, but it could change without notice.

## Install

```sh
./build.sh
```

This builds `dist/Cricket Tray.app` and `dist/CricketTray-1.0.0.dmg`. Open the DMG and drag
**Cricket Tray** into **Applications**. It runs in the menu bar only (no Dock icon).

The app is ad-hoc signed, not notarized. On another Mac, macOS will block the first launch:
right-click the app → **Open**, or allow it under System Settings → Privacy & Security.

To start it at login: System Settings → General → Login Items → add Cricket Tray.

## Run from source

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

To just print current scores in the terminal: `python scores.py`.
