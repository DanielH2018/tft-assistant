const SNAPSHOTS = JSON.parse(document.getElementById("snapshots").textContent);
const state = { snapshot: 0, comp: null, filters: [], filter: "", sort: "avg", column: "c-tier", ascending: false, component: null };
const el = (id) => document.getElementById(id);
const esc = (text) =>
  String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const pct = (share) => `${Math.round(share * 100)}%`;
const snap = () => SNAPSHOTS[state.snapshot];
const unitOf = (id) => snap().units[id] || { name: id, cost: 0, traits: [] };
const traitName = (id) => (snap().traits[id] || { name: id }).name;

// The text of a hover card, as a `data-tip` attribute: one line for each part that has something to say.
const tipOf = (...lines) => `data-tip="${esc(lines.filter(Boolean).join("\n"))}"`;

// A unit's hover card names the unit, its cost and its traits. `note` adds what this place on the
// page says about the unit.
function unitTip(id, note = "") {
  const unit = unitOf(id);
  return tipOf(unit.name, [unit.cost && `${unit.cost} cost`, ...unit.traits.map(traitName)].filter(Boolean).join(" · "), note);
}

function unitTile(id, size = "l", options = {}) {
  const unit = unitOf(id);
  const image = unit.icon ? `<img src="${esc(unit.icon)}" alt="" loading="lazy">` : `<span class="blank"></span>`;
  const stars = options.threeStar ? `<b class="stars">★★★</b>` : "";
  return `<span class="unit ${size} cost${unit.cost}" ${unitTip(id, options.note)}>${image}${stars}<span class="unit-name">${esc(unit.name)}</span></span>`;
}

// An item's hover card names the item and the components it is built from, then `note`.
function itemIcon(id, { note = "" } = {}) {
  const item = snap().items[id] || { name: id };
  const tip = tipOf(item.name, (item.recipe || []).join(" + "), note);
  return item.icon ? `<img class="item-icon" src="${esc(item.icon)}" alt="" ${tip} loading="lazy">` : "";
}
const itemName = (id) => esc((snap().items[id] || { name: id }).name);

// Everything the filter box searches in a comp: its name, style, level, units, items, traits and categories.
function searchedNames(comp) {
  const units = [...comp.core, ...comp.flex.flat().flatMap((p) => p.units)].map((id) => unitOf(id).name);
  const built = [
    ...comp.items.map((pick) => pick.item),
    ...comp.key_units.flatMap((key) => key.build.map((note) => note.item)),
    ...comp.specials.map((special) => special.item),
  ].map((id) => (snap().items[id] || { name: id }).name);
  const names = [nameOf(comp), comp.name, comp.style, `level ${comp.roll_level}`, ...units, ...built, ...comp.traits.map((t) => traitName(t.trait)), ...categoriesOf(comp).map(categoryName)];
  return names.map((name) => name.toLowerCase());
}

// A filter that is part of one name, such as "fae emblem", lists the comps with that name. Any
// other filter lists the comps that hold every one of its words somewhere. The list shows the
// comps that pass every kept filter and the one being typed.
function visibleComps() {
  const filters = [...state.filters, state.filter].map((filter) => filter.trim().toLowerCase()).filter(Boolean);
  const comps = snap().comps.map((comp) => [comp, searchedNames(comp)]);
  const passing = (phrase) => {
    const words = phrase.split(/\s+/);
    const named = comps.filter(([, names]) => names.some((name) => name.includes(phrase)));
    return new Set(named.length ? named : comps.filter(([, names]) => words.every((word) => names.some((name) => name.includes(word)))));
  };
  const passes = filters.map(passing);
  return comps
    .filter((entry) => passes.every((passed) => passed.has(entry)))
    .map(([comp]) => comp)
    .sort((a, b) => (state.ascending ? -1 : 1) * SORTS[state.sort](a, b));
}

// The list leaves out the comps few boards play, until its first switch asks for them. A comp of
// 0.3% of boards can read as the best on the list from sixty boards.
const LOW_PLAY = 0.01;
const SHOW_LOW_PLAY = "tft-assistant.low-play";
const EXPAND_ALL = "tft-assistant.expand-all";
state.lowPlay = localStorage.getItem(SHOW_LOW_PLAY) === "1";
state.expandAll = localStorage.getItem(EXPAND_ALL) === "1";
// The comps whose rows differ from what the second switch says: opened while it is off, or
// closed while it is on.
state.flipped = new Set();
const isListed = (comp) => state.lowPlay || comp.share >= LOW_PLAY;

// A subcomp is a whole board of the comp: its core and the units that fill the places the core
// leaves at the comp's level. The snapshot lists the commonest, most played first. Two subcomps
// of a comp can share boards, since a board can field more units than the level.
const subcompsOf = (comp) => comp.subcomps || [];
const isExpanded = (comp) => state.expandAll !== state.flipped.has(comp.id);
function subcompRow(comp, sub) {
  const names = sub.units.map((id) => unitOf(id).name).join(", ");
  return `<li data-id="${comp.id}" class="comp-row sub" ${tipOf(`${nameOf(comp)} with ${names}: ${pct(sub.share)} of its boards`)}>
    <span class="c-tier"></span>
    <span class="c-name">+ ${esc(names)}</span>
    <span class="c-level"></span>
    <span class="c-core">${sub.units.map((id) => unitTile(id, "s")).join("")}</span>
    <span class="c-avg num">${sub.avg_placement.toFixed(2)}</span>
    <span class="c-top4 num">${pct(sub.top4)}</span>
    <span class="c-win num">${pct(sub.win_rate)}</span>
    <span class="c-play num">${(comp.share * sub.share * 100).toFixed(1)}%</span>
  </li>`;
}

// A category groups comps that want the same thing from a game. The snapshot derives each comp's
// categories by rule, and the reader's edit changes them: a list where `-reroll` takes the comp
// out of a derived category and any other entry puts it in one.
const CATEGORY_NAMES = { reroll: "Reroll", "fast-9": "Fast 9", items: "Item Dependent" };
// A category of the reader's own is stored in lower case and shown with each word capitalised.
const capitalised = (words) => words.replace(/(^|\s)\S/g, (first) => first.toUpperCase());
const CATEGORY_TIPS = {
  reroll: "The comp takes units to three stars, so it rolls at a low level.",
  "fast-9": "The comp levels to 9 before it rolls.",
  items: "The comp's carry has an item its boards place clearly worse without.",
};
const TRAIT_CATEGORY = "trait:";
const categoryName = (category) =>
  category.startsWith(TRAIT_CATEGORY) ? traitName(category.slice(TRAIT_CATEGORY.length)) : CATEGORY_NAMES[category] || capitalised(category);
const categoryTip = (category) =>
  category.startsWith(TRAIT_CATEGORY)
    ? `The comp fields ${categoryName(category)} as a vertical.`
    : CATEGORY_TIPS[category] || "A category you added.";
const ownCategories = (comp) =>
  ((edits && edits[comp.id] && edits[comp.id].categories) || "").split(",").map((entry) => entry.trim()).filter(Boolean);
function categoriesOf(comp) {
  const own = ownCategories(comp);
  const kept = comp.categories.filter((category) => !own.includes(`-${category}`));
  return [...new Set([...kept, ...own.filter((entry) => !entry.startsWith("-"))])];
}

// The categories of the selection's comps with the count of comps in each, the fixed ones first
// and then the traits by name.
function categoryCounts() {
  const counts = new Map();
  for (const comp of snap().comps) for (const category of categoriesOf(comp)) counts.set(category, (counts.get(category) || 0) + 1);
  const rank = (category) => (category.startsWith(TRAIT_CATEGORY) ? 1 : 0);
  return [...counts].sort(([a], [b]) => rank(a) - rank(b) || categoryName(a).localeCompare(categoryName(b)));
}

// The category the reader named, as its stored form: a known category by its shown name, or else
// the text as a category of their own.
function categoryNamed(text) {
  const wanted = text.trim().toLowerCase().replace(/,/g, " ").replace(/^-+/, "");
  const traits = Object.keys(snap().traits).map((id) => `${TRAIT_CATEGORY}${id}`);
  return [...Object.keys(CATEGORY_NAMES), ...traits].find((category) => categoryName(category).toLowerCase() === wanted) || wanted;
}

// Puts the comp in the category or takes it out, as the smallest change to the reader's list.
function setCategory(comp, category, member) {
  const derived = comp.categories.includes(category);
  const own = ownCategories(comp).filter((entry) => entry !== category && entry !== `-${category}`);
  if (member !== derived) own.push(member ? category : `-${category}`);
  return putEdit(comp.id, "categories", own.join(",")).then(renderList);
}

function categoriesHtml(comp) {
  const mine = categoriesOf(comp);
  if (!edits && !mine.length) return "";
  const chips = mine.map((category) => {
    const remove = edits ? `<button data-uncategory="${esc(category)}" data-tip="Take this comp out of the category">×</button>` : "";
    return `<span class="filter-chip" ${tipOf(categoryTip(category))}>${esc(categoryName(category))}${remove}</span>`;
  });
  const known = categoryCounts().filter(([category]) => !mine.includes(category));
  const add = edits
    ? `<input id="add-category" list="known-categories" maxlength="40" placeholder="add a category" ${tipOf("Enter puts this comp in the category. A name no category has starts one.")}>
       <datalist id="known-categories">${known.map(([category]) => `<option value="${esc(categoryName(category))}">`).join("")}</datalist>`
    : "";
  return `<p class="categories">${chips.join("")}${add}<span class="note edit-state"></span></p>`;
}

// ── The explorer ─────────────────────────────────────────────────────────────────────────────
// The explorer filters every board of the selection and says how units, items and traits do on
// the boards that pass. The boards are a file beside the page, which the page loads when the tab
// first opens: a line a board, as `explorer.py` writes them. A filter is one of:
//   a unit's name          boards that field the unit
//   an item's name         boards where a unit holds the item
//   a trait's name         boards where the trait reaches a breakpoint; "4 elderwood" asks for 4
//   "level 8"              boards at that level
//   "unit: item"           boards where that unit holds that item
//   "3 star unit"          boards that field the unit at that star level; "unit 3*" too, and
//                          "3 star unit: item" for the unit at that level holding the item
Object.assign(state, { exploreFilters: [], exploreFilter: "", exploreSort: "play", exploreAscending: false, exploreHolder: true });
const explored = new Map();
// A row needs this many boards and this share of the boards that pass, so one board does not
// read as a 1.00 average.
const EXPLORE_BOARDS = 20;
const EXPLORE_SHARE = 0.005;
const EXPLORE_ROWS = 40;

// The traits a board has active, as trait → the breakpoint its count reaches. An emblem counts on
// a unit that lacks its trait.
function boardTraits(units) {
  const s = snap();
  const counts = new Map();
  const seen = new Set();
  for (const unit of units) {
    const own = s.units[unit.id].traits;
    if (!seen.has(unit.id)) for (const trait of own) counts.set(trait, (counts.get(trait) || 0) + 1);
    seen.add(unit.id);
    for (const item of unit.items) {
      const trait = s.items[item].emblem_of;
      if (trait && !own.includes(trait)) counts.set(trait, (counts.get(trait) || 0) + 1);
    }
  }
  const active = new Map();
  for (const [trait, count] of counts) {
    const reached = ((s.traits[trait] || {}).breakpoints || []).filter((at) => at <= count).pop();
    if (reached) active.set(trait, reached);
  }
  return active;
}

function decodeBoards(doc) {
  const s = snap();
  const symbols = new Map([...doc.alphabet].map((symbol, number) => [symbol, number]));
  const two = (line, at) => symbols.get(line[at]) * symbols.size + symbols.get(line[at + 1]);
  return doc.boards
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      const units = [];
      for (let at = 2; at < line.length; ) {
        const code = symbols.get(line[at + 2]);
        const held = code % 4;
        const id = doc.units[two(line, at)];
        const items = [];
        for (let n = 0; n < held; n += 1) {
          const item = doc.items[two(line, at + 3 + 2 * n)];
          if (s.items[item]) items.push(s.items[item].radiant_of && s.items[s.items[item].radiant_of] ? s.items[item].radiant_of : item);
        }
        if (s.units[id]) units.push({ id, stars: Math.floor(code / 4), items });
        at += 3 + 2 * held;
      }
      return { placement: Number(line[0]), level: symbols.get(line[1]), units, traits: boardTraits(units) };
    });
}

function loadExplorer() {
  const path = snap().explorer;
  if (!path || explored.has(path)) return;
  explored.set(path, "loading");
  fetch(path)
    .then((reply) => (reply.ok ? reply.json() : Promise.reject(new Error(`the server answered ${reply.status}`))))
    .then((doc) => explored.set(path, decodeBoards(doc)))
    .catch(() => explored.set(path, "failed"))
    .then(() => (state.view === "planner" ? renderPlanner() : ["explorer", "items"].includes(state.view) && renderList()));
}

// The thing a name names: the one whose name is the text, or starts with it, or holds it, the
// shortest name first.
function named(table, text, nameOf_) {
  const found = Object.keys(table)
    .map((id) => [id, nameOf_(id).toLowerCase()])
    .filter(([, name]) => name.includes(text))
    .sort((a, b) => Number(b[1] === text) - Number(a[1] === text) || Number(b[1].startsWith(text)) - Number(a[1].startsWith(text)) || a[1].length - b[1].length);
  return found.length ? found[0][0] : null;
}
// A unit as a filter names it: its name, with a star level before or after it or none.
const STARRED = /^(?:(\d)\s*(?:\*|★|-?\s*stars?)\s+(.+)|(.+?)\s+(\d)\s*(?:\*|★|-?\s*stars?))$/;
function namedUnit(text) {
  const starred = text.match(STARRED);
  const unit = named(explorableUnits(), (starred ? starred[2] || starred[3] : text).trim(), (id) => unitOf(id).name);
  return unit ? { unit, stars: starred ? Number(starred[1] || starred[4]) : null } : null;
}
const starsPass = (unit, condition) => unit.id === condition.unit && (!condition.stars || unit.stars === condition.stars);
const explorableUnits = () => Object.fromEntries(Object.entries(snap().units).filter(([, unit]) => unit.traits.length));
function exploreCondition(phrase) {
  const s = snap();
  const text = phrase.toLowerCase().trim();
  if (!text) return null;
  const level = text.match(/^(?:level|lvl)\s*(\d+)$/);
  if (level) return { kind: "level", level: Number(level[1]) };
  if (text.includes(":")) {
    const [unitText, itemText] = text.split(":").map((part) => part.trim());
    const unit = namedUnit(unitText);
    const item = itemText && named(s.items, itemText, itemName);
    return unit && item ? { kind: "holds", ...unit, item } : null;
  }
  if (STARRED.test(text)) {
    const unit = namedUnit(text);
    return unit ? { kind: "unit", ...unit } : null;
  }
  const counted = text.match(/^(\d+)\s+(.+)$/);
  if (counted) {
    const trait = named(s.traits, counted[2], traitName);
    return trait ? { kind: "trait", trait, at: Number(counted[1]) } : null;
  }
  const unit = namedUnit(text);
  if (unit) return { kind: "unit", ...unit };
  const item = named(s.items, text, itemName);
  if (item) return { kind: "item", item };
  const trait = named(s.traits, text, traitName);
  return trait ? { kind: "trait", trait, at: 1 } : null;
}
function boardPasses(board, condition) {
  if (condition.kind === "level") return board.level === condition.level;
  if (condition.kind === "unit") return board.units.some((unit) => starsPass(unit, condition));
  if (condition.kind === "item") return board.units.some((unit) => unit.items.includes(condition.item));
  if (condition.kind === "holds") return board.units.some((unit) => starsPass(unit, condition) && unit.items.includes(condition.item));
  return (board.traits.get(condition.trait) || 0) >= condition.at;
}

