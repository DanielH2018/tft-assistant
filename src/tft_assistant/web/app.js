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
  const traits = options.traits ? `<span class="unit-traits">${unit.traits.map((t) => esc(traitName(t))).join("<br>")}</span>` : "";
  return `<span class="unit ${size} cost${unit.cost}" title="${esc(unit.name)}">${image}${stars}<span class="unit-name">${esc(unit.name)}</span>${traits}</span>`;
}

function itemIcon(id) {
  const item = snap().items[id] || { name: id };
  return item.icon ? `<img class="item-icon" src="${esc(item.icon)}" alt="" title="${esc(item.name)}" loading="lazy">` : "";
}
const itemName = (id) => esc((snap().items[id] || { name: id }).name);

// A reroll style names a unit cost, so it also says the level the comp rolls at.
function styleHtml(comp) {
  const level = comp.style.includes(String(comp.roll_level)) ? "" : ` <span class="note">Lv ${comp.roll_level}</span>`;
  return `${esc(comp.style)}${level}`;
}

function matches(comp, words) {
  if (!words.length) return true;
  const units = [...comp.core, ...comp.flex.flat().flatMap((p) => p.units)].map((id) => unitOf(id).name);
  const text = [comp.name, comp.style, ...units, ...comp.traits.map((t) => traitName(t.trait))].join(" ").toLowerCase();
  return words.every((word) => text.includes(word));
}

function visibleComps() {
  const words = state.filter.toLowerCase().split(/\s+/).filter(Boolean);
  return snap()
    .comps.filter((comp) => matches(comp, words))
    .sort(SORTS[state.sort]);
}

function renderList() {
  const comps = visibleComps();
  if (!comps.some((comp) => comp.id === state.comp)) state.comp = comps.length ? comps[0].id : null;
  el("head").innerHTML = COLUMNS.map(([label, sort, numeric]) => {
    const sorted = sort === state.sort ? "sorted" : "";
    const cell = `class="${numeric ? "num" : ""} ${sorted}"`;
    return sort ? `<button data-sort="${sort}" ${cell}>${label}</button>` : `<span ${cell}>${label}</span>`;
  }).join("");
  el("comps").innerHTML = comps
    .map(
      (comp) => `<li data-id="${comp.id}" class="comp-row ${comp.id === state.comp ? "selected" : ""}">
        <span class="tier t${comp.tier}">${comp.tier}</span>
        <span class="name">${esc(comp.name)}</span>
        <span class="style">${styleHtml(comp)}</span>
        <span class="mini">${comp.core.map((id) => unitTile(id, "s")).join("")}</span>
        <span class="num">${comp.avg_placement.toFixed(2)}</span>
        <span class="num">${pct(comp.top4)}</span>
        <span class="num">${(comp.share * 100).toFixed(1)}%</span>
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
  const note = comp.board_is_default ? "Default rows from attack range. Front row is at the top." : "";
  return `<div><div class="board">${lines.join("")}</div><div class="note">${note}</div></div>`;
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
        <div><div class="note">builds here</div><div class="row">${build.map(buildItem).join("") || "varies"}</div></div>
        ${holders.length ? `<div class="holders"><div class="note">can hold its items, cheapest first</div><div class="row">${tiles(holders)}</div></div>` : ""}
      </div>`;
    })
    .join("");
}

const SORTS = {
  play: (a, b) => b.share - a.share,
  avg: (a, b) => a.avg_placement - b.avg_placement,
  top4: (a, b) => b.top4 - a.top4,
  name: (a, b) => a.name.localeCompare(b.name),
  style: (a, b) => a.roll_level - b.roll_level || a.style.localeCompare(b.style) || a.avg_placement - b.avg_placement,
};
const COLUMNS = [
  ["Tier", "avg"],
  ["Comp", "name"],
  ["Style", "style"],
  ["Core", null],
  ["Avg", "avg", true],
  ["Top 4", "top4", true],
  ["Play", "play", true],
];

