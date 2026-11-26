from __future__ import annotations

import argparse
import re
import time
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from tft_assistant.crawl import crawl
from tft_assistant.riot import REGION_OF_PLATFORM, RiotClient, load_key
from tft_assistant.store import Store

_MECHANIC_FIELD = re.compile(r"encounter|portal|unlock|augment", re.IGNORECASE)
_PLAYER_FIELDS = {"puuid", "riotIdGameName", "riotIdTagline", "participants"}


def _keys_matching(node: Any, pattern: re.Pattern[str], path: str = "") -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else key
            if pattern.search(key):
                yield here
            yield from _keys_matching(value, pattern, here)
    elif isinstance(node, list) and node:
        yield from _keys_matching(node[0], pattern, f"{path}[]")


def describe_match(match: dict[str, Any]) -> list[str]:
    """What one match payload holds, with no field that identifies a player."""
    info = match["info"]
    boards = sorted(info["participants"], key=lambda p: p["placement"])
    winner = boards[0]
    lines = [
        f"metadata fields: {sorted(set(match['metadata']) - _PLAYER_FIELDS)}",
        f"info fields: {sorted(set(info) - _PLAYER_FIELDS)}",
        *(f"info.{name}: {info.get(name)!r}" for name in sorted(info) if not isinstance(info[name], (list, dict))),
        f"participant fields: {sorted(set(winner) - _PLAYER_FIELDS)}",
        "placement, level, last_round, units, augments, gold_left:",
        *(
            f"  {p['placement']}  {p.get('level')}  {p.get('last_round')}  {len(p['units'])}"
            f"  {len(p.get('augments') or [])}  {p.get('gold_left')}"
            for p in boards
        ),
        f"unit fields: {sorted(winner['units'][0])}",
        *(f"  unit: {unit}" for unit in winner["units"]),
        f"trait fields: {sorted(winner['traits'][0])}",
        *(f"  trait: {trait}" for trait in winner["traits"]),
        f"fields naming a set mechanic: {sorted(set(_keys_matching(match, _MECHANIC_FIELD)))}",
    ]
    return lines


def probe(client: RiotClient, platform: str) -> list[str]:
    players = list(client.apex_players(platform))
    lines = [f"{platform} players by tier: {dict(Counter(p.tier for p in players))}"]
    since = int(time.time()) - 2 * 86400
    for player in players:
        ids = client.match_ids(platform, player.puuid, since=since, count=20)
        if ids:
            lines.append(f"one {player.tier} player has {len(ids)} matches in the last 2 days")
            lines += describe_match(client.match(platform, ids[0]))
            break
    lines += [f"rate limit, {bucket}: {limits}" for bucket, limits in sorted(client.limits_seen.items())]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(prog="tft")
    commands = parser.add_subparsers(dest="command", required=True)
    probe_args = commands.add_parser("probe", help="report the rate limits and the fields of one real match")
    probe_args.add_argument("--platform", default="na1")
    crawl_args = commands.add_parser("crawl", help="store the matches of each platform's apex ladder")
    crawl_args.add_argument("--platform", action="append", choices=sorted(REGION_OF_PLATFORM), dest="platforms")
    crawl_args.add_argument("--days-back", type=float, default=2.0, help="how far back a match may have started")
    crawl_args.add_argument("--minutes", type=float, default=60.0, help="time budget per platform")
    args = parser.parse_args()

    if args.command == "probe":
        print("\n".join(probe(RiotClient(load_key()), args.platform)))
    elif args.command == "crawl":
        client, store = RiotClient(load_key()), Store()
        since = int(time.time() - args.days_back * 86400)
        platforms = args.platforms or sorted(REGION_OF_PLATFORM)
        with ThreadPoolExecutor(len(platforms)) as pool:
            reports = pool.map(
                lambda platform: crawl(client, store, platform, since=since, budget_seconds=args.minutes * 60),
                platforms,
            )
            for report in reports:
                print(report.line())
        for summary in store.patches():
            print(f"set {summary.set_number} patch {summary.patch}: {summary.matches} ranked matches")
        for bucket, limits in sorted(client.limits_seen.items()):
            print(f"rate limit, {bucket}: {limits}")
