"""Stumpbar: a macOS menu bar app showing live cricket scores."""

import sys
import webbrowser

import rumps

from notify import SETTINGS_URL, Notifier
from scores import fetch_matches
from wickets import Wicket, WicketWatcher, parse_dismissal

REFRESH_SECONDS = 15
SECTIONS = [("in", "Live"), ("post", "Results"), ("pre", "Upcoming")]

# Scorecard lines in ESPN's format, one per dismissal type, for --demo-dismissals.
DEMO_DISMISSALS = [
    ("AUS-A", "7/277 (84.5)", "T Murphy  b Kamboj 33 (91b 2x4 1x6) SR: 36.26"),
    ("AUS-A", "1/12 (7.1)", "JR Philippe c Padikkal b Bhute 5 (21b 0x4 0x6) SR: 23.8"),
    ("AUS-A", "3/31 (11.6)", "PSP Handscomb c &dagger;Kushagra b Bhute 0 (15b 0x4 0x6) SR: 0"),
    ("IND", "3/142 (31.2)", "V Kohli c & b Lyon 44 (60b 5x4 0x6) SR: 73.33"),
    ("SA", "1/20 (2.4)", "Q de Kock lbw b Starc 12 (9b 2x4 0x6) SR: 133.33"),
    ("IND", "5/188 (24.3)", "RR Pant st &dagger;Carey b Zampa 27 (18b 3x4 1x6) SR: 150"),
    ("AUS", "4/201 (44.1)", "M Labuschagne hit wicket b Bumrah 3 (7b 0x4 0x6) SR: 42.85"),
    ("AUS", "3/150 (30.4)", "SPD Smith run out (Jadeja/&dagger;Pant) 61 (80b 6x4 0x6) SR: 76.25"),
    ("IND", "1/40 (5.2)", "RG Sharma retired hurt 20 (22b 3x4 0x6) SR: 90.9"),
]


class Stumpbar(rumps.App):
    def __init__(self):
        super().__init__("🏏", quit_button=None)
        self.pinned_id = None
        self.international_only = False
        self.wicket_alerts = True
        self.watcher = WicketWatcher()
        self.notifier = Notifier()
        self.matches = []
        self.refresh(None)
        if "--demo-wicket" in sys.argv:
            rumps.Timer(self.demo_wicket, 2).start()
        if "--demo-dismissals" in sys.argv:
            self.demo_queue = list(DEMO_DISMISSALS)
            rumps.Timer(self.demo_next_dismissal, 3).start()

    @rumps.timer(REFRESH_SECONDS)
    def tick(self, _):
        self.refresh(None)

    def refresh(self, _):
        try:
            self.matches = fetch_matches()
            self.error = None
        except Exception as exc:  # network errors etc. — keep the last good data
            self.error = str(exc)
        else:
            self.check_wickets()
        self.rebuild()

    def check_wickets(self):
        pinned = next((m for m in self.matches if m.id == self.pinned_id), None)
        for wicket in self.watcher.check(pinned if self.wicket_alerts else None):
            self.notify(wicket)

    def notify(self, wicket: Wicket):
        self.notifier.send(wicket.title, wicket.subtitle, wicket.commentary)

    def demo_wicket(self, timer):
        """Show a sample wicket alert (launch with --demo-wicket) to check notifications work."""
        timer.stop()
        self.notify(Wicket("AUS-A", "Murphy b Kamboj", "33", "91", "7/277 (84.5)",
                           "Kamboj does the job straightaway. A perfect length on middle, "
                           "nips in enough to beat the bat and to rattle stumps."))
        rumps.Timer(lambda t: (t.stop(), self.notifier.log_delivered()), 3).start()

    def demo_next_dismissal(self, timer):
        """Send one sample alert per dismissal type (launch with --demo-dismissals)."""
        if not self.demo_queue:
            timer.stop()
            self.notifier.log_delivered()
            return
        team, score, text = self.demo_queue.pop(0)
        line, runs, balls = parse_dismissal(text)
        self.notify(Wicket(team, line, runs, balls, score, "Demo alert: " + text.split(" (")[0]))

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
        alerts = rumps.MenuItem("Wicket alerts (pinned match)", callback=self.toggle_wicket_alerts)
        alerts.state = self.wicket_alerts
        self.menu.add(alerts)
        if self.wicket_alerts and self.notifier.allowed is False:
            self.menu.add(rumps.MenuItem("   ⚠️ Notifications are off — open Settings…",
                                         callback=lambda _: webbrowser.open(SETTINGS_URL)))
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

    def toggle_wicket_alerts(self, _):
        self.wicket_alerts = not self.wicket_alerts
        self.rebuild()

    def toggle_international(self, _):
        self.international_only = not self.international_only
        self.rebuild()


if __name__ == "__main__":
    Stumpbar().run()
