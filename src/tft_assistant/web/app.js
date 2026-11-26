const SNAPSHOTS = JSON.parse(document.getElementById("snapshots").textContent);
const state = { snapshot: 0, comp: null, filter: "", sort: "avg" };
const el = (id) => document.getElementById(id);
const esc = (text) =>
  String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const pct = (share) => `${Math.round(share * 100)}%`;
const snap = () => SNAPSHOTS[state.snapshot];
const unitOf = (id) => snap().units[id] || { name: id, cost: 0, traits: [] };
const traitName = (id) => (snap().traits[id] || { name: id }).name;

function unitTile(id, size = "l", options = {}) {
  const unit = unitOf(id);
  const image = unit.icon ? `<img src="${esc(unit.icon)}" alt="" loading="lazy">` : `<span class="blank"></span>`;
  const stars = options.threeStar ? `<b class="stars">★★★</b>` : "";
  const traits = unit.traits.map((t) => traitName(t)).join(", ");
  return `<span class="unit ${size} cost${unit.cost}" title="${esc(unit.name)}${traits ? `: ${esc(traits)}` : ""}">${image}${stars}<span class="unit-name">${esc(unit.name)}</span></span>`;
}

function itemIcon(id) {
  const item = snap().items[id] || { name: id };
  return item.icon ? `<img class="item-icon" src="${esc(item.icon)}" alt="" title="${esc(item.name)}" loading="lazy">` : "";
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
  const names = [comp.name, comp.style, `level ${comp.roll_level}`, ...units, ...built, ...comp.traits.map((t) => traitName(t.trait))];
  return names.map((name) => name.toLowerCase());
}

// A filter that is part of one name, such as "fae emblem", lists the comps with that name. Any
// other filter lists the comps that hold every one of its words somewhere.
function visibleComps() {
  const phrase = state.filter.trim().toLowerCase();
  const words = phrase.split(/\s+/).filter(Boolean);
  const comps = snap().comps.map((comp) => [comp, searchedNames(comp)]);
  const named = comps.filter(([, names]) => names.some((name) => name.includes(phrase)));
  const found = named.length ? named : comps.filter(([, names]) => words.every((word) => names.some((name) => name.includes(word))));
  return found.map(([comp]) => comp).sort(SORTS[state.sort]);
}

