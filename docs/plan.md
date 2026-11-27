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
| No source records unlock conditions for Set 18. | A hand-kept file per set holds them. See *Data Dragon from Set 19.1* for what replaces it. |
| A set lasts about four months and replaces the roster and at least one mechanic. | See *Built to take a new set*. |

### Data Dragon from Set 19.1

Riot's [developer page](https://developer.riotgames.com/docs/tft#data-dragon) announces a
Data Dragon export from a different pipeline, starting with 19.1 on 2026-12-01. The tool reads
Community Dragon, and the page says nothing about it. Read on 2026-11-26, the page lists these
changes that bear on the plan:

- **Unlock conditions are in the export.** They lose `traitId`, `traitName`, `traits`,
  `requiredContributionCount` and `requiredTotalStarLevels`. Check the export before seeding
  the Set 19 unlock file by hand: it may fill the file, or replace it.
- **Encounter data is added**, in `tft-encounters.json`. The augment and encounter categories
  of a later slice can start from it.
- **Identifiers change shape.** The page's example is `TFT16_Ahri` becoming `DA_19_Ahri`. No
  code here names a set's prefix, but the first Set 19 crawl is the check that a match's
  `character_id` still joins to the static data's unit ids.
- **Description markup changes.** The deferred unit and trait descriptions (*Hover cards*)
  were blocked on Community Dragon's calculated values. Read the 19.1 export before resuming.
- **Champion square icons are added**, and the sprite sheets are removed.

The page states that further, smaller changes may follow. None of it is verified against a
19.1 export, which does not exist before 2026-12-01.

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

### Which ranks the crawl reads

A crawl walks one platform's ladder from the top: Challenger, Grandmaster, Master. Those are
the ranks the page is meant to show. It goes on below Master, Diamond I first and a page of
players at a time, only while it has listed fewer than `--min-players` players, 1,000 unless
told otherwise (`crawl.MIN_PLAYERS`).

A new set starts with nobody in Master, and Challenger and Grandmaster stay empty for its first
weeks. Without the lower tiers a crawl then lists no player and the page has no comps. With
them, the first days read Diamond and whatever tier it takes to list 1,000 players, and the
lower tiers drop out by themselves as Master fills: late in Set 18 an hour's crawl listed about
2,800 Master-and-above players per platform and never reached Diamond.

