"""Fetch and parse cricket scores from ESPN's public scoreboard feed."""

from dataclasses import dataclass

import requests

FEED_URL = "https://site.web.api.espn.com/apis/v2/scoreboard/header?sport=cricket"


@dataclass
class Team:
    abbr: str
    name: str
    score: str


@dataclass
class Match:
    id: str
    state: str  # "pre", "in" or "post"
    title: str
    description: str
    summary: str
    international: bool
    link: str
    teams: list[Team]

    @property
    def short_score(self) -> str:
        """Compact line for the menu bar, e.g. 'IND 250/3 v AUS'."""
        parts = [f"{t.abbr} {t.score}".strip() for t in self.teams]
        return " v ".join(parts)


def fetch_matches(timeout: float = 10) -> list[Match]:
    resp = requests.get(FEED_URL, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    matches = []
    for sport in data.get("sports", []):
        for league in sport.get("leagues", []):
            for ev in league.get("events", []):
                status = ev.get("fullStatus", {})
                matches.append(
                    Match(
                        id=ev["id"],
                        state=status.get("type", {}).get("state", ev.get("status", "")),
                        title=ev.get("name", ""),
                        description=ev.get("description", ""),
                        summary=status.get("summary") or ev.get("summary", ""),
                        international=ev.get("class", {}).get("internationalClassId", "0") != "0",
                        link=ev.get("link", ""),
                        teams=[
                            Team(
                                abbr=c.get("abbreviation", "?"),
                                name=c.get("displayName", ""),
                                score=c.get("score", ""),
                            )
                            for c in ev.get("competitors", [])
                        ],
                    )
                )
    return matches


if __name__ == "__main__":
    for m in fetch_matches():
        print(f"[{m.state:4}] {m.short_score}  —  {m.summary}")
