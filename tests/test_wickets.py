import json
from pathlib import Path

import pytest

from scores import Match, Team
from wickets import (MAX_PENDING_CHECKS, WicketWatcher, parse_dismissal,
                     recent_balls_from_summary, surname, team_wickets)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("text, line, runs, balls", [
    # Real lines from ESPN's feed (India A v Australia A, Sep 2026).
    ("T Murphy  b Kamboj 33 (91b 2x4 1x6) SR: 36.26", "Murphy b Kamboj", "33", "91"),
    ("JR Philippe c Padikkal b Bhute 5 (21b 0x4 0x6) SR: 23.8", "Philippe c Padikkal b Bhute", "5", "21"),
    ("PSP Handscomb c &dagger;Kushagra b Bhute 0 (15b 0x4 0x6) SR: 0",
     "Handscomb c †Kushagra b Bhute", "0", "15"),
    # Other methods, in the same notation.
    ("Q de Kock lbw b Starc 12 (9b 2x4 0x6) SR: 133.33", "de Kock lbw b Starc", "12", "9"),
    ("V Kohli c & b Lyon 44 (60b 5x4 0x6) SR: 73.33", "Kohli c & b Lyon", "44", "60"),
    ("RR Pant st &dagger;Carey b Zampa 27 (18b)", "Pant st †Carey b Zampa", "27", "18"),
    ("SPD Smith run out (Jadeja/&dagger;Pant) 61 (80b)", "Smith run out (Jadeja/†Pant)", "61", "80"),
    ("M Labuschagne hit wicket b Bumrah 3 (7b)", "Labuschagne hit wicket b Bumrah", "3", "7"),
    ("RG Sharma retired hurt 20 (22b)", "Sharma retired hurt", "20", "22"),
])
def test_parse_dismissal(text, line, runs, balls):
    assert parse_dismissal(text) == (line, runs, balls)


def test_unusual_method_is_kept_as_is():
    assert parse_dismissal("SPD Smith obstructing the field 4 (10b)") == ("Smith obstructing the field", "4", "10")


@pytest.mark.parametrize("name, expected", [
    ("T Murphy", "Murphy"), ("Q de Kock", "de Kock"), ("Todd Murphy", "Murphy"), ("Murphy", "Murphy"),
])
def test_surname(name, expected):
    assert surname(name) == expected


@pytest.mark.parametrize("score, wickets", [
    ("282/7 (87 ov)", 7),
    ("140/8 (20 ov, target 176)", 8),
    ("350/6d & 120/3 (40 ov)", 3),
    ("350", 10),  # all out
    ("", None),
])
def test_team_wickets(score, wickets):
    assert team_wickets(score) == wickets


def match(aus_score, ind_score=""):
    return Match(id="1535673", league_id="24375", state="in", title="", description="", summary="",
                 international=False, link="",
                 teams=[Team("1781", "IND-A", "India A", ind_score),
                        Team("49", "AUS-A", "Australia A", aus_score)],
                 batting_team_id="49")


def recorded_balls(_match):
    summary = json.loads((FIXTURES / "summary_1535673.json").read_text())
    return recent_balls_from_summary(summary)


def test_no_alert_for_wickets_before_watching():
    w = WicketWatcher(recorded_balls)
    assert w.check(match("277/7 (84.5 ov)")) == []
    assert w.check(match("277/7 (84.5 ov)")) == []


def test_new_wicket_is_reported_with_method():
    # Replays the real fall of Todd Murphy: 277/6 -> 277/7.
    w = WicketWatcher(recorded_balls)
    w.check(match("277/6 (84.4 ov)"))
    [wicket] = w.check(match("277/7 (84.5 ov)"))

    assert wicket.title == "WICKET! AUS-A 7/277 (84.5)"
    assert wicket.subtitle == "Murphy b Kamboj · 33 (91)"
    assert wicket.commentary.startswith("Kamboj does the job straightaway")

    # Reported once only.
    assert w.check(match("277/7 (84.5 ov)")) == []
    assert w.check(match("282/7 (87 ov)")) == []


def test_new_innings_resets_without_alert():
    w = WicketWatcher(recorded_balls)
    w.check(match("350", "200/9"))
    assert w.check(match("350", "210 & 0/0 (0.1 ov)")) == []


def test_falls_back_when_details_never_arrive():
    w = WicketWatcher(lambda _m: [])  # ball-by-ball feed never shows the wicket
    w.check(match("290/7 (88 ov)"))
    results = [w.check(match("290/8 (88.2 ov)")) for _ in range(MAX_PENDING_CHECKS)]

    assert results[:-1] == [[]] * (MAX_PENDING_CHECKS - 1)
    [wicket] = results[-1]
    assert wicket.title == "WICKET! AUS-A 8/290 (88.2)"
    assert wicket.subtitle == ""


def test_feed_error_does_not_crash():
    def broken(_m):
        raise ConnectionError("offline")

    w = WicketWatcher(broken)
    w.check(match("290/7 (88 ov)"))
    assert w.check(match("290/8 (88.2 ov)")) == []


def test_switching_match_resets():
    w = WicketWatcher(recorded_balls)
    w.check(match("277/6 (84.4 ov)"))
    other = match("100/1 (20 ov)")
    other.id = "999"
    assert w.check(other) == []
    assert w.check(None) == []
