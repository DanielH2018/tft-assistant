"""The document a page reads: one analysis of one selection, as plain JSON.

Analysis writes a snapshot and the pages read nothing else, so this shape is the contract
between them. A change that removes or renames a field raises `SCHEMA`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from tft_assistant.boards import Board
from tft_assistant.categories import TRAIT, categories_of
from tft_assistant.comp_detail import TANK, ItemPick, Swap
from tft_assistant.comp_ids import CompIds
from tft_assistant.comps import Comp, find_comps
from tft_assistant.item_groups import ItemGroup, find_item_groups
from tft_assistant.positioning import usual_row
from tft_assistant.riot import APEX_TIERS
from tft_assistant.static_data import StaticData
from tft_assistant.store import Selection

SCHEMA = 3

_TIERS = ((4.10, "S"), (4.35, "A"), (4.60, "B"))
"""A comp's tier is the first whose average placement it does not exceed; the rest are C."""


def _tier(avg_placement: float) -> str:
    return next((tier for limit, tier in _TIERS if avg_placement <= limit), "C")


def _fielded(comp: Comp) -> list[str]:
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


def _recipes(static: StaticData, built: set[str]) -> dict[str, list[str]]:
    """The two components of every item a player can build, whether or not a comp builds it.

    The static data also holds the recipes of earlier sets, under other component names. The
    components in play are the ones the `built` items are made of, and a recipe counts when both
    of its components are among them.
    """
    every = {
        name: list(item.components)
        for name, item in sorted(static.items.items())
        if len(item.components) == 2 and not item.radiant_of
    }
    in_play = {part for name in built & set(every) for part in every[name]}
    return {name: parts for name, parts in every.items() if set(parts) <= in_play}


def _group(group: ItemGroup) -> dict[str, Any]:
    return {
        "items": list(group.items),
        "units": list(group.units),
        "held": {
            unit: {
                "boards": held.boards,
                "avg": round(held.avg_placement, 3),
                "items": {item: [round(share, 3), round(avg, 3)] for item, (share, avg) in held.items.items()},
            }
            for unit, held in group.held.items()
        },
    }


def tank_groups_last(groups: Sequence[ItemGroup], comps: Sequence[Comp]) -> list[ItemGroup]:
    """The groups with the ones tanks build in at the end, each part in the order given.

    A group is a tank group when more of its units are some comp's tank than some comp's carry.
    The reader looks up a carry's items far more often, so those groups come first.
    """
    roles = {(key.unit, key.role == TANK) for comp in comps for key in comp.key_units}
    tanks = {unit for unit, tank in roles if tank}
    carries = {unit for unit, tank in roles if not tank}

    def for_tanks(group: ItemGroup) -> bool:
        return len(tanks & set(group.units)) > len(carries & set(group.units))

    return sorted(groups, key=for_tanks)


def below_master(floors: dict[str, str], selection: Selection) -> list[list[str]]:
    """The selection's platforms whose latest crawl went below Master, each with the tier it reached."""
    return [
        [platform, tier]
        for platform, tier in sorted(floors.items())
        if tier not in APEX_TIERS and (not selection.platforms or platform in selection.platforms)
    ]


def roster(static: StaticData) -> list[str]:
    """The units a player can buy: the ones Riot's team planner lists that have a trait.

    The static data also holds what a board cannot field by choice, such as a training dummy
    or an anvil. The page's planner offers these units, whether or not a comp fields them.
    """
    return sorted(name for name, unit in static.units.items() if unit.planner_code and unit.traits)


COMPONENT_ORDER = (
    "BFSword",
    "RecurveBow",
    "ChainVest",
    "NegatronCloak",
    "NeedlesslyLargeRod",
    "TearOfTheGoddess",
    "GiantsBelt",
    "SparringGloves",
    "Spatula",
    "FryingPan",
)
"""The order the owner reads components in: damage, defence, magic, utility, then the emblem makers.

Each entry is the ending of a component's id. A set changes the prefix of the ids and keeps
the endings: Set 18 has `DA_Component_BFSword`.
"""


def components_in_order(recipes: dict[str, list[str]], static: StaticData) -> list[str]:
    """The components the recipes use, in `COMPONENT_ORDER`, then any other by name."""

    def place(part: str) -> tuple[int, str]:
        known = [at for at, ending in enumerate(COMPONENT_ORDER) if part.endswith(ending)]
        name = static.items[part].name if part in static.items else part
        return (known[0] if known else len(COMPONENT_ORDER), name)

    return sorted({part for parts in recipes.values() for part in parts}, key=place)


def _pick(pick: ItemPick) -> dict[str, Any]:
    return {
        "item": pick.item,
        "holder": pick.holder,
        "share": pick.share,
        "avg_with": pick.avg_with,
        "avg_without": pick.avg_without,
    }


def _swap(swap: Swap) -> dict[str, Any]:
    return {"unit": swap.unit, "share_with": swap.share_with, "share_without": swap.share_without}