The rule counts players, not matches, because a crawl learns how many matches it has only
after it has spent the requests. A crawl's report line says how far down it went: `down to
diamond II`.

The page says so too. A crawl records the lowest tier it listed on its platform
(`Store.note_floor`), and a snapshot names the platforms of its selection whose latest crawl
went below Master (`below_master`). The line under the list then ends `ranks down to Diamond II
on KR`, and says nothing when every platform stayed in Master and above. It describes the
latest crawl, not each match: the store does not record which rank a match came from, and a
match holds eight players of mixed ranks. Matches from an earlier, deeper crawl stay in a
selection until they age out of it.

### The unattended run

`tft refresh` keeps a deployment current. It builds the page from the matches the store holds,
then crawls and builds again once a cycle. The first build comes before any crawl, so a
restarted run has a page within seconds. A crawl that walks the whole ladder before its cycle
ends waits out the cycle.

The run is one process with one directory. `TFT_STATE_DIR` names the directory, which holds the
match store, the static-data cache and the built page. The run serves nothing: a static file
server reads the page from the same directory. A crawl that fails does not end the run: the run
prints the failure, builds from what the crawl stored, and crawls again next cycle. The page
that was built last stays up meanwhile, and its footer states the age of its newest match, which
is how a reader learns of an expired key.

Until release 0.2.7 a failed crawl ended the run. A development key expires after 24 hours, so
on 2026-11-27 the crawler container of the deployment restarted in a loop, its pod read as not
ready, and the deployment read as unavailable while the page itself was up. A container that
shares a pod with the page must not exit over a condition that outlasts a restart.

Two bounds keep a run that never stops inside a fixed budget:

- **Memory.** A build holds every board of a selection in memory, so a selection is analysed
  from its newest 20,000 matches at most (`cli.MAX_MATCHES`). The snapshot's label and its
  recorded window say so when the cap applies.
- **Disk.** After each crawl the run deletes matches that started more than `--keep-days` ago,
  30 unless told otherwise. That covers the live patch and the one before it. SQLite reuses
  the freed pages, so the store's file stops growing.

CI builds and proves the image on every commit and publishes it when a version tag is pushed.
A deployment follows releases, so it moves when a release is cut and not on every merge. A
set's patch calendar is part of the image, so a new patch reaches a deployment as a release.

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
  ├─ key units              carry, 2nd carry and tank, each with its build and item group
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
5. Each analysis matches its cores to the cores a file remembers, by overlap, so a comp keeps its
   id from run to run and has one id in every snapshot of a page (`comp_ids.py`). Two cores are
   one comp when they share at least 60% of the units either has: a core of five that swaps one
   unit keeps its id, and one that swaps two does not. The file is `keep/comp-ids.json` beside the
   match store, with one table per set. A comp's name is derived again in each snapshot, so one
   id can read under two names in two selections. On 108,760 stored boards the patch snapshot
   and the 3-day snapshot share 24 of 26 ids; ids made from the core alone shared 17.
6. The page shows the share of boards that fit no cluster.

### How item groups are derived

1. Each unit gets a vector of how often it holds each item, counted over boards where it holds
   two or more.
2. Units with similar vectors form a group. The static `role` places cheap units that final
   boards rarely show with items.
3. Pivots are other carries in the same group. A holder chain is the cheaper units of a carry's
   group in cost order. A safe slam is an item that many strong cores use.

### The Items tab

The side panel has three tabs, and the browser keeps the open one across a reload. *Planner* has its own section below. *Comps* is the
list beside one comp's page. *Items* puts the slam grid in the side panel and the item groups
in the pane beside it. The groups tanks build in come last (`snapshot.tank_groups_last`): a
group is one of those when more of its units are some comp's tank than some comp's carry.

The slam grid has a row and a column for each component, and the item two components build
stands where they cross. The components run in the owner's order, across and down: sword, bow,
chain vest, negatron cloak, rod, tear, belt, glove, spatula, pan. `snapshot.COMPONENT_ORDER`
holds it as id endings, because a set changes an id's prefix and keeps its ending, and the
snapshot's `components` field carries the ordered list to the page. The snapshot's `recipes` field lists every item of the components in
play, whether or not a comp builds it. The static data also holds earlier sets' recipes under
other component names, so the components in play are the ones the comps' own items are made of.
The number on an item is how many comps of tier B or better build it, counted from each comp's
item priority, its key units' builds and its emblems. An item a third of those comps build is
outlined as safe. An item none builds is dimmed. A hover card names the comps and the unit that
holds the item in each.

A click on a component lights its row and column. A click on an item picks it, which orders
the item groups for it and stays on the tab; a second click, or *Clear*, undoes it.

Each item group is one row: the items its units hold most, then its units, the best placed
first. A group's `held` field gives each unit its average placement over the boards where it
holds two or more finished items, and for each item it holds on a tenth of them or more, the
share of those boards and its placement there (`item_groups.Held`). With an item picked, the
groups whose units hold it come first and are marked, and within every group the units that
hold it lead, by share and then by their placement with it. A unit that is a comp's main carry
is outlined. A click on a unit or an item of a group opens the comps tab with its name as the
filter. The group's `units` stay cheapest first in the snapshot, which is the order a holder
chain reads in.

With the list hidden, the comp page has the whole window and the tabs are out of reach until
the list is back.

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

An emblem's row also says what it makes: the count of its trait with the emblem on a unit that
lacks the trait, beside the comp as it is usually fielded. The row is marked when that count is
a breakpoint the usual board does not reach, and its hover card gives the count without the
emblem, the trait's breakpoints and, when the emblem reaches none, the next one. The snapshot
carries the trait as the row's `emblem_of`.

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

The Items section ends with the two components a comp uses least and the items its boards
build with each: the two most built, of those the boards hold 0.05 times per board or more. A
comp that uses few Rods shows Crownguard. The section names no holder. A component's use is
counted over the recipes of every finished item on the comp's boards.

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
style. The list sorts by a click on a column header and opens sorted by tier. A column's own order
puts the best or the most first, and the header shows a down arrow for it. A second click on
the sorted column reverses the order and the arrow.

The filter box holds several filters at once. Enter keeps the typed filter as a chip and starts
another, Backspace in the empty box removes the last chip, and each chip has an X. The list
shows the comps that pass every chip and the text being typed.

A "names" checkbox beside the filter box shows or hides each unit's name under its picture on
the comp page, and the browser keeps the choice. A unit's traits are in its tooltip, not under
its picture.

### How the page fits a screen

The detail content keeps one size. It is laid out at the pane's width and wraps to it, and the
pane scrolls down when the content is taller. Nothing reaches past the pane's right edge: every
row wraps, and only a pane too narrow for the widest thing that cannot wrap draws the content
smaller.

Sections share a row while their widths fit it, then start the next row. A section is as wide as
its content laid on one line, so a section with little content leaves room for its neighbour,
and one with a lot takes a row and wraps inside it. Four sections wrap by nature and ask for a
fixed width instead: Traits asks for 300 pixels, and Key units, Items, and Emblems
and artifacts ask for 480 each. The rows form in two groups, so Key units always starts a row:
Core, Traits, Flex and Level up, then Key units, Items, and Emblems and artifacts. Positioning
has the full width under them. A click on a section's heading folds the section to its heading
or opens it again, and the browser keeps the folds. A folded section keeps a row to itself, so
a fold changes the page's height and moves no other section sideways.

Figures the operator does not read during a game are in hover cards, not on the page: a level's
share of boards and placement, a unit's share at a level, and an emblem's or artifact's share
of boards.

### Icons

A build copies every icon its snapshots name into `icons/` beside the page (`icons.mirror`), and
the snapshots name the copies. The page's own server then serves them, over the connection the
page came on. Community Dragon serves an icon with an hour's cache life, so a browser asked a
second host about every icon again each hour: 188 icons, about 2.7 MB, for the 26 comps of
patch 18.7.

A copy is named by a digest of its picture, so its address changes when the picture does. The
server tells a browser to keep an icon for a year, and to ask whether the page changed each time
it loads it: a kept page would name icons a later build removed. A build downloads an icon at
most once a week, keeps the download in the cache directory, and removes the copies no snapshot
names. An icon that cannot be downloaded keeps its Community Dragon address, so the page still
shows it.

The copies are the 128-pixel pictures as Community Dragon serves them. The page draws them at
16 to 48 pixels, so smaller copies would cut the first load, at the cost of an image library in
the build. Not done: after the first load a browser has them all.
||||||| parent of 6297b40 (Hide low play rate comps behind a switch, and list a comp's subcomps under it)
### Low play rates and subcomps

Two switches sit under the filter box, and the browser keeps both.

**Show low play rate comps.** The list leaves out a comp that under 1% of boards play, until the
switch asks for it. On the 18.7 matches that is 6 of 26 comps, and the switch's label counts
them. The smallest, 68 boards, read as an A tier comp on the default list. The switch changes
the list only: a filter, the Items tab and the planner still read every comp, and a comp opened
from another tab opens although the list leaves it out.

**Expand all subcomps.** A subcomp is a comp with one of its flex packages: the boards of the
comp that add those units to the core. Its row sits under the comp's row, set in, with the
package's units and its own average placement, top 4 rate, win rate and play rate. A board can
hold two packages, so two subcomps of a comp can share boards and their play rates can add up to
more than the comp's. The switch opens every comp, and the mark before a comp's name opens or
closes that comp alone. A click on a subcomp row opens its comp. A column sorts the comps, and
each comp's subcomps follow it, most played first.

The other definition, each distinct set of flex units as a subcomp, splits a comp's boards with
no overlap. It was not taken: a comp with seven packages has dozens of such sets, most of a few
boards each, and the packages are what the comp page already shows.

### Hover cards

One box is the hover card of the whole page. It shows at once, under the thing the pointer is
on, and the page sets no native tooltip on its content.

- A unit's card names the unit, its cost and its traits, then what that place on the page says
  about it, such as its share of boards at a level.
- A trait's card gives the count on a usual board, the tier, the trait's breakpoints, and the
  comp's core units that have the trait.
- An item's card names the item and the components it is built from.
- An "i" beside a section's heading explains how to read the section. Explanations that stood
  on the page as sentences live there, including the thresholds for "critical" and "needs".

A card does not say what a trait or a unit's ability does. The operator asked for both on
2026-11-26 and then deferred them. What a first look at Set 18's data found:

- **Traits can be filled in from the summary document.** A trait has a `desc` template and one
  `effects` entry per breakpoint, each with a table of variables. 92 of the 239 variables the
  templates name sit under a hashed key such as `{2c61751d}`. The key is the 32-bit FNV-1a hash
  of the variable's lower-cased name, written in hex between braces. Matching by that hash
  resolves 239 of 239. The n-th `<row>` of a template reads the n-th breakpoint's variables.
- **Abilities cannot.** The summary gives an ability's name and its template, but its
  `variables` list is empty for 72 of the 74 Set 18 units. Older sets have the list. The
  templates name calculated values such as `@MagicDamageCalc1@`, which no list of raw values
  holds: they come from the spell's calculations and the unit's stats at each star level.
- **Where the spell data lives is open.** Community Dragon's raw map file
  (`game/data/maps/shipping/map22/map22.bin.json`, 70 MB) holds a `TftCharacter` record per unit
  and 638 spell objects, and none under a Set 18 unit's name.

A layout of two fixed columns was built on 2026-11-26 and replaced the same day. It put Level up
and Flex in columns too narrow to lay their content on one line, and left the rest of each
column empty.

Two designs that scaled the content to the pane's height were built and dropped on 2026-11-26.
One laid the content out at a fixed width and scaled it down, which left an empty band beside
it. The other searched for the largest scale that fit the height, which drew a one-column page
at 0.78 of full size with half the pane's width unused. The operator's rule is that the height
may overflow and the width may not.

The list's columns never move. Every column has a fixed width but Comp, which is as wide as the
longest name in the snapshot, between 90 and 360 pixels: a comp renamed to a longer name widens
it. A list too narrow for all of them drops whole columns from the right: Play, Win, Top 4, Avg,
Core, then Level. A row wraps and shows its first line only, which is what drops them. Win is
the share of a comp's boards that place first. The list opens at the width that shows every
column, wherever that leaves the comp page 520 pixels. In a narrower window it opens narrower. The
border between the list and the detail pane drags right until the list shows every column and
no further, because a wider list only adds empty space. In a narrow window it also stops where
the comp page is 300 pixels wide, so the list reaches every column in any window 1,024 pixels
wide or more. The stylesheet's `--full-list` adds the Comp column's width, which the script measures, to the
width of the rest. The browser keeps the width that was asked for, and a double-click on the border resets it. The detail pane marks the
three-starred units on their pictures.

A button in the comp page's top left corner maximizes the page: the list goes to no width and
the page has the whole window. The button then restores the width the list had. A drag of the
border past the middle of the narrowest list, 130 pixels, maximizes the page too, and a drag
back out brings the list back. The button's face follows the list's width, so it reads the same
after a click and after a drag. The arrow keys still move through the list while it is hidden,
and the browser keeps a maximized page across a reload.

### Edits

`tft serve` serves the built page and an API over the edit store (`serve.py`, `edits.py`). The
page asks `api/edits/<set>` once when it opens, and a comp page can then be changed where it is
read: its name, its notes, its categories and its board. Each change is saved at once with
`PUT api/edits/<set>/<comp id>`, and a field set to nothing removes it. A page that gets no
answer, such as one opened from a file or served by a plain file server, shows nothing to
change, so the page still works as a static file.

A click on the name in a comp's heading turns it into a box. Enter or leaving the box keeps the
name, Escape drops the change, and an empty box goes back to the derived name.

An edit is keyed by set, comp id and field, which is why a comp's id has to hold between runs
(*How comps are derived*, step 5). The store takes the fields `edits.FIELDS` names, each with a
longest text: `name`, `plan`, `categories`, `board` and `notes`. The API takes JSON only: another site's page can post a
form with the reader's login, and cannot send JSON without the browser asking the server first.

The edit store and the comp ids its rows are keyed by are the files no API gives back. Both sit
under `keep/` in the state directory, and a deployment keeps that directory on storage that is
backed up, apart from the match store.

### Notes

A comp page has a *Notes* section, called *Plan* until 2026-11-27. Its lines are derived in the page from the snapshot, one for
each thing the comp's boards can say:

- the components to take first, from the item priority;
- the cheaper units of the main carry's item group, which hold its items until it arrives;
- the level to roll at and the units to three-star, or the level to reach before rolling;
- the levels its boards end at, for each level 15% of them or more end at.

The derived lines need no server, so a page opened from a file shows them. With `tft serve`, a
box above the list adds a line of the reader's own on Enter, at the top. Every line, derived or
not, has a button to reword it and one to remove it.

The `plan` field of the comp's edit holds only what the reader changed, as JSON: `own`, their
lines; `hidden`, the kinds of the derived lines they removed; and `changed`, their words for a
derived line by its kind. A derived line has a kind (`take`, `holders`, `roll`, `ends`) because
its words change with every build. A derived line the reader left alone therefore keeps
following the data, and one they reworded keeps their words. *Restore the derived lines* clears
`hidden` and `changed`, and a plan with no change left is stored as nothing.

Two older forms are read as lines of the reader's own: a `plan` of plain text, and the free text
of the `notes` field, which a separate *Notes* box wrote until 2026-11-27. The next save of the
comp's notes moves that text into `plan` and clears `notes`.

A match records no per-round data, so nothing here is a stage-by-stage plan from the data: the
lines say what the final boards imply, and the stages are the reader's to write.

### Comp categories

A category groups comps that want the same thing from a game. `categories.py` derives each
comp's categories from its boards, and the snapshot carries them as the comp's `categories`:

| Category | The comp is in it when |
|---|---|
| `reroll` | its boards take a unit to three stars |
| `fast-9` | it takes no unit to three stars and rolls at level 9 or later |
| `items` | its carry has an item marked critical |
| `trait:<id>` | a trait with more than one breakpoint has 4 or more units on its usual board |

The rules name no unit, trait or item of one set. On the 18.7 matches the 26 comps give 12
`reroll`, 2 `fast-9`, 21 `items` and 9 traits. `items` holds four comps in five, so it separates
little on this patch.

The filter box finds comps by category, as it does by unit or item: `reroll` lists the reroll
comps. A row of chips above the list did the same until the owner asked for it to go on
2026-11-27. A comp page shows its categories under its statistics as tags, each word
capitalised: `Reroll`, `Fast 9`, `Item Dependent` for `items`, and the trait's name. With `tft serve`, each has a button that
takes the comp out, and a box puts the comp in a category by name. A name no category has starts
one of the reader's own. The changes are the `categories` field of the comp's edit: a
comma-separated list where `-reroll` takes the comp out of a derived category and any other
entry puts it in one. Putting back what was taken out removes the entry, so the field holds only
what differs from the rules.

Augments and encounters join these categories once Set 19 matches exist to check them against:
a condition names the categories it helps, and choosing it moves their comps up.

### Comp names

A comp is named `<main trait> <main carry>`. The main trait is the comp's largest vertical, a
tiered trait with four or more units. Without a vertical it is the main carry's largest active
trait. An earlier rule took the trait closest to its top tier, which named a board of seven
Elderwood units after a two-unit trait.

Two comps that would share a name are told apart by the trait their two carries share, which
replaces the carry: `Elderwood Executioners` beside `Elderwood Ezreal`. Comps that still share a
name each take the costliest core unit the others lack. The carry trait is used only on a clash,
because a carry's name identifies a comp better than a second trait does.

A reader can name a comp by hand, in the box above its notes. The name is an edit, so it
needs `tft serve`. It replaces the derived name in the list, in the page's heading and in the
hover cards that name the comp, and the filter box finds the comp by either name. Clearing
the box goes back to the derived name.

A key unit lists the units of its item group that cost less than it does, cheapest first, as the
units that can hold its items.

A carry and a 2nd carry also list their pivots: the main carries of other comps that are in the
same item group and outside this comp's core. A pivot is where the carry's items go if the comp
is dropped. The row runs from the best average placement, a hover card names the comp a pivot
carries, and a click opens that comp. A unit that carries several comps opens the most played
one. A tank lists none, because a tank's items fit most front lines.

### Default positions

A match payload records no positions. Until a board is edited by hand, each unit stands in the
row it usually takes: the row of its attack range, or of its role where the range is missing.
Tanks stand central in the front row, and carries take a back corner. The board is the comp
page's last section, Positioning, at full width under the others.

The board holds the comp's core and the flex units picked on the page, so it changes with a
pick. That splits the work in two. `positioning.usual_row` gives each unit its row, and the
snapshot's unit table carries it. The page's `standing` places the units within the rows,
because only the page knows which flex units are picked. A comp's `fielded` units are the picks
a page opens with: its core, then the commonest option of each flex slot, up to its usual
level.

### Saved positions

With `tft serve`, the reader drags a unit on a comp's board to another hex, and dropping it on
a unit swaps the two. The page then saves the place of every unit on the board as the `board`
field of the comp's edit: a JSON object from unit id to `row,column`. Saving every unit, and not
only the one that moved, keeps the board as the reader left it when a later crawl changes the
derived places.

The places are kept per unit, not per board. A comp's board changes with the flex units picked,
so a place is remembered for a flex unit that is not picked just now, and a unit with no place
takes its derived hex, or the nearest free one when the reader put something there. *Derived
positions* under the board clears the field.

### The planner

The *Planner* tab is a board the reader fills from the roster. The side panel lists the units a
player can buy by cost: the ones Riot's team planner lists that have a trait (`snapshot.roster`),
which leaves out a training dummy or an anvil. The snapshot's unit and trait tables carry the
whole roster for it, where they used to carry only the units some comp fields.

A click on a roster unit puts it on the board, in the free hex of its usual row nearest the
centre, and a second click takes it off. On the board a unit drags to another hex, a drop on a
unit swaps the two, and a click takes it off. The pane shows:

- the traits the units field, each with its count and next breakpoint, the ones that reach a
  breakpoint first;
- a team code for the board, the first ten units;
- the comps whose core the board holds most of, each with the core units still missing, and a
  click opens the comp.

The board is kept in the browser, one for each set, so it needs no server and a page opened
from a file has it too. It is one working board, not a list of saved ones.

Still to come in slice 5: unit suggestions, saved boards with a name and a stage, and emblems
on the planner's units.

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
- The crawl covers NA, EUW and KR, Master and above, and lower ranks while fewer than 1,000 players are listed there.
- SQLite holds the matches and the edits.
- The unlock file is seeded from a guide once per set and then corrected by hand. It lives in
  the repository, because unlock conditions are facts about the game.
- The list sorts by average placement, with a play-rate floor.
- A condition re-ranks and never hides.