// How many boards hold each thing and how they place, as key → [boards, placements summed, top 4s, wins].
function tally(counts, key, board) {
  const row = counts.get(key) || [0, 0, 0, 0];
  row[0] += 1;
  row[1] += board.placement;
  row[2] += Number(board.placement <= 4);
  row[3] += Number(board.placement === 1);
  counts.set(key, row);
}
// `holder` limits the items to the ones that unit holds, and `starred` is the unit whose star
// levels are counted.
function exploreStats(boards, holder, starred) {
  const levels = new Map();
  const all = new Map();
  const units = new Map();
  const items = new Map();
  const traits = new Map();
  for (const board of boards) {
    tally(all, "all", board);
    for (const id of new Set(board.units.map((unit) => unit.id))) tally(units, id, board);
    const held = new Set(board.units.filter((unit) => !holder || unit.id === holder).flatMap((unit) => unit.items));
    for (const item of held) tally(items, item, board);
    for (const [trait, at] of board.traits) tally(traits, `${at} ${trait}`, board);
    for (const stars of new Set(board.units.filter((unit) => unit.id === starred).map((unit) => unit.stars))) tally(levels, stars, board);
  }
  return { all: all.get("all") || [0, 0, 0, 0], units, items, traits, levels };
}

const EXPLORE_COLUMNS = [
  ["play", "Play", (a, b) => b[1][0] - a[1][0]],
  ["avg", "Avg", (a, b) => a[1][1] / a[1][0] - b[1][1] / b[1][0]],
  ["top4", "Top 4", (a, b) => b[1][2] / b[1][0] - a[1][2] / a[1][0]],
  ["win", "Win", (a, b) => b[1][3] / b[1][0] - a[1][3] / a[1][0]],
];
// One table of the explorer. `show` gives a row's picture and name, and `ask` the filter a click adds.
function exploreTable(title, counts, total, show, ask) {
  const overall = total[1] / total[0];
  const floor = Math.max(EXPLORE_BOARDS, EXPLORE_SHARE * total[0]);
  const order = EXPLORE_COLUMNS.find(([key]) => key === state.exploreSort)[2];
  const rows = [...counts]
    .filter(([, row]) => row[0] >= floor)
    .sort((a, b) => (state.exploreAscending ? -1 : 1) * order(a, b))
    .slice(0, EXPLORE_ROWS)
    .map(([key, row]) => {
      const avg = row[1] / row[0];
      const apart = avg - overall;
      return `<tr data-explore="${esc(ask(key))}" ${tipOf(`On ${row[0].toLocaleString()} of these ${total[0].toLocaleString()} boards.`, "Click to add it to the filters.")}>
        <td><span class="explore-name">${show(key)}</span></td>
        <td>${pct(row[0] / total[0])}</td>
        <td>${avg.toFixed(2)}</td><td class="${apart < -0.005 ? "better" : apart > 0.005 ? "worse" : "note"}">${apart > 0 ? "+" : ""}${apart.toFixed(2)}</td>
        <td>${pct(row[2] / row[0])}</td><td>${pct(row[3] / row[0])}</td></tr>`;
    });
  const head = EXPLORE_COLUMNS.map(([key, label]) => {
    const arrow = key === state.exploreSort ? `<span class="arrow">${state.exploreAscending ? "▲" : "▼"}</span>` : "";
    // The delta is the average less the boards' own, so it sorts as the average does.
    const delta = key === "avg" ? `<th ${tipOf("The average placement less that of all these boards.")}><button data-explore-sort="avg">Delta</button></th>` : "";
    return `<th class="${key === state.exploreSort ? "sorted" : ""}"><button data-explore-sort="${key}">${label}${arrow}</button></th>${delta}`;
  }).join("");
  return `<table class="explore-table"><caption>${title}</caption><thead><tr><th></th>${head}</tr></thead>
    <tbody>${rows.join("") || `<tr><td colspan="6" class="note">Nothing is on ${Math.ceil(floor)} of these boards.</td></tr>`}</tbody></table>`;
}

function renderExplorer() {
  showTip(null);
  loadExplorer();
  const s = snap();
  const boards = explored.get(s.explorer);
  const shell = (body) => `<div id="sheet"><header><h1>${MAXIMIZE} Explorer</h1></header>${body}</div>`;
  const help = `<p class="note">Type a filter and press Enter. A filter is a unit, an item, a trait (<code>4 elderwood</code> asks for that count), <code>level 8</code>, <code>3 star unit</code>, or <code>unit: item</code> for a unit that holds an item. A click on a row adds it.</p>`;
  if (!Array.isArray(boards)) {
    const why = !s.explorer
      ? "This page was built without its boards."
      : boards === "failed"
        ? "The boards did not load. A page opened from a file cannot load them: the explorer needs the page's server."
        : "Loading the boards…";
    el("explore").innerHTML = help;
    el("detail").innerHTML = shell(`<p class="empty">${why}</p>`);
    return;
  }
  const conditions = [...state.exploreFilters, state.exploreFilter].map(exploreCondition).filter(Boolean);
  const passing = boards.filter((board) => conditions.every((condition) => boardPasses(board, condition)));
  // With one unit in the filters, the items table can list what that unit holds.
  const one = [...new Set(conditions.filter((condition) => condition.kind === "unit" || condition.kind === "holds").map((condition) => condition.unit))];
  const holder = one.length === 1 && state.exploreHolder ? one[0] : null;
  const { all, units, items, traits, levels } = exploreStats(passing, holder, one.length === 1 ? one[0] : null);
  // A unit the filters name is on every board that passes, so its row would say nothing.
  for (const id of one) units.delete(id);
  const whose = one.length === 1
    ? `<label class="switch" ${tipOf("On: only the items that unit holds. Off: the items any unit on the board holds.")}><input id="explore-holder" type="checkbox" ${state.exploreHolder ? "checked" : ""}><i></i>Items on ${esc(unitOf(one[0]).name)} only</label>`
    : "";
  const traitOf = (key) => key.slice(key.indexOf(" ") + 1);
  // The two long tables fill the page. The short ones go under the figures in the list pane,
  // which is otherwise empty below them.
  const short = `${one.length === 1 ? exploreTable(`${esc(unitOf(one[0]).name)} by stars`, levels, all, (stars) => `${unitTile(one[0], "s")}${"★".repeat(stars)}`, (stars) => `${stars} star ${unitOf(one[0]).name}`) : ""}
    ${exploreTable("Traits", traits, all, (key) => `${(s.traits[traitOf(key)] || {}).icon ? `<img src="${esc(s.traits[traitOf(key)].icon)}" alt="">` : ""}${parseInt(key, 10)} ${esc(traitName(traitOf(key)))}`, (key) => `${parseInt(key, 10)} ${traitName(traitOf(key))}`)}`;
  el("explore").innerHTML = all[0]
    ? `<p class="big">${all[0].toLocaleString()} boards</p>
       <p class="note">of ${boards.length.toLocaleString()} in ${esc(s.label)}: ${pct(all[0] / boards.length)}</p>
       <dl><dt>Average placement</dt><dd>${(all[1] / all[0]).toFixed(2)}</dd><dt>Top 4</dt><dd>${pct(all[2] / all[0])}</dd><dt>Win</dt><dd>${pct(all[3] / all[0])}</dd></dl>${whose}${short}${help}`
    : `<p class="big">No board</p><p class="note">No board of ${boards.length.toLocaleString()} passes every filter.</p>${help}`;
  const tables = all[0]
    ? `<div class="explore-tables">
        ${exploreTable("Units", units, all, (id) => `${unitTile(id, "s")}${esc(unitOf(id).name)}`, (id) => unitOf(id).name)}
        ${exploreTable(holder ? `Items on ${esc(unitOf(holder).name)}` : "Items", items, all, (item) => `${itemIcon(item)}${itemName(item)}`, (item) => (holder ? `${unitOf(holder).name}: ${itemName(item)}` : itemName(item)))}
      </div>`
    : `<p class="empty">Remove a filter to see boards.</p>`;
  el("detail").innerHTML = shell(tables);
  fitWidth();
}

// The filter box belongs to the view: the comps view filters its comps, and the items view
// filters the units of the item groups. Each keeps its own filters and its own typed text.
Object.assign(state, { groupFilters: [], groupFilter: "" });
const filterKeys = () => ({ items: ["groupFilters", "groupFilter"], explorer: ["exploreFilters", "exploreFilter"] })[state.view] || ["filters", "filter"];
// A unit passes a filter that is part of its name, of one of its traits' names or of its cost:
// "4", "4 cost" and "cost 4" all list the 4-cost units.
function unitPasses(id, phrase) {
  const unit = unitOf(id);
  const asked = phrase.toLowerCase().replace("-", " ").trim();
  if (/^\d+$/.test(asked)) return unit.cost === Number(asked);
  return [unit.name, `${unit.cost} cost`, `cost ${unit.cost}`, ...unit.traits.map(traitName)].some((name) => name.toLowerCase().includes(asked));
}
const groupPhrases = () => [...state.groupFilters, state.groupFilter].filter((phrase) => phrase.trim());

function renderFilters() {
  const [kept] = filterKeys();
  el("chips").innerHTML = state[kept]
    .map((filter, index) => `<span class="filter-chip ${state.view === "explorer" && !exploreCondition(filter) ? "unmatched" : ""}">${esc(filter)}<button data-remove="${index}" data-tip="Remove this filter">×</button></span>`)
    .join("");
  const asks = { items: "unit, cost or trait", explorer: "unit, item, trait, level 8, 3 star unit, or unit: item" }[state.view] || "unit, trait, item or level";
  el("filter").placeholder = state[kept].length ? "add a filter" : asks;
  renderList();
}

// The page has three views of one snapshot. "comps" is the comp list beside one comp's page.
// "items" is the slam grid beside the item groups. "planner" is the roster beside a board the
// reader fills. The browser keeps the view across a reload.
const VIEW = "tft-assistant.view";
state.view = ["items", "planner", "explorer"].includes(localStorage.getItem(VIEW)) ? localStorage.getItem(VIEW) : "comps";
// Shows one comp on the comps view. The list's filters go when they would leave the comp out,
// because the list opens its first comp in place of one it does not hold.
function openComp(id) {
  state.comp = id;
  if (!visibleComps().some((comp) => comp.id === id)) {
    state.filters = [];
    state.filter = "";
  }
  setView("comps");
}
function setView(view) {
  state.view = view;
  localStorage.setItem(VIEW, view);
  el("filter").value = state[filterKeys()[1]];
  renderFilters();
}

// A comp counts toward a slam when its boards place well enough to copy.
const isStrong = (comp) => comp.tier !== "C";

// Every item a comp's boards build: its item priority, its key units' builds and its emblems.
function builtBy(comp) {
  const holders = new Map();
  for (const key of comp.key_units) for (const note of key.build) holders.set(note.item, key.unit);
  for (const special of comp.specials) holders.set(special.item, special.holder);
  for (const pick of comp.items) holders.set(pick.item, pick.holder);
  return holders;
}

// The grid has a row and a column for each component, and the item two components build stands
// where they cross. The number on an item is how many strong comps build it. An item a third of
// them build is marked safe: it fits whichever of them the game turns into.
// The number on a grid item can be hidden; the browser keeps the choice.
const SLAM_COUNTS = "tft-assistant.hide-slam-counts";
state.slamCounts = !localStorage.getItem(SLAM_COUNTS);
function slamGridHtml() {
  const s = snap();
  const strong = s.comps.filter(isStrong).sort(SORTS.play);
  const users = new Map();
  for (const comp of strong) {
    for (const [item, holder] of builtBy(comp)) users.set(item, [...(users.get(item) || []), [comp, holder]]);
  }
  const made = new Map(Object.entries(s.recipes || {}).map(([item, parts]) => [[...parts].sort().join("+"), item]));
  const name = (id) => (s.items[id] || { name: id }).name;
  const components = s.components || [];
  const cell = (first, second) => {
    const item = made.get([first, second].sort().join("+"));
    const lit = first === state.component || second === state.component ? "lit" : "";
    if (!item) return `<td class="${lit}"></td>`;
    const built = users.get(item) || [];
    const tone = built.length >= strong.length / 3 ? "safe" : built.length ? "" : "unused";
    const lines = built.slice(0, 8).map(([comp, holder]) => `${nameOf(comp)} → ${unitOf(holder).name}`);
    const note = built.length
      ? `Built by ${built.length} of ${strong.length} comps of tier B or better:\n${lines.join("\n")}${built.length > 8 ? "\n…" : ""}\nClick to bring the units that hold it to the top of the item groups.`
      : "No comp of tier B or better builds it.";
    return `<td class="slam ${tone} ${lit} ${state.items.includes(item) ? "picked" : ""}" data-slam="${esc(item)}">${itemIcon(item, { note })}<b>${built.length || ""}</b></td>`;
  };
  const part = (id) =>
    `<th class="${id === state.component ? "lit" : ""}" data-component="${esc(id)}">${itemIcon(id, { note: "Click to light up its row and column." })}</th>`;
  const head = `<tr><th></th>${components.map(part).join("")}</tr>`;
  const rows = components.map((row, at) => {
    const blank = (column) => `<td class="${row === state.component || column === state.component ? "lit" : ""}"></td>`;
    return `<tr>${part(row)}${components.map((column, across) => (across < at ? blank(column) : cell(row, column))).join("")}</tr>`;
  });
  const counts = `<label class="switch slam-switch" ${tipOf("The number on an item is how many strong comps build it.")}><input id="slam-counts" type="checkbox" ${state.slamCounts ? "checked" : ""}><i></i>Numbers on the items</label>`;
  return `${counts}<table class="slams ${state.slamCounts ? "" : "no-counts"}">${head}${rows.join("")}</table>`;
}

// Each group lists the items its units build and its units, the best placed first. A unit that
// is a comp's main carry is outlined. A click on a unit or an item goes to the comps tab with
// its name as the filter.
//
// With an item picked, a group lists only the units that hold it on a tenth of their itemised
// boards or more, or a hundredth for an emblem or an artifact: the floors the snapshot keeps an
// item at. A tank leaves when a
// carry's item is picked. The units that stay are drawn as cards, with how often each holds
// the item and how it places with it. With two picked, `bothItemsHtml` takes over.
const PICKED_ITEMS = 2;
state.items = [];
// A radiant item is picked as its base: the groups count a radiant item as the item it upgrades.
function pickItem(asked) {
  const item = (snap().items[asked] || {}).radiant_of || asked;
  const kept = state.items.filter((other) => other !== item);
  state.items = kept.length < state.items.length ? kept : [...kept, item].slice(-PICKED_ITEMS);
}
// With two items picked: the boards that hold both, as the pairs of units that hold them. One
// unit can hold both, or two units one each, and then both are shown. A pair is counted once a
// board, whichever of its units' copies it is. The boards are the explorer's file, so this is
// null where they cannot be had, and the caller lists the units that hold either item.
const PAIR_BOARDS = 10;
const PAIR_SHARE = 0.01;
const PAIRS_SHOWN = 40;
Object.assign(state, { pairSort: "play", pairAscending: false });
function bothItemsHtml([first, second], phrases) {
  loadExplorer();
  const boards = explored.get(snap().explorer);
  if (boards === "loading") return `<p class="empty">Loading the boards…</p>`;
  if (!Array.isArray(boards)) return null;
  const pairs = new Map();
  let holding = 0;
  let placed = 0;
  for (const board of boards) {
    const firsts = [...new Set(board.units.filter((unit) => unit.items.includes(first)).map((unit) => unit.id))];
    const seconds = [...new Set(board.units.filter((unit) => unit.items.includes(second)).map((unit) => unit.id))];
    if (!firsts.length || !seconds.length) continue;
    holding += 1;
    placed += board.placement;
    for (const a of firsts) for (const b of seconds) tally(pairs, `${a}|${b}`, board);
  }
  if (!holding) return `<p class="empty">No board holds both items.</p>`;
  const floor = Math.max(PAIR_BOARDS, PAIR_SHARE * holding);
  const holder = (id, items) => `<span class="pair-unit to-filter" data-filter="${esc(unitOf(id).name)}" ${tipOf("Click to list the comps that field it.")}>${unitTile(id, "s")}<span class="pair-name">${esc(unitOf(id).name)}</span><span class="pair-items">${items.map((item) => itemIcon(item)).join("")}</span></span>`;
  const overall = placed / holding;
  const order = EXPLORE_COLUMNS.find(([key]) => key === state.pairSort)[2];
  const rows = [...pairs]
    .map(([key, row]) => [key.split("|"), row])
    .filter(([units, row]) => row[0] >= floor && phrases.every((phrase) => units.some((id) => unitPasses(id, phrase))))
    .sort((a, b) => (state.pairAscending ? -1 : 1) * order(a, b))
    .slice(0, PAIRS_SHOWN)
    .map(([[a, b], row]) => {
      const units = a === b ? holder(a, [first, second]) : `${holder(a, [first])}<span class="joint">+</span>${holder(b, [second])}`;
      const avg = row[1] / row[0];
      const apart = avg - overall;
      return `<tr ${tipOf(`${row[0].toLocaleString()} of the ${holding.toLocaleString()} boards that hold both items.`)}>
        <td><span class="pair-holders">${units}</span></td>
        <td>${pct(row[0] / holding)}</td><td>${avg.toFixed(2)}</td>
        <td class="${apart < -0.005 ? "better" : apart > 0.005 ? "worse" : "note"}">${apart > 0 ? "+" : ""}${apart.toFixed(2)}</td>
        <td>${pct(row[2] / row[0])}</td><td>${pct(row[3] / row[0])}</td><td class="note">${row[0].toLocaleString()}</td></tr>`;
    });
  const head = EXPLORE_COLUMNS.map(([key, label]) => {
    const arrow = key === state.pairSort ? `<span class="arrow">${state.pairAscending ? "▲" : "▼"}</span>` : "";
    const delta = key === "avg" ? `<th ${tipOf("The average placement less that of all the boards with both items.")}><button data-pair-sort="avg">Delta</button></th>` : "";
    return `<th class="${key === state.pairSort ? "sorted" : ""}"><button data-pair-sort="${key}">${label}${arrow}</button></th>${delta}`;
  }).join("");
  const summary = `<p class="note">${holding.toLocaleString()} boards hold both · ${overall.toFixed(2)} avg</p>`;
  const none = `<tr><td colspan="7" class="note">No pair of holders is on ${Math.ceil(floor)} of them${phrases.length ? " and passes the filters" : ""}.</td></tr>`;
  return `${summary}<table class="explore-table pair-table"><thead><tr><th>Holders</th>${head}<th>Boards</th></tr></thead><tbody>${rows.join("") || none}</tbody></table>`;
}

