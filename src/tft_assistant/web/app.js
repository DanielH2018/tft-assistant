const SNAPSHOTS = JSON.parse(document.getElementById("snapshots").textContent);
const state = { snapshot: 0, comp: null, filter: "" };
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

function matches(comp, words) {
  if (!words.length) return true;
  const units = [...comp.core, ...comp.packages.flatMap((p) => p.units)].map((id) => unitOf(id).name);
  const text = [comp.name, ...units, ...comp.traits.map((t) => traitName(t.trait))].join(" ").toLowerCase();
  return words.every((word) => text.includes(word));
}

function visibleComps() {
  const words = state.filter.toLowerCase().split(/\s+/).filter(Boolean);
  return snap().comps.filter((comp) => matches(comp, words));
}

function renderList() {
  const comps = visibleComps();
  if (!comps.some((comp) => comp.id === state.comp)) state.comp = comps.length ? comps[0].id : null;
  el("comps").innerHTML = comps
    .map(
      (comp) => `<li data-id="${comp.id}" class="${comp.id === state.comp ? "selected" : ""}">
        <span class="tier t${comp.tier}">${comp.tier}</span>
        <span class="name">${esc(comp.name)}</span>
        <span class="mini">${comp.core.map((id) => unitTile(id, "s")).join("")}</span>
        <span class="num">${comp.avg_placement.toFixed(2)}</span>
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

function groupHtml(comp) {
  return comp.carries
    .map((carry) => {
      const group = snap().item_groups.find((g) => g.units.includes(carry));
      if (!group) return "";
      const cost = unitOf(carry).cost;
      const others = group.units.filter((id) => id !== carry);
      const holders = others.filter((id) => unitOf(id).cost < cost);
      const pivots = others.filter((id) => unitOf(id).cost >= cost);
      return `<div class="row">${unitTile(carry, "m")}
        <div><div class="note">builds like</div><div class="row">${group.items.map(itemIcon).join("")}</div></div>
        <div><div class="note">holders, cheapest first</div><div class="row">${holders.map((id) => unitTile(id, "s")).join("") || "none"}</div></div>
        <div><div class="note">pivots</div><div class="row">${pivots.map((id) => unitTile(id, "s")).join("") || "none"}</div></div>
      </div>`;
    })
    .join("");
}

function renderDetail() {
  const comp = snap().comps.find((candidate) => candidate.id === state.comp);
  if (!comp) {
    el("detail").innerHTML = `<p class="empty">No comp matches.</p>`;
    return;
  }
  const levels = comp.levels.filter(([, share]) => share >= 0.05).map(([level, share]) => `level ${level} <b>${pct(share)}</b>`);
  const reroll = comp.three_stars.length
    ? `<div class="row"><span class="note">usually three-starred</span>${comp.three_stars.map((id) => unitTile(id, "s", { threeStar: true })).join("")}</div>`
    : "";
  const packages = comp.packages
    .map(
      (p) => `<div class="package">${p.units.map((id) => unitTile(id, "m")).join("")}
        <div class="figures"><b>${pct(p.share)}</b> of boards<br>avg ${delta(p.avg_placement, comp.avg_placement)}</div></div>`,
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
    .map(
      (pick, index) => `<tr><td class="rank">${index + 1}</td><td>${itemIcon(pick.item)} ${itemName(pick.item)}</td>
        <td>→ ${esc(unitOf(pick.holder).name)}</td><td>${pct(pick.share)}</td>
        <td class="note">avg ${delta(pick.avg_with, comp.avg_placement)} with${pick.avg_without === null ? "" : `, ${pick.avg_without.toFixed(2)} without`}</td></tr>`,
    )
    .join("");
  el("detail").innerHTML = `
    <h1><span class="tier t${comp.tier}">${comp.tier}</span>${esc(comp.name)}</h1>
    <p class="stats">avg <b>${comp.avg_placement.toFixed(2)}</b> · top 4 <b>${pct(comp.top4)}</b> · play <b>${(comp.share * 100).toFixed(1)}%</b> · ${comp.boards.toLocaleString()} boards</p>
    <section><h2>Tempo</h2><div><div class="stats" style="margin:0">${levels.join(" · ")}</div>${reroll}</div></section>
    <section><h2>Core</h2><div class="row">${comp.core.map((id) => unitTile(id, "l", { traits: true })).join("")}</div></section>
    <section><h2>Flex</h2><div class="row">${packages || `<span class="note">no regular flex units</span>`}</div></section>
    <section><h2>Traits</h2><div class="row">${traits}</div></section>
    <section><h2>Items</h2><div class="split">
      <div><table class="items">${items}</table>
        <div class="row" style="margin-top:6px"><span class="note">take first</span>${comp.take.map(itemIcon).join("")}</div>
        <div class="note">Placements beside an item are correlations, not effects.</div></div>
      ${boardHtml(comp)}
    </div></section>
    <section><h2>Carries</h2><div>${groupHtml(comp) || `<span class="note">no carry with an item group</span>`}</div></section>`;
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

el("selection").innerHTML = SNAPSHOTS.map((s, index) => `<option value="${index}">${esc(s.label)}</option>`).join("");
el("selection").addEventListener("change", (event) => {
  state.snapshot = Number(event.target.value);
  renderList();
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
