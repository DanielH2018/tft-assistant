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
from tft_assistant.comp_detail import ItemPick
from tft_assistant.comps import Comp, find_comps
from tft_assistant.item_groups import find_item_groups
from tft_assistant.positioning import default_board
from tft_assistant.static_data import StaticData
from tft_assistant.store import Selection

SCHEMA = 2

_TIERS = ((4.10, "S"), (4.35, "A"), (4.60, "B"))
"""A comp's tier is the first whose average placement it does not exceed; the rest are C."""


def _tier(avg_placement: float) -> str:
    return next((tier for limit, tier in _TIERS if avg_placement <= limit), "C")


def _board_units(comp: Comp) -> list[str]:
    """The comp as usually fielded: its core, then the commonest option of each flex slot, up to its usual level."""
    size = max(comp.tempo.levels, key=lambda level: level[1])[0]
    units = list(comp.core)
    for slot in comp.flex:
        commonest = max(slot.options, key=lambda package: package.share)
        units += [unit for unit in commonest.units if unit not in units]
    return units[: max(size, len(comp.core))]


def _clashes(names: list[str]) -> list[list[int]]:
    """The positions of each name that more than one comp has."""
    positions: dict[str, list[int]] = {}
    for position, name in enumerate(names):
        positions.setdefault(name, []).append(position)
    return [same for same in positions.values() if len(same) > 1]


def _as_a_group(trait_name: str) -> str:
    """A trait named for what its units do reads as a group in the plural; other names stay as they are."""
    return f"{trait_name}s" if trait_name.endswith(("er", "or")) else trait_name


def _names(comps: Sequence[Comp], static: StaticData) -> list[str]:
    """A name for each comp: its main trait and its main carry, made unique among the comps.

    Comps that would share a name are told apart first by the trait their two carries share,
    which replaces the carry, and then by the costliest core unit each has and the others lack.
    """

    def trait_name(trait: str | None) -> str:
        return static.traits[trait].name if trait in static.traits else ""

    names = []
    for comp in comps:
        carry = static.units[comp.carries[0]].name if comp.carries else ""
        names.append(f"{trait_name(comp.main_trait)} {carry}".strip() or "Unnamed")
    for same in _clashes(names):
        for position in same:
            comp = comps[position]
            if comp.carry_trait in static.traits and comp.carry_trait != comp.main_trait:
                names[position] = f"{trait_name(comp.main_trait)} {_as_a_group(trait_name(comp.carry_trait))}"
    for same in _clashes(names):
        shared = set.intersection(*(set(comps[position].core) for position in same))
        for position in same:
            comp = comps[position]
            own = [unit for unit in comp.core if unit not in shared and unit not in comp.carries[:1]]
            if own:
                names[position] += f" · {static.units[own[0]].name}"
    return names


def _pick(pick: ItemPick) -> dict[str, Any]:
    return {
        "item": pick.item,
        "holder": pick.holder,
        "share": pick.share,
        "avg_with": pick.avg_with,
        "avg_without": pick.avg_without,
    }


def _comp(comp: Comp, name: str, static: StaticData) -> dict[str, Any]:
    board = default_board(_board_units(comp), comp.carries, static)
    return {
        "id": hashlib.sha1(" ".join(sorted(comp.core)).encode()).hexdigest()[:10],
        "name": name,
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
        "flex": [
            [
                {"units": list(package.units), "share": package.share, "avg_placement": package.avg_placement}
                for package in slot.options
            ]
            for slot in comp.flex
        ],
        "traits": [
            {"trait": trait.name, "units": trait.units, "tier": trait.tier, "tiers": trait.tiers}
            for trait in comp.traits
        ],
        "levels": [[level, share] for level, share in comp.tempo.levels],
        "three_stars": list(comp.tempo.three_stars),
        "style": comp.tempo.style,
        "roll_level": comp.tempo.roll_level,
        "items": [_pick(pick) for pick in comp.item_priority],
        "take": list(comp.take),
        "spare": [
            {"component": spare.component, "share": spare.share, "uses": [_pick(pick) for pick in spare.uses]}
            for spare in comp.spare
        ],
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
    comps = [_comp(comp, name, static) for comp, name in zip(report.comps, _names(report.comps, static))]

    units = {unit for comp in comps for unit in [*comp["core"], *comp["three_stars"]]}
    units |= {unit for comp in comps for slot in comp["flex"] for package in slot for unit in package["units"]}
    spare_uses = [pick for comp in comps for spare in comp["spare"] for pick in spare["uses"]]
    units |= {pick["holder"] for comp in comps for pick in comp["items"]} | {u for g in groups for u in g.units}
    units |= {pick["holder"] for pick in spare_uses}
    units |= {s["unit"] for comp in comps for up in comp["level_ups"] for s in [*up["adds"], *up["drops"]]}
    units |= {key["unit"] for comp in comps for key in comp["key_units"]}
    items = {pick["item"] for comp in comps for pick in comp["items"]} | {i for g in groups for i in g.items}
    items |= {item for comp in comps for item in comp["take"]}
    items |= {pick["item"] for pick in spare_uses} | {spare["component"] for comp in comps for spare in comp["spare"]}
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
