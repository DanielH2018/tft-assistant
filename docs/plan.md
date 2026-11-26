# Plan

TFT Assistant is a personal second-monitor reference for live Teamfight Tactics games. It puts
a comp's core, flex packages, items, item group, holder chain, unlock conditions and early plan
on one screen, from a crawl of Riot's API.

## What the reference sites show

Each site holds one piece of the target, and none groups units across comps by the items they
share.

| Site | What to copy | What it lacks |
|---|---|---|
| [TFT Academy](https://tftacademy.com/tierlist/comps) | One click gives board, positioning, early units, a stage plan and items on one screen. A filter by comp style. | Hand-curated. The list shows portraits only. |
| [tactics.tools](https://tactics.tools/team-compositions) | Computed rows with name, placement, play rate and tempo tags. Core and flex on every row. A grid of which unit holds which item. | No positioned board and no stage plan. About 2 rows on the first screen. |
| [tftable](https://tftable.cc/meta) | About 28 comps on one screen. A primary board plus variants, each with its share. Items per unit ranked Core / Important / Optional. A "contested by" list. | No early game. No positions. |
| [datatft](https://www.datatft.com/kai#detail) | Real final boards from top lobbies. A per-unit placement delta inside a comp. | About 5 comps per screen. No early game. |

Early game and positioning exist only where a person wrote them. That is why the rule for every
manual field is: data proposes, the user edits.

## Constraints

| Fact | Consequence |
|---|---|
| A unit record in a match holds `character_id`, `tier` and `itemNames`, and nothing about position. | Positions come only from boards saved in the board editor. |
| A participant record has no per-round data. | Stage plans and strong early boards are hand-written, with suggestions. |
| A match payload names no patch. | A patch is a time window from the set's hand-kept calendar. |
| A participant record carries Riot's own trait tally. | A comp from real boards shows that tally. The trait module serves boards a user builds. |
| Riot enforces the rate limit per routing value. | Three regions crawl in parallel, each with 100 requests per 2 minutes. |
| League endpoints route by platform (`na1`, `euw1`, `kr`). Match endpoints route by region (`americas`, `europe`, `asia`). | `riot.py` maps one to the other. |
| A personal key is for a private project. Riot forbids public use of it and forbids showing augment win rates. | A deployment stays private, and it shows no augment win rates. |
| No source records unlock conditions. | A hand-kept file per set holds them. |
| A set lasts about four months and replaces the roster and at least one mechanic. | See *Built to take a new set*. |

## Pipeline

```
Riot API ──► crawl ──► SQLite (raw matches, indexed by set, patch, start time, region, queue)
                           │
Community Dragon ──► static data (units, traits, items, roles, icons)
                           │
          Selection ──► analyse ──► snapshot.json ──► build ──► static pages
                                                                    ▲
                              api (SQLite: edits, saved boards) ────┘ merged in the browser
```

- `snapshot.json` is the contract. Analysis writes one document per selection, and the pages read
  only that.
- The store keeps each raw payload. Re-clustering with a changed method costs no API requests,
  and a field Riot adds for a set is available without a second crawl.
- Edits merge in the browser. The pages stay static, and an edit shows without a rebuild.

## Selecting data

A `Selection` names a set, a time window, regions and a queue. It is the only way an analysis
reads boards, so every number on a page comes from a stated selection. A patch resolves to a
time window through the set's calendar, because a payload names no patch.

- The store indexes each match by set, start time, region and queue.
- A snapshot records its selection, its board count and the age of its newest match.
- The build job produces a fixed list of selections: the live patch, its last 24 hours, its last
  3 days, and the previous patch. A switcher on the page moves between them.
- `tft analyse` takes any selection on the command line. A custom range in the page arrives with
  the API in slice 4, which runs the analysis on request and caches the snapshot.
- A time window matters inside one patch: Riot ships balance changes that keep the patch number,
  and the first day of a patch differs from its settled state.

## The model

```
unit                        cost, traits, role, stats (static data, keyed by set)
  └─ unlock                 absent for a shop unit (hand-kept file, per set)
      ├─ condition text     as the game states it
      ├─ requires           predicates: units, traits and counts, items, level; or free text
      └─ checked at         the patch the entry was verified against

item group                  units whose item distributions are similar
  └─ unit ── holder chain   cheaper units → carry, by item overlap and role

comp core                   units present in nearly every board of a cluster
  ├─ flex packages          non-core units that co-occur, each package with a share
  ├─ unlocks                per unlockable unit: condition, met by the board or not,
  │                         share of boards holding it, placement with and without
  ├─ item priority          ordered (item → holder) pairs, plus components to take
  ├─ carries ──► item group
  ├─ key units              carry, second carry and tank, each with its build and item group
  ├─ tempo                  final-level and star-level distribution
  ├─ level-ups              per level above the usual one: units that come in, units that go out
  ├─ early plan             derived proposal + edits
  └─ saved boards           final or early (stage tag), with positions

board                       any set of units and emblems
  ├─ active traits          count, breakpoint tier, count for the next tier
  └─ unit suggestions       trait fit, pairing, item fit, where it leads

category                    reroll · XP · econ · items · one per trait · any the user adds
  ├─ comps                  derived by predicates, plus overrides
  ├─ augments               proposed from augment text, plus edits
  └─ encounters             proposed from encounter text, else by hand

condition                   an augment or an encounter
  ├─ categories             selecting the condition boosts the comps in them
  └─ direct links           one-off links to a unit's or a trait's comps
```

### How comps are derived

1. Each final board becomes a vector over the set's units. A costly unit or a unit holding three
   items counts for more than a cheap trait filler.
2. The job clusters the vectors. Slice 0 compares a rule (main carry plus its two largest traits)
   with density clustering, and the simpler one wins unless the other is visibly better.
3. Inside a cluster, a unit present in at least 85% of boards is core. The job groups the
   non-core units that co-occur into flex packages.
4. Two flex packages share a slot when the comp's boards hold both less than 30% as often as
   chance would put them together: one is played in the other's place. The page shows a slot
   cheapest option first, with an arrow to a costlier option, which is what the cheaper one is
   played until. The comparison needs 10 boards expected to hold both, so two rare packages that
   never met stay apart. A comp's default board takes the commonest option of each slot.
5. Each run matches its cores to the previous run's cores by overlap, so a comp keeps its ID, its
   name and its edits.
6. The page shows the share of boards that fit no cluster.

### How item groups are derived

1. Each unit gets a vector of how often it holds each item, counted over boards where it holds
   two or more.
2. Units with similar vectors form a group. The static `role` places cheap units that final
   boards rarely show with items.
3. Pivots are other carries in the same group. A holder chain is the cheaper units of a carry's
   group in cost order. A safe slam is an item that many strong cores use.

### What the data supports

| Want | From final boards |
|---|---|
| Core, flex packages, item priority and holders, safe slams, pivots, tempo, active traits | Yes |
| Filter by artifact or emblem | Yes, with thin samples for rare artifacts |
| Holder chains, opener to comp | Partly: overlap, not a record of real openers |
| Strong early boards, positioning, unlock conditions | No: by hand, with suggestions |
| Filter by augment, re-rank by encounter | No: categories kept by hand, proposed from text |

### Key units and level-ups

A carry holds 1.5 or more finished items on an average board of its comp. The tank is the most
itemised unit whose items are mostly defensive. The static data marks no item as defensive, so
the set file names the defensive and the offensive components, and an item is defensive when its
recipe has a defensive component and no offensive one. Counting an item with one defensive
component as defensive labelled a carry holding Edge of Night and Quicksilver as a tank.

Each key unit carries build notes from the comp's own boards. An item is critical when 70% of
the unit's builds hold it, or when 40% do and builds without it place 0.4 worse. An item needs a
partner when it places 0.5 better beside that item than apart from it, and by 0.25 more than the
partner helps without it. A fixed template such as "a mana item, a damage item and an amplifier"
was rejected, because it does not always hold; the data decides. Only builds of the unit's usual
size are compared: a build holding both of two items is otherwise a more finished build than one
holding either, which made nearly every item appear to need a partner.

A level-up compares the comp's boards that end one level above with the boards one level below:
a unit whose share rises by 15 points comes in, and one whose share falls by 15 goes out. A level
is reported once 20 boards and 5% of the comp end there. The placement at a higher level is
better partly because only a winning player reaches it.

### Emblems and artifacts

A comp lists the emblems and the artifacts its boards hold: up to three emblems, then up to two
artifacts, commonest first. An item is listed once 20 boards and 3% of the comp hold it. Each
row gives the unit that most often holds it, the finished items that unit builds beside it, and
the units that come in and go out: those whose share differs by 15 points between the boards
with the item and the boards without. A Fae Emblem on Kayle brings Lillia in and pushes Ornn
out. Each figure is a correlation, because a player who was offered an emblem made other choices
too.

The static data marks no item as an artifact, so the set file gives the start of an artifact's
API name. The list's filter box searches item names as well: the items of the item priority, of
the key units' builds and of this section. A filter that is part of one name, such as
`fae emblem`, lists the comps with that name; any other filter lists the comps that hold every
one of its words.

### Team codes

Each comp has a "Copy team code" button, which copies a code Riot's in-game team planner
accepts. The code holds the comp's core and the flex packages picked on the page. A click on a
flex package picks it or drops it, and picking one option of a shared slot drops the others. A
comp opens with the packages its default board holds.

The format is `02`, then ten units as three lower-case hex digits each with `000` for an empty
place, then the set's name, such as `TFTSet18`. Riot documents none of it. The format comes from
the README of [nkhoit/tftkit](https://github.com/nkhoit/tftkit), and two of its example
numbers match Community Dragon's `tftchampions-teamplanner.json`, which holds each unit's
number. The planner lists one unit where the roster has a variant per origin, named
`Unit (Origin)`, so a variant takes the number of the unit it is a variant of. A code carries
units only: no positions, stars or items.

The picks are kept in the page's memory and are gone on a reload. Saved picks arrive with the
saved boards of slice 5.

### Least-used components

The Items section ends with the two components a comp uses least and where its boards put
them: the (item, holder) pairs built with each on 5% of the comp's boards, most common first. A
comp that uses few Rods shows Crownguard on its tank. A component's use is counted over the
recipes of every finished item on the comp's boards.

A share threshold for "unwanted" was tried and dropped. A comp's finished boards use every
component, at shares between 6% and 25% on patch 18.7, so half the even share marked nothing in
any of 26 comps.

### Comp style

A comp's style is the name players give its tempo, and it comes from what the comp rolls for.
The level a comp's boards end at is not used, because a winning board levels past the point at
which its comp was built: a comp carried by 4-cost units is a level 8 comp even when half its
boards end at level 9.

- A comp that takes a unit of cost 3 or less to three stars on 40% of its boards is a reroll
  comp: `1-cost reroll`. The cost is the main carry's when the carry is one of those units, and
  otherwise the costliest of them.
- Any other comp plays at the level that finds its main carry: `Level 8` for a 4-cost carry and
  `Fast 9` for a 5-cost one.
- A comp whose carry is cheap and not three-starred takes the level most of its boards end at.

A player finds a unit four levels above its cost, so a 1-cost reroll comp rolls at level 5 and a
3-cost one at level 7. The snapshot carries that level as `roll_level`.

The comp list shows the roll level as its Level column, and the detail pane's heading shows the
style. The list sorts by a click on a column header and opens sorted by tier.

A "names" checkbox beside the filter box shows or hides each unit's name under its picture on
the comp page, and the browser keeps the choice. A unit's traits are in its tooltip, not under
its picture.

### How the page fits a screen

The detail pane never scrolls and leaves no empty band beside its content. Its content is laid
out at the pane's width divided by a scale, and drawn at that scale, so it always spans the
pane. A larger scale gives a narrower layout, which wraps more rows and stands taller. The page
takes the largest scale whose layout still fits the pane's height, between 0.4 and 2.

One scale serves every comp of a snapshot, so the content does not change size from comp to
comp: it is the scale that fits the tallest comp. A comp that still does not fit takes a smaller
one. Two earlier designs failed. A layout that only reflows cannot promise a fit, because a
narrower pane wraps rows and grows taller. A layout of fixed width, scaled down, left an empty
band on the right of any pane wider than the layout.

The list's columns have fixed widths and never move. A list too narrow for all of them drops
whole columns from the right: Play, Top 4, Avg, Core, then Level. The list opens 660 pixels
wide, or 40% of a narrower window. The border between the list and the detail pane drags; the
browser keeps the width, and a double-click on the border resets it. The detail pane marks the three-starred units on their pictures.

### Comp names

A comp is named `<main trait> <main carry>`. The main trait is the comp's largest vertical, a
tiered trait with four or more units. Without a vertical it is the main carry's largest active
trait. An earlier rule took the trait closest to its top tier, which named a board of seven
Elderwood units after a two-unit trait.

Two comps that would share a name are told apart by the trait their two carries share, which
replaces the carry: `Elderwood Executioners` beside `Elderwood Ezreal`. Comps that still share a
name each take the costliest core unit the others lack. The carry trait is used only on a clash,
because a carry's name identifies a comp better than a second trait does. Naming a comp by hand
arrives with the edits of slice 4.

A key unit lists the units of its item group that cost less than it does, cheapest first, as the
units that can hold its items.

### Default positions

A match payload records no positions. Until a board is edited by hand, `positioning.default_board`
puts each unit in the row it usually takes: the row of its attack range, or of its role where the
range is missing. Tanks stand central in the front row, and carries take a back corner. A
snapshot marks such a board `board_is_default`, and a saved board replaces it.

### Assistance for the manual parts

Every manual field starts from a derived proposal. The board editor scores candidate units on
four signals and names the signals beside each suggestion: trait fit, pairing in real boards,
item fit for the target carry, and whether strong cores keep the unit. The data shows that an
early board is coherent. It does not show that the board wins stage 2.

## Built to take a new set

```
core: the same every set        per set: data, no code          per mechanic: one module
────────────────────────        ───────────────────────         ────────────────────────
match, board, unit on board     static data (the roster)        unlocks
comp core, flex package         set file: source, mechanics     encounters (a condition kind)
item group, pairing table       hand-kept files (unlocks)       augments   (a condition kind)
category, condition             edits, saved boards,            a later set's mechanic
trait module, predicates        category assignments
selection, snapshot schema
```

1. The core names no unit, trait, item or mechanic.
2. A set is a directory under `src/tft_assistant/data/sets/`: a set file that names the
   static-data source, the ranked queue, the patch calendar and the set's mechanics, plus the
   hand-kept files.
3. A mechanic is a module behind one interface. It reads its own data file and the raw payload,
   and returns annotations, pane sections, condition kinds and suggestion signals.
4. The detail pane renders sections generically, so a mechanic changes neither the snapshot
   schema nor the pages.
5. One predicate vocabulary serves every hand-kept file: unlock conditions, category membership
   and any later mechanic.
6. `tft new-set` scaffolds a set directory and reports what the set needs: payload fields and
   static-data fields the tool has not met, unlockable units with no entry, and augments with no
   category.

Category definitions, predicates, methods and mechanic modules carry across sets. Category
assignments, the unlock file, edits and saved boards are per set. A finished set stays readable
behind a set switcher.

A mechanic that changes what a board is, such as two boards per player, needs a core change.

## The main view

```
+---------------------------+--------------------------------------------------+
| [unit/trait] [item]       | Comp name     avg 4.02   play 14%   n=3,812      |
| [augment]    [encounter]  | fast 9  ·  contested by: Comp B, Comp C          |
| patch [v]  window [v]     | core   [u][u][u][u*]                             |
| S  Comp A     4.02  14%   | flex   [A C] 41% 3.9 · [B* D] 33% 4.2 · [E]/[F]  |
| S  Comp B     4.10  17%   | unlocks u* field 3 Trait A · met by the core     |
| A  Comp C  ^  4.21   6%   | traits 6 Trait A (8 next) · 4 Trait B · 2 Trait C |
| A  Comp D     4.30   5%   | items  1. X → carry 1   2. Y → carry 1           |
| ...  about 25 rows        |        take: bow, rod, belt                      |
|                           | group  AD backline  →  pivots: U, V              |
| data 3h old · 81k boards  | holders  1-cost → 2-cost → 3-cost → carry        |
| 9% unclassified           | early  derived units + notes · saved board       |
+---------------------------+--------------------------------------------------+
```

The default view needs no input. A unit, trait, artifact or emblem narrows the list. An augment
or encounter re-ranks it and marks each row that moved. Nothing is hidden by a condition.

## Slices

Each slice ends with something to use.

| # | Slice | Exercised by | Needs |
|---|---|---|---|
| 0 | Spike: crawl one region for a few hours, cluster, write a report. | Reading the report. | Development key |
| 1 | Comps view: list and detail pane from a real snapshot, with traits, item priority, unlocks and the patch and window switcher. | Using it on the second monitor in a game. | Slice 0's data |
| 2 | Unattended: image, k3s role, three regions, stable comp IDs, `new-set`, set switcher. | Loading the site and reading data a few hours old. | Registered personal key |
| 3 | Item groups: groups view, pivots, holder chains, safe-slam grid, artifact and emblem filter. | Checking a slam decision in a game. | |
| 4 | Edits and conditions: notes, stage plans, categories, augments and encounters, custom selections. | Putting an encounter in `reroll` and watching reroll comps move up. | |
| 5 | Board editor: planner, early boards, unit suggestions, saved boards that replace a comp's default board. | Building a stage 2 board from the suggestions. | |
| 6 | Explorer: filter boards by units, items, traits and level, and read the stats of units, items and traits under that filter, as [tactics.tools' explorer](https://tactics.tools/explorer) does. | Asking a question the comp list cannot answer, such as how a unit does with one item. | The API from slice 4, or the boards shipped to the browser |

[slice-0-findings.md](slice-0-findings.md) records what slice 0 has measured. Slice 0's report answers: requests and matches per hour, whether the comps and item groups are
recognisable, the first-day sample size, which core threshold reads best, whether the flex
packages match real play, which fields a real payload fills, how often the trait module
disagrees with the payload's own trait tally, and where a set's static data comes from at
launch.

## Decisions

- The repository is public. A deployment stays private, because Riot forbids public use of an
  app on a personal key. The key, crawled data, personal notes and deployment hostnames stay out
  of the repository. Icons are fetched at build time.
- The crawl covers NA, EUW and KR, Master and above.
- SQLite holds the matches and the edits.
- The unlock file is seeded from a guide once per set and then corrected by hand. It lives in
  the repository, because unlock conditions are facts about the game.
- The list sorts by average placement, with a play-rate floor.
- A condition re-ranks and never hides.
