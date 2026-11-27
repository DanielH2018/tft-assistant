"""Walk one platform's ladder from the top and store every match its players finished."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from tft_assistant.riot import APEX_TIERS, RiotClient
from tft_assistant.store import Store


MIN_PLAYERS = 1000
"""Players a crawl lists on one platform before it stops going below Master.

Late in a set Master and above hold several thousand players on each platform, and an hour's
crawl lists about 2,800 of them, so the lower tiers are never reached. In a set's first days
those tiers are empty, and this many players still play enough matches to derive comps from.
"""


@dataclass
class CrawlReport:
    platform: str
    players_listed: int = 0
    requests: int = 0
    matches_stored: int = 0
    seconds: float = 0.0
    finished_ladder: bool = False
    lowest_tier: str = ""
    """The tier of the last player listed, which is the lowest, because the walk runs downward."""

    def line(self) -> str:
        hours = max(self.seconds, 1.0) / 3600
        return (
            f"{self.platform}: {self.players_listed} players listed, {self.matches_stored} matches stored,"
            f" {self.requests} requests in {self.seconds / 60:.0f} min"
            f" ({self.requests / hours:.0f} requests/h, {self.matches_stored / hours:.0f} matches/h)"
            f"{'' if self.lowest_tier in ('', *APEX_TIERS) else f', down to {self.lowest_tier}'}"
            f"{'' if self.finished_ladder else ', stopped at the time budget'}"
        )


def crawl(
    client: RiotClient,
    store: Store,
    platform: str,
    *,
    since: int,
    budget_seconds: float,
    min_players: int = MIN_PLAYERS,
    clock: Callable[[], float] = time.monotonic,
) -> CrawlReport:
    """Store matches that started at or after `since`, highest tier first, until the budget ends.

    The walk covers Master and above. It goes on below Master only while it has listed fewer
    than `min_players` players, so the lower tiers fill in when the top of the ladder is thin
    and drop out again as it fills. The store keeps the lowest tier it listed, for the page to
    say where its matches came from.
    """
    report = _walk(client, store, platform, since, budget_seconds, min_players, clock)
    if report.lowest_tier:
        store.note_floor(platform, report.lowest_tier)
    return report


def _walk(
    client: RiotClient,
    store: Store,
    platform: str,
    since: int,
    budget_seconds: float,
    min_players: int,
    clock: Callable[[], float],
) -> CrawlReport:
    report = CrawlReport(platform)
    started = clock()
    for players in client.ladder(platform, below_master=lambda: report.players_listed < min_players):
        report.requests += 1
        for player in players:
            report.seconds = clock() - started
            if report.seconds >= budget_seconds:
                return report
            ids = client.match_ids(platform, player.puuid, since=since)
            report.players_listed += 1
            report.lowest_tier = player.tier
            report.requests += 1
            for match_id in store.missing(ids):
                store.add_match(platform, client.match(platform, match_id))
                report.matches_stored += 1
                report.requests += 1
    report.seconds = clock() - started
    report.finished_ladder = True
    return report
