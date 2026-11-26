from __future__ import annotations

import argparse
import re
import time
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from tft_assistant.boards import boards
from tft_assistant.comps import CompReport, find_comps
from tft_assistant.crawl import crawl
from tft_assistant.item_groups import find_item_groups
from tft_assistant.riot import REGION_OF_PLATFORM, RiotClient, load_key
from tft_assistant.sets import GameSet, latest_set_number
from tft_assistant.static_data import StaticData, document
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


def _moment(text: str) -> datetime:
    moment = datetime.fromisoformat(text)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def comp_lines(report: CompReport, static: StaticData, top: int) -> list[str]:
    def names(units: tuple[str, ...]) -> str:
        return ", ".join(static.units[unit].name for unit in units)

    lines = [f"{report.boards} boards, {len(report.comps)} comps, {report.unclassified:.1%} unclassified"]
    for comp in report.comps[:top]:
        trait = static.traits[comp.main_trait].name if comp.main_trait in static.traits else "?"
        lines.append(
            f"{comp.share:5.1%}  avg {comp.avg_placement:.2f}  top4 {comp.top4:.0%}"
            f"  {trait} / {names(comp.carries) or '?'}  core: {names(comp.core)}"
        )
        lines += [
            f"        flex {package.share:4.0%}  avg {package.avg_placement:.2f}  {names(package.units)}"
            for package in comp.packages
        ]
        lines.append(
            "        traits  "
            + " · ".join(f"{t.units} {static.traits[t.name].name if t.name in static.traits else t.name}" for t in comp.traits)
        )
        levels = " ".join(f"L{level} {share:.0%}" for level, share in comp.tempo.levels if share >= 0.05)
        lines.append(f"        tempo   {levels}" + (f" · 3-star: {names(comp.tempo.three_stars)}" if comp.tempo.three_stars else ""))
        for pick in comp.item_priority:
            without = f"{pick.avg_without:.2f}" if pick.avg_without is not None else "n/a"
            lines.append(
                f"        item {pick.share:4.0%}  {static.items[pick.item].name} → {static.units[pick.holder].name}"
                f"  (avg {pick.avg_with:.2f} with, {without} without)"
            )
        lines.append("        take    " + ", ".join(static.items[c].name if c in static.items else c for c in comp.take))
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
    selected = argparse.ArgumentParser(add_help=False)
    selected.add_argument("--set", type=int, dest="set_number", default=latest_set_number())
    selected.add_argument("--patch", help="a patch from the set's calendar, such as 18.7")
    selected.add_argument("--since", type=_moment, help="ISO date or time, UTC unless it carries an offset")
    selected.add_argument("--until", type=_moment)
    selected.add_argument("--platform", action="append", choices=sorted(REGION_OF_PLATFORM), dest="platforms")
    comps_args = commands.add_parser(
        "comps", parents=[selected], help="derive comps from the stored ranked boards of a selection"
    )
    comps_args.add_argument("--top", type=int, default=25, help="how many comps to print")
    commands.add_parser(
        "item-groups", parents=[selected], help="group units by the items they hold in a selection's boards"
    )
    args = parser.parse_args()

    if args.command in ("comps", "item-groups"):
        game_set = GameSet.load(args.set_number)
        selection = game_set.selection(
            patch=args.patch, since=args.since, until=args.until, platforms=tuple(args.platforms or ())
        )
        static = StaticData.from_document(document(), game_set.static_data)
        found = [board for match in Store().matches(selection) for board in boards(match)]
        if args.command == "comps":
            print("\n".join(comp_lines(find_comps(found, static), static, args.top)))
        else:
            print(f"{len(found)} boards")
            for group in find_item_groups(found, static):
                print("items: " + ", ".join(static.items[item].name for item in group.items))
                print("    " + ", ".join(f"{static.units[u].name} ({static.units[u].cost})" for u in group.units))
    elif args.command == "probe":
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
        for held in store.holdings():
            print(
                f"set {held.set_number} queue {held.queue_id}: {held.matches} matches,"
                f" {held.first:%Y-%m-%d %H:%M} to {held.last:%Y-%m-%d %H:%M} UTC"
            )
        for bucket, limits in sorted(client.limits_seen.items()):
            print(f"rate limit, {bucket}: {limits}")
