# Slice 0 findings

Measured on 2026-11-26 against Riot's API with a development key, on Set 18 in its final patch.
Each entry says what was measured and what it changes.

## The API

| Measured | Result |
|---|---|
| Application limit, per routing value | 100 requests per 120 s and 20 per 1 s, on `na1` and on `americas` separately |
| Endpoint limits | match 200 per 10 s; match IDs 400 per 10 s; each league list 30 per 10 s and 500 per 600 s |
| NA apex ladder | 250 Challenger, 495 Grandmaster, 6,918 Master |
| Activity late in a set | Of 25 Challenger players, 20 had no match in the last 7 days. Their recent ranked games date from 11 to 21 November. |

The application limit binds; every endpoint limit is far above it. One pass over NA's ladder
costs 7,663 match-list requests, about 2.5 hours of the budget.

## The match payload

| Question | Answer |
|---|---|
| Does it name the patch? | No. `game_version` reads `TFT Unreal Version ?.?.?.?` on all 490 ranked matches checked. |
| Does it carry augments? | No. None of 3,920 participant records has an `augments` field. |
| Does it name an encounter or an unlock? | No field does. |
| What is `level`? | The player's level. Values from 5 to 10 appear. Riot's schema text, which calls it the Little Legend's level, is wrong. |
| Does it carry a trait tally? | Yes: `name`, `num_units`, `style`, `tier_current`, `tier_total` per trait. |
| Which queue is ranked? | 1100. Queues 1090, 1160, 1220, 1230 and 6080 also appear in a player's history. |

**A patch is a time window.** `sets.GameSet` holds a patch calendar per set, and a patch name
resolves to the window from its start to the next patch's start. The calendar is hand-kept, and
its starts are dates, so a match within hours of a patch release can land in the wrong patch.

## The join to static data

Every unit and every item on 2,000 real boards resolves to an `apiName` in Community Dragon's
document. A payload's `character_id`, trait `name` and `itemNames` entries are the join keys.

| Static-data field | Set 18 |
|---|---|
| Unit `role` | Null on 72 of 74 playable units. Set 17 fills it. |
| Emblem's trait | No structured link. The item is named `<trait name> Emblem`, and `static_data` matches on that. Two "Phantom Emblem" items match no trait. |
| Artifact marker | None as a field. 29 items carry the `DA_Artifact_` name prefix. |
| Unit forms | Lux appears as `DA_Lux18_Base`, `DA_Lux18_Blackthorn` and `DA_Lux18_Blossom`, each a unit record. |

**The `role` prior for item groups is unavailable in Set 18.** Item groups have to stand on item
distributions and attack range.

## Deriving comps

Measured on about 10,000 ranked boards of Set 18, part-way through the crawl.

| Method | Groups | Unclassified | Mean core size | Verdict |
|---|---|---|---|---|
| Rule: main carry + top trait | 580 | 0% | 4.3 | The 30 largest groups hold 39% of boards. One comp splits across many groups. |
| Rule: top two traits | 204 | 0% | 3.8 | Cores are loose: several comps share one trait pair. |
| Density clustering, default cluster selection | 22 | 25% | 5.7 | The largest group holds 10% of boards and has a core of one unit, Sivir. It lumps several comps. |
| Density clustering on leaf clusters, then merge, then assign | 27 | 19% | 5.1 | One group has a core under 4 units. `comps.find_comps` does this. |

Three steps make the last row:

1. Leaf clusters are small and tight, so no group lumps two comps.
2. Clusters whose centroids are at least 0.7 alike merge. Two variants of a comp become one comp,
   and the variant shows as a flex package.
3. Every board joins the nearest comp it is at least 0.7 like. Without this step 40% of boards
   stay unclassified.

The two thresholds trade against each other:

| Assignment likeness | Unclassified | Mean core size | Comps with a core under 4 |
|---|---|---|---|
| own members only | 40.0% | 5.70 | 1 |
| 0.7 | 19.1% | 5.11 | 1 |
| 0.6 | 10.1% | 4.67 | 4 |
| 0.5 | 3.6% | 4.33 | 7 |

The core threshold, at assignment likeness 0.6: 70% gives a mean core of 6.2 units, 80% gives
5.4, 85% gives 4.7, 90% gives 3.9.

**Flex packages show what a unit is worth to a comp.** In patch 18.7 the Riftbeast comp holds
Elder Dragon and Taric together on 47% of its boards. Those boards average 3.19 against 4.26
for the comp.

## Item groups

Measured on 16,208 ranked boards of Set 18.

`item_groups.find_item_groups` gives each unit the rate at which it holds each finished item,
over boards where it holds two or more, and groups units whose rates are alike. At a cosine
distance of 0.45 it finds 9 groups, and at 0.6 it finds 6. The five largest:

| Items held most | Units, cheapest first |
|---|---|
| Gargoyle Stoneplate, Warmog's Armor, Spirit Visage | Leona, Ornn, Rakan … Sett, Amumu, Maokai. Every one has attack range 1. |
| Jeweled Gauntlet, Spear of Shojin, Void Staff, Blue Buff | Karma, Pebbles, Veigar, LeBlanc, Teemo, Cassiopeia, Ahri, Morgana, Soraka, Zyra, Alune, Ivern, Lux |
| Infinity Edge, Last Whisper, Spear of Shojin, Deathblade | Cinderling, Varus, Gromp, Yunara, Kog'Maw, Ezreal, Sivir, Ashe, Elder Dragon |
| Guinsoo's Rageblade, Hextech Gunblade, Kraken's Fury | Xayah, Caitlyn, Kayle, Azir, Mama Beak, Tristana, Aphelios, Draven |
| Thief's Gloves, Edge of Night, Hand of Justice, Bloodthirster | Murkwolf, Diana, Gnar, Kennen |

**Cheap units hold items often enough to place.** The plan expected final boards to show few
holders, because players sell them. Every playable unit but one has at least 30 boards with a
two-item build, and 1-cost units have between 107 and 1,093. A group read in cost order is
therefore a holder chain from data, and the static `role`, which Set 18 leaves null, is not
needed.

## The trait module against Riot's tally

`traits.count_traits` counts unique units per trait plus emblems. On 2,000 boards its counts
differ from Riot's on 47%, always as an undercount. The shortfalls trace to single units:

| Trait short by one | Unit on the board | Share of short boards holding it |
|---|---|---|
| Riftbeast | Elder Dragon | 98% |
| Summoner | Krug | 99% |
| Lunar | Lux, base form | 96% |

Sprykin, Brawler and Elderwood fall short on boards with Ezreal, Taric, Kennen and Ivern. These
are unit rules that the static data does not record: a unit that counts twice, grants a trait,
or takes one on.

**A comp from real boards shows Riot's tally, which is exact.** The trait module serves boards a
user builds, where no tally exists. It needs a per-set table of trait adjustments, and this
comparison is the measure of that table: the mismatch rate falls as the table fills.