function itemGroupsHtml() {
  const s = snap();
  const carried = new Map();
  for (const comp of [...s.comps].sort(SORTS.play)) {
    if (comp.carries[0] && !carried.has(comp.carries[0])) carried.set(comp.carries[0], comp);
  }
  const named = (id) => (s.items[id] || { name: id }).name;
  const picked = state.items;
  const heldBy = (group, id) => (group.held || {})[id];
  // What a unit holds of the picked items, as [item, share of its boards, placement with it].
  const matches = (group, id) => picked.map((item) => [item, ...((heldBy(group, id) || { items: {} }).items[item] || [])]).filter((match) => match.length > 1);
  const shares = (group, id) => matches(group, id).reduce((sum, match) => sum + match[1], 0);
  const artifacts = new Set((s.item_stats || []).filter((stat) => stat.kind === "artifact").map((stat) => stat.item));
  const isRare = (item) => Boolean((s.items[item] || {}).emblem_of) || artifacts.has(item);
  // What the picked items do to a unit's placement: its placement with the item less its own average.
  const gain = (group, id) => Math.min(...matches(group, id).map((match) => match[2] - heldBy(group, id).avg));
  const order = (group) => (a, b) => {
    // An emblem or an artifact is on few boards of any unit, so its holders run from the unit it
    // helps most. An item a player builds runs from the unit that holds it most.
    if (picked.length && picked.every(isRare)) return gain(group, a) - gain(group, b);
    if (picked.length) return matches(group, b).length - matches(group, a).length || shares(group, b) - shares(group, a);
    const avg = (id) => (heldBy(group, id) || { avg: 9 }).avg;
    return avg(a) - avg(b) || unitOf(a).cost - unitOf(b).cost;
  };
  const tile = (group) => (id) => {
    const held = heldBy(group, id);
    const comp = carried.get(id);
    const note = [
      held && `Average placement ${held.avg.toFixed(2)} over ${held.boards.toLocaleString()} boards where it holds items.`,
      comp && `Carries ${nameOf(comp)}.`,
      "Click to list the comps that field it.",
    ]
      .filter(Boolean)
      .join("\n");
    return `<span class="to-filter ${comp ? "carrier" : ""}" data-filter="${esc(unitOf(id).name)}">${unitTile(id, "m", { note })}</span>`;
  };
  const card = (group) => (id) => {
    const held = heldBy(group, id);
    const comp = carried.get(id);
    const lines = matches(group, id)
      .map(([item, share, avg]) => {
        const apart = avg - held.avg;
        const tone = apart < -0.005 ? "better" : apart > 0.005 ? "worse" : "note";
        return `<span class="held-line" ${tipOf(`Holds ${named(item)} on ${pct(share)} of its itemised boards, and places ${avg.toFixed(2)} there: ${Math.abs(apart).toFixed(2)} ${apart < 0 ? "better" : "worse"} than its ${held.avg.toFixed(2)} over all of them.`)}>${itemIcon(item)}<b class="${tone}">${apart > 0 ? "+" : ""}${apart.toFixed(2)}</b><span class="note">${avg.toFixed(2)} on ${pct(share)}</span></span>`;
      })
      .join("");
    return `<div class="unit-card to-filter ${comp ? "carrier" : ""}" data-filter="${esc(unitOf(id).name)}" ${tipOf("Click to list the comps that field it.")}>
      ${unitTile(id, "m")}
      <div class="card-lines">${lines}
        <span class="note">${held.avg.toFixed(2)} avg over ${held.boards.toLocaleString()}${comp ? ` · carries ${esc(nameOf(comp))}` : ""}</span></div>
    </div>`;
  };
  const phrases = groupPhrases();
  const passing = (group) => group.units.filter((id) => phrases.every((phrase) => unitPasses(id, phrase)));
  const listed = (group) => passing(group).filter((id) => !picked.length || matches(group, id).length);
    const groups = [...s.item_groups]
    .filter((group) => listed(group).length)
    .map(
      (group) => `<div class="group ${picked.length ? "detailed" : ""}">
      <div class="group-items">${group.items
        .map((item) => `<span class="to-filter ${picked.includes(item) ? "picked" : ""}" data-filter="${esc(named(item))}">${itemIcon(item, { note: "Click to list the comps that build it." })}</span>`)
        .join("")}</div>
      <div class="group-units">${listed(group).sort(order(group)).map(picked.length ? card(group) : tile(group)).join("")}</div>
    </div>`,
    );
  const info = "Units in one group build alike on real boards, so they can hold each other's items.\nA group lists the items its units hold most, then its units, the best placed first.\nClick one or two items in the grid or the table to list only the units that hold them, each with how often and how it places. An outlined unit is a comp's main carry.";
  const names = picked.map((item) => `<b>${esc(named(item))}</b>`).join(" + ");
  const ordered = picked.length ? `<p class="stats">${names} <button id="clear-item" ${tipOf("List every unit again.")}>Clear</button></p>` : "";
  const both = picked.length === PICKED_ITEMS ? bothItemsHtml(picked, phrases) : null;
  if (both !== null) {
    return `<div id="sheet"><header><h1>${MAXIMIZE} Item groups <span class="info" tabindex="0" ${tipOf(info)}>i</span></h1>${ordered}</header>${both}</div>`;
  }
  const none = picked.length ? "No unit in an item group holds a picked item that often." : phrases.length ? "No unit in an item group passes the filters." : "No unit has enough itemised boards to group.";
  return `<div id="sheet"><header><h1>${MAXIMIZE} Item groups <span class="info" tabindex="0" ${tipOf(info)}>i</span></h1>${ordered}</header>
    ${groups.join("") || `<p class="empty">${none}</p>`}</div>`;
}

// How the boards that hold an item place, one row an item. A kind button lists one kind of item.
// "Craftable" holds no emblem: an emblem is under "Emblem" whether two components make it or a
// game hands it out, and a second row of buttons tells those apart.
const KINDS = [
  [null, "All"],
  ["craftable", "Craftable"],
  ["artifact", "Artifact"],
  ["emblem", "Emblem"],
  ["radiant", "Radiant"],
  ["other", "Other"],
];
const EMBLEM_KINDS = [
  [null, "All"],
  [true, "Craftable"],
  [false, "Uncraftable"],
];
// Each column's own order puts the best or the most first, as in the comp list.
const STAT_COLUMNS = [
  ["Item", "name", (a, b) => itemName(a.item).localeCompare(itemName(b.item))],
  ["Avg", "avg", (a, b) => a.avg_placement - b.avg_placement],
  ["Top 4", "top4", (a, b) => b.top4 - a.top4],
  ["Win", "win", (a, b) => b.win_rate - a.win_rate],
  ["Play", "play", (a, b) => b.share - a.share],
];
Object.assign(state, { statKind: null, emblemCraft: null, statSort: "avg", statAscending: false });
function itemStatsHtml() {
  const stats = snap().item_stats || [];
  if (!stats.length) return "";
  const button = (attribute, value, label, on) => `<button ${attribute}="${value === null ? "" : value}" class="${on ? "on" : ""}">${label}</button>`;
  const kinds = KINDS.map(([kind, label]) => button("data-kind", kind, label, kind === state.statKind)).join("");
  const emblems =
    state.statKind === "emblem"
      ? `<div class="stat-kinds sub">${EMBLEM_KINDS.map(([craft, label]) => button("data-craft", craft, label, craft === state.emblemCraft)).join("")}</div>`
      : "";
  const order = STAT_COLUMNS.find(([, key]) => key === state.statSort)[2];
  const rows = stats
    .filter((stat) => state.statKind === null || stat.kind === state.statKind)
    .filter((stat) => state.statKind !== "emblem" || state.emblemCraft === null || stat.has_recipe === state.emblemCraft)
    .sort((a, b) => (state.statAscending ? -1 : 1) * order(a, b))
    .map(
      (stat) => `<tr data-slam="${esc(stat.item)}" class="${state.items.includes(stat.item) ? "picked" : ""}" ${tipOf(`On ${stat.boards.toLocaleString()} boards. Click to list the units that hold it.`)}>
        <td class="stat-item">${itemIcon(stat.item)} ${itemName(stat.item)}</td>
        <td class="num">${stat.avg_placement.toFixed(2)}</td><td class="num">${pct(stat.top4)}</td>
        <td class="num">${pct(stat.win_rate)}</td><td class="num">${(stat.share * 100).toFixed(1)}%</td>
      </tr>`,
    );
  const head = STAT_COLUMNS.map(([label, key]) => {
    const arrow = key === state.statSort ? `<span class="arrow">${state.statAscending ? "▲" : "▼"}</span>` : "";
    return `<th class="${key === "name" ? "" : "num"} ${key === state.statSort ? "sorted" : ""}"><button data-stat-sort="${key}">${label}${arrow}</button></th>`;
  }).join("");
  return `<h3 class="stats-title">Item stats <span class="info" tabindex="0" ${tipOf("How the boards that hold an item place. A board holds an artifact or a radiant item because it was ahead or was offered one, so their figures say less about the item.")}>i</span></h3>
    <div class="stat-kinds">${kinds}</div>${emblems}
    <table class="stats"><thead><tr>${head}</tr></thead><tbody>${rows.join("") || `<tr><td colspan="5" class="note">No item of this kind is on 50 boards.</td></tr>`}</tbody></table>`;
}

function renderItems() {
  showTip(null);
  el("slams").innerHTML = slamGridHtml() + itemStatsHtml();
  el("detail").innerHTML = itemGroupsHtml();
  fitWidth();
}

function renderList() {
  document.body.dataset.view = state.view;
  for (const tab of el("tabs").children) tab.classList.toggle("on", tab.dataset.view === state.view);
  const s = snap();
  const age = s.newest_match ? `newest match ${hoursAgo(s.newest_match)}` : "no matches";
  // A crawl goes below Master when the top of the ladder is thin, as it is when a set starts.
  const ranks = (s.below_master || []).map(([platform, tier]) => `${capitalised(tier.split(" ")[0])} ${tier.split(" ")[1] || ""} on ${platform.toUpperCase()}`.replace("  ", " "));
  const floor = ranks.length ? ` · ranks down to ${ranks.join(", ")}` : "";
  el("health").textContent = `${s.boards.toLocaleString()} boards · ${pct(s.unclassified)} unclassified · ${age}${floor}`;
  el("health").title = ranks.length ? "The latest crawl found too few players in Master and above, so it read lower ranks too." : "";
  // Every view has an open comp, the one the comps tab shows: a click that opens a comp from
  // another tab changes it and goes there.
  const comps = visibleComps();
  if (!comps.some((comp) => comp.id === state.comp)) state.comp = comps.length ? comps[0].id : null;
  if (state.view === "items") {
    renderItems();
    return;
  }
  if (state.view === "planner") {
    renderPlanner();
    return;
  }
  if (state.view === "explorer") {
    renderExplorer();
    return;
  }
  fitNames();
  el("head").innerHTML = COLUMNS.map(([label, sort, column]) => {
    const cell = `class="${column} ${column === state.column ? "sorted" : ""}"`;
    const arrow = column === state.column ? `<span class="arrow">${state.ascending ? "▲" : "▼"}</span>` : "";
    return sort ? `<button data-sort="${sort}" data-column="${column}" ${cell}>${label}${arrow}</button>` : `<span ${cell}>${label}</span>`;
  }).join("");
  el("low-play").checked = state.lowPlay;
  el("expand-all").checked = state.expandAll;
  const low = comps.filter((comp) => comp.share < LOW_PLAY).length;
  el("low-play-label").textContent = `Show low play rate comps${low ? ` (${low})` : ""}`;
  el("comps").innerHTML = comps
    .filter(isListed)
    .map(
      (comp) => `<li data-id="${comp.id}" class="comp-row ${comp.id === state.comp ? "selected" : ""}">
        <span class="c-tier"><span class="tier t${comp.tier}">${comp.tier}</span></span>
        <span class="c-name">${subcompsOf(comp).length ? `<button class="expand" data-expand="${comp.id}" title="${isExpanded(comp) ? "Hide" : "List"} its subcomps">${isExpanded(comp) ? "▾" : "▸"}</button>` : `<span class="no-subs"></span>`}${esc(nameOf(comp))}</span>
        <span class="c-level">${comp.roll_level}</span>
        <span class="c-core">${comp.core.map((id) => unitTile(id, "s")).join("")}</span>
        <span class="c-avg num">${comp.avg_placement.toFixed(2)}</span>
        <span class="c-top4 num">${pct(comp.top4)}</span>
        <span class="c-win num">${pct(comp.win_rate)}</span>
        <span class="c-play num">${(comp.share * 100).toFixed(1)}%</span>
      </li>${isExpanded(comp) ? subcompsOf(comp).map((sub) => subcompRow(comp, sub)).join("") : ""}`,
    )
    .join("");
  renderDetail();
}

function hoursAgo(iso) {
  const hours = (Date.now() - new Date(iso).getTime()) / 3.6e6;
  return hours < 48 ? `${Math.max(0, Math.round(hours))}h ago` : `${Math.round(hours / 24)}d ago`;
}

function delta(value, baseline) {
  const tone = value < baseline - 0.05 ? "good" : value > baseline + 0.05 ? "bad" : "";
  return `<span class="${tone}">${value.toFixed(2)}</span>`;
}

// How much better or worse boards with an item place than boards without it. A lower placement
// is better, so a negative gap is the good one.
function placementGap(withIt, withoutIt) {
  if (withoutIt === null) return `<span data-tip="Every board has it; they average ${withIt.toFixed(2)}">always built</span>`;
  const gap = withIt - withoutIt;
  const tone = gap <= -0.05 ? "good" : gap >= 0.05 ? "bad" : "";
  const sign = gap <= -0.005 ? "−" : gap >= 0.005 ? "+" : "";
  return `<span data-tip="Average placement ${withIt.toFixed(2)} with it, ${withoutIt.toFixed(2)} without">avg <span class="${tone}">${sign}${Math.abs(gap).toFixed(2)}</span></span>`;
}

