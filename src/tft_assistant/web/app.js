const SNAPSHOTS = JSON.parse(document.getElementById("snapshots").textContent);
const state = { snapshot: 0, comp: null, filters: [], filter: "", sort: "avg" };
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

// Everything the filter box searches in a comp: its name, style, level, units, items and traits.
function searchedNames(comp) {
  const units = [...comp.core, ...comp.flex.flat().flatMap((p) => p.units)].map((id) => unitOf(id).name);
  const built = [
    ...comp.items.map((pick) => pick.item),
    ...comp.key_units.flatMap((key) => key.build.map((note) => note.item)),
    ...comp.specials.map((special) => special.item),
  ].map((id) => (snap().items[id] || { name: id }).name);
  const names = [nameOf(comp), comp.name, comp.style, `level ${comp.roll_level}`, ...units, ...built, ...comp.traits.map((t) => traitName(t.trait))];
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
    .sort(SORTS[state.sort]);
}

function renderFilters() {
  el("chips").innerHTML = state.filters
    .map((filter, index) => `<span class="filter-chip">${esc(filter)}<button data-remove="${index}" data-tip="Remove this filter">×</button></span>`)
    .join("");
  el("filter").placeholder = state.filters.length ? "add a filter" : "unit, trait, item or level";
  renderList();
}

