import httpx
import pytest

from tft_assistant.riot import RateLimiter, RiotClient, RiotError, load_key


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.slept = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def client_answering(responses, fake_time):
    requests = []

    def handler(request):
        requests.append(request)
        return responses[min(len(requests), len(responses)) - 1]

    limiter = RateLimiter(fake_time.clock, fake_time.sleep)
    return RiotClient("key", transport=httpx.MockTransport(handler), limiter=limiter), requests


def test_limiter_waits_until_the_oldest_request_leaves_a_full_window():
    fake_time = FakeTime()
    limiter = RateLimiter(fake_time.clock, fake_time.sleep)
    limiter.learn("app", "2:10")

    limiter.acquire("app")
    fake_time.now = 3.0
    limiter.acquire("app")
    fake_time.now = 4.0
    limiter.acquire("app")

    assert fake_time.slept == [6.0]


def test_client_adopts_the_limits_a_response_reports():
    fake_time = FakeTime()
    client, _ = client_answering([httpx.Response(200, json=[], headers={"X-App-Rate-Limit": "1:5"})], fake_time)

    client.match_ids("na1", "player", since=0)
    client.match_ids("na1", "player", since=0)

    assert client.limits_seen["americas app"] == "1:5"
    assert fake_time.slept == [5.0]


def test_client_waits_out_a_429_and_returns_the_retried_payload():
    fake_time = FakeTime()
    refused = httpx.Response(429, headers={"Retry-After": "7", "X-Rate-Limit-Type": "application"})
    client, requests = client_answering([refused, httpx.Response(200, json={"info": {}})], fake_time)

    assert client.match("na1", "NA1_1") == {"info": {}}
    assert fake_time.slept == [7.0]
    assert len(requests) == 2


def test_league_routes_by_platform_and_matches_route_by_region():
    league = httpx.Response(200, json={"entries": [{"puuid": "p", "leaguePoints": 900}]})
    client, requests = client_answering([league, league, league, httpx.Response(200, json=["KR_1"])], FakeTime())

    players = list(client.apex_players("kr"))
    client.match_ids("kr", players[0].puuid, since=0)

    assert [p.tier for p in players] == ["challenger", "grandmaster", "master"]
    assert [r.url.host for r in requests] == ["kr.api.riotgames.com"] * 3 + ["asia.api.riotgames.com"]


def test_a_refused_key_raises_without_retrying():
    client, requests = client_answering([httpx.Response(403, json={"status": {"message": "Forbidden"}})], FakeTime())

    with pytest.raises(RiotError, match="403"):
        client.match("na1", "NA1_1")
    assert len(requests) == 1


def test_load_key_reads_the_key_file_and_prefers_the_environment(tmp_path, monkeypatch):
    key_file = tmp_path / "riot.env"
    key_file.write_text("RIOT_API_KEY=from-file\n")

    monkeypatch.delenv("RIOT_API_KEY", raising=False)
    assert load_key(key_file) == "from-file"

    monkeypatch.setenv("RIOT_API_KEY", "from-environment")
    assert load_key(key_file) == "from-environment"