// Where each unit stands on a board nobody has positioned by hand, as "row,column" → unit. A match
// records no positions, so each unit takes its usual row: row 0 is the front. A row lines up its
// carries first and then its costliest units. The back row fills from a corner, so a carry stands
// in it, and the other rows fill from the centre, so a tank stands there. A row with more units
// than columns passes the extras to the next row inward.
const ROWS = 4;
const CENTRE_OUT = [3, 2, 4, 1, 5, 0, 6];
const CORNER_IN = [0, 1, 2, 3, 4, 5, 6];
function standing(units, carries) {
  const rows = Array.from({ length: ROWS }, () => []);
  for (const id of units) rows[unitOf(id).row ?? ROWS - 1].push(id);
  const rank = (id) => [carries.includes(id) ? 0 : 1, -unitOf(id).cost];
  const placed = {};
  for (const row of [0, ROWS - 1, 1, ROWS - 2]) {
    const line = rows[row].sort((a, b) => rank(a)[0] - rank(b)[0] || rank(a)[1] - rank(b)[1] || (a < b ? -1 : 1));
    rows[row < ROWS / 2 ? row + 1 : row - 1].push(...line.slice(CORNER_IN.length));
    const columns = row === ROWS - 1 ? CORNER_IN : CENTRE_OUT;
    line.slice(0, columns.length).forEach((id, place) => (placed[`${row},${columns[place]}`] = id));
  }
  return placed;
}

const HEXES = Array.from({ length: ROWS }, (_, row) => CORNER_IN.map((column) => `${row},${column}`)).flat();

// The places the reader gave a comp's units, as unit → "row,column". It is the `board` field of the
// comp's edit, and it keeps a place for a flex unit that is not picked just now.
function ownPlaces(comp) {
  try {
    const kept = JSON.parse((edits && edits[comp.id] && edits[comp.id].board) || "{}");
    return kept && typeof kept === "object" ? kept : {};
  } catch {
    return {};
  }
}

// Where the comp's units stand, as "row,column" → unit: each unit the reader placed stands there,
// and every other unit takes its derived place, or the nearest free hex when that one is taken.
function placesOf(comp) {
  const units = teamUnits(comp);
  const own = ownPlaces(comp);
  const placed = {};
  for (const id of units) if (HEXES.includes(own[id]) && !placed[own[id]]) placed[own[id]] = id;
  const kept = new Set(Object.values(placed));
  const far = (hex, from) => {
    const [row, column] = hex.split(",").map(Number);
    const [fromRow, fromColumn] = from.split(",").map(Number);
    return Math.abs(row - fromRow) * CORNER_IN.length + Math.abs(column - fromColumn);
  };
  for (const [hex, id] of Object.entries(standing(units, comp.carries))) {
    if (kept.has(id)) continue;
    const free = HEXES.filter((candidate) => !placed[candidate]).sort((a, b) => far(a, hex) - far(b, hex))[0];
    if (free) placed[free] = id;
  }
  return placed;
}

// A page that can save edits lets the reader drag a unit to another hex. Dropping it on a unit
// swaps the two.
function boardHtml(comp) {
  const at = placesOf(comp);
  const lines = [0, 1, 2, 3].map((row) => {
    const hexes = CORNER_IN.map((column) => {
      const id = at[`${row},${column}`];
      const unit = id && unitOf(id);
      const image = unit && unit.icon ? `<img src="${esc(unit.icon)}" alt="" draggable="false">` : "";
      return `<span class="hex" data-hex="${row},${column}" ${id && edits ? `draggable="true"` : ""} ${id ? unitTip(id) : ""}>${image}</span>`;
    });
    return `<div class="line">${hexes.join("")}</div>`;
  });
  const mine = Object.keys(ownPlaces(comp)).length > 0;
  const how = edits ? "Drag a unit to another hex to place it; the page keeps your places for this comp." : "";
  const about = mine
    ? "Your own places for these units. A unit you have not placed stands in the row of its attack range."
    : "The core and the picked flex units, each in the row of its attack range.";
  const reset = mine ? `<button id="reset-board" ${tipOf("Forget your places for this comp and show the derived ones.")}>Derived positions</button>` : "";
  return `<div class="board-box"><div class="board" ${tipOf(about, "The front row is at the top.", how)}>${lines.join("")}</div>
    <p class="note">${mine ? "your positions" : "derived positions"} ${reset}<span class="edit-state"></span></p></div>`;
}

// Moves the unit on one hex to another, swaps with a unit already there, and saves every unit's
// place, so the board stays as the reader left it when the derived places change with the data.
function moveUnit(comp, from, to) {
  const at = placesOf(comp);
  if (from === to || !at[from]) return;
  [at[from], at[to]] = [at[to], at[from]];
  const own = ownPlaces(comp);
  for (const [hex, id] of Object.entries(at)) if (id) own[id] = hex;
  saveBoard(comp, JSON.stringify(own));
}

function saveBoard(comp, text) {
  putEdit(comp.id, "board", text)
    .then(() => {
      const box = el("detail").querySelector(".board-box");
      if (box && state.comp === comp.id) box.outerHTML = boardHtml(comp);
    })
    .catch((error) => {
      const shown = el("detail").querySelector(".board-box .edit-state");
      if (shown) shown.textContent = `not saved: ${error.message}`;
    });
}

const SHOWN_IN_A_GROUP = 9;
const ITEM_ROWS = 6;

// The cheaper units of a unit's item group, cheapest first: what holds its items on the way up.
function holdersOf(unit) {
  const group = snap().item_groups.find((g) => g.units.includes(unit));
  const cost = unitOf(unit).cost;
  return (group ? group.units : []).filter((id) => unitOf(id).cost < cost).sort((a, b) => unitOf(a).cost - unitOf(b).cost);
}

// The stage plan a comp's own numbers propose, a line for each thing they can say, as [kind, line]:
// the components to take, who holds the carry's items until the carry arrives, when to roll, and
// where boards end. The kind names a line across builds, while its words change with the data.
function proposedPlan(comp) {
  const names = (ids) => ids.map((id) => unitOf(id).name).join(", ");
  const carry = comp.carries[0];
  const holders = carry ? holdersOf(carry).slice(0, 3) : [];
  const ends = comp.levels.filter(([, share]) => share >= 0.15).sort((a, b) => b[1] - a[1]);
  return [
    ["take", comp.take.length && `Take ${comp.take.map((id) => (snap().items[id] || { name: id }).name).join(", ")} first.`],
    ["holders", holders.length && `Until ${unitOf(carry).name} arrives, ${names(holders)} can hold its items.`],
    [
      "roll",
      comp.three_stars.length
        ? `Roll at level ${comp.roll_level} for 3-star ${names(comp.three_stars)}.`
        : `Level to ${comp.roll_level} before rolling.`,
    ],
    ["ends", ends.length && `Boards end at ${ends.map(([level, share]) => `level ${level} (${pct(share)})`).join(" or ")}.`],
  ].filter(([, line]) => line);
}

// What the reader changed in a comp's notes: lines of their own, the derived lines they removed,
// and the derived lines they reworded. The `plan` field of the comp's edit holds it as JSON.
// Two older forms are read as lines of the reader's own: a `plan` of plain text, and the free
// text of the `notes` field, which the next save moves into `plan`.
const textLines = (text) => (text || "").split("\n").map((line) => line.trim()).filter(Boolean);
function ownPlan(comp) {
  const edit = (edits && edits[comp.id]) || {};
  const before = textLines(edit.notes);
  const none = { own: [], hidden: [], changed: {} };
  try {
    const kept = JSON.parse(edit.plan || "{}");
    if (kept && typeof kept === "object" && !Array.isArray(kept)) {
      const mine = { ...none, ...kept };
      return { ...mine, own: [...mine.own, ...before] };
    }
  } catch {
    // Plain text from before the notes had lines.
  }
  return { ...none, own: [...textLines(edit.plan), ...before] };
}

// The plan's lines in order: the reader's own, then each derived line they left in, in their
// words where they reworded it. A line's key says which it is: `own:2` or a derived line's kind.
function planLines(comp) {
  const mine = ownPlan(comp);
  const own = mine.own.map((text, at) => ({ key: `own:${at}`, text }));
  const derived = proposedPlan(comp)
    .filter(([kind]) => !mine.hidden.includes(kind))
    .map(([kind, text]) => ({ key: kind, text: mine.changed[kind] || text }));
  return [...own, ...derived];
}

// Sets the line with this key to `text`, or removes it when `text` is empty. A derived line that
// goes back to its own words is no longer a change.
function withPlanLine(comp, key, text) {
  const mine = ownPlan(comp);
  const own = [...mine.own];
  const hidden = mine.hidden.filter((kind) => kind !== key);
  const changed = { ...mine.changed };
  if (key.startsWith("own:")) {
    const at = Number(key.slice(4));
    if (text) own[at] = text;
    else own.splice(at, 1);
  } else {
    delete changed[key];
    const derived = new Map(proposedPlan(comp)).get(key);
    if (!text) hidden.push(key);
    else if (text !== derived) changed[key] = text;
  }
  return { own, hidden, changed };
}

const PENCIL = `<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M10.6 2.4 13.6 5.4 5.4 13.6 2 14 2.4 10.6Z"/><path d="M9 4 12 7"/></svg>`;
let planEditing = null;
const PLAN_LINE = 300;

// Every line is in one list. On a page a server keeps edits for, a box above the list adds a
// line on Enter, and each line has a button to reword it and one to remove it.
function planHtml(comp) {
  const mine = ownPlan(comp);
  const line = ({ key, text }) => {
    if (!edits) return `<li>${esc(text)}</li>`;
    if (planEditing === `${comp.id}:${key}`) {
      return `<li><input class="plan-edit" data-plan-key="${key}" value="${esc(text)}" maxlength="${PLAN_LINE}" ${tipOf("Enter keeps the change. Escape leaves the line as it was.")}></li>`;
    }
    return `<li><span>${esc(text)}</span><button data-plan-edit="${key}" data-tip="Reword this line" aria-label="Reword this line">${PENCIL}</button><button data-plan-remove="${key}" data-tip="Remove this line">×</button></li>`;
  };
  const entry = edits
    ? `<input id="plan-entry" maxlength="${PLAN_LINE}" placeholder="Add a note" ${tipOf("Enter adds the note to the top of the list.")}>`
    : "";
  const restore =
    edits && (mine.hidden.length || Object.keys(mine.changed).length)
      ? `<button id="plan-restore" ${tipOf("Bring back the derived lines you removed or reworded. Your own lines stay.")}>Restore the derived lines</button>`
      : "";
  return `<div class="notes plan-box">${entry}<ul class="plan">${planLines(comp).map(line).join("")}</ul>
    <p class="note">${restore}<span class="edit-state"></span></p></div>`;
}

// Saves the reader's changes to the plan and draws the plan again. A plan with no change left
// is saved as nothing, so the comp's edit holds no `plan` at all.
function savePlan(comp, mine, focus = "") {
  const unchanged = !mine.own.length && !mine.hidden.length && !Object.keys(mine.changed).length;
  const moved = edits[comp.id] && edits[comp.id].notes ? { notes: "" } : {};
  putEdits(comp.id, { plan: unchanged ? "" : JSON.stringify(mine), ...moved })
    .then(() => {
      planEditing = null;
      drawPlan(comp, focus);
    })
    .catch((error) => {
      const shown = el("detail").querySelector(".plan-box .edit-state");
      if (shown) shown.textContent = `not saved: ${error.message}`;
    });
}

function drawPlan(comp, focus = "") {
  const box = el("detail").querySelector(".plan-box");
  if (!box || state.comp !== comp.id) return;
  box.outerHTML = planHtml(comp);
  const next = focus && el("detail").querySelector(focus);
  if (next) {
    next.focus();
    if (next.select && focus === ".plan-edit") next.select();
  }
}

function keyUnitsHtml(comp) {
  const tiles = (ids) => ids.slice(0, SHOWN_IN_A_GROUP).map((id) => unitTile(id, "s")).join("");
  const buildItem = (note) => {
    const needs = note.needs
      .map(
        (pair) =>
          `<span class="needs" data-tip="${pair.avg_together.toFixed(2)} together, ${pair.avg_apart.toFixed(2)} apart">needs ${itemIcon(pair.item)}</span>`,
      )
      .join("");
    const without = note.avg_without === null ? "every build has it" : `${note.avg_without.toFixed(2)} without`;
    const placed = `In ${pct(note.share)} of its builds. Average placement ${note.avg_with.toFixed(2)} with it, ${without}.`;
    return `<span class="build-item ${note.critical ? "critical" : ""}" ${tipOf(placed)}>
      ${itemIcon(note.item, { note: placed })}<span class="figures">${pct(note.share)}${note.critical ? `<br><b>critical</b>` : ""}</span>${needs}</span>`;
  };
  return comp.key_units
    .map(({ unit, role, build }) => {
      const group = snap().item_groups.find((g) => g.units.includes(unit));
      const holders = holdersOf(unit);
      const pivots = role === "tank" ? [] : pivotsFrom(comp, unit, group);
      return `<div class="key-unit"><div class="role">${esc(role)}</div>${unitTile(unit, "m")}
        <div class="uses">
          <div class="row"><span class="note">builds</span>${build.map(buildItem).join("") || "varies"}</div>
          ${holders.length ? `<div class="row"><span class="note" data-tip="Cheaper units that can hold its items, cheapest first">holders</span>${tiles(holders)}</div>` : ""}
          ${pivots.length ? `<div class="row"><span class="note" data-tip="Carries of other comps that build the same items. Click one to open its comp.">pivots</span>${pivots.join("")}</div>` : ""}
        </div>
      </div>`;
    })
    .join("");
}

// The main carries of other comps that share `unit`'s item group: where its items go if the comp is dropped.
// Each opens the most played comp it carries.
function pivotsFrom(comp, unit, group) {
  const carried = new Map();
  for (const other of [...snap().comps].sort(SORTS.play)) {
    const carry = other.carries[0];
    if (other.id !== comp.id && carry && !carried.has(carry)) carried.set(carry, other);
  }
  return (group ? group.units : [])
    .filter((id) => id !== unit && !comp.core.includes(id) && carried.has(id))
    .sort((a, b) => carried.get(a).avg_placement - carried.get(b).avg_placement)
    .slice(0, SHOWN_IN_A_GROUP)
    .map((id) => {
      const target = carried.get(id);
      const note = `Carries ${nameOf(target)}: average placement ${target.avg_placement.toFixed(2)}, played ${pct(target.share)}`;
      return `<span class="pivot" data-open="${target.id}">${unitTile(id, "s", { note })}</span>`;
    });
}

// Each column's own order is the one the page calls descending: the best or the most first.
// A second click on the sorted column turns it round.
const SORTS = {
  play: (a, b) => b.share - a.share,
  avg: (a, b) => a.avg_placement - b.avg_placement,
  top4: (a, b) => b.top4 - a.top4,
  win: (a, b) => b.win_rate - a.win_rate,
  name: (a, b) => nameOf(a).localeCompare(nameOf(b)),
  level: (a, b) => a.roll_level - b.roll_level || a.avg_placement - b.avg_placement,
};
// The stylesheet gives each column a fixed width and hides columns from the right as the list narrows.
const COLUMNS = [
  ["Tier", "avg", "c-tier"],
  ["Comp", "name", "c-name"],
  ["Level", "level", "c-level"],
  ["Core", null, "c-core"],
  ["Avg", "avg", "c-avg num"],
  ["Top 4", "top4", "c-top4 num"],
  ["Win", "win", "c-win num"],
  ["Play", "play", "c-play num"],
];

// The detail content keeps one size. It is laid out at the pane's width and wraps to it, and the
// pane scrolls down when the content is taller. Only a pane too narrow for the widest thing that
// cannot wrap draws the content smaller, so nothing reaches past the pane's right edge.
// The Comp column is as wide as the longest name in the snapshot, so a comp renamed to a longer
// name widens it. The names of every comp count, not only the listed ones, so the column keeps
// its width while a filter changes the list.
const NAME_WIDTHS = [90, 360];
const pen = document.createElement("canvas").getContext("2d");
let nameWidth = 0;
function fitNames() {
  const row = getComputedStyle(el("comps"));
  pen.font = `${row.fontWeight} ${row.fontSize} ${row.fontFamily}`;
  const longest = Math.max(0, ...snap().comps.map((comp) => pen.measureText(nameOf(comp)).width));
  // The 18 pixels are the mark that opens a comp's subcomps.
  const width = Math.ceil(Math.min(Math.max(longest + 20, NAME_WIDTHS[0]), NAME_WIDTHS[1]));
  if (width === nameWidth) return;
  nameWidth = width;
  document.documentElement.style.setProperty("--name-width", `${width}px`);
  applyListWidth();
}

