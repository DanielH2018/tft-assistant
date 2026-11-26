"""A set's roster from Community Dragon: units, traits and items, keyed by the names a match uses.

A match payload names a unit by `character_id`, a trait by `name` and an item by its entry in
`itemNames`. Each of those equals an `apiName` here, so the keys of these tables join to a
payload directly.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

DOCUMENT_URL = "https://raw.communitydragon.org/{channel}/cdragon/tft/en_us.json"
PLANNER_URL = (
    "https://raw.communitydragon.org/{channel}/plugins/rcp-be-lol-game-data/global/default/v1/"
    "tftchampions-teamplanner.json"
)
ICON_BASE = "https://raw.communitydragon.org/latest/game/"
CACHE_DIR = Path("~/.cache/tft-assistant").expanduser()
_MAX_AGE_SECONDS = 24 * 3600


@dataclass(frozen=True)
class Unit:
    api_name: str
    name: str
    cost: int
    traits: tuple[str, ...]
    attack_range: float
    role: str | None
    icon: str | None = None
    planner_code: int | None = None
    """The unit's number in Riot's team planner, which a team code is made of."""


@dataclass(frozen=True)
class Breakpoint:
    min_units: int
    max_units: int
    style: int


@dataclass(frozen=True)
class Trait:
    api_name: str
    name: str
    breakpoints: tuple[Breakpoint, ...]
    icon: str | None = None


@dataclass(frozen=True)
class Item:
    api_name: str
    name: str
    components: tuple[str, ...]
    emblem_of: str | None
    radiant_of: str | None
    is_component: bool
    icon: str | None = None
    is_defensive: bool = False
    """The recipe has a defensive component and no offensive one, as the set file lists them."""
    is_artifact: bool = False


def _icon_url(path: str | None) -> str | None:
    """Where Community Dragon serves a game asset: the path lower-cased, as a PNG."""
    return f"{ICON_BASE}{path.lower().removesuffix('.tex')}.png" if path else None


def _daily(url: str, cache_name: str) -> Any:
    """A JSON file from Community Dragon, downloaded at most once a day."""
    cached = CACHE_DIR / cache_name
    if not cached.exists() or time.time() - cached.stat().st_mtime > _MAX_AGE_SECONDS:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        response = httpx.get(url, timeout=120.0, follow_redirects=True)
        response.raise_for_status()
        cached.write_bytes(response.content)
    return json.loads(cached.read_bytes())


def document(channel: str = "latest") -> dict[str, Any]:
    """Community Dragon's TFT document."""
    return _daily(DOCUMENT_URL.format(channel=channel), f"cdragon-{channel}.json")


def planner_codes(mutator: str, channel: str = "latest") -> dict[str, int]:
    """The number Riot's team planner gives each unit of one set; empty for a set the file lacks."""
    table = _daily(PLANNER_URL.format(channel=channel), f"cdragon-planner-{channel}.json")
    return {entry["character_id"]: entry["team_planner_code"] for entry in table.get(mutator, [])}


def _emblem_trait(item: dict[str, Any], trait_by_name: dict[str, str]) -> str | None:
    name = item.get("name") or ""
    if not name.endswith(" Emblem"):
        return None
    excluded = item.get("incompatibleTraits") or []
    if len(excluded) == 1:
        return excluded[0]
    return trait_by_name.get(name.removesuffix(" Emblem"))


def _is_defensive(recipe: Sequence[str], defensive: set[str], offensive: set[str]) -> bool:
    return any(part in defensive for part in recipe) and not any(part in offensive for part in recipe)


def _radiant_base(item: dict[str, Any], by_name: dict[str | None, str]) -> str | None:
    name = item.get("name") or ""
    return by_name.get(name.removeprefix("Radiant ")) if name.startswith("Radiant ") else None


@dataclass(frozen=True)
class StaticData:
    units: dict[str, Unit]
    traits: dict[str, Trait]
    items: dict[str, Item]
    mutator: str = ""
    """The set's name in Riot's data, which a team code ends with."""

    def finished_items(self, held: Iterable[str]) -> set[str]:
        """The items among `held` that say how a unit is built: no emblem, no loose component.

        A radiant item counts as its base item.
        """
        build = set()
        for name in held:
            item = self.items.get(name)
            if item and not item.emblem_of and not item.is_component:
                build.add(item.radiant_of or name)
        return build

    @classmethod
    def from_document(
        cls,
        source: dict[str, Any],
        mutator: str,
        defensive_components: Iterable[str] = (),
        offensive_components: Iterable[str] = (),
        planner: Mapping[str, int] | None = None,
        artifact_prefix: str = "",
    ) -> StaticData:
        """The roster of one game mode of one set, named as in Community Dragon's `setData`.

        The document marks no item as defensive, so the caller names the defensive and the
        offensive components. A component in neither list, such as one that gives mana, is neutral.
        The document holds no team planner numbers either; `planner` gives each unit's. It marks
        no artifact, so an item whose API name starts with `artifact_prefix` is one.
        """
        defensive, offensive = set(defensive_components), set(offensive_components)
        planner = planner or {}
        found = [entry for entry in source["setData"] if entry["mutator"] == mutator]
        if not found:
            raise KeyError(f"no {mutator!r} in the document; it has {sorted(e['mutator'] for e in source['setData'])}")
        entry = found[0]
        traits = {
            trait["apiName"]: Trait(
                trait["apiName"],
                trait["name"],
                tuple(
                    Breakpoint(effect["minUnits"], effect["maxUnits"], effect["style"])
                    for effect in sorted(trait["effects"], key=lambda effect: effect["minUnits"])
                ),
                _icon_url(trait.get("icon")),
            )
            for trait in entry["traits"]
        }
        trait_by_name = {trait.name: trait.api_name for trait in traits.values()}
        # The planner lists one unit where the roster has a variant of it per origin, named
        # "Unit (Origin)". A variant takes the number of the unit it is a variant of.
        planner_by_name = {unit["name"]: planner[unit["apiName"]] for unit in entry["champions"] if unit["apiName"] in planner}
        units = {
            unit["apiName"]: Unit(
                unit["apiName"],
                unit["name"],
                unit["cost"],
                tuple(trait_by_name[name] for name in unit["traits"] if name in trait_by_name),
                unit["stats"].get("range") or 0.0,
                unit.get("role"),
                _icon_url(unit.get("tileIcon") or unit.get("squareIcon")),
                planner.get(unit["apiName"], planner_by_name.get((unit["name"] or "").split(" (")[0])),
            )
            for unit in entry["champions"]
        }
        records = [item for item in source["items"] if item["apiName"] in set(entry["items"])]
        by_name = {item.get("name"): item["apiName"] for item in records}
        built_from = {part for item in records for part in item.get("composition") or ()}
        items = {
            item["apiName"]: Item(
                item["apiName"],
                item.get("name") or item["apiName"],
                tuple(item.get("composition") or ()),
                _emblem_trait(item, trait_by_name),
                _radiant_base(item, by_name),
                item["apiName"] in built_from,
                _icon_url(item.get("icon")),
                _is_defensive(item.get("composition") or (), defensive, offensive),
                bool(artifact_prefix) and item["apiName"].startswith(artifact_prefix),
            )
            for item in records
        }
        return cls(units, traits, items, mutator)
