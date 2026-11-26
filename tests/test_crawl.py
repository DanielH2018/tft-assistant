from tft_assistant.crawl import crawl
from tft_assistant.riot import Player
from tft_assistant.store import Selection, Store


class FakeClient:
    def __init__(self, ids_by_player):
        self.ids_by_player = ids_by_player
        self.fetched = []

    def apex_players(self, platform):
        return [Player(puuid, platform, "challenger", 1000) for puuid in self.ids_by_player]

    def match_ids(self, platform, puuid, *, since):
        return self.ids_by_player[puuid]

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
    assert (report.players_listed, report.matches_stored, report.requests, report.finished_ladder) == (2, 3, 8, True)


def test_crawl_stops_listing_players_when_the_budget_ends():
    client = FakeClient({"a": ["NA1_1"], "b": ["NA1_2"]})
    ticks = iter([0, 0, 90, 90])

    report = crawl(client, Store(":memory:"), "na1", since=0, budget_seconds=60, clock=lambda: next(ticks))

    assert client.fetched == ["NA1_1"]
    assert not report.finished_ladder