function fitWidth() {
  const sheet = el("sheet");
  if (!sheet) return;
  const pane = el("detail");
  const padding = getComputedStyle(pane);
  const width = pane.clientWidth - parseFloat(padding.paddingLeft) - parseFloat(padding.paddingRight);
  let scale = 1;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    sheet.style.zoom = scale;
    sheet.style.width = `${width / scale}px`;
    if (sheet.scrollWidth <= sheet.clientWidth) break;
    scale *= sheet.clientWidth / sheet.scrollWidth;
  }
}

let shownComp = null;
function renderDetail() {
  showTip(null);
  const comp = snap().comps.find((candidate) => candidate.id === state.comp);
  if (!comp) {
    el("detail").innerHTML = `<p class="empty">${MAXIMIZE} No comp matches.</p>`;
    return;
  }
  el("detail").innerHTML = detailHtml(comp);
  fitWidth();
  const shown = `${state.snapshot}:${comp.id}`;
  if (shown !== shownComp) el("detail").scrollTop = 0;
  shownComp = shown;
}

// The flex packages picked for each comp, as "slot.option" keys. A comp nobody has touched starts
// with the packages it is usually fielded with.
const pickedByComp = new Map();
function pickedFlex(comp) {
  const key = `${state.snapshot}:${comp.id}`;
  if (!pickedByComp.has(key)) {
    const placed = new Set(comp.fielded);
    const picked = new Set();
    comp.flex.forEach((options, slot) =>
      options.forEach((p, option) => p.units.every((id) => placed.has(id)) && picked.add(`${slot}.${option}`)),
    );
    pickedByComp.set(key, picked);
  }
  return pickedByComp.get(key);
}

// One slot holds one option, so picking an option drops the others of its slot.
function togglePick(comp, key) {
  const picked = pickedFlex(comp);
  if (picked.delete(key)) return;
  const slot = key.split(".")[0];
  for (const other of [...picked]) if (other.split(".")[0] === slot) picked.delete(other);
  picked.add(key);
}

function teamUnits(comp) {
  const picked = pickedFlex(comp);
  const flex = comp.flex.flatMap((options, slot) => options.filter((_, option) => picked.has(`${slot}.${option}`)).flatMap((p) => p.units));
  return [...new Set([...comp.core, ...flex])];
}

// Riot's team code: "02", ten units as three hex digits each with 000 for an empty place, then the set's name.
const TEAM_PLACES = 10;
const teamCode = (comp) => teamCodeOf(teamUnits(comp));

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
}

function detailHtml(comp) {
  const threeStar = (id) => comp.three_stars.includes(id);
  const picked = pickedFlex(comp);
  const packageHtml = (p, key) => `<div class="package ${picked.has(key) ? "picked" : ""}" data-flex="${key}">${p.units.map((id) => unitTile(id, "m", { threeStar: threeStar(id) })).join("")}
        <div class="figures" ${tipOf(`On ${pct(p.share)} of boards. Those boards place ${p.avg_placement.toFixed(2)} on average.`)}><b>${pct(p.share)}</b><br>${delta(p.avg_placement, comp.avg_placement)}</div></div>`;
  const cost = (p) => Math.max(...p.units.map((id) => unitOf(id).cost));
  const slotHtml = (options, slot) =>
    options
      .map((p, option) => {
        if (!option) return packageHtml(p, `${slot}.${option}`);
        const upgrade = cost(p) > cost(options[option - 1]);
        const joint = upgrade
          ? `<span class="joint" data-tip="Played until the costlier one is found">→</span>`
          : `<span class="joint" data-tip="One is played in the other's place">or</span>`;
        return joint + packageHtml(p, `${slot}.${option}`);
      })
      .join("");
  const packages = comp.flex.map((options, slot) => `<div class="slot ${options.length > 1 ? "shared" : ""}">${slotHtml(options, slot)}</div>`).join("");
  const team = teamUnits(comp);
  const teamNote = team.length > TEAM_PLACES ? `the first ${TEAM_PLACES} of ${team.length} units` : `${team.length} units`;
  const sharedSlots = comp.flex.some((options) => options.length > 1);
  const shift = (s) => unitTile(s.unit, "m", { note: `On ${pct(s.share)} of boards at this level, ${pct(s.share_below)} a level below.` });
  const levelUps = comp.level_ups
    .map(
      (up) => `<div class="level-up">
        <b data-tip="${pct(up.share)} of boards, avg ${up.avg_placement.toFixed(2)}">Level ${up.level}</b>
        ${up.adds.length ? `<div class="row">${up.adds.map(shift).join("")}</div>` : ""}
        ${up.drops.length ? `<div class="out"><span class="note">goes out</span><div class="row">${up.drops.map(shift).join("")}</div></div>` : ""}
      </div>`,
    )
    .join("");
  const tiered = comp.traits.filter((t) => t.tiers > 1);
  const top = Math.max(...tiered.map((t) => t.tier / t.tiers), 0);
  const traits = comp.traits
    .map((t) => {
      const { icon, breakpoints = [] } = snap().traits[t.trait] || {};
      const full = t.tiers > 1 && t.tier / t.tiers === top;
      const holders = comp.core.filter((id) => unitOf(id).traits.includes(t.trait)).map((id) => unitOf(id).name);
      const tip = tipOf(
        traitName(t.trait),
        `${t.units} on a usual board${t.tiers > 1 ? `, tier ${t.tier} of ${t.tiers}` : ""}`,
        breakpoints.length && `Breakpoints: ${breakpoints.join(" / ")}`,
        holders.length && `Core units: ${holders.join(", ")}`,
      );
      return `<span class="trait ${full ? "top" : ""}" ${tip}>${icon ? `<img src="${esc(icon)}" alt="">` : ""}${t.units} ${esc(traitName(t.trait))}</span>`;
    })
    .join("");
  const items = comp.items
    .slice(0, ITEM_ROWS)
    .map(
      (pick, index) => `<tr><td class="rank">${index + 1}</td><td>${itemIcon(pick.item)}</td>
        <td class="holder"><span class="joint">→</span>${unitTile(pick.holder, "s")}</td><td>${pct(pick.share)}</td>
        <td class="note">${placementGap(pick.avg_with, pick.avg_without)}</td></tr>`,
    )
    .join("");
  const spare = comp.spare
    .map(
      (found) => `<div class="row">${itemIcon(found.component)}<span class="joint">→</span>${found.uses.map((item) => `<span class="use">${itemIcon(item)} ${itemName(item)}</span>`).join("")}</div>`,
    )
    .join("");
  const smallTiles = (swaps) => swaps.map((swap) => unitTile(swap.unit, "s", { note: `On ${pct(swap.share_with)} of boards with it, ${pct(swap.share_without)} without.` })).join("");
  const onBoards = (special) => `On ${pct(special.share)} of the comp's boards.`;
  // The snapshot gives the placement of the boards that hold an emblem or artifact. The comp's own
  // average is the mean of those boards and the rest, weighted by the share, so the rest follows.
  const placementWithout = (special, comp) =>
    special.share < 1 ? (comp.avg_placement - special.share * special.avg_placement) / (1 - special.share) : null;
  const specials = comp.specials
    .map(
      (special) => `<div class="special">
        <span class="what" ${tipOf(onBoards(special))}>${itemIcon(special.item, { note: onBoards(special) })} ${itemName(special.item)} <span class="note">${special.kind}</span></span>
        <span class="figures">${placementGap(special.avg_placement, placementWithout(special, comp))}</span>
        <span class="part"><span class="note">on</span>${unitTile(special.holder, "s")} ${esc(unitOf(special.holder).name)} <span class="note">${pct(special.holder_share)}</span></span>
        ${special.beside.length ? `<span class="part"><span class="note">beside</span>${special.beside.map((item) => itemIcon(item)).join("")}</span>` : ""}
        ${special.adds.length ? `<span class="part"><span class="note">comes in</span>${smallTiles(special.adds)}</span>` : ""}
        ${special.drops.length ? `<span class="part"><span class="note">goes out</span>${smallTiles(special.drops)}</span>` : ""}
      </div>`,
    )
    .join("");
  return `<div id="sheet">
    <header><div class="title">${MAXIMIZE}<h1><span class="tier t${comp.tier}">${comp.tier}</span>${nameHtml(comp)}</h1>
      <button id="copy-team" ${tipOf(teamCode(comp), `${teamNote}: the core and the picked flex units`)}>Copy team code</button>
      <button id="open-planner" ${tipOf("Put this board on the planner: the core and the picked flex units, where they stand here.", "It replaces the planner's working board.")}>Open in planner</button></div>
      <p class="stats"><b>${esc(comp.style)}</b> · avg <b>${comp.avg_placement.toFixed(2)}</b> · top 4 <b>${pct(comp.top4)}</b> · win <b>${pct(comp.win_rate)}</b> · play <b>${(comp.share * 100).toFixed(1)}%</b> · ${comp.boards.toLocaleString()} boards</p>${categoriesHtml(comp)}</header>
    <div class="flow">
      ${section("Core", `<div class="row">${comp.core.map((id) => unitTile(id, "l", { threeStar: threeStar(id) })).join("")}</div>`)}
      ${section("Traits", `<div class="row">${traits}</div>`, { width: "wraps" })}
      ${section("Flex", `<div class="row">${packages || `<span class="note">no regular flex units</span>`}</div>`, {
        info: `Units the comp's boards add to its core, with the share of boards that hold each and how those boards place. Click one to put it in the team code, or to take it out.${
          sharedSlots ? "\nUnits in one outline take one slot: a board rarely holds both. An arrow points to the costlier unit, which the cheaper one is played until." : ""
        }`,
      })}
      ${section("Level up", `<div class="levels">${levelUps || `<span class="note">no level above the usual one has enough boards</span>`}</div>`, {
        info: "The units that come in at each level above the comp's usual one. A unit comes in when its share of boards rises 15 points from the level below, and goes out when it falls 15.\nHover a level or a unit for its figures. A higher level places better partly because only a winning player reaches it.",
      })}
    </div>
    <div class="flow">
      ${section("Key units", `<div>${keyUnitsHtml(comp) || `<span class="note">no unit holds items regularly</span>`}</div>`, {
        width: "half",
        info: "The carry, the 2nd carry and the tank, each with its commonest items and the share of its builds that hold each.\nCritical: in 70% of the unit's builds, or in 40% and builds without it place 0.4 worse.\nNeeds: the item places 0.5 better beside that one than apart.\nHolders: cheaper units that can hold its items, cheapest first.\nCorrelations, from builds of one size.",
      })}
      ${section(
        "Items",
        `<div><div class="row take"><span class="note">Priority</span>${comp.take.map((item) => itemIcon(item)).join("")}</div>
        <table class="items">${items}</table>
        ${spare ? `<div class="spare"><div class="note">the components it uses least go into</div>${spare}</div>` : ""}</div>`,
        {
          width: "half",
          info: "Priority: the components to take first.\nThe table lists the items the comp's boards hold most, the unit that holds each, and the share of boards.\navg: how boards with the item place against boards without it. Negative is better. A correlation, not an effect.\nThe last rows list the two components the comp uses least and the items built with them.",
        },
      )}
      ${
        specials
          ? section("Emblems, artifacts", `<div>${specials}</div>`, {
              width: "half",
              info: "An emblem or artifact on 3% of the comp's boards or more.\navg: how boards with it place against the comp's other boards. Negative is better. A correlation, not an effect.\non: the unit that holds it most.\nbeside: items that unit also holds.\ncomes in, goes out: units those boards play more or less often, by 15 points.\nHover a figure or a unit for its shares.",
            })
          : ""
      }
    </div>
    ${section("Positioning", `<div>${boardHtml(comp)}</div>`)}
    ${savedBoards(comp.id).length ? section("Saved boards", `<div class="saved-cards">${compBoardsHtml(comp)}</div>`, { info: "Boards saved from the planner for this comp.\nClick one to open it in the planner." }) : ""}
    ${section("Notes", planHtml(comp), { info: "The lines are derived from the comp's boards: its item priority, its carry's item group, what it three-stars and the levels its boards end at.\nWhen the page can save, type a line and press Enter to add it, and use a line's buttons to reword or remove it. A derived line you leave alone keeps following the data." })}
    </div>`;
}

// What the reader has written about each comp of this set, as comp id → field → text. It stays
// null on a page no server keeps edits for, such as one opened from a file, and the page then
// shows nothing to edit. Every snapshot of a page is of one set, so one request covers them all.
let edits = null;
const editsOf = () => `api/edits/${snap().selection.set}`;
function loadEdits() {
  fetch(editsOf())
    .then((reply) => (reply.ok ? reply.json() : null))
    .then((found) => {
      if (!found) return;
      edits = found;
      renderList();
    })
    .catch(() => {});
}

// The name a comp goes by: the one the reader gave it, or else the one the analysis derived.
const nameOf = (comp) => (edits && edits[comp.id] && edits[comp.id].name) || comp.name;

// On a page a server keeps edits for, a click on the name in the comp's heading turns it into a
// box. Enter or leaving the box keeps the name, Escape drops the change, and an empty box goes
// back to the derived name.
let naming = null;
function nameHtml(comp) {
  if (!edits) return esc(nameOf(comp));
  if (naming !== comp.id) {
    return `<span id="comp-name" tabindex="0" ${tipOf("Click to rename this comp.")}>${esc(nameOf(comp))}</span>`;
  }
  const own = (edits[comp.id] || {}).name || "";
  return `<input id="name-edit" maxlength="60" value="${esc(own || comp.name)}" placeholder="${esc(comp.name)}" ${tipOf("Enter keeps the name. Escape leaves it as it was. Empty goes back to the derived name.")}>`;
}

function keepName(comp, box) {
  if (naming !== comp.id) return;
  naming = null;
  const typed = box.value.trim();
  const name = typed === comp.name ? "" : typed;
  if (name === ((edits[comp.id] || {}).name || "")) return renderDetail();
  putEdit(comp.id, "name", name)
    .then(renderList)
    .catch(() => renderDetail());
}

// Saves fields of a comp's edit in one request, and keeps the page's copy in step.
function putEdits(compId, fields) {
  const sent = { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields) };
  return fetch(`${editsOf()}/${compId}`, sent).then((reply) => {
    if (!reply.ok) throw new Error(`the server answered ${reply.status}`);
    edits[compId] = { ...edits[compId], ...fields };
  });
}
const putEdit = (compId, field, text) => putEdits(compId, { [field]: text });


function move(step) {
  const comps = visibleComps();
  const index = comps.findIndex((comp) => comp.id === state.comp);
  const next = comps[Math.min(comps.length - 1, Math.max(0, index + step))];
  if (next) {
    state.comp = next.id;
    renderList();
    document.querySelector("#comps li.selected")?.scrollIntoView({ block: "nearest" });
  }
}

// The list's width is a number of pixels, or "" for the width the stylesheet gives it. At 0 the
// comp page is maximized: it has the whole window. The browser keeps the width, and the width to
// go back to from maximized. The body's `maximized` class follows the width however it was set,
// so the button in the comp page's corner reads the same after a click and after a drag.
const LIST_WIDTH = "tft-assistant.list-width";
const LIST_RESTORE = "tft-assistant.list-restore";
const NARROWEST_LIST = 260;
// The list is never wider than the width that shows all of its columns: the Comp column's width
// and what the stylesheet states for the rest. A wider list would only add empty space and take
// it from the comp page.
const OTHER_COLUMNS = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--other-columns"));
// The comp page's least width leaves the list its full width in a window 1,024 pixels wide.
const NARROWEST_DETAIL = 300;
const storedWidth = (key) => (localStorage.getItem(key) ? Number(localStorage.getItem(key)) : "");
// The browser keeps the width that was asked for, so a list dragged to its full width has it
// again after a longer name widens the Comp column.
function applyListWidth() {
  const asked = storedWidth(LIST_WIDTH);
  if (asked === "") document.body.style.removeProperty("--list-width");
  else document.body.style.setProperty("--list-width", `${Math.min(asked, OTHER_COLUMNS + nameWidth)}px`);
  document.body.classList.toggle("maximized", asked === 0);
  fitWidth();
}
function setListWidth(asked) {
  localStorage.setItem(LIST_WIDTH, asked);
  applyListWidth();
}
function maximize(from) {
  if (from !== 0) localStorage.setItem(LIST_RESTORE, from);
  setListWidth(0);
}
const MAXIMIZE = `<button id="maximize">
  <span class="grow" data-tip="Give the comp page the whole window"><svg viewBox="0 0 16 16"><path d="M9.5 2H14v4.5M14 2 9 7M6.5 14H2V9.5M2 14l5-5"/></svg></span>
  <span class="shrink" data-tip="Bring the list back"><svg viewBox="0 0 16 16"><path d="M13.5 7H9V2.5M9 7l5-5M2.5 9H7v4.5M7 9l-5 5"/></svg></span>
</button>`;
applyListWidth();
addEventListener("resize", fitWidth);

