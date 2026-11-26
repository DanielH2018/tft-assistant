"""Derive comps from final boards: a core of units, and the flex packages played around it.

Density clustering finds the comps on a sample of boards. Every board is then assigned to the
nearest comp it resembles closely enough, so the clustering's own "noise" label does not decide
how many boards count. A board that resembles no comp stays unclassified, and that share is the
health check on the method.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import HDBSCAN

from tft_assistant.boards import Board
from tft_assistant.comp_detail import (
    CompTrait,
    ItemPick,
    Tempo,
    TANK,
    KeyUnit,
    LevelUp,
    components_to_take,
    item_priority,
    key_units,
    level_ups,
    tempo,
    typical_traits,
)
from tft_assistant.static_data import StaticData

MIN_UNITS = 7
"""A board with fewer distinct units belongs to a player eliminated early; it describes no comp."""

MIN_CORE = 3
"""A group of boards that share fewer units than this is not a comp; its boards are unclassified."""

_FIT_SAMPLE = 15_000
_PACKAGE_FLOOR = 0.10
_PACKAGE_LINK = 0.60


@dataclass(frozen=True)
class FlexPackage:
    """Non-core units that are played together, with how the comp does when it holds them."""

    units: tuple[str, ...]
    share: float
    avg_placement: float


@dataclass(frozen=True)
class Comp:
    core: tuple[str, ...]
    carries: tuple[str, ...]
    main_trait: str | None
    boards: int
    share: float
    avg_placement: float
    top4: float
    packages: tuple[FlexPackage, ...]
    traits: tuple[CompTrait, ...]
    tempo: Tempo
    item_priority: tuple[ItemPick, ...]
    take: tuple[str, ...]
    """The components to take first, from the item priority."""
    level_ups: tuple[LevelUp, ...]
    key_units: tuple[KeyUnit, ...]


@dataclass(frozen=True)
class CompReport:
    comps: tuple[Comp, ...]
    boards: int
    unclassified: float


def _unit_ids(board: Board, static: StaticData) -> set[str]:
    return {u.character_id for u in board.units if u.character_id in static.units and static.units[u.character_id].traits}


def _vectors(boards: Sequence[Board], columns: dict[str, int], static: StaticData) -> np.ndarray:
    """One unit-length row per board. A costly unit or an itemised unit weighs more than a filler."""
    rows = np.zeros((len(boards), len(columns)), dtype=np.float32)
    for row, board in zip(rows, boards):
        for unit in board.units:
            column = columns.get(unit.character_id)
            if column is not None:
                weight = (1 + 0.25 * min(static.units[unit.character_id].cost, 5)) * (1 + 0.5 * len(unit.items))
                row[column] = max(row[column], weight)
    return rows / np.linalg.norm(rows, axis=1, keepdims=True)


def _centroid(rows: np.ndarray) -> np.ndarray:
    centroid = rows.mean(axis=0)
    return centroid / np.linalg.norm(centroid)


def _merge_variants(sample: np.ndarray, labels: np.ndarray, likeness: float) -> np.ndarray:
    """Relabel, in place, clusters whose centroids are alike: two variants of a comp are one comp.

    Density clustering separates a comp's variants when each is dense by itself. Merging them
    here is what lets a variant show as a flex package of its comp.
    """
    while True:
        found = sorted(set(labels) - {-1})
        centroids = np.array([_centroid(sample[labels == label]) for label in found])
        alike = centroids @ centroids.T
        np.fill_diagonal(alike, 0.0)
        if len(found) < 2 or alike.max() < likeness:
            return labels
        first, second = np.unravel_index(alike.argmax(), alike.shape)
        labels[labels == found[second]] = found[first]


def _packages(members: list[Board], core: set[str], static: StaticData) -> tuple[FlexPackage, ...]:
    held = [_unit_ids(board, static) - core for board in members]
    seen = Counter(unit for units in held for unit in units)
    flex = [unit for unit, count in seen.items() if count / len(members) >= _PACKAGE_FLOOR]
    together = Counter((a, b) for units in held for a in units for b in units if a < b)

    group = {unit: {unit} for unit in flex}
    for (a, b), count in together.items():
        if a in group and b in group and count / seen[a] >= _PACKAGE_LINK and count / seen[b] >= _PACKAGE_LINK:
            merged = group[a] | group[b]
            for unit in merged:
                group[unit] = merged

    packages = []
    for units in {frozenset(units) for units in group.values()}:
        holding = [board for board, flexed in zip(members, held) if units <= flexed]
        if len(holding) / len(members) >= _PACKAGE_FLOOR:
            packages.append(
                FlexPackage(
                    tuple(sorted(units, key=lambda unit: (-static.units[unit].cost, unit))),
                    len(holding) / len(members),
                    float(np.mean([board.placement for board in holding])),
                )
            )
    return tuple(sorted(packages, key=lambda package: -package.share))


def _comp(members: list[Board], total: int, core_share: float, static: StaticData) -> Comp:
    seen = Counter(unit for board in members for unit in _unit_ids(board, static))
    core = [unit for unit, count in seen.items() if count / len(members) >= core_share]
    core.sort(key=lambda unit: (-static.units[unit].cost, unit))

    key = key_units(members, static)
    carries = [unit.unit for unit in key if unit.role != TANK]

    reached = Counter()
    for board in members:
        for name, trait in board.riot_traits.items():
            if trait.tiers > 1:
                reached[name] += trait.tier / trait.tiers
    placements = [board.placement for board in members]
    picks = item_priority(members, static)
    return Comp(
        tuple(core),
        tuple(carries),
        reached.most_common(1)[0][0] if reached else None,
        len(members),
        len(members) / total,
        float(np.mean(placements)),
        sum(1 for placement in placements if placement <= 4) / len(members),
        _packages(members, set(core), static),
        typical_traits(members),
        tempo(members, static),
        picks,
        components_to_take(picks, static),
        level_ups(members, static),
        key,
    )


def find_comps(
    boards: Sequence[Board],
    static: StaticData,
    *,
    core_share: float = 0.85,
    merge_likeness: float = 0.7,
    fit_likeness: float = 0.7,
    min_cluster: int | None = None,
    seed: int = 0,
) -> CompReport:
    """Comps among the boards, largest first, and the share of boards that fit none."""
    eligible = [board for board in boards if len(_unit_ids(board, static)) >= MIN_UNITS]
    columns = {unit: index for index, unit in enumerate(sorted(static.units))}
    vectors = _vectors(eligible, columns, static)

    sample = vectors
    if len(vectors) > _FIT_SAMPLE:
        sample = vectors[np.random.default_rng(seed).choice(len(vectors), _FIT_SAMPLE, replace=False)]
    labels = HDBSCAN(
        min_cluster_size=min_cluster or max(10, len(sample) // 400),
        min_samples=5,
        cluster_selection_method="leaf",
        copy=True,
    ).fit_predict(sample)

    centroids, floors = [], []
    for label in sorted(set(_merge_variants(sample, labels, merge_likeness)) - {-1}):
        cluster = sample[labels == label]
        centroid = _centroid(cluster)
        centroids.append(centroid)
        floors.append(min(np.percentile(cluster @ centroid, 5), fit_likeness))
    if not centroids:
        return CompReport((), len(eligible), 1.0 if eligible else 0.0)

    likeness = vectors @ np.array(centroids).T
    nearest = likeness.argmax(axis=1)
    fits = likeness[np.arange(len(vectors)), nearest] >= np.array(floors)[nearest]

    comps = []
    for index in range(len(centroids)):
        members = [board for board, near, fit in zip(eligible, nearest, fits) if fit and near == index]
        if members:
            comp = _comp(members, len(eligible), core_share, static)
            if len(comp.core) >= MIN_CORE:
                comps.append(comp)
    comps.sort(key=lambda comp: -comp.boards)
    return CompReport(tuple(comps), len(eligible), 1 - sum(comp.boards for comp in comps) / len(eligible))