def _comp(comp: Comp, comp_id: str, name: str, static: StaticData) -> dict[str, Any]:
    return {
        "id": comp_id,
        "name": name,
        "tier": _tier(comp.avg_placement),
        "boards": comp.boards,
        "share": comp.share,
        "avg_placement": comp.avg_placement,
        "top4": comp.top4,
        "win_rate": comp.win_rate,
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
                {
                    "units": list(package.units),
                    "share": package.share,
                    "avg_placement": package.avg_placement,
                    "top4": package.top4,
                    "win_rate": package.win_rate,
                }
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
            {"component": spare.component, "share": spare.share, "uses": list(spare.uses)}
            for spare in comp.spare
        ],
        "specials": [
            {
                "item": special.item,
                "kind": "emblem" if static.items[special.item].emblem_of else "artifact",
                "emblem_of": static.items[special.item].emblem_of,
                "share": special.share,
                "avg_placement": special.avg_placement,
                "holder": special.holder,
                "holder_share": special.holder_share,
                "beside": list(special.beside),
                "adds": [_swap(swap) for swap in special.adds],
                "drops": [_swap(swap) for swap in special.drops],
            }
            for special in comp.specials
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
        "fielded": _fielded(comp),
        "categories": list(categories_of(comp)),
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
    ids: CompIds,
    floors: dict[str, str],
) -> dict[str, Any]:
    """Analyse the boards of one selection into the document the page reads.

    A comp takes the id `ids` remembers for it, so it has one id in every snapshot it is in.
    `floors` is each platform's lowest tier in its latest crawl. The snapshot names the
    platforms whose crawl went below Master, so the page can say its data is not all from
    the top of the ladder.
    """
    report = find_comps(boards, static)
    groups = tank_groups_last(find_item_groups(boards, static), report.comps)
    comp_ids = ids.assign(selection.set_number, [comp.core for comp in report.comps])
    comps = [
        _comp(comp, comp_id, name, static)
        for comp, comp_id, name in zip(report.comps, comp_ids, _names(report.comps, static))
    ]

    units = {unit for comp in comps for unit in [*comp["core"], *comp["three_stars"]]}
    units |= {unit for comp in comps for slot in comp["flex"] for package in slot for unit in package["units"]}
    units |= {pick["holder"] for comp in comps for pick in comp["items"]} | {u for g in groups for u in g.units}
    specials = [special for comp in comps for special in comp["specials"]]
    units |= {special["holder"] for special in specials}
    units |= {swap["unit"] for special in specials for swap in [*special["adds"], *special["drops"]]}
    units |= {s["unit"] for comp in comps for up in comp["level_ups"] for s in [*up["adds"], *up["drops"]]}
    units |= set(roster(static))
    units |= {key["unit"] for comp in comps for key in comp["key_units"]}
    items = {pick["item"] for comp in comps for pick in comp["items"]} | {i for g in groups for i in g.items}
    items |= {item for comp in comps for item in comp["take"]}
    items |= {item for comp in comps for spare in comp["spare"] for item in [spare["component"], *spare["uses"]]}
    items |= {special["item"] for special in specials} | {item for special in specials for item in special["beside"]}
    items |= {note["item"] for comp in comps for key in comp["key_units"] for note in key["build"]}
    recipes = _recipes(static, items)
    items |= set(recipes) | {part for parts in recipes.values() for part in parts}
    traits = {trait["trait"] for comp in comps for trait in comp["traits"]}
    traits |= {trait for unit in units for trait in static.units[unit].traits}
    traits |= {special["emblem_of"] for special in specials if special["emblem_of"]}
    traits |= {name.removeprefix(TRAIT) for comp in comps for name in comp["categories"] if name.startswith(TRAIT)}

    return {
        "schema": SCHEMA,
        "label": label,
        "team_code_set": static.mutator,
        "selection": {
            "set": selection.set_number,
            "since": selection.since.isoformat() if selection.since else None,
            "until": selection.until.isoformat() if selection.until else None,
            "platforms": list(selection.platforms),
        },
        "built_at": built_at.isoformat(),
        "newest_match": newest_match.isoformat() if newest_match else None,
        "below_master": below_master(floors, selection),
        "boards": report.boards,
        "unclassified": report.unclassified,
        "comps": comps,
        "item_groups": [_group(group) for group in groups],
        "recipes": recipes,
        "components": components_in_order(recipes, static),
        "units": {
            unit: {
                "name": static.units[unit].name,
                "cost": static.units[unit].cost,
                "traits": list(static.units[unit].traits),
                "icon": static.units[unit].icon,
                "planner_code": static.units[unit].planner_code,
                "row": usual_row(static.units[unit]),
            }
            for unit in sorted(units)
        },
        "items": {
            item: {
                "name": static.items[item].name,
                "icon": static.items[item].icon,
                "recipe": [static.items[part].name if part in static.items else part for part in static.items[item].components],
            }
            for item in sorted(items)
            if item in static.items
        },
        "traits": {
            trait: {
                "name": static.traits[trait].name,
                "icon": static.traits[trait].icon,
                "breakpoints": [breakpoint.min_units for breakpoint in static.traits[trait].breakpoints],
            }
            for trait in sorted(traits)
            if trait in static.traits
        },
    }