// A drag that passes the middle of the narrowest list maximizes the comp page, and a drag back
// past it brings the list back. `draggedFrom` is the width to restore after such a drag.
let draggedFrom = "";
el("divider").addEventListener("pointerdown", (event) => {
  event.target.setPointerCapture(event.pointerId);
  draggedFrom = storedWidth(LIST_WIDTH);
  document.body.classList.add("resizing");
});
el("divider").addEventListener("pointermove", (event) => {
  if (!document.body.classList.contains("resizing")) return;
  if (event.clientX < NARROWEST_LIST / 2) maximize(draggedFrom);
  else setListWidth(Math.round(Math.min(Math.max(event.clientX, NARROWEST_LIST), innerWidth - NARROWEST_DETAIL)));
});
el("divider").addEventListener("pointerup", () => document.body.classList.remove("resizing"));
el("divider").addEventListener("dblclick", () => setListWidth(""));

const HIDE_NAMES = "tft-assistant.hide-names";
const showNames = (shown) => {
  el("names").checked = shown;
  document.body.classList.toggle("hide-names", !shown);
};
showNames(!localStorage.getItem(HIDE_NAMES));
el("names").addEventListener("change", (event) => {
  showNames(event.target.checked);
  if (event.target.checked) localStorage.removeItem(HIDE_NAMES);
  else localStorage.setItem(HIDE_NAMES, "1");
  fitWidth();
});

// A click on a section's heading folds the section to its heading, or opens it again. The fold
// belongs to the section, not to one comp, so it holds as the comp changes and after a reload.
const FOLDED = "tft-assistant.folded-sections";
const folded = new Set(JSON.parse(localStorage.getItem(FOLDED) || "[]"));
// `width` says how a section shares a row with its neighbours. A section takes the width of its
// content laid on one line. "wraps" and "half" mark a section whose content wraps, so its content
// has no width of its own: it asks for a fixed width and takes what is left of the row.
// `info` explains how to read the section. It is the hover card of the "i" beside the heading,
// which stays on the line of the heading's last word.
function section(title, body, { width = "", info = "" } = {}) {
  const fold = folded.has(title) ? "folded" : "";
  const mark = info ? `<span class="info" tabindex="0" ${tipOf(info)}>i</span>` : "";
  const words = title.split(" ");
  const heading = `${words.slice(0, -1).join(" ")} <span class="last">${words.at(-1)}${mark}</span>`;
  return `<section class="${width} ${fold}" data-section="${title}"><h2>${heading}</h2>${body}</section>`;
}

// One box is the hover card of the whole page. It shows the `data-tip` of the nearest thing under
// the pointer or the focus that has one. It is fixed to the window, not laid out in the page, so
// no pane's edge clips it. It goes under its thing, or above when there is no room under.
const tip = document.body.appendChild(Object.assign(document.createElement("div"), { id: "tip" }));
function showTip(target) {
  const marked = target && target.closest ? target.closest("[data-tip]") : null;
  tip.style.display = marked ? "block" : "none";
  if (!marked) return;
  tip.textContent = marked.dataset.tip;
  tip.style.left = "0px";
  const at = marked.getBoundingClientRect();
  const below = at.bottom + 6;
  tip.style.left = `${Math.max(8, Math.min(at.left, innerWidth - tip.offsetWidth - 8))}px`;
  tip.style.top = `${below + tip.offsetHeight > innerHeight ? Math.max(8, at.top - 6 - tip.offsetHeight) : below}px`;
}
document.addEventListener("mouseover", (event) => showTip(event.target));
document.addEventListener("focusin", (event) => showTip(event.target));
document.addEventListener("focusout", () => showTip(null));
document.addEventListener("scroll", () => showTip(null), true);
document.documentElement.addEventListener("mouseleave", () => showTip(null));

el("detail").addEventListener("click", (event) => {
  if (event.target.closest("#maximize")) {
    if (document.body.classList.contains("maximized")) setListWidth(storedWidth(LIST_RESTORE));
    else maximize(storedWidth(LIST_WIDTH));
    return;
  }
  // Opening a comp and folding a section need no open comp: a filter can leave the list empty.
  const opened = event.target.closest("[data-open]");
  const folding = !event.target.closest(".info") && event.target.closest("section > h2");
  if (opened) {
    openComp(opened.dataset.open);
    document.querySelector("#comps li.selected")?.scrollIntoView({ block: "nearest" });
    return;
  }
  if (folding) {
    const title = folding.parentElement.dataset.section;
    if (!folded.delete(title)) folded.add(title);
    localStorage.setItem(FOLDED, JSON.stringify([...folded]));
    renderList();
    return;
  }
  const comp = snap().comps.find((candidate) => candidate.id === state.comp);
  if (!comp || event.target.closest(".info")) return;
  if (event.target.closest("#comp-name")) {
    naming = comp.id;
    renderDetail();
    const box = el("name-edit");
    box.focus();
    box.select();
    return;
  }
  const planEdit = event.target.closest("[data-plan-edit]");
  const planRemove = event.target.closest("[data-plan-remove]");
  if (planEdit) {
    planEditing = `${comp.id}:${planEdit.dataset.planEdit}`;
    drawPlan(comp, ".plan-edit");
    return;
  }
  if (planRemove) {
    savePlan(comp, withPlanLine(comp, planRemove.dataset.planRemove, ""));
    return;
  }
  if (event.target.closest("#plan-restore")) {
    savePlan(comp, { ...ownPlan(comp), hidden: [], changed: {} });
    return;
  }
  if (event.target.closest("#reset-board")) {
    saveBoard(comp, "");
    return;
  }
  const uncategory = event.target.closest("[data-uncategory]");
  if (uncategory) {
    changeCategory(uncategory.dataset.uncategory, false);
    return;
  }
  const flex = event.target.closest("[data-flex]");
  if (flex) {
    togglePick(comp, flex.dataset.flex);
    renderDetail();
  } else if (event.target.closest("#open-planner")) {
    // The comp's board as its page draws it, the reader's own places included.
    localStorage.setItem(plannerKey(), JSON.stringify(placesOf(comp)));
    localStorage.removeItem(emblemKey());
    Object.assign(state, { saveName: nameOf(comp), saveStage: "", saveComp: comp.id });
    setView("planner");
  } else if (event.target.closest("#copy-team")) {
    copyText(teamCode(comp)).then(() => {
      const button = el("copy-team");
      button.textContent = "Copied";
      setTimeout(() => (button.textContent = "Copy team code"), 1500);
    });
  }
});

el("selection").innerHTML = SNAPSHOTS.map((s, index) => `<option value="${index}">${esc(s.label)}</option>`).join("");
el("selection").addEventListener("change", (event) => {
  state.snapshot = Number(event.target.value);
  renderList();
});
// A category change draws the comp's page again, so a failure shows where the page says "saved".
function changeCategory(category, member) {
  const comp = snap().comps.find((candidate) => candidate.id === state.comp);
  setCategory(comp, category, member).catch((error) => {
    const shown = el("detail").querySelector(".categories .edit-state");
    if (shown) shown.textContent = `not saved: ${error.message}`;
  });
}
// ── The planner ──────────────────────────────────────────────────────────────────────────────
// The reader builds a board from the roster. The board is "row,column" → unit, kept in the
// browser for each set, so it is there after a reload and needs no server.
const PLANNER = "tft-assistant.planner";
const plannerKey = () => `${PLANNER}.${snap().selection.set}`;
function plannerBoard() {
  try {
    const kept = JSON.parse(localStorage.getItem(plannerKey()) || "{}");
    const board = {};
    for (const hex of HEXES) if (kept && snap().units[kept[hex]]) board[hex] = kept[hex];
    return board;
  } catch {
    return {};
  }
}
function keepPlanner(board) {
  localStorage.setItem(plannerKey(), JSON.stringify(board));
  renderPlanner();
}
// The emblems the board holds, as trait → 1. An emblem gives its trait to a unit that lacks it,
// so the page keeps the traits and not which unit holds which. The value is a count because a
// saved board stores it as one.
const emblemKey = () => `${plannerKey()}.emblems`;
function plannerEmblems() {
  try {
    const kept = JSON.parse(localStorage.getItem(emblemKey()) || "{}");
    return Object.fromEntries(
      Object.entries(kept || {})
        .filter(([trait, count]) => snap().traits[trait] && count > 0)
        .map(([trait]) => [trait, 1]),
    );
  } catch {
    return {};
  }
}
function keepEmblems(emblems) {
  localStorage.setItem(emblemKey(), JSON.stringify(emblems));
  renderPlanner();
}
// A saved board is a planner board with a name and a stage, kept by the server in the `boards`
// field of the comp it is attached to, or of NO_COMP when it is attached to none. A board saved
// under the name and stage of another of its comp replaces it.
const NO_COMP = "0000000000";
const STAGES = ["", "Stage 2", "Stage 3", "Stage 4", "Late"];
Object.assign(state, { saveName: "", saveStage: "", saveComp: null });
function savedBoards(compId) {
  try {
    const kept = JSON.parse((edits && edits[compId] && edits[compId].boards) || "[]");
    return Array.isArray(kept) ? kept.filter((board) => board && board.units) : [];
  } catch {
    return [];
  }
}
// Every saved board, as [comp id, place in its comp's list, board], attached ones first.
function allSaved() {
  const known = new Set(snap().comps.map((comp) => comp.id));
  return Object.keys(edits || {})
    .filter((id) => id === NO_COMP || known.has(id))
    .sort((a, b) => Number(a === NO_COMP) - Number(b === NO_COMP))
    .flatMap((id) => savedBoards(id).map((board, place) => [id, place, board]));
}
function putBoards(compId, boards) {
  return putEdits(compId, { boards: boards.length ? JSON.stringify(boards) : "" })
    .then(renderList)
    .catch((error) => {
      const shown = el("save-state");
      if (shown) shown.textContent = `not saved: ${error.message}`;
    });
}
function savePlanned() {
  const compId = state.saveComp || NO_COMP;
  const entry = { name: state.saveName.trim() || "Board", stage: state.saveStage, units: plannerBoard(), emblems: plannerEmblems() };
  const boards = savedBoards(compId).filter((board) => board.name !== entry.name || board.stage !== entry.stage);
  return putBoards(compId, [...boards, entry]);
}
function loadSaved(compId, place) {
  const board = savedBoards(compId)[place];
  if (!board) return;
  localStorage.setItem(emblemKey(), JSON.stringify(board.emblems || {}));
  localStorage.setItem(plannerKey(), JSON.stringify(board.units));
  Object.assign(state, { saveName: board.name, saveStage: board.stage || "", saveComp: compId === NO_COMP ? null : compId });
  setView("planner");
}
function miniBoardHtml(units) {
  const lines = [0, 1, 2, 3].map((row) => {
    const hexes = CORNER_IN.map((column) => {
      const unit = snap().units[units[`${row},${column}`]];
      return `<span class="hex">${unit && unit.icon ? `<img src="${esc(unit.icon)}" alt="">` : ""}</span>`;
    });
    return `<div class="line">${hexes.join("")}</div>`;
  });
  return `<div class="board mini">${lines.join("")}</div>`;
}
// The saved boards of one comp, on its page. A click opens one in the planner.
function compBoardsHtml(comp) {
  return savedBoards(comp.id)
    .map(
      (board, place) => `<div class="saved-card" data-load="${comp.id}:${place}" ${tipOf("Click to open it in the planner.")}>
        ${miniBoardHtml(board.units)}<p class="note"><b>${esc(board.name)}</b>${board.stage ? ` · ${esc(board.stage)}` : ""}</p></div>`,
    )
    .join("");
}

// One emblem for each trait that has one, by the trait's name.
function emblemItems() {
  const found = new Map();
  for (const [id, item] of Object.entries(snap().items)) if (item.emblem_of && snap().traits[item.emblem_of] && !found.has(item.emblem_of)) found.set(item.emblem_of, id);
  return [...found].sort((a, b) => traitName(a[0]).localeCompare(traitName(b[0])));
}

// The units a player can buy, cheapest first: the ones Riot's team planner lists.
const rosterUnits = () =>
  Object.keys(snap().units)
    .filter((id) => unitOf(id).planner_code && unitOf(id).traits.length)
    .sort((a, b) => unitOf(a).cost - unitOf(b).cost || unitOf(a).name.localeCompare(unitOf(b).name));

// Each trait the units field, with its count, how many breakpoints that count reaches and the
// next breakpoint. A unit counts once however often it is on the board. The traits that reach a
// breakpoint come first, then the ones nearest their first.
function activeTraits(units, emblems = {}) {
  const counts = new Map();
  const fielded = [...new Set(units)];
  for (const id of fielded) for (const trait of unitOf(id).traits) counts.set(trait, (counts.get(trait) || 0) + 1);
  // An emblem counts only on a unit that lacks its trait.
  for (const [trait, held] of Object.entries(emblems)) {
    const takers = fielded.filter((id) => !unitOf(id).traits.includes(trait)).length;
    if (Math.min(held, takers)) counts.set(trait, (counts.get(trait) || 0) + Math.min(held, takers));
  }
  return [...counts]
    .map(([trait, count]) => {
      const breakpoints = (snap().traits[trait] || {}).breakpoints || [];
      const reached = breakpoints.filter((at) => at <= count).length;
      return { trait, count, breakpoints, reached, next: breakpoints[reached] };
    })
    .sort((a, b) => Math.sign(b.reached) - Math.sign(a.reached) || b.count - a.count || traitName(a.trait).localeCompare(traitName(b.trait)));
}

// The hex a unit added from the roster takes: the free hex of its usual row nearest the centre,
// or else the nearest free hex of any row.
function freeHexFor(id, board) {
  const row = unitOf(id).row ?? ROWS - 1;
  const order = [...CENTRE_OUT.map((column) => `${row},${column}`), ...HEXES];
  return order.find((hex) => !board[hex]);
}

function togglePlanned(id) {
  const board = plannerBoard();
  const at = Object.keys(board).find((hex) => board[hex] === id);
  if (at) delete board[at];
  else {
    const hex = freeHexFor(id, board);
    if (hex) board[hex] = id;
  }
  keepPlanner(board);
}

function teamCodeOf(units) {
  const numbers = units.map((id) => unitOf(id).planner_code).filter(Boolean);
  const places = Array.from({ length: TEAM_PLACES }, (_, place) => (numbers[place] || 0).toString(16).padStart(3, "0"));
  return `02${places.join("")}${snap().team_code_set}`;
}

