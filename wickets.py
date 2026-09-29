"""Spot new wickets in a match and describe how the batter was out."""

import html
import re
from dataclasses import dataclass

import requests

from scores import Match, overs_balls, wickets_first

SUMMARY_URL = "https://site.web.api.espn.com/apis/site/v2/sports/cricket/{league}/summary?event={event}"

# If the ball-by-ball feed hasn't caught up with the score after this many
# refreshes, notify without the dismissal details rather than stay silent.
MAX_PENDING_CHECKS = 4

# Start of the method part of a scorecard line, e.g. "JR Philippe c Padikkal b Bhute 5 (21b ...)".
METHOD_START = re.compile(
    r"\s(?=(?:c|st|lbw|b|run out|hit wicket|retired|obstructing|handled|timed out|absent)\b)"
)
RUNS_BALLS = re.compile(r"\s+(\d+)\s+\((\d+)b\b")


@dataclass
class Wicket:
    team: str  # abbreviation of the batting side
    line: str  # scorecard style, e.g. "Philippe c Padikkal b Bhute"
    runs: str
    balls: str
    score: str  # after the wicket, wickets first, e.g. "7/277 (84.5)"
    commentary: str

    @property
    def title(self) -> str:
        return f"WICKET! {self.team} {self.score}".strip()

    @property
    def subtitle(self) -> str:
        line = self.line
        if line and self.runs:
            line += f" · {self.runs} ({self.balls})"
        return line


def team_wickets(score: str) -> int | None:
    """Wickets down in a side's current innings, from a score like '350 & 120/3 (40 ov)'.

    An innings with no '/' has finished all out, so counts as 10.
    """
    if not score.strip():
        return None
    innings = score.split("&")[-1]
    innings = re.sub(r"\(.*?\)", "", innings).strip()
    m = re.match(r"(\d+)/(\d+)", innings)
    if m:
        return int(m[2])
    return 10 if re.match(r"\d+", innings) else None


def surname(name: str) -> str:
    """'T Murphy' -> 'Murphy', 'Q de Kock' -> 'de Kock', 'Todd Murphy' -> 'Murphy'."""
    parts = name.split()
    if len(parts) > 1 and parts[0].isupper():  # scorecard initials
        return " ".join(parts[1:])
    return parts[-1] if parts else ""


def parse_dismissal(text: str, batter_name: str = "") -> tuple[str, str, str]:
    """'T Murphy  b Kamboj 33 (91b 2x4 1x6) SR: 36.26' -> ('Murphy b Kamboj', '33', '91')."""
    text = html.unescape(text)
    runs = balls = ""
    m = RUNS_BALLS.search(text)
    if m:
        runs, balls = m[1], m[2]
        text = text[: m.start()]
    start = METHOD_START.search(text)
    name, how = (text[: start.start()], text[start.end():]) if start else (batter_name, "")
    batter = surname(name or batter_name) or "Batter"
    return f"{batter} {' '.join(how.split())}".strip(), runs, balls


def fetch_recent_balls(match: Match, timeout: float = 10) -> list[dict]:
    """The last ~18 balls of a match from ESPN's summary feed, oldest first."""
    url = SUMMARY_URL.format(league=match.league_id, event=match.id)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return recent_balls_from_summary(resp.json())


def recent_balls_from_summary(summary: dict) -> list[dict]:
    comps = summary.get("header", {}).get("competitions", [{}])
    balls = list((comps[0].get("commentaries") or {}).values())
    return sorted(balls, key=lambda b: b.get("sequence", 0))


def wicket_from_ball(ball: dict, team_abbr: str) -> Wicket:
    dismissal = ball.get("dismissal", {})
    batter_name = dismissal.get("batsman", {}).get("athlete", {}).get("name", "")
    line, runs, balls = parse_dismissal(dismissal.get("text", ""), batter_name)
    innings, over = ball.get("innings", {}), ball.get("over", {})
    score = f"{innings.get('wickets')}/{innings.get('runs')}" if "runs" in innings else ""
    if over.get("overs") is not None:
        score += f" ({over['overs']})"
    return Wicket(
        team=ball.get("team", {}).get("abbreviation") or team_abbr,
        line=line,
        runs=runs,
        balls=balls,
        score=score,
        commentary=html.unescape(ball.get("text", "")).strip(),
    )


class WicketWatcher:
    """Tracks one match and reports each new wicket once."""

    def __init__(self, fetch_balls=fetch_recent_balls):
        self.fetch_balls = fetch_balls
        self.match_id = None
        self.wickets = {}  # team id -> wickets last seen
        self.pending = {}  # team id -> [wickets still to report, checks so far]
        self.notified = set()  # ball ids already reported

    def check(self, match: Match | None) -> list[Wicket]:
        if match is None or match.id != self.match_id:
            self.__init__(self.fetch_balls)
            self.match_id = match.id if match else None
            if match:
                self.wickets = {t.id: team_wickets(t.score) for t in match.teams}
            return []  # never alert for wickets that fell before we started watching

        for team in match.teams:
            now, before = team_wickets(team.score), self.wickets.get(team.id)
            if now is not None and before is not None and now > before:
                pending = self.pending.setdefault(team.id, [0, 0])
                pending[0] += now - before
            self.wickets[team.id] = now

        if not self.pending:
            return []
        return self.resolve_pending(match)

    def resolve_pending(self, match: Match) -> list[Wicket]:
        try:
            balls = self.fetch_balls(match)
        except Exception:
            balls = []

        found = []
        for team in match.teams:
            if team.id not in self.pending:
                continue
            count, checks = self.pending[team.id]
            outs = [b for b in balls
                    if b.get("dismissal", {}).get("dismissal")
                    and str(b.get("team", {}).get("id")) == team.id
                    and b.get("id") not in self.notified]
            new = outs[-count:] if outs else []
            for b in new:
                self.notified.add(b.get("id"))
                found.append(wicket_from_ball(b, team.abbr))
            count -= len(new)
            checks += 1

            if count > 0 and checks >= MAX_PENDING_CHECKS:
                # Details never showed up: still let the user know.
                score = overs_balls(wickets_first(team.score))
                found.extend(Wicket(team.abbr, "", "", "", score, "") for _ in range(count))
                count = 0
            if count > 0:
                self.pending[team.id] = [count, checks]
            else:
                del self.pending[team.id]
        return found