function renderList() {
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
        <span class="c-name">${esc(comp.name)}</span>
        <span class="c-level">${comp.roll_level}</span>
        <span class="c-core">${comp.core.map((id) => unitTile(id, "s")).join("")}</span>
        <span class="c-avg num">${comp.avg_placement.toFixed(2)}</span>
        <span class="c-top4 num">${pct(comp.top4)}</span>
        <span class="c-play num">${(comp.share * 100).toFixed(1)}%</span>
      </li>`,
    )
    .join("");
  const s = snap();
  const age = s.newest_match ? `newest match ${hoursAgo(s.newest_match)}` : "no matches";
  el("health").textContent = `${s.boards.toLocaleString()} boards · ${pct(s.unclassified)} unclassified · ${age}`;
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

function boardHtml(comp) {
  const at = Object.fromEntries(comp.board.map((place) => [`${place.row},${place.column}`, place.unit]));
  const lines = [0, 1, 2, 3].map((row) => {
    const hexes = [0, 1, 2, 3, 4, 5, 6].map((column) => {
      const id = at[`${row},${column}`];
      const unit = id && unitOf(id);
      return `<span class="hex" title="${unit ? esc(unit.name) : ""}">${unit && unit.icon ? `<img src="${esc(unit.icon)}" alt="">` : ""}</span>`;
    });
    return `<div class="line">${hexes.join("")}</div>`;
  });
  const note = comp.board_is_default ? "Default rows from attack range. Front row is at the top." : "Front row is at the top.";
  return `<div class="board" title="${note}">${lines.join("")}</div>`;
}

const SHOWN_IN_A_GROUP = 9;
const ITEM_ROWS = 6;

function keyUnitsHtml(comp) {
  const tiles = (ids) => ids.slice(0, SHOWN_IN_A_GROUP).map((id) => unitTile(id, "s")).join("");
  const buildItem = (note) => {
    const needs = note.needs
      .map(
        (pair) =>
          `<span class="needs" title="${pair.avg_together.toFixed(2)} together, ${pair.avg_apart.toFixed(2)} apart">needs ${itemIcon(pair.item)}</span>`,
      )
      .join("");
    const without = note.avg_without === null ? "every build has it" : `${note.avg_without.toFixed(2)} without`;
    return `<span class="build-item ${note.critical ? "critical" : ""}" title="${itemName(note.item)}: avg ${note.avg_with.toFixed(2)} with, ${without}">
      ${itemIcon(note.item)}<span class="figures">${pct(note.share)}${note.critical ? `<br><b>critical</b>` : ""}</span>${needs}</span>`;
  };
  return comp.key_units
    .map(({ unit, role, build }) => {
      const group = snap().item_groups.find((g) => g.units.includes(unit));
      const cost = unitOf(unit).cost;
      const holders = (group ? group.units : [])
        .filter((id) => unitOf(id).cost < cost)
        .sort((a, b) => unitOf(a).cost - unitOf(b).cost);
      return `<div class="key-unit"><div class="role">${esc(role)}</div>${unitTile(unit, "m")}
        <div class="uses">
          <div class="row"><span class="note">builds</span>${build.map(buildItem).join("") || "varies"}</div>
          ${holders.length ? `<div class="row"><span class="note" title="Cheaper units that can hold its items, cheapest first">holders</span>${tiles(holders)}</div>` : ""}
        </div>
      </div>`;
    })
    .join("");
}

const SORTS = {
  play: (a, b) => b.share - a.share,
  avg: (a, b) => a.avg_placement - b.avg_placement,
  top4: (a, b) => b.top4 - a.top4,
  name: (a, b) => a.name.localeCompare(b.name),
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
  ["Play", "play", "c-play num"],
];

// The detail pane never scrolls and leaves no empty band beside its content. The sheet is laid out
// at the pane's width divided by a scale and drawn at that scale, so it always spans the pane. A
// larger scale gives a narrower layout, which wraps more and stands taller, so the largest scale
// whose layout fits the pane's height fills the pane both ways.
const BLANK_PICTURE = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";
const SMALLEST_SCALE = 0.4;
const LARGEST_SCALE = 2;
let sheetScale = 1;

function paneSize() {
  const pane = el("detail");
  const padding = getComputedStyle(pane);
  return [
    pane.clientWidth - parseFloat(padding.paddingLeft) - parseFloat(padding.paddingRight),
    pane.clientHeight - parseFloat(padding.paddingTop) - parseFloat(padding.paddingBottom),
  ];
}

function layOut(scale) {
  const sheet = el("sheet");
  const [width, height] = paneSize();
  sheet.style.zoom = scale;
  sheet.style.width = `${width / scale}px`;
  return sheet.getBoundingClientRect().height <= height && sheet.scrollWidth <= sheet.clientWidth;
}

function largestScaleThatFits(upper) {
  if (layOut(upper)) return upper;
  let [fitting, tooLarge] = [SMALLEST_SCALE, upper];
  for (let step = 0; step < 8; step += 1) {
    const middle = (fitting + tooLarge) / 2;
    if (layOut(middle)) fitting = middle;
    else tooLarge = middle;
  }
  layOut(fitting);
  return fitting;
}

// One scale serves every comp of a snapshot, so the pane does not change size from comp to comp.
// It is the scale that fits the tallest comp; a comp that still does not fit takes a smaller one.
function settleScale() {
  const comps = snap().comps;
  if (!comps.length) return;
  // Every picture has a fixed size, so a blank one measures the same and downloads nothing.
  const measured = (comp) => detailHtml(comp).replace(/ src="[^"]*"/g, ` src="${BLANK_PICTURE}"`);
  const heights = comps.map((comp) => {
    el("detail").innerHTML = measured(comp);
    layOut(1);
    return el("sheet").offsetHeight;
  });
  el("detail").innerHTML = measured(comps[heights.indexOf(Math.max(...heights))]);
  sheetScale = largestScaleThatFits(LARGEST_SCALE);
  renderDetail();
}

function renderDetail() {
  const comp = snap().comps.find((candidate) => candidate.id === state.comp);
  if (!comp) {
    el("detail").innerHTML = `<p class="empty">No comp matches.</p>`;
    return;
  }
  el("detail").innerHTML = detailHtml(comp);
  largestScaleThatFits(sheetScale);
}

// The flex packages picked for each comp, as "slot.option" keys. A comp nobody has touched starts
// with the packages its default board holds.
const pickedByComp = new Map();
function pickedFlex(comp) {
  const key = `${state.snapshot}:${comp.id}`;
  if (!pickedByComp.has(key)) {
    const placed = new Set(comp.board.map((place) => place.unit));
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
  const packageHtml = (p, key) => `<div class="package ${picked.has(key) ? "picked" : ""}" data-flex="${key}" title="Click to put it in the team code, or to take it out">${p.units.map((id) => unitTile(id, "m", { threeStar: threeStar(id) })).join("")}
        <div class="figures"><b>${pct(p.share)}</b> of boards<br>avg ${delta(p.avg_placement, comp.avg_placement)}</div></div>`;
  const cost = (p) => Math.max(...p.units.map((id) => unitOf(id).cost));
  const slotHtml = (options, slot) =>
    options
      .map((p, option) => {
        if (!option) return packageHtml(p, `${slot}.${option}`);
        const upgrade = cost(p) > cost(options[option - 1]);
        const joint = upgrade
          ? `<span class="joint" title="Played until the costlier one is found">→</span>`
          : `<span class="joint" title="One is played in the other's place">or</span>`;
        return joint + packageHtml(p, `${slot}.${option}`);
      })
      .join("");
  const packages = comp.flex.map((options, slot) => `<div class="slot ${options.length > 1 ? "shared" : ""}">${slotHtml(options, slot)}</div>`).join("");
  const team = teamUnits(comp);
  const teamNote = team.length > TEAM_PLACES ? `the first ${TEAM_PLACES} of ${team.length} units` : `${team.length} units`;
  const sharedSlots = comp.flex.some((options) => options.length > 1);
  const shift = (s) =>
    `<span class="shift">${unitTile(s.unit, "m")}<span class="figures">${pct(s.share)}<br><span class="note">was ${pct(s.share_below)}</span></span></span>`;
  const levelUps = comp.level_ups
    .map(
      (up) => `<div class="level-up">
        <div class="figures"><b>Level ${up.level}</b><br>${pct(up.share)} of boards<br>avg ${delta(up.avg_placement, comp.avg_placement)}</div>
        ${up.adds.length ? `<div><div class="note">comes in</div><div class="row">${up.adds.map(shift).join("")}</div></div>` : ""}
        ${up.drops.length ? `<div><div class="note">goes out</div><div class="row">${up.drops.map(shift).join("")}</div></div>` : ""}
      </div>`,
    )
    .join("");
  const tiered = comp.traits.filter((t) => t.tiers > 1);
  const top = Math.max(...tiered.map((t) => t.tier / t.tiers), 0);
  const traits = comp.traits
    .map((t) => {
      const icon = (snap().traits[t.trait] || {}).icon;
      const full = t.tiers > 1 && t.tier / t.tiers === top;
      return `<span class="trait ${full ? "top" : ""}">${icon ? `<img src="${esc(icon)}" alt="">` : ""}${t.units} ${esc(traitName(t.trait))}</span>`;
    })
    .join("");
  const items = comp.items
    .slice(0, ITEM_ROWS)
    .map(
      (pick, index) => `<tr><td class="rank">${index + 1}</td><td>${itemIcon(pick.item)} ${itemName(pick.item)}</td>
        <td>→ ${esc(unitOf(pick.holder).name)}</td><td>${pct(pick.share)}</td>
        <td class="note">avg ${delta(pick.avg_with, comp.avg_placement)} with${pick.avg_without === null ? "" : `, ${pick.avg_without.toFixed(2)} without`}</td></tr>`,
    )
    .join("");
  const spare = comp.spare
    .map(
      (found) => `<div class="row">${itemIcon(found.component)}<span class="joint">→</span>${found.uses
        .map(
          (use) =>
            `<span class="use" title="${itemName(use.item)}: on ${pct(use.share)} of boards, avg ${use.avg_with.toFixed(2)}">${itemIcon(use.item)} ${itemName(use.item)} on ${esc(unitOf(use.holder).name)} <span class="note">${pct(use.share)}</span></span>`,
        )
        .join("")}</div>`,
    )
    .join("");
  const smallTiles = (swaps) => swaps.map((swap) => `<span title="${esc(unitOf(swap.unit).name)}: on ${pct(swap.share_with)} of boards with it, ${pct(swap.share_without)} without">${unitTile(swap.unit, "s")}</span>`).join("");
  const specials = comp.specials
    .map(
      (special) => `<div class="special">
        <span class="what">${itemIcon(special.item)} ${itemName(special.item)} <span class="note">${special.kind}</span></span>
        <span class="figures"><b>${pct(special.share)}</b> of boards · avg ${delta(special.avg_placement, comp.avg_placement)}</span>
        <span class="part"><span class="note">on</span>${unitTile(special.holder, "s")} ${esc(unitOf(special.holder).name)} <span class="note">${pct(special.holder_share)}</span></span>
        ${special.beside.length ? `<span class="part"><span class="note">beside</span>${special.beside.map(itemIcon).join("")}</span>` : ""}
        ${special.adds.length ? `<span class="part"><span class="note">comes in</span>${smallTiles(special.adds)}</span>` : ""}
        ${special.drops.length ? `<span class="part"><span class="note">goes out</span>${smallTiles(special.drops)}</span>` : ""}
      </div>`,
    )
    .join("");
  return `<div id="sheet">
    <header><div class="title"><h1><span class="tier t${comp.tier}">${comp.tier}</span>${esc(comp.name)}</h1>
      <button id="copy-team" title="${esc(teamCode(comp))}">Copy team code</button><span class="note">${teamNote}: core and picked flex</span></div>
      <p class="stats"><b>${esc(comp.style)}</b> · avg <b>${comp.avg_placement.toFixed(2)}</b> · top 4 <b>${pct(comp.top4)}</b> · play <b>${(comp.share * 100).toFixed(1)}%</b> · ${comp.boards.toLocaleString()} boards</p></header>
    <section><h2>Core</h2><div class="row">${comp.core.map((id) => unitTile(id, "l", { threeStar: threeStar(id) })).join("")}</div></section>
    <section><h2>Flex</h2><div><div class="row">${packages || `<span class="note">no regular flex units</span>`}</div>
      ${sharedSlots ? `<div class="note">Units in one outline take one slot: a board rarely holds both. An arrow points to the costlier unit, which the cheaper one is played until.</div>` : ""}</div></section>
    <section><h2>Level up</h2><div>${levelUps || `<span class="note">no level above the usual one has enough boards</span>`}</div></section>
    <section><h2>Traits</h2><div class="row">${traits}</div></section>
    <section><h2>Key units</h2><div>${keyUnitsHtml(comp) || `<span class="note">no unit holds items regularly</span>`}</div></section>
    <div class="band">
      <section><h2>Items</h2><div><div class="row take"><span class="note">components to take first</span>${comp.take.map(itemIcon).join("")}</div>
        <table class="items">${items}</table>
        ${spare ? `<div class="spare"><div class="note">the components it uses least go into</div>${spare}</div>` : ""}</div></section>
      <section><h2>Positioning</h2>${boardHtml(comp)}</section>
    </div>
    ${specials ? `<section><h2>Emblems, artifacts</h2><div>${specials}</div></section>` : ""}</div>`;
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

const LIST_WIDTH = "tft-assistant.list-width";
const NARROWEST_LIST = 260;
const NARROWEST_DETAIL = 640;
const setListWidth = (pixels) => document.body.style.setProperty("--list-width", `${pixels}px`);
if (localStorage.getItem(LIST_WIDTH)) setListWidth(localStorage.getItem(LIST_WIDTH));
addEventListener("resize", settleScale);
el("divider").addEventListener("pointerdown", (event) => {
  event.target.setPointerCapture(event.pointerId);
  document.body.classList.add("resizing");
});
el("divider").addEventListener("pointermove", (event) => {
  if (!document.body.classList.contains("resizing")) return;
  const width = Math.round(Math.min(Math.max(event.clientX, NARROWEST_LIST), innerWidth - NARROWEST_DETAIL));
  setListWidth(width);
  localStorage.setItem(LIST_WIDTH, width);
  if (el("sheet")) largestScaleThatFits(LARGEST_SCALE);
});
el("divider").addEventListener("pointerup", () => {
  document.body.classList.remove("resizing");
  settleScale();
});
el("divider").addEventListener("dblclick", () => {
  document.body.style.removeProperty("--list-width");
  localStorage.removeItem(LIST_WIDTH);
  settleScale();
});

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
  settleScale();
});

el("detail").addEventListener("click", (event) => {
  const comp = snap().comps.find((candidate) => candidate.id === state.comp);
  if (!comp) return;
  const flex = event.target.closest("[data-flex]");
  if (flex) {
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
  settleScale();
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
el("comps").addEventListener("click", (event) => {
  const row = event.target.closest("li");
  if (row) {
    state.comp = row.dataset.id;
    renderList();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    move(event.key === "ArrowDown" ? 1 : -1);
  }
});
if (SNAPSHOTS.length) {
  renderList();
  settleScale();
}
else el("detail").innerHTML = `<p class="empty">No snapshot was built.</p>`;