// The comps whose core the board shares most of, as [comp, shared units, missing units].
const CLOSEST_SHOWN = 6;
// A comp is close to the board when the board holds two of its core units or one of its key
// units, when a unit on the board is an early holder for its main carry, or when it builds an
// item selected on the planner. A row is [comp, shared core units, missing core units, holders
// on the board, selected items it builds, closeness], the closest first. Closeness is the share
// of the core on the board, plus a part for the main carry or another key unit, a part for a
// holder and a part for the selected items it builds.
function closestComps(units, items = []) {
  const on = new Set(units);
  return snap()
    .comps.map((comp) => {
      const shared = comp.core.filter((id) => on.has(id));
      const held = comp.carries[0] && !on.has(comp.carries[0]) ? holdersOf(comp.carries[0]).filter((id) => on.has(id)) : [];
      const builds = builtBy(comp);
      const built = items.filter((item) => builds.has(item));
      const keyed = on.has(comp.carries[0]) ? 0.4 : comp.key_units.some((key) => on.has(key.unit)) ? 0.2 : 0;
      const close = shared.length / comp.core.length + keyed + (held.length ? 0.3 : 0) + (items.length ? (0.4 * built.length) / items.length : 0);
      return [comp, shared, comp.core.filter((id) => !on.has(id)), held, built, close, keyed];
    })
    .filter(([, shared, , held, built, , keyed]) => shared.length >= 2 || keyed || held.length || built.length)
    .sort((a, b) => b[5] - a[5] || a[0].avg_placement - b[0].avg_placement)
    .slice(0, CLOSEST_SHOWN);
}
// The items selected on the planner: ones the reader has or expects, on no unit in particular.
// They bring forward the comps that build them and the units that hold them.
const selectedKey = () => `${plannerKey()}.items`;
function plannerItems() {
  try {
    const kept = JSON.parse(localStorage.getItem(selectedKey()) || "[]");
    return Array.isArray(kept) ? kept.filter((item) => snap().items[item]) : [];
  } catch {
    return [];
  }
}
function keepItems(items) {
  localStorage.setItem(selectedKey(), JSON.stringify(items));
  renderPlanner();
}
// The items the planner offers: the craftable ones the item stats list, most held first.
const offeredItems = () => (snap().item_stats || []).filter((stat) => stat.kind === "craftable").map((stat) => stat.item);

// The units worth adding next, each with why, the strongest reason first. A unit is suggested
// because a comp the board is close to has it in its core or plays it often, or because it takes
// a trait on the board to its next breakpoint.
const SUGGESTED = 8;

// What the real boards that hold every unit on the planner add to it. `adds` is each other unit
// with its boards and their placements summed, `rests` each set of two or more units a board
// adds, `extra` how many boards add each number of units, and `room` the most units a tenth of
// the boards add. It is null with nothing on the board, before the boards load, and when fewer
// than `LIKE_BOARDS` hold the units: the comps then decide what is suggested.
const LIKE_BOARDS = 20;
const LIKE_SHARE = 0.05;
function plannerContext(units) {
  const boards = explored.get(snap().explorer);
  const on = new Set(units);
  if (!Array.isArray(boards) || !on.size) return null;
  const like = boards.filter((board) => [...on].every((id) => board.units.some((unit) => unit.id === id)));
  if (like.length < LIKE_BOARDS) return null;
  const buyable = new Set(rosterUnits());
  const adds = new Map();
  const rests = new Map();
  const extra = new Map();
  let placed = 0;
  for (const board of like) {
    const rest = [...new Set(board.units.map((unit) => unit.id))].filter((id) => !on.has(id) && buyable.has(id)).sort();
    placed += board.placement;
    extra.set(rest.length, (extra.get(rest.length) || 0) + 1);
    for (const id of rest) {
      const seen = adds.get(id) || [0, 0];
      adds.set(id, [seen[0] + 1, seen[1] + board.placement]);
    }
    if (rest.length < 2) continue;
    const seen = rests.get(rest.join(",")) || { add: rest, boards: 0, placed: 0 };
    rests.set(rest.join(","), { ...seen, boards: seen.boards + 1, placed: seen.placed + board.placement });
  }
  const room = Math.max(0, ...[...extra].filter(([, count]) => count / like.length >= 0.1).map(([size]) => size));
  return { on: on.size, boards: like.length, avg: placed / like.length, adds, rests, extra, room };
}
const theseUnits = (context) => (context.on === 1 ? "this unit" : `these ${context.on} units`);

// With real boards that hold the planner's units, the units those boards add come first, each
// with the share of the boards that add it. The comps fill the list only while the boards still
// add more than two units: on a nearly whole board a unit from another comp's core is noise.
function suggestions(units, emblems, items, context) {
  const on = new Set(units);
  const buyable = new Set(rosterUnits());
  const fromBoards = context
    ? [...context.adds]
        .filter(([, [count]]) => count / context.boards >= LIKE_SHARE)
        .sort((a, b) => b[1][0] - a[1][0])
        .slice(0, SUGGESTED)
        .map(([id, [count, placed]]) => ({
          id,
          share: count / context.boards,
          reasons: [`On ${pct(count / context.boards)} of the ${context.boards.toLocaleString()} boards that hold ${theseUnits(context)}.`, `Those boards place ${(placed / count).toFixed(2)}; all the boards that hold ${theseUnits(context)} place ${context.avg.toFixed(2)}.`],
        }))
    : [];
  if (context && context.room <= 2) return fromBoards;
  const found = new Map();
  const add = (id, score, reason) => {
    if (on.has(id) || !buyable.has(id)) return;
    const entry = found.get(id) || { id, score: 0, reasons: [] };
    entry.score += score;
    entry.reasons.push([score, reason]);
    found.set(id, entry);
  };
  for (const [comp, shared, , held, built, close] of closestComps(units, items)) {
    const why = [
      shared.length && `this board holds ${shared.length} of its ${comp.core.length} core units`,
      held.length && `${unitOf(held[0]).name} holds items for its carry`,
      built.length && `it builds ${built.map(itemName).join(" and ")}`,
    ].filter(Boolean);
    for (const id of comp.core) add(id, 2 * close, `In the core of ${nameOf(comp)}: ${why.join(", ")}.`);
    for (const flexed of comp.flex.flat()) for (const id of flexed.units) add(id, close * flexed.share, `On ${pct(flexed.share)} of ${nameOf(comp)} boards.`);
  }
  for (const item of items) {
    for (const group of snap().item_groups) {
      for (const [id, held] of Object.entries(group.held || {})) {
        if (held.items[item]) add(id, held.items[item][0], `Holds ${itemName(item)} on ${pct(held.items[item][0])} of its itemised boards, placing ${held.items[item][1].toFixed(2)}.`);
      }
    }
  }
  for (const { trait, count, next } of activeTraits(units, emblems)) {
    if (next - count !== 1) continue;
    for (const id of buyable) if (unitOf(id).traits.includes(trait)) add(id, 0.5, `Takes ${traitName(trait)} to ${next}.`);
  }
  const fromComps = [...found.values()]
    .filter((entry) => !fromBoards.some((listed) => listed.id === entry.id))
    .map((entry) => ({ ...entry, reasons: entry.reasons.sort((a, b) => b[0] - a[0]).map(([, reason]) => reason) }))
    .sort((a, b) => b.score - a.score || unitOf(a.id).cost - unitOf(b.id).cost);
  return [...fromBoards, ...fromComps].slice(0, SUGGESTED);
}

// Groups of units worth adding together, from the comps the board is closest to: the rest of a
// comp's core, and its most played subcomp, which fills its board. A group lists only the units the
// board lacks, and needs two of them.
const GROUPS_SUGGESTED = 5;
const REST_BOARDS = 5;
const REST_SHARE = 0.02;
function suggestedGroups(units, items, context) {
  const on = new Set(units);
  const buyable = new Set(rosterUnits());
  const found = new Map();
  const offer = (ids, score, label, why) => {
    const add = ids.filter((id) => !on.has(id) && buyable.has(id));
    const key = [...add].sort().join(",");
    if (add.length < 2 || (found.has(key) && found.get(key).score >= score)) return;
    found.set(key, { add, score, label, why });
  };
  for (const [comp, shared, missing, , , close] of closestComps(units, items)) {
    offer(missing, 2 * close, `the rest of ${nameOf(comp)}'s core`, `This board holds ${shared.length} of the ${comp.core.length} core units of ${nameOf(comp)}.`);
    // One whole board a comp, its most played: two under one comp's name read as one row twice.
    for (const sub of (comp.subcomps || []).slice(0, 1)) {
      offer([...missing, ...sub.units], close * (1 + sub.share), `${nameOf(comp)}, a whole board`, `The core of ${nameOf(comp)} with the units on ${pct(sub.share)} of its boards, which place ${sub.avg_placement.toFixed(2)}.`);
    }
  }
  // With real boards that hold the planner's units, the sets of units those boards add come
  // first, and a comp's group stays only when it fits in the room those boards leave.
  const fromBoards = context
    ? [...context.rests.values()]
        .filter((rest) => rest.boards >= REST_BOARDS && rest.boards / context.boards >= REST_SHARE)
        .sort((a, b) => b.boards - a.boards)
        .map((rest) => ({
          add: rest.add,
          label: `on ${pct(rest.boards / context.boards)} of the boards with ${theseUnits(context)}, avg ${(rest.placed / rest.boards).toFixed(2)}`,
          why: `${rest.boards.toLocaleString()} of the ${context.boards.toLocaleString()} boards that hold ${theseUnits(context)} add exactly these.`,
        }))
    : [];
  const listed = new Set(fromBoards.map((group) => group.add.join(",")));
  const fromComps = [...found.values()]
    .filter((group) => !listed.has([...group.add].sort().join(",")) && (!context || group.add.length <= context.room))
    .sort((a, b) => b.score - a.score || a.add.length - b.add.length);
  return [...fromBoards, ...fromComps].slice(0, GROUPS_SUGGESTED);
}

// What a unit on the board usually holds, and the comps it matters in. The items are the ones it
// holds most on real boards, from its item group. A comp lists it when it is one of the comp's
// key units or holds one of the comp's priority items.
const ROLE_ORDER = ["Main carry", "Carry", "Main tank", "Holds items"];
function unitAdvice(id) {
  const group = snap().item_groups.find((candidate) => candidate.held && candidate.held[id]);
  const items = group
    ? Object.entries(group.held[id].items)
        .map(([item, [share, avg]]) => [item, share, avg])
        .sort((a, b) => b[1] - a[1])
        .slice(0, 4)
    : [];
  const comps = [...snap().comps]
    .sort(SORTS.play)
    .map((comp) => {
      const key = comp.key_units.find((candidate) => candidate.unit === id);
      const role = key ? (comp.carries[0] === id ? "Main carry" : key.role === "tank" ? "Main tank" : "Carry") : comp.items.some((pick) => pick.holder === id) ? "Holds items" : null;
      return [comp, role];
    })
    .filter(([, role]) => role)
    .sort((a, b) => ROLE_ORDER.indexOf(a[1]) - ROLE_ORDER.indexOf(b[1]))
    .slice(0, 3);
  // The comps whose main carry is a costlier unit of this unit's item group: it holds their items early.
  const holds = [...snap().comps]
    .sort(SORTS.play)
    .filter((comp) => comp.carries[0] && !comps.some(([own]) => own === comp) && holdersOf(comp.carries[0]).includes(id))
    .slice(0, 3)
    .map((comp) => [comp, `Early holder for ${unitOf(comp.carries[0]).name}`]);
  return { items, comps: [...comps, ...holds] };
}

function rosterHtml(board) {
  const on = new Set(Object.values(board));
  const costs = new Map();
  for (const id of rosterUnits()) costs.set(unitOf(id).cost, [...(costs.get(unitOf(id).cost) || []), id]);
  return [...costs]
    .map(
      ([cost, ids]) => `<div class="roster-cost"><span class="note">${cost} cost</span>${ids
        .map((id) => `<span class="pick ${on.has(id) ? "on" : ""}" data-pick="${id}">${unitTile(id, "m", { note: on.has(id) ? "Click to take it off the board." : "Click to put it on the board." })}</span>`)
        .join("")}</div>`,
    )
    .join("");
}

