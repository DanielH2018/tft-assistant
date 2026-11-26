"""The document a page reads: one analysis of one selection, as plain JSON.

Analysis writes a snapshot and the pages read nothing else, so this shape is the contract
between them. A change that removes or renames a field raises `SCHEMA`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from tft_assistant.boards import Board
from tft_assistant.comps import Comp, find_comps
from tft_assistant.item_groups import find_item_groups
from tft_assistant.positioning import default_board
from tft_assistant.static_data import StaticData
from tft_assistant.store import Selection

SCHEMA = 1

_TIERS = ((4.10, "S"), (4.35, "A"), (4.60, "B"))
"""A comp's tier is the first whose average placement it does not exceed; the rest are C."""


def _tier(avg_placement: float) -> str:
    return next((tier for limit, tier in _TIERS if avg_placement <= limit), "C")


def _board_units(comp: Comp) -> list[str]:
    """The comp as usually fielded: its core, then its commonest flex units, up to its usual level."""
    size = max(comp.tempo.levels, key=lambda level: level[1])[0]
    units = list(comp.core)
    for package in comp.packages:
        units += [unit for unit in package.units if unit not in units]
    return units[: max(size, len(comp.core))]


def _tell_apart(comps: list[dict[str, Any]], static: StaticData) -> None:
    """Give comps that share a name the costliest core unit each has and the others lack."""
    by_name: dict[str, list[dict[str, Any]]] = {}
    for comp in comps:
        by_name.setdefault(comp["name"], []).append(comp)
    for same in by_name.values():
        if len(same) < 2:
            continue
        shared = set.intersection(*(set(comp["core"]) for comp in same))
        for comp in same:
            own = [unit for unit in comp["core"] if unit not in shared and unit not in comp["carries"][:1]]
            if own:
                comp["name"] += f" · {static.units[own[0]].name}"


def _comp(comp: Comp, static: StaticData) -> dict[str, Any]:
    trait = static.traits[comp.main_trait].name if comp.main_trait in static.traits else ""
    carries = " ".join(static.units[unit].name for unit in comp.carries[:1])
    board = default_board(_board_units(comp), comp.carries, static)
    return {
        "id": hashlib.sha1(" ".join(sorted(comp.core)).encode()).hexdigest()[:10],
        "name": f"{trait} {carries}".strip() or "Unnamed",
        "tier": _tier(comp.avg_placement),
        "boards": comp.boards,
        "share": comp.share,
        "avg_placement": comp.avg_placement,
        "top4": comp.top4,
        "core": list(comp.core),
        "carries": list(comp.carries),
        "key_units": [
            {
                "unit": key.unit,
                "role": key.role,
                "build": [
                    {
                        "item": note.item,
                        "share": note.share,
                        "avg_with": note.avg_with,
                        "avg_without": note.avg_without,
                        "critical": note.critical,
                        "needs": [
                            {"item": pair.partner, "avg_together": pair.avg_together, "avg_apart": pair.avg_apart}
                            for pair in note.needs
                        ],
                    }
                    for note in key.build
                ],
            }
            for key in comp.key_units
        ],
        "packages": [
            {"units": list(package.units), "share": package.share, "avg_placement": package.avg_placement}
            for package in comp.packages
        ],
        "traits": [
            {"trait": trait.name, "units": trait.units, "tier": trait.tier, "tiers": trait.tiers}
            for trait in comp.traits
        ],
        "levels": [[level, share] for level, share in comp.tempo.levels],
        "three_stars": list(comp.tempo.three_stars),
        "items": [
            {
                "item": pick.item,
                "holder": pick.holder,
                "share": pick.share,
                "avg_with": pick.avg_with,
                "avg_without": pick.avg_without,
            }
            for pick in comp.item_priority
        ],
        "take": list(comp.take),
        "level_ups": [
            {
                "level": up.level,
                "share": up.share,
                "avg_placement": up.avg_placement,
                "adds": [{"unit": s.unit, "share": s.share, "share_below": s.share_below} for s in up.adds],
                "drops": [{"unit": s.unit, "share": s.share, "share_below": s.share_below} for s in up.drops],
            }
            for up in comp.level_ups
        ],
        "board": [{"unit": unit, "row": row, "column": column} for unit, (row, column) in board.items()],
        "board_is_default": True,
        "sections": [],
    }


def build_snapshot(
    label: str,
    selection: Selection,
    boards: Sequence[Board],
    static: StaticData,
    *,
    built_at: datetime,
    newest_match: datetime | None,
) -> dict[str, Any]:
    """Analyse the boards of one selection into the document the page reads."""
    report = find_comps(boards, static)
    groups = find_item_groups(boards, static)
    comps = [_comp(comp, static) for comp in report.comps]
    _tell_apart(comps, static)

    units = {unit for comp in comps for unit in [*comp["core"], *comp["three_stars"]]}
    units |= {unit for comp in comps for package in comp["packages"] for unit in package["units"]}
    units |= {pick["holder"] for comp in comps for pick in comp["items"]} | {u for g in groups for u in g.units}
    units |= {s["unit"] for comp in comps for up in comp["level_ups"] for s in [*up["adds"], *up["drops"]]}
    units |= {key["unit"] for comp in comps for key in comp["key_units"]}
    items = {pick["item"] for comp in comps for pick in comp["items"]} | {i for g in groups for i in g.items}
    items |= {item for comp in comps for item in comp["take"]}
    items |= {note["item"] for comp in comps for key in comp["key_units"] for note in key["build"]}
    traits = {trait["trait"] for comp in comps for trait in comp["traits"]}
    traits |= {trait for unit in units for trait in static.units[unit].traits}

    return {
        "schema": SCHEMA,
        "label": label,
        "selection": {
            "set": selection.set_number,
            "since": selection.since.isoformat() if selection.since else None,
            "until": selection.until.isoformat() if selection.until else None,
            "platforms": list(selection.platforms),
        },
        "built_at": built_at.isoformat(),
        "newest_match": newest_match.isoformat() if newest_match else None,
        "boards": report.boards,
        "unclassified": report.unclassified,
        "comps": comps,
        "item_groups": [{"items": list(group.items), "units": list(group.units)} for group in groups],
        "units": {
            unit: {
                "name": static.units[unit].name,
                "cost": static.units[unit].cost,
                "traits": list(static.units[unit].traits),
                "icon": static.units[unit].icon,
            }
            for unit in sorted(units)
        },
        "items": {
            item: {"name": static.items[item].name, "icon": static.items[item].icon}
            for item in sorted(items)
            if item in static.items
        },
        "traits": {
            trait: {"name": static.traits[trait].name, "icon": static.traits[trait].icon}
            for trait in sorted(traits)
            if trait in static.traits
        },
    }
