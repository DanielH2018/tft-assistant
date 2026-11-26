"""Riot API client for Teamfight Tactics that stays inside the key's rate limits.

Riot enforces an application limit and a per-endpoint limit, each per routing value, and
states both only in response headers. The client starts from the limits printed on a personal
key and replaces them with what each response reports.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

KEY_FILE = Path("~/.config/tft-assistant/riot.env").expanduser()

# League endpoints route by platform; match endpoints route by the platform's region.
REGION_OF_PLATFORM = {"na1": "americas", "euw1": "europe", "kr": "asia"}

APEX_TIERS = ("challenger", "grandmaster", "master")

# The limits printed on a personal key: 20 requests per second, 100 per 2 minutes.
PERSONAL_KEY_LIMITS = "20:1,100:120"

_ATTEMPTS = 6


class RiotError(Exception):
    pass


def load_key(path: Path = KEY_FILE) -> str:
    key = os.environ.get("RIOT_API_KEY")
    if key:
        return key
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        raise RiotError(f"no RIOT_API_KEY in the environment and no key file at {path}") from None
    for line in lines:
        name, _, value = line.partition("=")
        if name.strip() == "RIOT_API_KEY" and value.strip():
            return value.strip()
    raise RiotError(f"{path} has no RIOT_API_KEY=<key> line")


def _parse_limits(header: str) -> list[tuple[int, float]]:
    return [(int(limit), float(seconds)) for limit, seconds in (part.split(":") for part in header.split(","))]


class _Bucket:
    def __init__(self) -> None:
        self.windows: list[tuple[int, float]] = []
        self.sent: deque[float] = deque()
        self.blocked_until = 0.0

    def delay(self, now: float) -> float:
        wait = self.blocked_until - now
        for limit, seconds in self.windows:
            recent = [t for t in self.sent if t > now - seconds]
            if len(recent) >= limit:
                wait = max(wait, recent[-limit] + seconds - now)
        return wait

    def record(self, now: float) -> None:
        self.sent.append(now)
        horizon = now - max((seconds for _, seconds in self.windows), default=0.0)
        while self.sent and self.sent[0] <= horizon:
            self.sent.popleft()


class RateLimiter:
    """Holds each named bucket to at most `limit` requests in any span of `seconds`."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._clock = clock
        self._sleep = sleep
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def _bucket(self, name: str) -> _Bucket:
        return self._buckets.setdefault(name, _Bucket())

    def acquire(self, *names: str) -> None:
        while True:
            with self._lock:
                now = self._clock()
                wait = max(self._bucket(name).delay(now) for name in names)
                if wait <= 0:
                    for name in names:
                        self._bucket(name).record(now)
                    return
            self._sleep(wait)

    def learn(self, name: str, header: str) -> None:
        with self._lock:
            self._bucket(name).windows = _parse_limits(header)

    def block(self, name: str, seconds: float) -> None:
        with self._lock:
            bucket = self._bucket(name)
            bucket.blocked_until = max(bucket.blocked_until, self._clock() + seconds)


@dataclass(frozen=True)
class Player:
    puuid: str
    platform: str
    tier: str
    league_points: int


class RiotClient:
    def __init__(
        self,
        key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        limiter: RateLimiter | None = None,
    ) -> None:
        self._http = httpx.Client(headers={"X-Riot-Token": key}, timeout=20.0, transport=transport)
        self._limiter = limiter or RateLimiter()
        self.limits_seen: dict[str, str] = {}

    def apex_players(self, platform: str) -> Iterator[Player]:
        """Every Challenger, Grandmaster and Master player on one platform's ranked ladder."""
        for tier in APEX_TIERS:
            league = self._get(platform, f"league-{tier}", f"/tft/league/v1/{tier}", {"queue": "RANKED_TFT"})
            for entry in league["entries"]:
                yield Player(entry["puuid"], platform, tier, entry["leaguePoints"])

    def match_ids(self, platform: str, puuid: str, *, since: int, count: int = 100) -> list[str]:
        """IDs of a player's matches that started at or after `since`, in epoch seconds."""
        return self._get(
            REGION_OF_PLATFORM[platform],
            "match-ids",
            f"/tft/match/v1/matches/by-puuid/{puuid}/ids",
            {"startTime": since, "count": count},
        )

    def match(self, platform: str, match_id: str) -> dict[str, Any]:
        return self._get(REGION_OF_PLATFORM[platform], "match", f"/tft/match/v1/matches/{match_id}")

    def _get(self, route: str, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        app, per_method = f"{route} app", f"{route} {method}"
        if app not in self.limits_seen:
            self._limiter.learn(app, PERSONAL_KEY_LIMITS)
        for attempt in range(_ATTEMPTS):
            self._limiter.acquire(app, per_method)
            response = self._http.get(f"https://{route}.api.riotgames.com{path}", params=params)
            for bucket, header in ((app, "X-App-Rate-Limit"), (per_method, "X-Method-Rate-Limit")):
                if header in response.headers:
                    self.limits_seen[bucket] = response.headers[header]
                    self._limiter.learn(bucket, response.headers[header])
            if response.status_code == 429:
                scope = app if response.headers.get("X-Rate-Limit-Type") == "application" else per_method
                self._limiter.block(scope, float(response.headers.get("Retry-After", 1)))
            elif response.status_code >= 500:
                self._limiter.block(per_method, 2.0**attempt)
            elif response.is_success:
                return response.json()
            else:
                raise RiotError(f"{method} on {route} returned {response.status_code}: {response.text[:200]}")
        raise RiotError(f"{method} on {route} still failed after {_ATTEMPTS} attempts")
