from __future__ import annotations

import argparse
import re
import time
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tft_assistant.boards import boards
from tft_assistant.build import build_site
from tft_assistant.comp_ids import CompIds
from tft_assistant.crawl import MIN_PLAYERS, crawl
from tft_assistant import explorer
from tft_assistant.edits import Edits
from tft_assistant.icons import mirror
from tft_assistant.refresh import refresh
from tft_assistant.riot import REGION_OF_PLATFORM, RiotClient, load_key
from tft_assistant.serve import server
from tft_assistant.sets import GameSet, latest_set_number
from tft_assistant.static_data import StaticData
from tft_assistant.store import Store

if TYPE_CHECKING:
    from tft_assistant.comps import CompReport

MIN_BOARDS = 1000
"""A selection with fewer boards gets no snapshot: clustering that few finds noise, not comps."""

MAX_MATCHES = 20_000
"""A selection with more matches is analysed from its newest 20,000, about 160,000 boards.

An unattended store grows by tens of thousands of matches a day, and a build holds every board
of a selection in memory: 13,600 matches took 790 MB on 2026-11-26. The cap keeps a build near
1 GB however long the store has run.
"""

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
    players = [player for listed in client.ladder(platform) for player in listed]
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
            f"{comp.share:5.1%}  avg {comp.avg_placement:.2f}  top4 {comp.top4:.0%}  win {comp.win_rate:.0%}"
            f"  {trait} / {names(comp.carries) or '?'}  core: {names(comp.core)}"
        )
        lines += [
            "        flex "
            + "  |  ".join(f"{p.share:4.0%}  avg {p.avg_placement:.2f}  {names(p.units)}" for p in slot.options)
            for slot in comp.flex
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


def build_page(store: Store, set_number: int, out: Path) -> None:
    """Analyse each standing selection of a set that has enough boards, and write the page."""
    from tft_assistant.snapshot import build_snapshot  # here, so serve and crawl load no numpy

    game_set = GameSet.load(set_number)
    static = game_set.roster()
    now, snapshots, built = datetime.now(UTC), [], {}
    for label, standing in game_set.standing_selections(now):
        selection = store.capped(standing, MAX_MATCHES)
        if selection is not standing:
            label += f", newest {MAX_MATCHES:,} matches"
        if selection in built:
            print(f"skipped {label}: the same matches as {built[selection]}")
            continue
        found = [board for match in store.matches(selection) for board in boards(match)]
        if len(found) < MIN_BOARDS:
            print(f"skipped {label}: {len(found)} boards, and a snapshot needs {MIN_BOARDS}")
            continue
        built[selection] = label
        snapshots.append(
            build_snapshot(
                label,
                selection,
                found,
                static,
                built_at=now,
                newest_match=store.newest(selection),
                ids=CompIds(),
                floors=store.floors(),
            )
        )
        snapshots[-1]["explorer"] = explorer.write(found, static, out)
        print(f"built {label}: {len(found)} boards, {len(snapshots[-1]['comps'])} comps")
    explorer.prune(out, [snapshot["explorer"] for snapshot in snapshots])
    print(mirror(snapshots, out))
    print(f"wrote {build_site(snapshots, out)}")


def crawl_platforms(
    client: RiotClient,
    store: Store,
    platforms: list[str] | None,
    days_back: float,
    minutes: float,
    min_players: int,
) -> None:
    """Crawl each platform's ladder at once, every platform when none is named, and report what the store holds."""
    since = int(time.time() - days_back * 86400)
    platforms = platforms or sorted(REGION_OF_PLATFORM)
    with ThreadPoolExecutor(len(platforms)) as pool:
        reports = pool.map(
            lambda platform: crawl(
                client, store, platform, since=since, budget_seconds=minutes * 60, min_players=min_players
            ),
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


def main() -> None:
    parser = argparse.ArgumentParser(prog="tft")
    commands = parser.add_subparsers(dest="command", required=True)
    probe_args = commands.add_parser("probe", help="report the rate limits and the fields of one real match")
    probe_args.add_argument("--platform", default="na1")
    crawled = argparse.ArgumentParser(add_help=False)
    crawled.add_argument("--platform", action="append", choices=sorted(REGION_OF_PLATFORM), dest="platforms")
    crawled.add_argument("--days-back", type=float, default=2.0, help="how far back a match may have started")
    crawled.add_argument("--minutes", type=float, default=60.0, help="time budget per platform")
    crawled.add_argument(
        "--min-players",
        type=int,
        default=MIN_PLAYERS,
        help="go below Master on a platform until this many players are listed",
    )
    built = argparse.ArgumentParser(add_help=False)
    built.add_argument("--set", type=int, dest="set_number", default=latest_set_number())
    built.add_argument("--out", type=Path, default=Path("site"), help="directory that receives index.html")
    commands.add_parser("crawl", parents=[crawled], help="store the matches of each platform's ladder, from the top")
    commands.add_parser("build", parents=[built], help="analyse the standing selections and write the page")
    refresh_args = commands.add_parser(
        "refresh",
        parents=[crawled, built],
        help="build the page, then crawl and build again every --minutes, until stopped",
    )
    refresh_args.add_argument(
        "--keep-days", type=float, default=30.0, help="after each crawl, delete matches that started longer ago"
    )
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
    served = commands.add_parser("serve", help="serve the built page and the edits made on it, until stopped")
    served.add_argument("--site", type=Path, default=Path("site"), help="directory that holds index.html")
    served.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    if args.command == "serve":
        print(f"serving {args.site} and the edits on port {args.port}")
        server(args.site, Edits(), args.port).serve_forever()
    elif args.command == "build":
        build_page(Store(), args.set_number, args.out)
    elif args.command == "crawl":
        crawl_platforms(RiotClient(load_key()), Store(), args.platforms, args.days_back, args.minutes, args.min_players)
    elif args.command == "refresh":
        client, store = RiotClient(load_key()), Store()
        # A match the crawl still looks back for is never pruned, or each cycle would fetch it again.
        keep_days = max(args.keep_days, args.days_back)

        def crawl_and_prune() -> None:
            crawl_platforms(client, store, args.platforms, args.days_back, args.minutes, args.min_players)
            gone = store.prune(datetime.now(UTC) - timedelta(days=keep_days))
            print(f"pruned {gone} matches that started more than {keep_days:g} days ago")

        refresh(crawl_and_prune, lambda: build_page(store, args.set_number, args.out), cycle_seconds=args.minutes * 60)
    elif args.command in ("comps", "item-groups"):
        from tft_assistant.comps import find_comps  # here, so serve and crawl load no numpy
        from tft_assistant.item_groups import find_item_groups

        game_set = GameSet.load(args.set_number)
        selection = game_set.selection(
            patch=args.patch, since=args.since, until=args.until, platforms=tuple(args.platforms or ())
        )
        static = game_set.roster()
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