// The page has two views of one snapshot. "comps" is the comp list beside one comp's page. "items"
// is the slam grid beside the item groups. The browser keeps the view across a reload.
const VIEW = "tft-assistant.view";
state.view = localStorage.getItem(VIEW) === "items" ? "items" : "comps";
function setView(view) {
  state.view = view;
  localStorage.setItem(VIEW, view);
  renderList();
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
function slamGridHtml() {
  const s = snap();
  const strong = s.comps.filter(isStrong).sort(SORTS.play);
  const users = new Map();
  for (const comp of strong) {
    for (const [item, holder] of builtBy(comp)) users.set(item, [...(users.get(item) || []), [comp, holder]]);
  }
  const made = new Map(Object.entries(s.recipes || {}).map(([item, parts]) => [[...parts].sort().join("+"), item]));
  const name = (id) => (s.items[id] || { name: id }).name;
  const components = [...new Set(Object.values(s.recipes || {}).flat())].sort((a, b) => name(a).localeCompare(name(b)));
  const cell = (first, second) => {
    const item = made.get([first, second].sort().join("+"));
    if (!item) return `<td></td>`;
    const built = users.get(item) || [];
    const tone = built.length >= strong.length / 3 ? "safe" : built.length ? "" : "unused";
    const lines = built.slice(0, 8).map(([comp, holder]) => `${nameOf(comp)} → ${unitOf(holder).name}`);
    const note = built.length
      ? `Built by ${built.length} of ${strong.length} comps of tier B or better:\n${lines.join("\n")}${built.length > 8 ? "\n…" : ""}\nClick to list them.`
      : "No comp of tier B or better builds it.";
    return `<td class="slam ${tone}" data-item="${esc(name(item))}">${itemIcon(item, { note })}<b>${built.length || ""}</b></td>`;
  };
  const head = `<tr><th></th>${components.map((id) => `<th>${itemIcon(id)}</th>`).join("")}</tr>`;
  const rows = components.map(
    (row, at) => `<tr><th>${itemIcon(row)}</th>${components.map((column, across) => (across < at ? `<td></td>` : cell(row, column))).join("")}</tr>`,
  );
  return `<table class="slams">${head}${rows.join("")}</table>`;
}

// Each group lists the items its units build and the units, cheapest first. A unit that is a comp's
// main carry is outlined, and a click on it opens the most played comp it carries.
function itemGroupsHtml() {
  const s = snap();
  const carried = new Map();
  for (const comp of [...s.comps].sort(SORTS.play)) {
    if (comp.carries[0] && !carried.has(comp.carries[0])) carried.set(comp.carries[0], comp);
  }
  const unit = (id) => {
    const comp = carried.get(id);
    if (!comp) return unitTile(id, "m");
    const note = `Carries ${nameOf(comp)}: average placement ${comp.avg_placement.toFixed(2)}, played ${pct(comp.share)}. Click to open it.`;
    return `<span class="carrier" data-open="${comp.id}">${unitTile(id, "m", { note })}</span>`;
  };
  const groups = s.item_groups.map(
    (group) => `<div class="group">
      <div class="group-items">${group.items.map((item) => itemIcon(item)).join("")}</div>
      <div class="group-units">${group.units.map(unit).join("")}</div>
    </div>`,
  );
  const info = "Units in one group build alike on real boards, so they can hold each other's items.\nA group lists the items its units hold most, then its units from the cheapest.\nAn outlined unit is a comp's main carry.";
  return `<div id="sheet"><header><h1>${MAXIMIZE} Item groups <span class="info" tabindex="0" ${tipOf(info)}>i</span></h1></header>
    ${groups.join("") || `<p class="empty">No unit has enough itemised boards to group.</p>`}</div>`;
}

function renderItems() {
  showTip(null);
  el("slams").innerHTML = slamGridHtml();
  el("detail").innerHTML = itemGroupsHtml();
  fitWidth();
}

function renderList() {
  document.body.dataset.view = state.view;
  for (const tab of el("tabs").children) tab.classList.toggle("on", tab.dataset.view === state.view);
  const s = snap();
  const age = s.newest_match ? `newest match ${hoursAgo(s.newest_match)}` : "no matches";
  el("health").textContent = `${s.boards.toLocaleString()} boards · ${pct(s.unclassified)} unclassified · ${age}`;
  if (state.view === "items") {
    renderItems();
    return;
  }
  const comps = visibleComps();
  if (!comps.some((comp) => comp.id === state.comp)) state.comp = comps.length ? comps[0].id : null;
  el("head").innerHTML = COLUMNS.map(([label, sort, column]) => {
    const cell = `class="${column} ${sort === state.sort ? "sorted" : ""}"`;
    return sort ? `<button data-sort="${sort}" ${cell}>${label}</button>` : `<span ${cell}>${label}</span>`;
  }).join("");
  el("comps").innerHTML = comps
    .map(
      (comp) => `<li data-id="${comp.id}" class="comp-row ${comp.id === state.comp ? "selected" : ""}">
        <span class="c-tier"><span class="tier t${comp.tier}">${comp.tier}</span></span>
        <span class="c-name">${esc(nameOf(comp))}</span>
        <span class="c-level">${comp.roll_level}</span>
        <span class="c-core">${comp.core.map((id) => unitTile(id, "s")).join("")}</span>
        <span class="c-avg num">${comp.avg_placement.toFixed(2)}</span>
        <span class="c-top4 num">${pct(comp.top4)}</span>
        <span class="c-win num">${pct(comp.win_rate)}</span>
        <span class="c-play num">${(comp.share * 100).toFixed(1)}%</span>
      </li>`,
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

function boardHtml(comp) {
  const at = standing(teamUnits(comp), comp.carries);
  const lines = [0, 1, 2, 3].map((row) => {
    const hexes = CORNER_IN.map((column) => {
      const id = at[`${row},${column}`];
      const unit = id && unitOf(id);
      return `<span class="hex" ${id ? unitTip(id) : ""}>${unit && unit.icon ? `<img src="${esc(unit.icon)}" alt="">` : ""}</span>`;
    });
    return `<div class="line">${hexes.join("")}</div>`;
  });
  return `<div class="board" ${tipOf("The core and the picked flex units, each in the row of its attack range. The front row is at the top.")}>${lines.join("")}</div>`;
}

const SHOWN_IN_A_GROUP = 9;
const ITEM_ROWS = 6;

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
      const cost = unitOf(unit).cost;
      const holders = (group ? group.units : [])
        .filter((id) => unitOf(id).cost < cost)
        .sort((a, b) => unitOf(a).cost - unitOf(b).cost);
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
function teamCode(comp) {
  const numbers = teamUnits(comp).map((id) => unitOf(id).planner_code).filter(Boolean);
  const places = Array.from({ length: TEAM_PLACES }, (_, place) => (numbers[place] || 0).toString(16).padStart(3, "0"));
  return `02${places.join("")}${snap().team_code_set}`;
}

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
      (pick, index) => `<tr><td class="rank">${index + 1}</td><td>${itemIcon(pick.item)} ${itemName(pick.item)}</td>
        <td>→ ${esc(unitOf(pick.holder).name)}</td><td>${pct(pick.share)}</td>
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
    <header><div class="title">${MAXIMIZE}<h1><span class="tier t${comp.tier}">${comp.tier}</span>${esc(nameOf(comp))}</h1>
      <button id="copy-team" data-tip="${esc(teamCode(comp))}">Copy team code</button><span class="note">${teamNote}: core and picked flex</span></div>
      <p class="stats"><b>${esc(comp.style)}</b> · avg <b>${comp.avg_placement.toFixed(2)}</b> · top 4 <b>${pct(comp.top4)}</b> · win <b>${pct(comp.win_rate)}</b> · play <b>${(comp.share * 100).toFixed(1)}%</b> · ${comp.boards.toLocaleString()} boards</p></header>
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
    ${edits ? section("Notes", notesHtml(comp)) : ""}</div>`;
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

// The name box is empty until the reader names the comp, and shows the derived name as its hint.
function notesHtml(comp) {
  const own = edits[comp.id] || {};
  return `<div class="notes">
    <input data-edit="name" maxlength="60" value="${esc(own.name || "")}" placeholder="${esc(comp.name)}" ${tipOf("Your own name for this comp. Empty goes back to the derived one.")}>
    <textarea data-edit="notes" id="notes" maxlength="4000" rows="3" placeholder="What to remember about this comp">${esc(own.notes || "")}</textarea>
    <span id="notes-state" class="note"></span></div>`;
}

// An edit is saved when its box loses the focus, under the comp it was written for. A name shows
// in the list and in the page's heading, so saving one draws both again.
function saveEdit(compId, field, text) {
  const shown = (words) => el("notes-state") && (el("notes-state").textContent = words);
  fetch(`${editsOf()}/${compId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ [field]: text }) })
    .then((reply) => {
      if (!reply.ok) throw new Error(`the server answered ${reply.status}`);
      edits[compId] = { ...edits[compId], [field]: text };
      if (field === "name") renderList();
      shown("saved");
    })
    .catch((error) => shown(`not saved: ${error.message}`));
}

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
// The list is never wider than the width that shows all of its columns, which the stylesheet
// states. A wider list would only add empty space and take it from the comp page.
const FULL_LIST = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--full-list"));
// The comp page's least width leaves the list its full width in a window 1,024 pixels wide.
const NARROWEST_DETAIL = 300;
const storedWidth = (key) => (localStorage.getItem(key) ? Number(localStorage.getItem(key)) : "");
function setListWidth(asked) {
  const width = asked === "" ? "" : Math.min(asked, FULL_LIST);
  if (width === "") document.body.style.removeProperty("--list-width");
  else document.body.style.setProperty("--list-width", `${width}px`);
  localStorage.setItem(LIST_WIDTH, width);
  document.body.classList.toggle("maximized", width === 0);
  fitWidth();
}
function maximize(from) {
  if (from !== 0) localStorage.setItem(LIST_RESTORE, from);
  setListWidth(0);
}
const MAXIMIZE = `<button id="maximize">
  <span class="grow" data-tip="Give the comp page the whole window"><svg viewBox="0 0 16 16"><path d="M9.5 2H14v4.5M14 2 9 7M6.5 14H2V9.5M2 14l5-5"/></svg></span>
  <span class="shrink" data-tip="Bring the list back"><svg viewBox="0 0 16 16"><path d="M13.5 7H9V2.5M9 7l5-5M2.5 9H7v4.5M7 9l-5 5"/></svg></span>
</button>`;
setListWidth(storedWidth(LIST_WIDTH));
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
  const comp = snap().comps.find((candidate) => candidate.id === state.comp);
  if (!comp || event.target.closest(".info")) return;
  const flex = event.target.closest("[data-flex]");
  const heading = event.target.closest("section > h2");
  const pivot = event.target.closest("[data-open]");
  if (pivot) {
    state.comp = pivot.dataset.open;
    setView("comps");
    document.querySelector("#comps li.selected")?.scrollIntoView({ block: "nearest" });
  } else if (heading) {
    const title = heading.parentElement.dataset.section;
    if (!folded.delete(title)) folded.add(title);
    localStorage.setItem(FOLDED, JSON.stringify([...folded]));
    renderDetail();
  } else if (flex) {
    togglePick(comp, flex.dataset.flex);
    renderDetail();
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
el("head").addEventListener("click", (event) => {
  const column = event.target.closest("button");
  if (column) {
    state.sort = column.dataset.sort;
    renderList();
  }
});
el("filter").addEventListener("input", (event) => {
  state.filter = event.target.value;
  renderList();
});
// Enter keeps the typed filter and starts another. Backspace in an empty box removes the last kept one.
el("filter").addEventListener("keydown", (event) => {
  const box = event.target;
  if (event.key === "Enter" && box.value.trim()) {
    state.filters.push(box.value.trim());
    box.value = state.filter = "";
    renderFilters();
  } else if (event.key === "Backspace" && !box.value && state.filters.length) {
    state.filters.pop();
    renderFilters();
  }
});
el("filters").addEventListener("click", (event) => {
  const remove = event.target.closest("[data-remove]");
  if (remove) {
    state.filters.splice(Number(remove.dataset.remove), 1);
    renderFilters();
  }
  el("filter").focus();
});
el("comps").addEventListener("click", (event) => {
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
el("slams").addEventListener("click", (event) => {
  const slam = event.target.closest("[data-item]");
  if (!slam) return;
  state.filters = [slam.dataset.item];
  el("filter").value = state.filter = "";
  state.view = "comps";
  localStorage.setItem(VIEW, "comps");
  renderFilters();
});
el("detail").addEventListener("change", (event) => {
  if (event.target.dataset.edit) saveEdit(state.comp, event.target.dataset.edit, event.target.value.trim());
});
document.addEventListener("keydown", (event) => {
  if (event.target.dataset.edit) return;
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
