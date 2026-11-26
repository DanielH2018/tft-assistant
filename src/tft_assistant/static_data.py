"""A set's roster from Community Dragon: units, traits and items, keyed by the names a match uses.

A match payload names a unit by `character_id`, a trait by `name` and an item by its entry in
`itemNames`. Each of those equals an `apiName` here, so the keys of these tables join to a
payload directly.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

DOCUMENT_URL = "https://raw.communitydragon.org/{channel}/cdragon/tft/en_us.json"
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


@dataclass(frozen=True)
class Item:
    api_name: str
    name: str
    components: tuple[str, ...]
    emblem_of: str | None
    radiant_of: str | None
    is_component: bool


def document(channel: str = "latest") -> dict[str, Any]:
    """Community Dragon's TFT document, downloaded at most once a day."""
    cached = CACHE_DIR / f"cdragon-{channel}.json"
    if not cached.exists() or time.time() - cached.stat().st_mtime > _MAX_AGE_SECONDS:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        response = httpx.get(DOCUMENT_URL.format(channel=channel), timeout=120.0, follow_redirects=True)
        response.raise_for_status()
        cached.write_bytes(response.content)
    return json.loads(cached.read_bytes())


def _emblem_trait(item: dict[str, Any], trait_by_name: dict[str, str]) -> str | None:
    name = item.get("name") or ""
    if not name.endswith(" Emblem"):
        return None
    excluded = item.get("incompatibleTraits") or []
    if len(excluded) == 1:
        return excluded[0]
    return trait_by_name.get(name.removesuffix(" Emblem"))


def _radiant_base(item: dict[str, Any], by_name: dict[str | None, str]) -> str | None:
    name = item.get("name") or ""
    return by_name.get(name.removeprefix("Radiant ")) if name.startswith("Radiant ") else None


@dataclass(frozen=True)
class StaticData:
    units: dict[str, Unit]
    traits: dict[str, Trait]
    items: dict[str, Item]

    @classmethod
    def from_document(cls, source: dict[str, Any], mutator: str) -> StaticData:
        """The roster of one game mode of one set, named as in Community Dragon's `setData`."""
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
            )
            for trait in entry["traits"]
        }
        trait_by_name = {trait.name: trait.api_name for trait in traits.values()}
        units = {
            unit["apiName"]: Unit(
                unit["apiName"],
                unit["name"],
                unit["cost"],
                tuple(trait_by_name[name] for name in unit["traits"] if name in trait_by_name),
                unit["stats"].get("range") or 0.0,
                unit.get("role"),
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
            )
            for item in records
        }
        return cls(units, traits, items)
