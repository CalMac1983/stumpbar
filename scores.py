"""Fetch and parse cricket scores from ESPN's public scoreboard feed."""

import re
from dataclasses import dataclass

import requests

FEED_URL = "https://site.web.api.espn.com/apis/v2/scoreboard/header?sport=cricket"

# Words in ESPN's live status that mean play has stopped (e.g. "Stumps", "Tea", "Rain delay").
BREAK_WORDS = ("stumps", "lunch", "tea", "dinner", "drinks", "innings break",
               "rain", "delay", "bad light", "wet outfield", "interrupt", "suspend")


@dataclass
class Team:
    id: str
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
    batting_team_id: str | None = None
    status_text: str = ""  # ESPN's status, e.g. "Stumps", "Lunch", "Result"

    @property
    def break_reason(self) -> str | None:
        """Why play is stopped in a live match, or None if play is under way."""
        text = self.status_text.lower()
        if self.state == "in" and any(w in text for w in BREAK_WORDS):
            return self.status_text
        return None

    @property
    def short_score(self) -> str:
        """Compact line for the menu bar, e.g. 'IND 250/3 v AUS'."""
        parts = [f"{t.abbr} {t.score}".strip() for t in self.teams]
        return " v ".join(parts)

    @property
    def batting_score(self) -> str:
        """Batting team only, wickets first, e.g. 'AUS 7/282 (87 ov)'.

        Falls back to both teams when the feed doesn't say who is batting.
        """
        batting = [t for t in self.teams if t.id == self.batting_team_id] or self.teams
        parts = []
        for t in batting:
            score = wickets_first(t.score)
            score = overs_to(score, self.break_reason) if self.break_reason else overs_balls(score)
            parts.append(f"{t.abbr} {score}".strip())
        return " v ".join(parts)


def wickets_first(score: str) -> str:
    """Flip ESPN's runs/wickets to wickets/runs: '282/7 (87 ov)' -> '7/282 (87 ov)'."""
    return re.sub(r"\b(\d+)/(\d+)", r"\2/\1", score)


def overs_balls(score: str) -> str:
    """Show overs as over.ball: '(87 ov)' -> '(87.0)', '(19.4 ov)' -> '(19.4)'."""
    return re.sub(r"\b(\d+)(?:\.(\d))? ov\b", lambda m: f"{m[1]}.{m[2] or 0}", score)


def overs_to(score: str, text: str) -> str:
    """Replace the overs with other text: '(87 ov)' -> '(Stumps)'."""
    return re.sub(r"\b\d+(?:\.\d)? ov\b", text, score)


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
                                id=str(c.get("id", "")),
                                abbr=c.get("abbreviation", "?"),
                                name=c.get("displayName", ""),
                                score=c.get("score", ""),
                            )
                            for c in ev.get("competitors", [])
                        ],
                        batting_team_id=str(status["battingTeamId"]) if status.get("battingTeamId") else None,
                        status_text=status.get("type", {}).get("description", ""),
                    )
                )
    return matches


if __name__ == "__main__":
    for m in fetch_matches():
        print(f"[{m.state:4}] {m.short_score}  —  {m.summary}")
