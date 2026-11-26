"""Walk one platform's apex ladder and store every match its players finished."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from tft_assistant.riot import RiotClient
from tft_assistant.store import Store


@dataclass
class CrawlReport:
    platform: str
    players_listed: int = 0
    requests: int = 0
    matches_stored: int = 0
    seconds: float = 0.0
    finished_ladder: bool = False

    def line(self) -> str:
        hours = max(self.seconds, 1.0) / 3600
        return (
            f"{self.platform}: {self.players_listed} players listed, {self.matches_stored} matches stored,"
            f" {self.requests} requests in {self.seconds / 60:.0f} min"
            f" ({self.requests / hours:.0f} requests/h, {self.matches_stored / hours:.0f} matches/h)"
            f"{'' if self.finished_ladder else ', stopped at the time budget'}"
        )


def crawl(
    client: RiotClient,
    store: Store,
    platform: str,
    *,
    since: int,
    budget_seconds: float,
    clock: Callable[[], float] = time.monotonic,
) -> CrawlReport:
    """Store matches that started at or after `since`, highest tier first, until the budget ends."""
    report = CrawlReport(platform)
    started = clock()
    players = list(client.apex_players(platform))
    report.requests += 3
    for player in players:
        report.seconds = clock() - started
        if report.seconds >= budget_seconds:
            return report
        ids = client.match_ids(platform, player.puuid, since=since)
        report.players_listed += 1
        report.requests += 1
        for match_id in store.missing(ids):
            store.add_match(platform, client.match(platform, match_id))
            report.matches_stored += 1
            report.requests += 1
    report.seconds = clock() - started
    report.finished_ladder = True
    return report
