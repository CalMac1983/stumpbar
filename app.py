"""Stumpbar: a macOS menu bar app showing live cricket scores."""

import webbrowser

import rumps

from scores import fetch_matches

REFRESH_SECONDS = 15
SECTIONS = [("in", "Live"), ("post", "Results"), ("pre", "Upcoming")]


class Stumpbar(rumps.App):
    def __init__(self):
        super().__init__("🏏", quit_button=None)
        self.pinned_id = None
        self.international_only = False
        self.matches = []
        self.refresh(None)

    @rumps.timer(REFRESH_SECONDS)
    def tick(self, _):
        self.refresh(None)

    def refresh(self, _):
        try:
            self.matches = fetch_matches()
            self.error = None
        except Exception as exc:  # network errors etc. — keep the last good data
            self.error = str(exc)
        self.rebuild()

    def rebuild(self):
        self.menu.clear()
        shown = [m for m in self.matches if m.international or not self.international_only]

        if self.error:
            self.menu.add(rumps.MenuItem(f"⚠️ Couldn't fetch scores: {self.error[:60]}"))
            self.menu.add(rumps.separator)

        for state, heading in SECTIONS:
            group = [m for m in shown if m.state == state]
            if not group:
                continue
            self.menu.add(rumps.MenuItem(heading))  # no callback = greyed-out header
            for m in group:
                self.menu.add(self.match_item(m))
            self.menu.add(rumps.separator)

        if not shown and not self.error:
            self.menu.add(rumps.MenuItem("No matches right now"))
            self.menu.add(rumps.separator)

        intl = rumps.MenuItem("International only", callback=self.toggle_international)
        intl.state = self.international_only
        self.menu.add(intl)
        if self.pinned_id:
            self.menu.add(rumps.MenuItem("Unpin", callback=self.unpin))
        self.menu.add(rumps.MenuItem("Refresh", callback=self.refresh, key="r"))
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application, key="q"))

        self.update_title()

    def match_item(self, m):
        item = rumps.MenuItem(f"{m.short_score}  —  {m.summary}")
        item.state = m.id == self.pinned_id
        item.add(rumps.MenuItem(m.description))
        item.add(rumps.separator)
        item.add(rumps.MenuItem("Pin to menu bar", callback=lambda _, mid=m.id: self.pin(mid)))
        if m.link:
            item.add(rumps.MenuItem("Open on ESPNcricinfo", callback=lambda _, url=m.link: webbrowser.open(url)))
        return item

    def update_title(self):
        pinned = next((m for m in self.matches if m.id == self.pinned_id), None)
        if pinned:
            self.title = f"🏏 {pinned.batting_score}"
        else:
            live = sum(1 for m in self.matches if m.state == "in"
                       and (m.international or not self.international_only))
            self.title = f"🏏 {live} live" if live else "🏏"

    def pin(self, match_id):
        self.pinned_id = match_id
        self.rebuild()

    def unpin(self, _):
        self.pinned_id = None
        self.rebuild()

    def toggle_international(self, _):
        self.international_only = not self.international_only
        self.rebuild()


if __name__ == "__main__":
    Stumpbar().run()
