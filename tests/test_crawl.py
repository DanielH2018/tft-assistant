from tft_assistant.crawl import crawl
from tft_assistant.riot import Player
from tft_assistant.store import Selection, Store


class FakeClient:
    def __init__(self, ids_by_player, diamond_pages=()):
        self.ids_by_player = ids_by_player
        self.diamond_pages = diamond_pages
        self.fetched = []

    def ladder(self, platform, *, below_master):
        yield [Player(puuid, platform, "challenger", 1000) for puuid in self.ids_by_player]
        for page in self.diamond_pages:
            if not below_master():
                return
            yield [Player(puuid, platform, "diamond I", 50) for puuid in page]

    def match_ids(self, platform, puuid, *, since):
        return self.ids_by_player.get(puuid, [])

    def match(self, platform, match_id):
        self.fetched.append(match_id)
        return {
            "metadata": {"match_id": match_id},
            "info": {"tft_set_number": 19, "game_version": "Version 19.1", "queue_id": 1100, "game_datetime": 0},
        }


def test_crawl_fetches_a_match_two_players_share_once():
    client = FakeClient({"a": ["NA1_1", "NA1_2"], "b": ["NA1_2", "NA1_3"]})
    store = Store(":memory:")

    report = crawl(client, store, "na1", since=0, budget_seconds=60)

    assert client.fetched == ["NA1_1", "NA1_2", "NA1_3"]
    assert store.count(Selection(19, 1100)) == 3
    assert (report.players_listed, report.matches_stored, report.requests, report.finished_ladder) == (2, 3, 6, True)


def test_crawl_stops_listing_players_when_the_budget_ends():
    client = FakeClient({"a": ["NA1_1"], "b": ["NA1_2"]})
    ticks = iter([0, 0, 90, 90])

    report = crawl(client, Store(":memory:"), "na1", since=0, budget_seconds=60, clock=lambda: next(ticks))

    assert client.fetched == ["NA1_1"]
    assert not report.finished_ladder


def test_a_crawl_goes_below_master_only_until_it_has_listed_enough_players():
    client = FakeClient({"a": [], "b": []}, diamond_pages=[["c", "d"], ["e", "f"], ["g", "h"]])

    store = Store(":memory:")
    thin = crawl(client, store, "na1", since=0, budget_seconds=60, min_players=5)
    floor_when_thin = store.floors()
    full = crawl(client, store, "na1", since=0, budget_seconds=60, min_players=2)

    assert (thin.players_listed, thin.lowest_tier) == (6, "diamond I")
    assert "down to diamond I" in thin.line()
    assert (full.players_listed, full.lowest_tier) == (2, "challenger")
    assert "down to" not in full.line()
    assert (floor_when_thin, store.floors()) == ({"na1": "diamond I"}, {"na1": "challenger"})