function plannerHtml(board) {
  const units = Object.values(board);
  const lines = [0, 1, 2, 3].map((row) => {
    const hexes = CORNER_IN.map((column) => {
      const id = board[`${row},${column}`];
      const unit = id && unitOf(id);
      const image = unit && unit.icon ? `<img src="${esc(unit.icon)}" alt="" draggable="false">` : "";
      return `<span class="hex" data-hex="${row},${column}" ${id ? `draggable="true" ${unitTip(id, "Drag to move it. Click to take it off the board.")}` : ""}>${image}</span>`;
    });
    return `<div class="line">${hexes.join("")}</div>`;
  });
  const emblems = plannerEmblems();
  const emblemRow = emblemItems()
    .map(([trait, item]) => {
      const held = emblems[trait] || 0;
      return `<span class="emblem ${held ? "on" : ""}" data-emblem="${esc(trait)}" ${tipOf(`${traitName(trait)} Emblem${held ? ": on the board" : ""}`, held ? "Click to take it off." : "Click to add it.")}>${itemIcon(item)}</span>`;
    })
    .join("");
  const selected = plannerItems();
  const context = plannerContext(units);
  const suggested = suggestions(units, emblems, selected, context)
    .map(
      ({ id, reasons, share }) =>
        `<span class="pick offer" data-pick="${id}">${unitTile(id, "m", { note: [...reasons.slice(0, 4), "Click to add it."].join("\n") })}${share ? `<span class="note offer-share">${pct(share)}</span>` : ""}</span>`,
    )
    .join("");
  // How many units the boards that hold these add, the commonest numbers first.
  const sizes = context
    ? [...context.extra]
        .filter(([, count]) => count / context.boards >= 0.1)
        .sort((a, b) => b[1] - a[1])
        .map(([size, count]) => `${pct(count / context.boards)} add ${size === 0 ? "no unit" : size === 1 ? "1 unit" : `${size} units`}`)
    : [];
  const likeLine = context ? `<p class="note like-line">${context.boards.toLocaleString()} boards hold ${theseUnits(context)}${sizes.length ? `: ${sizes.join(", ")}` : ""}.</p>` : "";
  const groups = suggestedGroups(units, selected, context)
    .map(
      ({ add, label, why }) => `<div class="suggest-group" data-picks="${add.join(",")}" ${tipOf(why, "Click to add them all.")}>
        <span class="group-tiles">${add.map((id) => unitTile(id, "s")).join("")}</span><span class="note">${esc(label)}</span></div>`,
    )
    .join("");
  const fielded = [...new Set(units)]
    .sort((a, b) => unitOf(b).cost - unitOf(a).cost || unitOf(a).name.localeCompare(unitOf(b).name))
    .map((id) => {
      const { items, comps } = unitAdvice(id);
      const held = items.map(([item, share, avg]) => itemIcon(item, { note: `${itemName(item)}: on ${pct(share)} of its itemised boards, placing ${avg.toFixed(2)} there.` })).join("");
      const plays = comps
        .map(([comp, role]) => `<span class="plays" data-open="${comp.id}" ${tipOf(`${role} in ${nameOf(comp)}.`, "Click to open the comp.")}><span class="tier t${comp.tier}">${comp.tier}</span>${esc(nameOf(comp))}</span>`)
        .join("");
      return `<div class="fielded">${unitTile(id, "s")}<span class="suggest-name">${esc(unitOf(id).name)}</span>
        <span class="fielded-items">${held || `<span class="note">no usual items</span>`}</span><span class="fielded-comps">${plays}</span></div>`;
    })
    .join("");
  const traits = activeTraits(units, emblems)
    .map(({ trait, count, breakpoints, reached, next }) => {
      const { icon } = snap().traits[trait] || {};
      const tip = tipOf(
        traitName(trait),
        breakpoints.length ? `Breakpoints: ${breakpoints.join(" / ")}` : "",
        reached ? `${count} reaches ${breakpoints[reached - 1]}` : `${count} of the ${breakpoints[0] || "?"} it needs`,
        next ? `${next - count} more for ${next}` : "",
      );
      return `<span class="trait ${reached ? "top" : ""}" ${tip}>${icon ? `<img src="${esc(icon)}" alt="">` : ""}${count}${next ? `/${next}` : ""} ${esc(traitName(trait))}</span>`;
    })
    .join("");
  const closest = closestComps(units, selected)
    .map(([comp, shared, missing, held, built]) => {
      const why = [
        `${shared.length} of ${comp.core.length}`,
        held.length && `${unitOf(held[0]).name} holds for ${unitOf(comp.carries[0]).name}`,
        built.length && `builds ${built.length} of your item${selected.length === 1 ? "" : "s"}`,
      ].filter(Boolean);
      return `<div class="closest" data-open="${comp.id}" ${tipOf(`${shared.length} of its ${comp.core.length} core units are on the board.`, held.length ? `${held.map((id) => unitOf(id).name).join(", ")} builds as its carry ${unitOf(comp.carries[0]).name} does, and costs less.` : "", built.length ? `It builds ${built.map(itemName).join(", ")}.` : "", "Click to open the comp.")}>
        <span class="tier t${comp.tier}">${comp.tier}</span><span class="closest-name">${esc(nameOf(comp))}</span>
        <span class="note">${esc(why.join(" · "))}${missing.length ? ", missing" : ""}</span>${missing.map((id) => unitTile(id, "s")).join("")}</div>`;
    })
    .join("");
  const itemRow = offeredItems()
    .map((item) => `<span class="emblem ${selected.includes(item) ? "on" : ""}" data-select-item="${esc(item)}" ${tipOf(itemName(item), selected.includes(item) ? "Click to unselect it." : "Click to select it: an item you have or expect.")}>${itemIcon(item)}</span>`)
    .join("");
  const attachable = [...snap().comps].sort((a, b) => nameOf(a).localeCompare(nameOf(b)));
  const saved = allSaved()
    .map(([compId, place, kept]) => {
      const comp = snap().comps.find((candidate) => candidate.id === compId);
      const about = [kept.stage, comp ? nameOf(comp) : "no comp", `${Object.keys(kept.units).length} units`].filter(Boolean).join(" · ");
      return `<div class="saved-row" data-load="${compId}:${place}" ${tipOf("Click to put it on the board.")}>
        <span class="saved-name">${esc(kept.name)}</span><span class="note">${esc(about)}</span>
        <button class="line-button" data-unsave="${compId}:${place}" ${tipOf("Delete this saved board.")}>×</button></div>`;
    })
    .join("");
  const saving = edits
    ? `<div class="save-form">
        <input id="save-name" maxlength="40" placeholder="name" value="${esc(state.saveName)}">
        <select id="save-stage">${STAGES.map((stage) => `<option value="${stage}" ${stage === state.saveStage ? "selected" : ""}>${stage || "any stage"}</option>`).join("")}</select>
        <select id="save-comp"><option value="">no comp</option>${attachable.map((comp) => `<option value="${comp.id}" ${comp.id === state.saveComp ? "selected" : ""}>${esc(nameOf(comp))}</option>`).join("")}</select>
        <button id="save-board" ${units.length ? "" : "disabled"} ${tipOf("Keep this board under the name and stage. A board of the same name, stage and comp is replaced.")}>Save</button>
        <span class="note" id="save-state"></span></div>
      <div>${saved || `<span class="note">No saved board yet.</span>`}</div>`
    : "";
  const cut = units.length > TEAM_PLACES ? `the first ${TEAM_PLACES} of ${units.length} units` : `${units.length} units`;
  return `<div id="sheet">
    <header><div class="title">${MAXIMIZE}<h1>Planner</h1>
      <button id="copy-plan" ${tipOf(teamCodeOf(units), cut)}>Copy team code</button>
      <button id="clear-plan" ${tipOf("Take every unit off the board.")}>Clear</button></div>
      <p class="stats">${units.length} unit${units.length === 1 ? "" : "s"} on the board. Click a unit in the roster to add it, and drag it on the board to place it.</p></header>
    <div class="flow">
      ${section("Board", `<div class="board planner-board" ${tipOf("The front row is at the top.")}>${lines.join("")}</div>`)}
      ${section("Traits", `<div class="row">${traits || `<span class="note">no unit on the board</span>`}</div>`, { width: "wraps" })}
      ${saving ? section("Saved boards", `<div>${saving}</div>`, { info: "Boards kept by the server, each with a name and a stage.\nA board attached to a comp also shows on that comp's page." }) : ""}
      ${itemRow ? section("Items", `<div class="row emblems">${itemRow}</div>`, { width: "wraps", info: "Items you have or expect, on no unit in particular.\nA selected item brings forward the comps that build it and the units that hold it." }) : ""}
      ${section("Emblems", `<div class="row emblems">${emblemRow || `<span class="note">This set's data names no emblem.</span>`}</div>`, { width: "wraps" })}
      ${fielded ? section("On the board", `<div>${fielded}</div>`, { info: "Each unit on the board, with the items it holds most on real boards and the comps it carries, tanks or holds items for.\nClick a comp to open it." }) : ""}
      ${groups ? section("Suggested groups", `<div>${groups}</div>`, { info: "Units worth adding together.\nA group with a share is a set the real boards that hold every unit here add, exactly. The others are the rest of a close comp's core or a whole board of that comp, kept only when they fit in what those boards add.\nClick a group to add all of it." }) : ""}
      ${section("Suggested units", `<div>${likeLine}<div class="row suggested">${suggested || `<span class="note">${context ? "The boards that hold these units add no unit often enough to name." : "Put a unit on the board or select an item."}</span>`}</div></div>`, {
        info: "Units worth adding next.\nA unit with a share under it is one the real boards that hold every unit here add, on a twentieth of them or more. When those boards add two units or fewer, only such units are listed.\nA unit with no share is listed because a comp this board is close to has it in its core or plays it often, because it holds a selected item, or because it takes a trait on the board to its next breakpoint.\nClick one to add it.",
      })}
      ${section("Closest comps", `<div>${closest || `<span class="note">No comp is close to this board.</span>`}</div>`, {
        info: "The comps this board is close to, each with the core units still missing.\nA comp is close when the board holds two of its core units or one of its key units, when a unit on the board is an early holder for its carry, or when it builds a selected item.\nClick one to open it.",
      })}
    </div></div>`;
}

function renderPlanner() {
  showTip(null);
  loadExplorer();
  const board = plannerBoard();
  el("roster").innerHTML = rosterHtml(board);
  el("detail").innerHTML = plannerHtml(board);
  fitWidth();
}

function movePlanned(from, to) {
  const board = plannerBoard();
  if (from === to || !board[from]) return;
  const [moved, other] = [board[from], board[to]];
  board[to] = moved;
  if (other) board[from] = other;
  else delete board[from];
  keepPlanner(board);
}

el("roster").addEventListener("click", (event) => {
  const pick = event.target.closest("[data-pick]");
  if (pick) togglePlanned(pick.dataset.pick);
});
el("detail").addEventListener("click", (event) => {
  if (state.view !== "planner") return;
  const hex = event.target.closest(".planner-board .hex[data-tip]");
  if (hex) {
    const board = plannerBoard();
    delete board[hex.dataset.hex];
    keepPlanner(board);
  } else if (event.target.closest("[data-unsave]")) {
    const [compId, place] = event.target.closest("[data-unsave]").dataset.unsave.split(":");
    putBoards(compId, savedBoards(compId).filter((_, index) => index !== Number(place)));
  } else if (event.target.closest("[data-load]")) {
    const [compId, place] = event.target.closest("[data-load]").dataset.load.split(":");
    loadSaved(compId, Number(place));
  } else if (event.target.closest("#save-board")) {
    savePlanned();
  } else if (event.target.closest("[data-select-item]")) {
    const item = event.target.closest("[data-select-item]").dataset.selectItem;
    const items = plannerItems();
    keepItems(items.includes(item) ? items.filter((other) => other !== item) : [...items, item]);
  } else if (event.target.closest("[data-emblem]")) {
    const trait = event.target.closest("[data-emblem]").dataset.emblem;
    const emblems = plannerEmblems();
    if (emblems[trait]) delete emblems[trait];
    else emblems[trait] = 1;
    keepEmblems(emblems);
  } else if (event.target.closest("[data-picks]")) {
    const board = plannerBoard();
    for (const id of event.target.closest("[data-picks]").dataset.picks.split(",")) {
      const hex = !Object.values(board).includes(id) && freeHexFor(id, board);
      if (hex) board[hex] = id;
    }
    keepPlanner(board);
  } else if (event.target.closest("[data-pick]")) {
    togglePlanned(event.target.closest("[data-pick]").dataset.pick);
  } else if (event.target.closest("#clear-plan")) {
    localStorage.removeItem(emblemKey());
    localStorage.removeItem(selectedKey());
    keepPlanner({});
  } else if (event.target.closest("#copy-plan")) {
    copyText(teamCodeOf(Object.values(plannerBoard()))).then(() => {
      const button = el("copy-plan");
      if (button) button.textContent = "Copied";
    });
  }
});

// The save form's boxes keep what was typed across the planner's redraws.
el("detail").addEventListener("input", (event) => {
  if (event.target.id === "save-name") state.saveName = event.target.value;
  if (event.target.id === "save-stage") state.saveStage = event.target.value;
  if (event.target.id === "save-comp") state.saveComp = event.target.value || null;
});
el("detail").addEventListener("click", (event) => {
  const card = state.view === "comps" && event.target.closest(".saved-card[data-load]");
  if (!card) return;
  const [compId, place] = card.dataset.load.split(":");
  loadSaved(compId, Number(place));
});

// The explorer: a click on a row adds it to the filters, and a click on a column sorts by it.
// Its tables are in the page and in the list pane.
function exploreClick(event) {
  if (state.view !== "explorer") return;
  const row = event.target.closest("[data-explore]");
  const sort = event.target.closest("[data-explore-sort]");
  if (sort) {
    state.exploreAscending = sort.dataset.exploreSort === state.exploreSort && !state.exploreAscending;
    state.exploreSort = sort.dataset.exploreSort;
    renderExplorer();
  } else if (row && !state.exploreFilters.includes(row.dataset.explore)) {
    state.exploreFilters.push(row.dataset.explore);
    renderFilters();
  }
}
for (const pane of ["detail", "explore"]) el(pane).addEventListener("click", exploreClick);
el("slams").addEventListener("change", (event) => {
  if (event.target.id !== "slam-counts") return;
  state.slamCounts = event.target.checked;
  if (state.slamCounts) localStorage.removeItem(SLAM_COUNTS);
  else localStorage.setItem(SLAM_COUNTS, "1");
  renderItems();
});
el("explore").addEventListener("change", (event) => {
  if (event.target.id !== "explore-holder") return;
  state.exploreHolder = event.target.checked;
  renderExplorer();
});

// A unit is dragged from its hex to another hex of the same board.
let heldHex = null;
el("detail").addEventListener("focusout", (event) => {
  const comp = snap().comps.find((candidate) => candidate.id === state.comp);
  if (comp && event.target.id === "name-edit") keepName(comp, event.target);
});
el("detail").addEventListener("dragstart", (event) => {
  const hex = event.target.closest(".hex[draggable]");
  if (!hex) return;
  heldHex = hex.dataset.hex;
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", heldHex);
  showTip(null);
});
el("detail").addEventListener("dragover", (event) => {
  if (heldHex && event.target.closest(".board .hex")) event.preventDefault();
});
el("detail").addEventListener("drop", (event) => {
  const hex = event.target.closest(".board .hex");
  const comp = snap().comps.find((candidate) => candidate.id === state.comp);
  if (!hex || !heldHex || !comp) return;
  event.preventDefault();
  if (state.view === "planner") movePlanned(heldHex, hex.dataset.hex);
  else moveUnit(comp, heldHex, hex.dataset.hex);
  heldHex = null;
});
el("detail").addEventListener("dragend", () => (heldHex = null));
el("detail").addEventListener("keydown", (event) => {
  const comp = snap().comps.find((candidate) => candidate.id === state.comp);
  const box = event.target;
  if (comp && box.id === "name-edit" && event.key === "Enter") {
    keepName(comp, box);
  } else if (comp && box.id === "name-edit" && event.key === "Escape") {
    naming = null;
    renderDetail();
  } else if (comp && box.id === "comp-name" && event.key === "Enter") {
    box.click();
  } else if (comp && box.id === "plan-entry" && event.key === "Enter" && box.value.trim()) {
    const mine = ownPlan(comp);
    savePlan(comp, { ...mine, own: [box.value.trim(), ...mine.own] }, "#plan-entry");
  } else if (comp && box.classList.contains("plan-edit") && event.key === "Enter") {
    savePlan(comp, withPlanLine(comp, box.dataset.planKey, box.value.trim()));
  } else if (comp && box.classList.contains("plan-edit") && event.key === "Escape") {
    planEditing = null;
    drawPlan(comp);
  }
  const named = event.target.id === "add-category" && event.key === "Enter" && categoryNamed(event.target.value);
  if (named) changeCategory(named, true);
});
el("head").addEventListener("click", (event) => {
  const column = event.target.closest("button");
  if (column) {
    state.ascending = column.dataset.column === state.column && !state.ascending;
    state.column = column.dataset.column;
    state.sort = column.dataset.sort;
    renderList();
  }
});
el("filter").addEventListener("input", (event) => {
  state[filterKeys()[1]] = event.target.value;
  renderList();
});
// Enter keeps the typed filter and starts another. Backspace in an empty box removes the last kept one.
el("filter").addEventListener("keydown", (event) => {
  const box = event.target;
  const [kept, typed] = filterKeys();
  if (event.key === "Enter" && box.value.trim()) {
    state[kept].push(box.value.trim());
    box.value = state[typed] = "";
    renderFilters();
  } else if (event.key === "Backspace" && !box.value && state[kept].length) {
    state[kept].pop();
    renderFilters();
  }
});
el("filters").addEventListener("click", (event) => {
  const remove = event.target.closest("[data-remove]");
  if (remove) {
    state[filterKeys()[0]].splice(Number(remove.dataset.remove), 1);
    renderFilters();
  }
  el("filter").focus();
});
el("switches").addEventListener("change", () => {
  state.lowPlay = el("low-play").checked;
  if (state.expandAll !== el("expand-all").checked) state.flipped.clear();
  state.expandAll = el("expand-all").checked;
  localStorage.setItem(SHOW_LOW_PLAY, state.lowPlay ? "1" : "0");
  localStorage.setItem(EXPAND_ALL, state.expandAll ? "1" : "0");
  renderList();
});
el("comps").addEventListener("click", (event) => {
  const mark = event.target.closest("[data-expand]");
  if (mark) {
    if (!state.flipped.delete(mark.dataset.expand)) state.flipped.add(mark.dataset.expand);
    renderList();
    return;
  }
  const row = event.target.closest("li");
  if (row) {
    state.comp = row.dataset.id;
    renderList();
  }
});
el("tabs").addEventListener("click", (event) => {
  const tab = event.target.closest("[data-view]");
  if (tab) setView(tab.dataset.view);
});
// A click on a slam lists the comps that build it: the comps view, filtered by the item's name.
// A click on a component lights its row and column, and a click on an item orders the item
// groups for it. A second click on either undoes it.
el("slams").addEventListener("click", (event) => {
  const part = event.target.closest("[data-component]");
  const slam = event.target.closest("[data-slam]");
  const kind = event.target.closest("[data-kind]");
  const craft = event.target.closest("[data-craft]");
  const sort = event.target.closest("[data-stat-sort]");
  if (kind) {
    state.statKind = kind.dataset.kind || null;
    state.emblemCraft = null;
  } else if (craft) state.emblemCraft = craft.dataset.craft === "" ? null : craft.dataset.craft === "true";
  else if (sort) {
    state.statAscending = sort.dataset.statSort === state.statSort && !state.statAscending;
    state.statSort = sort.dataset.statSort;
  } else if (part) state.component = state.component === part.dataset.component ? null : part.dataset.component;
  else if (slam) pickItem(slam.dataset.slam);
  else return;
  renderItems();
});
el("detail").addEventListener("click", (event) => {
  if (state.view !== "items") return;
  const named = event.target.closest("[data-filter]");
  const pairSort = event.target.closest("[data-pair-sort]");
  if (event.target.closest("#clear-item")) {
    state.items = [];
    renderItems();
  } else if (pairSort) {
    state.pairAscending = pairSort.dataset.pairSort === state.pairSort && !state.pairAscending;
    state.pairSort = pairSort.dataset.pairSort;
    renderItems();
  } else if (named) {
    state.view = "comps";
    state.filters = [named.dataset.filter];
    el("filter").value = state.filter = "";
    localStorage.setItem(VIEW, "comps");
    renderFilters();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.target.closest("#detail") && event.target.matches("input, textarea")) return;
  if (state.view === "comps" && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
    event.preventDefault();
    move(event.key === "ArrowDown" ? 1 : -1);
  }
});
if (SNAPSHOTS.length) {
  renderList();
  loadEdits();
}
else el("detail").innerHTML = `<p class="empty">No snapshot yet. A snapshot needs 1,000 boards of the live patch, and a new store gets them within its first crawl.</p>`;