function renderDetail() {
  const comp = snap().comps.find((candidate) => candidate.id === state.comp);
  if (!comp) {
    el("detail").innerHTML = `<p class="empty">No comp matches.</p>`;
    return;
  }
  const threeStar = (id) => comp.three_stars.includes(id);
  const packageHtml = (p) => `<div class="package">${p.units.map((id) => unitTile(id, "m", { threeStar: threeStar(id) })).join("")}
        <div class="figures"><b>${pct(p.share)}</b> of boards<br>avg ${delta(p.avg_placement, comp.avg_placement)}</div></div>`;
  const cost = (p) => Math.max(...p.units.map((id) => unitOf(id).cost));
  const slotHtml = (options) =>
    options
      .map((p, index) => {
        if (!index) return packageHtml(p);
        const upgrade = cost(p) > cost(options[index - 1]);
        const joint = upgrade
          ? `<span class="joint" title="Played until the costlier one is found">→</span>`
          : `<span class="joint" title="One is played in the other's place">or</span>`;
        return joint + packageHtml(p);
      })
      .join("");
  const packages = comp.flex.map((options) => `<div class="slot ${options.length > 1 ? "shared" : ""}">${slotHtml(options)}</div>`).join("");
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
  el("detail").innerHTML = `
    <header><h1><span class="tier t${comp.tier}">${comp.tier}</span>${esc(comp.name)}</h1>
      <p class="stats"><b>${styleHtml(comp)}</b> · avg <b>${comp.avg_placement.toFixed(2)}</b> · top 4 <b>${pct(comp.top4)}</b> · play <b>${(comp.share * 100).toFixed(1)}%</b> · ${comp.boards.toLocaleString()} boards</p></header>
    <section><h2>Core</h2><div class="row">${comp.core.map((id) => unitTile(id, "l", { traits: true, threeStar: threeStar(id) })).join("")}</div></section>
    <section><h2>Flex</h2><div><div class="row">${packages || `<span class="note">no regular flex units</span>`}</div>
      ${sharedSlots ? `<div class="note">Units in one outline take one slot: a board rarely holds both. An arrow points to the costlier unit, which the cheaper one is played until.</div>` : ""}</div></section>
    <section><h2>Level up</h2><div>${levelUps || `<span class="note">no level above the usual one has enough boards</span>`}</div></section>
    <section><h2>Traits</h2><div class="row">${traits}</div></section>
    <section><h2>Key units</h2><div>${keyUnitsHtml(comp) || `<span class="note">no unit holds items regularly</span>`}</div></section>
    <section><h2>Items</h2><div class="split">
      <div><div class="row take"><span class="note">components to take first</span>${comp.take.map(itemIcon).join("")}</div>
        <table class="items">${items}</table>
        <div class="note">Placements beside an item are correlations, not effects.</div></div>
      ${boardHtml(comp)}
    </div></section>`;
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
const NARROWEST_LIST = 520;
const NARROWEST_DETAIL = 640;
const setListWidth = (pixels) => document.body.style.setProperty("--list-width", `${pixels}px`);
if (localStorage.getItem(LIST_WIDTH)) setListWidth(localStorage.getItem(LIST_WIDTH));
el("divider").addEventListener("pointerdown", (event) => {
  event.target.setPointerCapture(event.pointerId);
  document.body.classList.add("resizing");
});
el("divider").addEventListener("pointermove", (event) => {
  if (!document.body.classList.contains("resizing")) return;
  const width = Math.round(Math.min(Math.max(event.clientX, NARROWEST_LIST), innerWidth - NARROWEST_DETAIL));
  setListWidth(width);
  localStorage.setItem(LIST_WIDTH, width);
});
el("divider").addEventListener("pointerup", () => document.body.classList.remove("resizing"));
el("divider").addEventListener("dblclick", () => {
  document.body.style.removeProperty("--list-width");
  localStorage.removeItem(LIST_WIDTH);
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
if (SNAPSHOTS.length) renderList();
else el("detail").innerHTML = `<p class="empty">No snapshot was built.</p>`;
