const DATA = /*__DATA__*/null;
DATA.actors_en = DATA.actors.filter(a => a.roles.some(r => (r.language || "").toLowerCase() === "english"));
DATA.actors_ja = DATA.actors.filter(a => a.roles.some(r => (r.language || "").toLowerCase() === "japanese"));

const BADGE_COLOR = {
  actors_en: "var(--lang-en)", actors_ja: "var(--lang-ja)", works: "var(--c-work)", characters: "var(--c-character)",
  studios: "var(--c-studio)", franchises: "var(--c-franchise)",
};
const LANG_COLOR = { "english": "var(--lang-en)", "japanese": "var(--lang-ja)" };

const SORT_OPTIONS = {
  // The first option of each list is the default: most-to-least.
  actors_en: [["count_desc", "Most roles"], ["count_asc", "Fewest roles"], ["name_first", "First name (A-Z)"], ["name_last", "Last name (A-Z)"]],
  actors_ja: [["count_desc", "Most roles"], ["count_asc", "Fewest roles"], ["name_first", "First name (A-Z)"], ["name_last", "Last name (A-Z)"]],
  works: [["count_desc", "Largest cast"], ["count_asc", "Smallest cast"], ["title", "Title (A-Z)"], ["year_desc", "Newest first"], ["year_asc", "Oldest first"]],
  characters: [["count_desc", "Most appearances"], ["name", "Name (A-Z)"]],
  studios: [["count_desc", "Most credits"], ["name", "Name (A-Z)"]],
  franchises: [["count_desc", "Most works"], ["name", "Name (A-Z)"], ["year_asc", "Oldest first"], ["year_desc", "Newest first"]],
};

let currentView = "actors_en";
let currentDetail = null; // {view, id, backView} while viewing a detail page, else null
let lastActorsTab = "actors_en";
let mediaFilter = "all";
let currentSort = null;
let suppressPush = false; // true while hash-driven navigation is in progress, so we replaceState instead of pushState
let viewMode = "grid"; // "grid" | "list" -- list is a denser alternative for browsing a lot of items at once
const PAGE_SIZE = 60;
let visibleCount = PAGE_SIZE; // reset to PAGE_SIZE whenever the filtered set changes; grown by "Load more"

function setViewMode(mode) {
  viewMode = mode;
  document.getElementById("viewGridBtn").classList.toggle("active", mode === "grid");
  document.getElementById("viewListBtn").classList.toggle("active", mode === "list");
  showList(currentView, document.getElementById("search").value.trim().toLowerCase());
}

// Grid/List toggle for the cast section of a Work or Character detail page
// (a big cast rendered as one full-width row per character used to force a
// long vertical scroll -- grid mode packs several character cards per row).
let castViewMode = "grid";
try { castViewMode = localStorage.getItem("actordb_cast_view") || "grid"; } catch (e) {}

function setCastViewMode(mode) {
  castViewMode = mode;
  try { localStorage.setItem("actordb_cast_view", mode); } catch (e) {}
  if (currentDetail) showDetail(currentDetail.view, currentDetail.id);
}

// Sorting for the cast list on a Work page (default: most important roles / best-known actors first)
// and for the appearance list on a Character page.
const ROLE_RANK = { Main: 0, Supporting: 1, Minor: 2, Cameo: 3 };
const ACTOR_CREDITS = {};
DATA.actors.forEach(a => { ACTOR_CREDITS[a.name] = a.roles.length; });
const CAST_SORTS = {
  work: [["importance", "Role importance"], ["credits", "Actors with most credits"], ["character", "Character (A-Z)"], ["actor", "Actor (A-Z)"]],
  character: [["newest", "Newest first"], ["oldest", "Oldest first"], ["title", "Work (A-Z)"]],
};
const castSort = { work: "importance", character: "newest" };
for (const k of Object.keys(castSort)) {
  try { const v = localStorage.getItem("actordb_cast_sort_" + k); if (v && CAST_SORTS[k].some(o => o[0] === v)) castSort[k] = v; } catch (e) {}
}
function setCastSort(kind, val) {
  castSort[kind] = val;
  try { localStorage.setItem("actordb_cast_sort_" + kind, val); } catch (e) {}
  if (currentDetail) showDetail(currentDetail.view, currentDetail.id);
}
function castSortHTML(kind) {
  return `<label class="cast-sort">Sort: <select onchange="setCastSort('${kind}', this.value)">` +
    CAST_SORTS[kind].map(([v, l]) => `<option value="${v}"${castSort[kind] === v ? " selected" : ""}>${esc(l)}</option>`).join("") +
    `</select></label>`;
}
function roleRankOf(g) { return Math.min(...g.performances.map(p => ROLE_RANK[p.role_type] ?? 4)); }
function maxCreditsOf(g) { return Math.max(...g.performances.map(p => ACTOR_CREDITS[p.actor] || 0)); }
function sortWorkCast(groups) {
  const byName = (a, b) => a.character.localeCompare(b.character);
  const arr = groups.slice();
  switch (castSort.work) {
    case "credits": arr.sort((a, b) => maxCreditsOf(b) - maxCreditsOf(a) || roleRankOf(a) - roleRankOf(b) || byName(a, b)); break;
    case "character": arr.sort(byName); break;
    case "actor": arr.sort((a, b) => a.performances[0].actor.localeCompare(b.performances[0].actor)); break;
    default: arr.sort((a, b) => roleRankOf(a) - roleRankOf(b) || maxCreditsOf(b) - maxCreditsOf(a) || byName(a, b));
  }
  return arr;
}
function sortCharacterAppearances(groups) {
  const arr = groups.slice();
  const yr = g => g.work_year == null ? 9999 : g.work_year;
  switch (castSort.character) {
    case "oldest": arr.sort((a, b) => yr(a) - yr(b) || a.work.localeCompare(b.work)); break;
    case "title": arr.sort((a, b) => a.work.localeCompare(b.work)); break;
    default: arr.sort((a, b) => yr(b) - yr(a) || a.work.localeCompare(b.work));
  }
  return arr;
}

function castViewToggleHTML(kind) {
  return `<div class="cast-controls">${kind ? castSortHTML(kind) : ""}<div class="cast-view-toggle">
    <button class="view-toggle-btn ${castViewMode === "grid" ? "active" : ""}" onclick="setCastViewMode('grid')" title="Card grid">Grid</button>
    <button class="view-toggle-btn ${castViewMode === "list" ? "active" : ""}" onclick="setCastViewMode('list')" title="Full-width list">List</button>
  </div></div>`;
}

const FAV_TYPES = ["actors", "works", "characters", "studios", "franchises"];
const FAV_KEYS = {
  actors: "actordb_favorite_actors", works: "actordb_favorite_works", characters: "actordb_favorite_characters",
  studios: "actordb_favorite_studios", franchises: "actordb_favorite_franchises",
};
// Favorites/watched flags set in the database are "seeds": each seed is applied
// to this browser once, so anything you later un-star here stays un-starred.
function applySeeds(set, seeds, appliedKey) {
  let applied = [];
  try { applied = JSON.parse(localStorage.getItem(appliedKey) || "[]"); } catch (e) { applied = []; }
  const seen = new Set(applied);
  let changed = false;
  for (const s of seeds || []) {
    if (!seen.has(s)) { set.add(s); applied.push(s); changed = true; }
  }
  if (changed) { try { localStorage.setItem(appliedKey, JSON.stringify(applied)); } catch (e) { /* ignore */ } }
  return changed;
}
function loadFavorites() {
  const obj = {};
  for (const t of FAV_TYPES) {
    try { obj[t] = new Set(JSON.parse(localStorage.getItem(FAV_KEYS[t]) || "[]")); } catch (e) { obj[t] = new Set(); }
    if (applySeeds(obj[t], ((DATA.flags || {}).favorites || {})[t], FAV_KEYS[t] + "_seeded")) {
      try { localStorage.setItem(FAV_KEYS[t], JSON.stringify(Array.from(obj[t]))); } catch (e) { /* ignore */ }
    }
  }
  return obj;
}
function saveFavorites(type) {
  try { localStorage.setItem(FAV_KEYS[type], JSON.stringify(Array.from(favorites[type]))); } catch (e) { /* storage unavailable; favorites stay in-memory for this session */ }
}
let favorites = loadFavorites();
function isFavorite(type, label) { return !!(favorites[type] && favorites[type].has(label)); }
function favRefBits(type, label) {
  const fav = isFavorite(type, label);
  return { cls: fav ? " fav-ref" : "", star: fav ? '<span class="fav-ref-star">&#9733;</span>' : "" };
}
function favDetailBadge(type, label) {
  const fav = isFavorite(type, label);
  return `<span class="fav-star-detail ${fav ? "active" : ""}" onclick="toggleFavorite('${type}','${jsStr(label)}')">${fav ? "&#9733; Favorited" : "&#9734; Add to favorites"}</span>`;
}
function toggleFavorite(type, name, evt) {
  if (evt) evt.stopPropagation();
  if (favorites[type].has(name)) favorites[type].delete(name); else favorites[type].add(name);
  saveFavorites(type);
  if (currentDetail) {
    showDetail(currentDetail.view, currentDetail.id);
  } else if (SORT_OPTIONS[currentView]) {
    showList(currentView, document.getElementById("search").value.trim().toLowerCase());
  }
  // else: on a computed tab (costars/counterparts/connections/compare/stats/todo) with no
  // detail open, there's no tile grid of this type to re-render here.
}

// Watched/played tracking -- separate from favorites, works only (you watch or
// play a work, not an actor/character/studio/franchise).
const WATCHED_KEY = "actordb_watched_works";
function loadWatched() {
  let s;
  try { s = new Set(JSON.parse(localStorage.getItem(WATCHED_KEY) || "[]")); } catch (e) { s = new Set(); }
  if (applySeeds(s, (DATA.flags || {}).watched, WATCHED_KEY + "_seeded")) {
    try { localStorage.setItem(WATCHED_KEY, JSON.stringify(Array.from(s))); } catch (e) { /* ignore */ }
  }
  return s;
}
function saveWatched() {
  try { localStorage.setItem(WATCHED_KEY, JSON.stringify(Array.from(watched))); } catch (e) { /* storage unavailable; watched stays in-memory for this session */ }
}
let watched = loadWatched();
function isWatched(title) { return watched.has(title); }
function toggleWatched(title, evt) {
  if (evt) evt.stopPropagation();
  if (watched.has(title)) watched.delete(title); else watched.add(title);
  saveWatched();
  if (currentDetail && currentDetail.view === "works") {
    showDetail("works", currentDetail.id);
  } else if (currentView === "works") {
    showList("works", document.getElementById("search").value.trim().toLowerCase());
  }
}

function esc(s) { return (s ?? "").toString().replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function jsStr(s) { return esc(s).replace(/'/g, "\\'"); }

function initials(name) {
  const parts = (name || "?").trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function lastName(name) {
  const parts = (name || "").trim().split(/\s+/);
  return parts[parts.length - 1] || "";
}

function langBadge(lang, inline) {
  if (!lang) return "";
  const color = LANG_COLOR[lang.toLowerCase()] || "var(--lang-other)";
  return `<span class="lang-tag${inline ? " inline" : ""}" style="background:${color}">${esc(lang)}</span>`;
}

function matchesMedia(mt) {
  return mediaFilter === "all" || mt === mediaFilter;
}

function isActorsView(view) { return view === "actors_en" || view === "actors_ja" || view === "actors"; }
function listSource(view) {
  if (view === "actors_en") return DATA.actors_en;
  if (view === "actors_ja") return DATA.actors_ja;
  return DATA[view];
}
function favTypeOf(view) { return isActorsView(view) ? "actors" : view; }

function countOf(it) {
  if (it.roles) return it.roles.length;
  if (it.appearances) return it.appearances.length;
  if (it.cast) return it.cast.length;
  if (it.works) return it.works.length;
  return 0;
}
function yearOf(it) {
  if (it.year != null) return it.year;
  if (it.works && it.works.length) return Math.min(...it.works.map(w => w.year == null ? 9999 : w.year));
  return 9999;
}

function sortItems(view, items, key) {
  const arr = items.slice();
  switch (key) {
    case "name_first": arr.sort((a, b) => (a.name || a.title || "").localeCompare(b.name || b.title || "")); break;
    case "name_last": arr.sort((a, b) => lastName(a.name).localeCompare(lastName(b.name))); break;
    case "title": arr.sort((a, b) => (a.title || "").localeCompare(b.title || "")); break;
    case "name": arr.sort((a, b) => (a.name || "").localeCompare(b.name || "")); break;
    case "count_desc": arr.sort((a, b) => countOf(b) - countOf(a)); break;
    case "count_asc": arr.sort((a, b) => countOf(a) - countOf(b)); break;
    case "year_asc": arr.sort((a, b) => yearOf(a) - yearOf(b)); break;
    case "year_desc": arr.sort((a, b) => yearOf(b) - yearOf(a)); break;
    default: break;
  }
  return arr;
}

function setCounts() {
  document.getElementById("count-actors_en").textContent = DATA.actors_en.length;
  document.getElementById("count-actors_ja").textContent = DATA.actors_ja.length;
  for (const k of ["works", "characters", "studios", "franchises"]) {
    document.getElementById("count-" + k).textContent = DATA[k].length;
  }
}

function populateFilters() {
  const mediaSel = document.getElementById("mediaFilter");
  for (const mt of (DATA.media_types || [])) {
    const opt = document.createElement("option");
    opt.value = mt;
    opt.textContent = mt;
    mediaSel.appendChild(opt);
  }
}

function populateSortSelect(view) {
  const sel = document.getElementById("sortSelect");
  const opts = SORT_OPTIONS[view] || [];
  sel.innerHTML = opts.map(([val, label]) => `<option value="${val}">${esc(label)}</option>`).join("");
  currentSort = opts.length ? opts[0][0] : null;
  sel.value = currentSort || "";
}

function setSearchUI(view) {
  const input = document.getElementById("search");
  const btn = document.getElementById("searchbtn");
  const mediaSel = document.getElementById("mediaFilter");
  const sortSel = document.getElementById("sortSelect");
  const hint = document.getElementById("searchhint");
  const favWrap = document.getElementById("favOnlyWrap");
  const watchedWrap = document.getElementById("watchedOnlyWrap");
  const viewToggleWrap = document.getElementById("viewToggleWrap");
  const placeholders = {
    actors_en: 'Search English VAs, e.g. "Troy Baker"',
    actors_ja: 'Search Japanese VAs, e.g. "Jun Fukuyama"',
    works: 'Search works, e.g. "Persona 5 Royal"',
    characters: 'Search characters, e.g. "Joker"',
    studios: 'Search studios, e.g. "Atlus"',
    franchises: 'Search franchises, e.g. "Persona"',
    costars: 'Actor name, e.g. "Yuri Lowenthal"',
    counterparts: 'Actor name, e.g. "Xander Mobus"',
    connections: 'Actor name, e.g. "Yuri Lowenthal"',
  };
  const hints = {
    actors_en: 'Type to filter the grid live, or press Enter/Search to jump straight to an exact match (case doesn\'t matter).',
    actors_ja: 'Type to filter the grid live, or press Enter/Search to jump straight to an exact match (case doesn\'t matter).',
    works: 'Type to filter, or press Enter/Search for an exact title match. Use the media filter to narrow by type.',
    characters: 'Type to filter, or press Enter/Search for an exact match. Use the media filter to narrow by type.',
    studios: 'Type to filter, or press Enter/Search for an exact match. Credits are grouped and filterable by medium.',
    franchises: 'Type to filter, or press Enter/Search for an exact match. Use the media filter to narrow by type.',
    costars: 'Type an actor name (any case) and press Enter/Search to see everyone they have shared a work with.',
    counterparts: 'Type an actor name (any case) and press Enter/Search to see their other-language counterparts.',
    connections: 'Type an actor name (any case) and press Enter/Search to see their co-star network as a graph.',
    compare: '',
  };
  const noSearchBar = view === "compare" || view === "stats" || view === "todo";
  const hasSort = !!SORT_OPTIONS[view];
  input.style.display = noSearchBar ? "none" : "";
  btn.style.display = noSearchBar ? "none" : "";
  mediaSel.style.display = noSearchBar ? "none" : "";
  sortSel.style.display = hasSort ? "" : "none";
  if (hasSort) populateSortSelect(view);
  input.placeholder = placeholders[view] || "Search...";
  hint.textContent = hints[view] || "";
  favWrap.style.display = hasSort ? "flex" : "none";
  watchedWrap.style.display = view === "works" ? "flex" : "none";
  viewToggleWrap.style.display = hasSort ? "inline-flex" : "none";
}

function switchTab(view) {
  snapshotScroll();
  currentView = view;
  currentDetail = null;
  if (view === "actors_en" || view === "actors_ja") lastActorsTab = view;
  document.querySelectorAll(".navtab").forEach(el => el.classList.toggle("active", el.dataset.view === view));
  setSearchUI(view);
  if (view === "costars") {
    showCostarsPrompt();
  } else if (view === "counterparts") {
    showCounterpartsPrompt();
  } else if (view === "connections") {
    showConnectionsPrompt();
  } else if (view === "compare") {
    showCompareUI();
  } else if (view === "stats") {
    showStats();
  } else if (view === "todo") {
    showTodo();
  } else {
    document.getElementById("search").value = "";
    // suppressPush is true while a popstate/back-forward restore is in
    // progress -- in that case keep whatever pagination depth was restored
    // instead of snapping back to the first page.
    showList(view, "", { keepPage: suppressPush });
  }
  syncHash();
}

function showList(view, filterText, opts) {
  opts = opts || {};
  currentView = view;
  currentDetail = null;
  let items = listSource(view).filter(it => {
    const label = (it.name || it.title || "").toLowerCase();
    return !filterText || label.includes(filterText);
  });
  if (view === "works") items = items.filter(it => matchesMedia(it.media_type));
  if (view === "characters") items = items.filter(it => it.appearances.some(g => matchesMedia(g.media_type)));
  if (view === "studios") items = items.filter(it => it.works.some(w => matchesMedia(w.media_type)));
  if (view === "franchises") items = items.filter(it => it.works.some(w => matchesMedia(w.media_type)));
  if (isActorsView(view)) items = items.filter(it => it.roles.some(r => matchesMedia(r.media_type)));
  if (document.getElementById("favOnly").checked) {
    const type = favTypeOf(view);
    items = items.filter(it => isFavorite(type, it.name || it.title));
  }
  if (view === "works" && document.getElementById("watchedOnly").checked) {
    items = items.filter(it => isWatched(it.title));
  }
  items = sortItems(view, items, currentSort);

  if (!opts.keepPage) visibleCount = PAGE_SIZE;
  const total = items.length;
  const content = document.getElementById("content");
  if (total === 0) {
    content.innerHTML = `<div class="empty">No results${filterText ? ` for "${esc(filterText)}"` : ""}.</div>`;
    return;
  }
  const shown = items.slice(0, visibleCount);

  const body = viewMode === "list"
    ? `<div class="list">` + shown.map(it => renderListRow(view, it)).join("") + `</div>`
    : `<div class="grid">` + shown.map(it => renderTile(view, it)).join("") + `</div>`;
  const remaining = total - shown.length;
  const loadMore = remaining > 0
    ? `<div class="load-more-wrap"><button class="load-more-btn" onclick="loadMoreItems()">Load ${Math.min(PAGE_SIZE, remaining)} more (${remaining} remaining)</button></div>`
    : "";

  content.innerHTML = body + loadMore;
}

function loadMoreItems() {
  visibleCount += PAGE_SIZE;
  showList(currentView, document.getElementById("search").value.trim().toLowerCase(), { keepPage: true });
  // Stamp the grown page size onto the current history entry so navigating
  // away and back restores however far the user had paged, not just page 1.
  try { history.replaceState({ ...(history.state || {}), visibleCount }, "", location.hash); } catch (e) {}
}

function renderTile(view, it) {
  const color = BADGE_COLOR[view];
  const label = it.name || it.title;
  const actorsView = isActorsView(view);
  const type = favTypeOf(view);
  let sub = "";
  if (actorsView) sub = (it.birth_year ? "b. " + it.birth_year : "b. unknown") + " &middot; " + it.roles.length + " role" + (it.roles.length===1?"":"s");
  if (view === "works") sub = esc(it.media_type) + (it.year ? " &middot; " + it.year : "") + (it.franchise ? "<br>" + esc(it.franchise) : "") + (it.cast.length === 0 ? '<br><span class="no-cast-badge">no cast yet</span>' : "");
  if (view === "characters") sub = it.appearances.length + " appearance" + (it.appearances.length===1?"":"s");
  if (view === "studios") sub = "" + it.works.length + " credit" + (it.works.length===1?"":"s");
  if (view === "franchises") sub = it.works.length + " work" + (it.works.length===1?"":"s");

  const fav = isFavorite(type, label);
  const star = `<button class="fav-star ${fav ? "active" : ""}" onclick="toggleFavorite('${type}','${jsStr(label)}', event)" title="Toggle favorite">${fav ? "&#9733;" : "&#9734;"}</button>`;
  const watchBtn = view === "works"
    ? `<button class="watch-check ${isWatched(label) ? "active" : ""}" onclick="toggleWatched('${jsStr(label)}', event)" title="Toggle watched/played">&#10003;</button>`
    : "";
  const detailView = actorsView ? "actors" : view;

  return `<div class="tile" onclick="showDetail('${detailView}','${it.id}')">
    ${star}
    ${watchBtn}
    <div class="tile-badge" style="background:${color}">${esc(initials(label))}</div>
    <div class="tile-body">
      <div class="tile-title">${esc(label)}</div>
      <div class="tile-sub">${sub}</div>
    </div>
  </div>`;
}

function renderListRow(view, it) {
  const color = BADGE_COLOR[view];
  const label = it.name || it.title;
  const actorsView = isActorsView(view);
  const type = favTypeOf(view);
  let meta = "";
  if (actorsView) meta = (it.birth_year ? "b. " + it.birth_year : "b. unknown") + " &middot; " + it.roles.length + " role" + (it.roles.length===1?"":"s");
  if (view === "works") meta = esc(it.media_type) + (it.year ? " &middot; " + it.year : "") + (it.franchise ? " &middot; " + esc(it.franchise) : "");
  if (view === "characters") meta = it.appearances.length + " appearance" + (it.appearances.length===1?"":"s");
  if (view === "studios") meta = "" + it.works.length + " credit" + (it.works.length===1?"":"s");
  if (view === "franchises") meta = it.works.length + " work" + (it.works.length===1?"":"s");

  const fav = isFavorite(type, label);
  const favBtn = `<button class="list-fav ${fav ? "active" : ""}" onclick="toggleFavorite('${type}','${jsStr(label)}', event)" title="Toggle favorite">${fav ? "&#9733;" : "&#9734;"}</button>`;
  let watchBtn = "";
  if (view === "works") {
    const w = isWatched(label);
    watchBtn = `<button class="list-watch ${w ? "active" : ""}" onclick="toggleWatched('${jsStr(label)}', event)" title="Toggle watched/played">&#10003;</button>`;
  }
  const noCast = view === "works" && it.cast.length === 0 ? `<span class="no-cast-badge">no cast yet</span>` : "";
  const detailView = actorsView ? "actors" : view;

  return `<div class="list-row${fav ? " fav-ref" : ""}" onclick="showDetail('${detailView}','${it.id}')">
    <span class="list-dot" style="background:${color}"></span>
    <span class="list-title">${esc(label)}</span>
    ${noCast}
    <span class="list-meta">${meta}</span>
    ${watchBtn}${favBtn}
  </div>`;
}

function findById(view, id) { return listSource(view === "actors" ? "actors" : view).find(x => String(x.id) === String(id)); }
function findByName(view, name) {
  const lname = (name || "").toLowerCase();
  return listSource(view === "actors" ? "actors" : view).find(x =>
    (x.name && x.name.toLowerCase() === lname) || (x.title && x.title.toLowerCase() === lname));
}

function renderVASquares(performances) {
  return `<div class="va-square-row">` + performances.map(p => {
    const fr = favRefBits("actors", p.actor);
    const src = p.source ? ` <a class="source-link" href="${esc(p.source)}" target="_blank" rel="noopener" onclick="event.stopPropagation()" title="${p.verified ? "Source" : "Source (not yet verified)"}">&#128279;</a>` : "";
    const perfType = p.performance_type && p.performance_type !== "Voice" ? ` &middot; ${esc(p.performance_type)}` : "";
    return `<div class="va-square${fr.cls}" onclick="jumpTo('actors','${jsStr(p.actor)}')">
      ${fr.star}${langBadge(p.language)}
      <div class="va-name">${esc(p.actor)}</div>
      <div class="va-roletype">${esc(p.role_type || "")}${perfType}${src}</div>
    </div>`;
  }).join("") + `</div>`;
}

function showDetail(view, id) {
  snapshotScroll();
  const it = findById(view, id);
  const backView = (view === "actors") ? lastActorsTab : view;
  currentView = view;
  currentDetail = { view, id, backView };
  document.querySelectorAll(".navtab").forEach(el => el.classList.toggle("active", el.dataset.view === backView));
  setSearchUI(backView);
  const content = document.getElementById("content");
  let html = `<span class="back-link" onclick="switchTab('${backView}')">&larr; back to ${backView.replace("_en"," (EN)").replace("_ja"," (JA)")}</span>`;

  if (view === "actors") {
    html += `<h2 class="detail-heading">${esc(it.name)}</h2>
      ${favDetailBadge("actors", it.name)}
      <div class="detail-meta">${it.birth_year ? "Born " + it.birth_year : "Birth year unknown"}
      &nbsp; <span class="costars-btn" onclick="queryCostars('${jsStr(it.name)}')">View co-stars</span>
      &nbsp; <span class="costars-btn" onclick="queryCounterparts('${jsStr(it.name)}')">View counterparts</span>
      &nbsp; <span class="costars-btn" onclick="queryConnections('${jsStr(it.name)}')">View connections</span></div>`;
    const roles = it.roles.filter(r => matchesMedia(r.media_type));
    if (roles.length === 0) html += `<div class="empty">No roles match the current media filter.</div>`;
    html += roles.map(r => {
      const fr = favRefBits("works", r.work);
      const src = r.source ? ` <a class="source-link" href="${esc(r.source)}" target="_blank" rel="noopener" title="${r.verified ? "Source" : "Source (not yet verified)"}">&#128279;</a>` : "";
      const perfType = r.performance_type && r.performance_type !== "Voice" ? ` &middot; ${esc(r.performance_type)}` : "";
      return `<div class="detail-row${fr.cls}"><div class="left">${fr.star}<a onclick="jumpTo('characters','${jsStr(r.character)}')">${esc(r.character)}</a> in <a onclick="jumpTo('works','${jsStr(r.work)}')">${esc(r.work)}</a></div>
      <div class="right">${esc(r.media_type||"")} &middot; ${esc(r.role_type||"")}${perfType}${langBadge(r.language)}${src}</div></div>`;
    }).join("");
  } else if (view === "works") {
    html += `<h2 class="detail-heading">${esc(it.title)}${it.year ? " (" + it.year + ")" : ""}</h2>
      ${favDetailBadge("works", it.title)}
      <span class="watch-badge-detail ${isWatched(it.title) ? "active" : ""}" onclick="toggleWatched('${jsStr(it.title)}')">${isWatched(it.title) ? "&#10003; Watched/played" : "&#10003; Mark as watched/played"}</span>`;
    html += `<div class="detail-meta">${esc(it.media_type)}`
      + (it.franchise ? ` &middot; <a onclick="jumpTo('franchises','${jsStr(it.franchise)}')">${esc(it.franchise)}</a> franchise` : "")
      + (it.parent_title ? ` &middot; ${esc(it.relationship_type)} of <a onclick="jumpTo('works','${jsStr(it.parent_title)}')">${esc(it.parent_title)}</a>` : "")
      + `</div>`;
    if (it.studios.length) html += `<div style="margin-bottom:14px;">` + it.studios.map(s => `<span class="tag" onclick="jumpTo('studios','${jsStr(s.name)}')">${esc(s.name)} &middot; ${esc(s.role)}${s.source ? ` <a class="source-link" href="${esc(s.source)}" target="_blank" rel="noopener" onclick="event.stopPropagation()" title="Source">&#128279;</a>` : ""}</span>`).join("") + `</div>`;
    if (it.cast.length === 0) {
      html += `<div class="empty">No cast recorded for this work yet.</div>`;
    } else {
      html += castViewToggleHTML("work");
      const castClass = castViewMode === "grid" ? "appearance-grid" : "appearance-list";
      html += `<div class="${castClass}">` + sortWorkCast(it.cast).map(g => {
        const fr = favRefBits("characters", g.character);
        return `<div class="appearance-block${castViewMode === "grid" ? " grid-card" : ""}">
          <div class="appearance-title${fr.cls}">${fr.star}<a onclick="jumpTo('characters','${jsStr(g.character)}')">${esc(g.character)}</a></div>
          ${renderVASquares(g.performances)}
        </div>`;
      }).join("") + `</div>`;
    }
  } else if (view === "characters") {
    html += `<h2 class="detail-heading">${esc(it.name)}</h2>
      ${favDetailBadge("characters", it.name)}
      <div class="detail-meta">${it.appearances.length} appearance${it.appearances.length===1?"":"s"}</div>`;
    const groups = it.appearances.filter(g => matchesMedia(g.media_type));
    if (groups.length === 0) {
      html += `<div class="empty">No appearances match the current media filter.</div>`;
    } else {
      html += castViewToggleHTML("character");
      const castClass = castViewMode === "grid" ? "appearance-grid" : "appearance-list";
      html += `<div class="${castClass}">` + sortCharacterAppearances(groups).map(g => {
        const fr = favRefBits("works", g.work);
        return `<div class="appearance-block${castViewMode === "grid" ? " grid-card" : ""}">
          <div class="appearance-title${fr.cls}">${fr.star}<a onclick="jumpTo('works','${jsStr(g.work)}')">${esc(g.work)}</a> ${g.work_year ? "("+g.work_year+")" : ""} <span class="tag">${esc(g.media_type)}</span></div>
          ${renderVASquares(g.performances)}
        </div>`;
      }).join("") + `</div>`;
    }
  } else if (view === "studios") {
    html += `<h2 class="detail-heading">${esc(it.name)}</h2>
      ${favDetailBadge("studios", it.name)}
      <div class="detail-meta">${it.works.length} credit${it.works.length===1?"":"s"}</div>`;
    const filtered = it.works.filter(w => matchesMedia(w.media_type));
    if (filtered.length === 0) html += `<div class="empty">No credits match the current media filter.</div>`;
    const byMedia = {};
    for (const w of filtered) (byMedia[w.media_type] = byMedia[w.media_type] || []).push(w);
    html += Object.keys(byMedia).sort().map(mt => {
      const list = byMedia[mt].slice().sort((a, b) => (a.year || 0) - (b.year || 0));
      return `<div class="media-group">
        <div class="media-group-heading">${esc(mt)}</div>
        ${list.map(w => {
          const fr = favRefBits("works", w.title);
          return `<div class="detail-row${fr.cls}"><div class="left">${fr.star}<a onclick="jumpTo('works','${jsStr(w.title)}')">${esc(w.title)}</a> ${w.year ? "("+w.year+")" : ""}</div>
          <div class="right">${esc(w.role)}</div></div>`;
        }).join("")}
      </div>`;
    }).join("");
  } else if (view === "franchises") {
    html += `<h2 class="detail-heading">${esc(it.name)}</h2>
      ${favDetailBadge("franchises", it.name)}
      <div class="detail-meta">${it.works.length} works</div>`;
    const filtered = it.works.filter(w => matchesMedia(w.media_type));
    if (filtered.length === 0) html += `<div class="empty">No works match the current media filter.</div>`;
    html += filtered.map(w => {
      const fr = favRefBits("works", w.title);
      return `<div class="detail-row${fr.cls}"><div class="left">${fr.star}<a onclick="jumpTo('works','${jsStr(w.title)}')">${esc(w.title)}</a> ${w.year ? "("+w.year+")" : ""}</div>
      <div class="right">${w.parent_title ? esc(w.relationship_type) + " of " + esc(w.parent_title) : esc(w.media_type)}</div></div>`;
    }).join("");
  }
  content.innerHTML = html;
  syncHash();
}

function jumpTo(view, name) {
  const it = findByName(view, name);
  if (!it) return;
  showDetail(view, it.id);
}

// -------------------------
// Shareable URLs: the current tab/detail/query/compare state is mirrored
// into location.hash so pages can be bookmarked or shared, and the
// browser's back/forward buttons navigate between visited states.
// -------------------------
function snapshotScroll() {
  // Stamps the scroll position of the page we're about to LEAVE onto its
  // own history entry, so that navigating back can restore it. Called at
  // the top of every function that's about to replace #content.
  try {
    const el = document.getElementById("content");
    history.replaceState({ ...(history.state || {}), scrollTop: el ? el.scrollTop : 0 }, "", location.hash);
  } catch (e) { /* pushState/replaceState can throw on some file:// setups -- degrade gracefully */ }
}

function computeHash() {
  if (currentDetail) {
    const it = findById(currentDetail.view, currentDetail.id);
    const label = it ? (it.name || it.title || "") : "";
    return "#" + currentDetail.view + "/" + encodeURIComponent(label);
  }
  if (currentView === "costars" || currentView === "counterparts" || currentView === "connections") {
    const val = document.getElementById("search").value.trim();
    return "#" + currentView + (val ? "/" + encodeURIComponent(val) : "");
  }
  if (currentView === "compare") {
    const items = Array.from(document.querySelectorAll(".compare-item")).map(i => i.value.trim()).filter(Boolean);
    return "#compare" + (items.length ? "/" + items.map(encodeURIComponent).join("|") : "");
  }
  return "#" + currentView;
}

function syncHash() {
  const h = computeHash();
  const state = { visibleCount };
  if (location.hash === h) {
    // Same page (e.g. pagination grew) -- keep the entry but refresh its state.
    try { history.replaceState(state, "", h); } catch (e) {}
    return;
  }
  if (suppressPush) {
    history.replaceState(state, "", h);
  } else {
    history.pushState(state, "", h);
  }
}

function applyHash() {
  const h = location.hash.slice(1); // still URI-encoded
  if (!h) { switchTab("actors_en"); return; }
  const slashIdx = h.indexOf("/");
  const view = slashIdx === -1 ? h : h.slice(0, slashIdx);
  const restRaw = slashIdx === -1 ? "" : h.slice(slashIdx + 1);

  if (["actors", "works", "characters", "studios", "franchises"].includes(view) && restRaw) {
    const it = findByName(view, decodeURIComponent(restRaw));
    if (it) { showDetail(view, it.id); return; }
  }
  if (["actors_en", "actors_ja", "works", "characters", "studios", "franchises", "costars", "counterparts", "connections", "compare", "stats", "todo"].includes(view)) {
    switchTab(view);
    if (view === "costars" && restRaw) {
      const name = decodeURIComponent(restRaw);
      document.getElementById("search").value = name;
      runCostarsQuery(name);
    } else if (view === "counterparts" && restRaw) {
      const name = decodeURIComponent(restRaw);
      document.getElementById("search").value = name;
      runCounterpartsQuery(name);
    } else if (view === "connections" && restRaw) {
      const name = decodeURIComponent(restRaw);
      document.getElementById("search").value = name;
      runConnectionsQuery(name);
    } else if (view === "compare" && restRaw) {
      const items = restRaw.split("|").map(decodeURIComponent).filter(Boolean);
      const rowsDiv = document.getElementById("compareRows");
      rowsDiv.innerHTML = items.map(() => `<div class="compare-row"><input type="text" class="compare-item" placeholder="Franchise or work title"></div>`).join("");
      const inputs = rowsDiv.querySelectorAll(".compare-item");
      items.forEach((val, i) => { if (inputs[i]) inputs[i].value = val; });
      if (items.length < 2) addCompareRow();
      runCompare();
    }
    return;
  }
  switchTab("actors_en");
}

// -------------------------
// Co-stars (mirrors `python scripts/query.py costars "<name>"`, case-insensitive)
// -------------------------
function showCostarsPrompt() {
  document.getElementById("content").innerHTML = `<div class="empty">Type an actor's name above (any case) and press Search (or Enter) to see everyone they've shared a work with -- including which characters were involved.</div>`;
}

function computeCostars(actorName) {
  const actor = findByName("actors", actorName);
  if (!actor) return null;

  const map = new Map();
  for (const role of actor.roles) {
    if (!matchesMedia(role.media_type)) continue;
    const work = findByName("works", role.work);
    if (!work) continue;
    for (const g of work.cast) {
      for (const p of g.performances) {
        if (p.actor === actor.name) continue;
        const key = p.actor + "|" + g.character + "|" + work.title + "|" + p.language;
        if (!map.has(key)) {
          map.set(key, {
            costar: p.actor, costarCharacter: g.character, costarLanguage: p.language,
            work: work.title, year: work.year, myCharacters: new Set(),
            sameLanguage: (p.language || "") === (role.language || ""),
          });
        }
        map.get(key).myCharacters.add(role.character);
      }
    }
  }
  const results = Array.from(map.values()).map(r => ({ ...r, myCharacters: Array.from(r.myCharacters).join(", ") }));
  results.sort((a, b) => (a.year || 0) - (b.year || 0) || a.costar.localeCompare(b.costar));
  return {
    actor,
    sameLanguage: results.filter(r => r.sameLanguage),
    otherLanguage: results.filter(r => !r.sameLanguage),
  };
}

function queryCostars(actorName) {
  switchTab("costars");
  document.getElementById("search").value = actorName;
  runCostarsQuery(actorName);
}

function renderCostarRows(results) {
  return results.map(r => {
    const frActor = favRefBits("actors", r.costar);
    const frWork = favRefBits("works", r.work);
    const cls = frActor.cls || frWork.cls;
    return `<div class="detail-row${cls}"><div class="left">${frActor.star}<a onclick="jumpTo('actors','${jsStr(r.costar)}')">${esc(r.costar)}</a>${langBadge(r.costarLanguage, true)} as ${esc(r.costarCharacter)}</div>
    <div class="right">as ${esc(r.myCharacters)} in <a onclick="jumpTo('works','${jsStr(r.work)}')">${esc(r.work)}</a> ${r.year ? "("+r.year+")" : ""}</div></div>`;
  }).join("");
}

function runCostarsQuery(actorName) {
  snapshotScroll();
  const content = document.getElementById("content");
  const found = computeCostars(actorName);
  if (!found) {
    content.innerHTML = `<div class="empty">No actor found matching "${esc(actorName)}".</div>`;
    return;
  }
  const total = found.sameLanguage.length + found.otherLanguage.length;
  if (total === 0) {
    content.innerHTML = `<div class="empty">${esc(found.actor.name)} has no shared works with anyone else matching the current media filter.</div>`;
    return;
  }
  let html = `<h2 class="detail-heading">Co-stars of ${esc(found.actor.name)}</h2>
    <div class="detail-meta">${total} shared credit${total===1?"":"s"} &middot; <a onclick="queryCounterparts('${jsStr(found.actor.name)}')">view exact counterparts instead</a> &middot; <a onclick="queryConnections('${jsStr(found.actor.name)}')">view as a connections graph</a></div>`;
  html += `<div class="appearance-title">Co-starred with (same dub)</div>`;
  html += found.sameLanguage.length
    ? renderCostarRows(found.sameLanguage)
    : `<div class="empty">No same-dub co-stars matching the current media filter.</div>`;
  html += `<div class="appearance-title" style="margin-top:20px;">Cast in the other language version</div>`;
  html += found.otherLanguage.length
    ? renderCostarRows(found.otherLanguage)
    : `<div class="empty">No other-language cast matching the current media filter.</div>`;
  content.innerHTML = html;
  syncHash();
}

// -------------------------
// Counterparts: who played the SAME character in the other language,
// for each of this actor's roles (a precise subset of "other-language cast").
// -------------------------
function showCounterpartsPrompt() {
  document.getElementById("content").innerHTML = `<div class="empty">Type an actor's name above (any case) and press Search (or Enter) to see who played their exact same characters in the other language.</div>`;
}

function computeCounterparts(actorName) {
  const actor = findByName("actors", actorName);
  if (!actor) return null;

  const results = [];
  for (const role of actor.roles) {
    if (!matchesMedia(role.media_type)) continue;
    const work = findByName("works", role.work);
    if (!work) continue;
    const group = work.cast.find(g => g.character_id === role.character_id);
    if (!group) continue;
    for (const p of group.performances) {
      if (p.actor === actor.name) continue;
      results.push({
        character: role.character, work: work.title, year: work.year,
        myLanguage: role.language, counterpart: p.actor, counterpartLanguage: p.language,
      });
    }
  }
  results.sort((a, b) => (a.year || 0) - (b.year || 0) || a.character.localeCompare(b.character));
  return { actor, results };
}

function queryCounterparts(actorName) {
  switchTab("counterparts");
  document.getElementById("search").value = actorName;
  runCounterpartsQuery(actorName);
}

function runCounterpartsQuery(actorName) {
  snapshotScroll();
  const content = document.getElementById("content");
  const found = computeCounterparts(actorName);
  if (!found) {
    content.innerHTML = `<div class="empty">No actor found matching "${esc(actorName)}".</div>`;
    return;
  }
  if (found.results.length === 0) {
    content.innerHTML = `<div class="empty">${esc(found.actor.name)} has no other-language counterparts recorded yet matching the current media filter.</div>`;
    return;
  }
  let html = `<h2 class="detail-heading">Counterparts of ${esc(found.actor.name)}</h2>
    <div class="detail-meta">${found.results.length} role${found.results.length===1?"":"s"} with a counterpart on record</div>`;
  html += found.results.map(r => {
    const fr = favRefBits("actors", r.counterpart);
    return `<div class="detail-row${fr.cls}"><div class="left"><a onclick="jumpTo('characters','${jsStr(r.character)}')">${esc(r.character)}</a> in <a onclick="jumpTo('works','${jsStr(r.work)}')">${esc(r.work)}</a> ${r.year ? "("+r.year+")" : ""}</div>
    <div class="right">${fr.star}${langBadge(r.myLanguage, true)}&rarr;<a onclick="jumpTo('actors','${jsStr(r.counterpart)}')">${esc(r.counterpart)}</a>${langBadge(r.counterpartLanguage, true)}</div></div>`;
  }).join("");
  content.innerHTML = html;
  syncHash();
}

// -------------------------
// Stats: a snapshot of the whole database, ignoring the current media filter
// -------------------------
function computeStats() {
  const stats = {};
  stats.totals = {
    Actors: DATA.actors.length, Works: DATA.works.length, Characters: DATA.characters.length,
    Studios: DATA.studios.length, Franchises: DATA.franchises.length,
    Performances: DATA.actors.reduce((sum, a) => sum + a.roles.length, 0),
  };

  stats.topActorsEn = DATA.actors_en.slice().sort((a, b) => b.roles.length - a.roles.length).slice(0, 10);
  stats.topActorsJa = DATA.actors_ja.slice().sort((a, b) => b.roles.length - a.roles.length).slice(0, 10);

  const enSet = new Set(DATA.actors_en.map(a => a.name));
  const jaSet = new Set(DATA.actors_ja.map(a => a.name));
  let both = 0;
  for (const n of enSet) if (jaSet.has(n)) both++;
  stats.langSplit = { enOnly: enSet.size - both, jaOnly: jaSet.size - both, both };

  const byDecade = {};
  for (const w of DATA.works) {
    if (w.year == null) continue;
    const decade = Math.floor(w.year / 10) * 10;
    byDecade[decade] = (byDecade[decade] || 0) + 1;
  }
  stats.byDecade = Object.keys(byDecade).map(d => ({ decade: +d, count: byDecade[d] })).sort((a, b) => a.decade - b.decade);

  stats.topStudios = DATA.studios.slice().sort((a, b) => b.works.length - a.works.length).slice(0, 8);
  stats.topFranchises = DATA.franchises.slice().sort((a, b) => b.works.length - a.works.length).slice(0, 8);

  let maxActor = null, maxCount = -1;
  for (const a of DATA.actors) {
    const c = computeCostars(a.name);
    if (!c) continue;
    const total = c.sameLanguage.length + c.otherLanguage.length;
    if (total > maxCount) { maxCount = total; maxActor = a.name; }
  }
  stats.mostConnected = { actor: maxActor, count: maxCount };

  return stats;
}

// -------------------------
// Needs work -- to-do list of thin / unverified corners of the dataset
// -------------------------

function computeTodo() {
  const perfs = (w) => (w.cast || []).flatMap(g => g.performances);
  const plural = (n, s) => n + " " + s + (n === 1 ? "" : "s");
  const wk = (w) => ({ view: "works", name: w.title, label: w.title + (w.year ? " (" + w.year + ")" : "") });
  const withCount = (arr, key, label) => arr.map(w => ({ w, n: key(w) })).filter(x => x.n > 0).sort((a, b) => b.n - a.n)
    .map(x => ({ ...wk(x.w), note: x.n + " " + label }));
  const thisYear = new Date().getFullYear();
  const langs = (w) => new Set(perfs(w).map(p => (p.language || "").toLowerCase()).filter(Boolean));
  return [
    { title: "Works with no cast yet", hint: "Added, but no credits recorded.",
      items: DATA.works.filter(w => !(w.cast || []).length).map(wk) },
    { title: "Unverified credits", hint: "Credits whose source page hasn't been read and confirmed. Works with the most first.",
      items: withCount(DATA.works, w => perfs(w).filter(p => !p.verified).length, "unverified") },
    { title: "Credits with no source link", hint: "No URL at all.",
      items: withCount(DATA.works, w => perfs(w).filter(p => !p.source).length, "without a source") },
    { title: "Works with no studio", hint: "No developer, publisher or animation studio recorded (unsourced studio credits are not kept).",
      items: DATA.works.filter(w => !(w.studios || []).length).map(wk) },
    { title: "Studio credits with no source", hint: "Should be empty: studio credits are only kept with a source.",
      items: DATA.works.filter(w => (w.studios || []).some(s => !s.source)).map(wk) },
    { title: "Thin casts (under 10 characters)", hint: "Only a few roles recorded; likely missing side cast.",
      items: DATA.works.filter(w => (w.cast || []).length > 0 && w.cast.length < 10).sort((a, b) => a.cast.length - b.cast.length)
        .map(w => ({ ...wk(w), note: plural(w.cast.length, "character") })) },
    { title: "Only one language track", hint: "Check whether an English dub or Japanese original is missing (Japanese-only games may be correct).",
      items: DATA.works.filter(w => (w.cast || []).length > 0 && langs(w).size === 1 && ["Anime", "Video Game", "Movie", "OVA"].includes(w.media_type))
        .map(w => ({ ...wk(w), note: Array.from(langs(w))[0] + " only" })) },
    { title: "Not released yet", hint: "Credits may change before release.",
      items: DATA.works.filter(w => w.year && w.year > thisYear).map(w => ({ ...wk(w), note: "" + w.year })) },
    { title: "Works with no franchise", hint: "Fine for standalone titles; check the series ones.",
      items: DATA.works.filter(w => !w.franchise).map(wk) },
    { title: "Actors missing a birth year", hint: "Most-credited first.",
      items: DATA.actors.filter(a => !a.birth_year).sort((a, b) => b.roles.length - a.roles.length)
        .map(a => ({ view: "actors", name: a.name, label: a.name, note: plural(a.roles.length, "role") })) },
    { title: "Japanese actors missing a native name", hint: "Add the kanji/kana name. Most-credited first.",
      items: DATA.actors_ja.filter(a => !a.native_name).sort((a, b) => b.roles.length - a.roles.length)
        .map(a => ({ view: "actors", name: a.name, label: a.name, note: plural(a.roles.length, "role") })) },
  ];
}

function showTodo() {
  const sections = computeTodo();
  const LIMIT = 25;
  let html = `<h2 class="detail-heading">Needs work</h2><div class="detail-meta">Gaps in the data, worst first. Click an entry to open it.</div>`;
  for (const s of sections) {
    html += `<div class="stats-section"><h3>${esc(s.title)} <span class="tile-sub">(${s.items.length})</span></h3>
      <div class="detail-meta" style="margin-bottom:6px;">${esc(s.hint)}</div>`;
    if (!s.items.length) {
      html += `<div class="tile-sub">Nothing to do here.</div>`;
    } else {
      html += s.items.slice(0, LIMIT).map(it =>
        `<div class="stats-row"><a onclick="jumpTo('${it.view}','${jsStr(it.name)}')">${esc(it.label)}</a>${it.note ? ` <span class="tile-sub">&middot; ${esc(it.note)}</span>` : ""}</div>`
      ).join("");
      if (s.items.length > LIMIT) html += `<div class="tile-sub">&hellip;and ${s.items.length - LIMIT} more</div>`;
    }
    html += `</div>`;
  }
  document.getElementById("content").innerHTML = html;
  document.getElementById("searchhint").textContent = "";
}

function showStats() {
  const savedFilter = mediaFilter;
  mediaFilter = "all"; // stats always reflect the whole database
  const stats = computeStats();
  mediaFilter = savedFilter;

  let html = `<h2 class="detail-heading">Stats &amp; Insights</h2><div class="detail-meta">A snapshot of the whole database (ignores the media filter).</div>`;

  html += `<div class="stats-grid">` + Object.keys(stats.totals).map(label =>
    `<div class="stat-card"><div class="stat-value">${stats.totals[label]}</div><div class="stat-label">${esc(label)}</div></div>`
  ).join("") + `</div>`;

  if (stats.mostConnected.actor) {
    html += `<div class="stats-callout">Most-connected actor: <a onclick="jumpTo('actors','${jsStr(stats.mostConnected.actor)}')">${esc(stats.mostConnected.actor)}</a> shares a work with <strong>${stats.mostConnected.count}</strong> other actor credit${stats.mostConnected.count === 1 ? "" : "s"} across the database.</div>`;
  }

  html += `<div class="stats-section"><h3>Language overlap</h3><div class="detail-meta" style="margin-bottom:0;">${stats.langSplit.enOnly} English-only &middot; ${stats.langSplit.jaOnly} Japanese-only &middot; ${stats.langSplit.both} actor${stats.langSplit.both === 1 ? "" : "s"} with roles in both languages</div></div>`;

  html += `<div class="stats-section"><h3>Most prolific actors</h3><div class="stats-columns">
    <div><div class="tile-sub" style="margin-bottom:6px;">English</div>${stats.topActorsEn.map(a =>
      `<div class="detail-row"><div class="left"><a onclick="jumpTo('actors','${jsStr(a.name)}')">${esc(a.name)}</a></div><div class="right">${a.roles.length} role${a.roles.length === 1 ? "" : "s"}</div></div>`
    ).join("")}</div>
    <div><div class="tile-sub" style="margin-bottom:6px;">Japanese</div>${stats.topActorsJa.map(a =>
      `<div class="detail-row"><div class="left"><a onclick="jumpTo('actors','${jsStr(a.name)}')">${esc(a.name)}</a></div><div class="right">${a.roles.length} role${a.roles.length === 1 ? "" : "s"}</div></div>`
    ).join("")}</div>
  </div></div>`;

  const maxDecadeCount = Math.max(1, ...stats.byDecade.map(d => d.count));
  html += `<div class="stats-section"><h3>Works by decade</h3>` + stats.byDecade.map(d =>
    `<div class="bar-row"><div class="bar-label">${d.decade}s</div><div class="bar-track"><div class="bar-fill" style="width:${Math.round(d.count / maxDecadeCount * 100)}%"></div></div><div class="bar-count">${d.count}</div></div>`
  ).join("") + `</div>`;

  html += `<div class="stats-section"><h3>Top studios &amp; franchises</h3><div class="stats-columns">
    <div>${stats.topStudios.map(s =>
      `<div class="detail-row"><div class="left"><a onclick="jumpTo('studios','${jsStr(s.name)}')">${esc(s.name)}</a></div><div class="right">${s.works.length} credit${s.works.length === 1 ? "" : "s"}</div></div>`
    ).join("")}</div>
    <div>${stats.topFranchises.map(f =>
      `<div class="detail-row"><div class="left"><a onclick="jumpTo('franchises','${jsStr(f.name)}')">${esc(f.name)}</a></div><div class="right">${f.works.length} work${f.works.length === 1 ? "" : "s"}</div></div>`
    ).join("")}</div>
  </div></div>`;

  document.getElementById("content").innerHTML = html;
}

// -------------------------
// Connections: the co-star network around one actor, drawn as a small
// radial graph (center = the actor, surrounding nodes = distinct
// co-stars sized/weighted by number of shared credits).
// -------------------------
function showConnectionsPrompt() {
  document.getElementById("content").innerHTML = `<div class="empty">Type an actor's name above (any case) and press Search (or Enter) to see their co-star network as a graph.</div>`;
}

function computeConnections(actorName) {
  const found = computeCostars(actorName);
  if (!found) return null;
  const all = [...found.sameLanguage, ...found.otherLanguage];
  const map = new Map();
  for (const r of all) {
    if (!map.has(r.costar)) map.set(r.costar, { name: r.costar, weight: 0, language: r.costarLanguage });
    map.get(r.costar).weight++;
  }
  const nodes = Array.from(map.values()).sort((a, b) => b.weight - a.weight || a.name.localeCompare(b.name));
  return { actor: found.actor, nodes };
}

function renderConnectionsGraph(found) {
  const TOP_N = 40;
  const shown = found.nodes.slice(0, TOP_N);
  const cx = 320, cy = 320, radius = 250;
  const maxW = shown[0].weight;
  const minW = shown[shown.length - 1].weight;
  const spread = Math.max(1, maxW - minW);
  const nodeR = w => 8 + (w - minW) / spread * 14;

  let svg = `<svg class="connections-graph" viewBox="0 0 640 640" style="width:100%;max-width:640px;display:block;margin:0 auto;">`;
  shown.forEach((n, i) => {
    const angle = (i / shown.length) * 2 * Math.PI - Math.PI / 2;
    n._x = cx + radius * Math.cos(angle);
    n._y = cy + radius * Math.sin(angle);
    const opacity = 0.15 + (n.weight - minW) / spread * 0.55;
    svg += `<line x1="${cx}" y1="${cy}" x2="${n._x}" y2="${n._y}" stroke="var(--border)" stroke-width="${(1 + n.weight / maxW * 3).toFixed(1)}" opacity="${opacity.toFixed(2)}" />`;
  });
  svg += `<circle cx="${cx}" cy="${cy}" r="22" fill="var(--accent)" />`;
  svg += `<text x="${cx}" y="${cy + 40}" text-anchor="middle" font-size="13" fill="var(--text)" font-weight="700">${esc(found.actor.name)}</text>`;
  shown.forEach(n => {
    const r = nodeR(n.weight);
    const fav = isFavorite("actors", n.name);
    const color = LANG_COLOR[(n.language || "").toLowerCase()] || "var(--lang-other)";
    const label = n.name.length > 16 ? n.name.slice(0, 15) + "." : n.name;
    svg += `<g style="cursor:pointer;" onclick="jumpTo('actors','${jsStr(n.name)}')">
      <circle cx="${n._x}" cy="${n._y}" r="${r.toFixed(1)}" fill="${color}" stroke="${fav ? "var(--star)" : "var(--panel)"}" stroke-width="${fav ? 3 : 1.5}" />
      <text x="${n._x}" y="${n._y + r + 13}" text-anchor="middle" font-size="10.5" fill="var(--text-dim)">${esc(label)}</text>
    </g>`;
  });
  svg += `</svg>`;
  return svg;
}

function queryConnections(actorName) {
  switchTab("connections");
  document.getElementById("search").value = actorName;
  runConnectionsQuery(actorName);
}

function runConnectionsQuery(actorName) {
  snapshotScroll();
  const content = document.getElementById("content");
  const found = computeConnections(actorName);
  if (!found) {
    content.innerHTML = `<div class="empty">No actor found matching "${esc(actorName)}".</div>`;
    return;
  }
  if (found.nodes.length === 0) {
    content.innerHTML = `<div class="empty">${esc(found.actor.name)} has no co-stars matching the current media filter.</div>`;
    return;
  }
  const note = found.nodes.length > 40
    ? `Showing the top 40 of ${found.nodes.length} co-stars, by number of shared credits.`
    : `${found.nodes.length} co-star${found.nodes.length === 1 ? "" : "s"}, sized by number of shared credits.`;
  let html = `<h2 class="detail-heading">Connections for ${esc(found.actor.name)}</h2><div class="detail-meta">${note}</div>`;
  html += renderConnectionsGraph(found);
  content.innerHTML = html;
  syncHash();
}

// -------------------------
// Compare: "who has been in both/all of these franchises or works" (case-insensitive)
// -------------------------
function showCompareUI() {
  document.getElementById("content").innerHTML = `
    <div class="compare-intro">List two or more franchises and/or exact work titles (any case), then find every actor who has a role in all of them.</div>
    <div id="compareRows">
      <div class="compare-row"><input type="text" class="compare-item" placeholder="Franchise or work title, e.g. Persona"></div>
      <div class="compare-row"><input type="text" class="compare-item" placeholder="Franchise or work title, e.g. Danganronpa"></div>
    </div>
    <div class="compare-actions">
      <button onclick="addCompareRow()">+ Add another</button>
      <button class="primary" onclick="runCompare()">Find shared actors</button>
    </div>
    <div id="compareResults"></div>
  `;
}

function addCompareRow() {
  const rows = document.getElementById("compareRows");
  const div = document.createElement("div");
  div.className = "compare-row";
  div.innerHTML = `<input type="text" class="compare-item" placeholder="Franchise or work title">`;
  rows.appendChild(div);
}

function resolveCompareItem(text) {
  const t = text.trim().toLowerCase();
  const franchise = DATA.franchises.find(f => f.name.toLowerCase() === t);
  if (franchise) {
    const workTitles = new Set(franchise.works.map(w => w.title));
    const matches = new Map();
    for (const a of DATA.actors) {
      const hits = a.roles.filter(r => workTitles.has(r.work));
      if (hits.length) matches.set(a.name, hits);
    }
    return { label: franchise.name, type: "franchise", matches };
  }
  const work = DATA.works.find(w => w.title.toLowerCase() === t);
  if (work) {
    const matches = new Map();
    for (const a of DATA.actors) {
      const hits = a.roles.filter(r => r.work_id === work.id);
      if (hits.length) matches.set(a.name, hits);
    }
    return { label: work.title, type: "work", matches };
  }
  return { label: text.trim(), type: "unknown", matches: null };
}

function runCompare() {
  const inputs = Array.from(document.querySelectorAll(".compare-item")).map(i => i.value.trim()).filter(Boolean);
  const results = document.getElementById("compareResults");
  if (inputs.length < 2) {
    results.innerHTML = `<div class="empty">Enter at least two franchises or works to compare.</div>`;
    return;
  }
  const resolved = inputs.map(resolveCompareItem);
  const unknown = resolved.filter(r => r.type === "unknown");
  if (unknown.length) {
    results.innerHTML = `<div class="empty">No exact franchise or work match for: ${unknown.map(u => esc(u.label)).join(", ")}.</div>`;
    return;
  }
  let shared = new Set(resolved[0].matches.keys());
  for (const r of resolved.slice(1)) {
    shared = new Set([...shared].filter(name => r.matches.has(name)));
  }
  if (shared.size === 0) {
    results.innerHTML = `<div class="empty">No actor appears in all of: ${resolved.map(r => esc(r.label)).join(", ")}.</div>`;
    return;
  }
  let html = `<h2 class="detail-heading">Shared actors</h2><div class="detail-meta">${shared.size} actor${shared.size===1?"":"s"} in all of: ${resolved.map(r => esc(r.label)).join(" + ")}</div>`;
  html += Array.from(shared).sort().map(name => {
    const lang = resolved[0].matches.get(name)[0].language;
    const fr = favRefBits("actors", name);
    const perItem = resolved.map(r => {
      const hits = r.matches.get(name);
      const characters = [...new Set(hits.map(h => h.character))].join(", ");
      return `<a onclick="jumpTo('works','${jsStr(hits[0].work)}')">${esc(r.label)}</a>: ${esc(characters)}`;
    }).join(" &middot; ");
    return `<div class="detail-row${fr.cls}"><div class="left">${fr.star}<a onclick="jumpTo('actors','${jsStr(name)}')">${esc(name)}</a>${langBadge(lang, true)}</div><div class="right">${perItem}</div></div>`;
  }).join("");
  results.innerHTML = html;
  syncHash();
}

// -------------------------
// Search bar: live filter for browse tabs, direct query (Enter/button) for all
// -------------------------
function runQuery() {
  const value = document.getElementById("search").value.trim();
  if (!value) return;
  if (currentView === "costars") {
    runCostarsQuery(value);
    return;
  }
  if (currentView === "counterparts") {
    runCounterpartsQuery(value);
    return;
  }
  if (currentView === "connections") {
    runConnectionsQuery(value);
    return;
  }
  const exact = findByName(currentView, value);
  if (exact) {
    const detailView = isActorsView(currentView) ? "actors" : currentView;
    showDetail(detailView, exact.id);
  } else {
    showList(currentView, value.toLowerCase());
  }
}

document.querySelectorAll(".navtab").forEach(el => el.addEventListener("click", () => switchTab(el.dataset.view)));

document.getElementById("search").addEventListener("input", e => {
  if (currentView === "costars" || currentView === "counterparts" || currentView === "connections" || currentView === "compare" || currentDetail) return;
  showList(currentView, e.target.value.trim().toLowerCase());
});
document.getElementById("search").addEventListener("keydown", e => {
  if (e.key === "Enter") runQuery();
});
document.getElementById("favOnly").addEventListener("change", () => {
  showList(currentView, document.getElementById("search").value.trim().toLowerCase());
});
document.getElementById("watchedOnly").addEventListener("change", () => {
  showList(currentView, document.getElementById("search").value.trim().toLowerCase());
});
document.getElementById("mediaFilter").addEventListener("change", e => {
  mediaFilter = e.target.value;
  if (currentDetail) {
    showDetail(currentDetail.view, currentDetail.id);
  } else if (currentView === "costars") {
    const v = document.getElementById("search").value.trim();
    if (v) runCostarsQuery(v);
  } else if (currentView === "counterparts") {
    const v = document.getElementById("search").value.trim();
    if (v) runCounterpartsQuery(v);
  } else if (currentView === "connections") {
    const v = document.getElementById("search").value.trim();
    if (v) runConnectionsQuery(v);
  } else if (currentView !== "compare" && currentView !== "stats" && currentView !== "todo") {
    showList(currentView, document.getElementById("search").value.trim().toLowerCase());
  }
});
document.getElementById("sortSelect").addEventListener("change", e => {
  currentSort = e.target.value;
  if (!currentDetail && currentView !== "costars" && currentView !== "counterparts" && currentView !== "compare") {
    showList(currentView, document.getElementById("search").value.trim().toLowerCase());
  }
});

window.addEventListener("popstate", (event) => {
  suppressPush = true;
  if (event.state && typeof event.state.visibleCount === "number") visibleCount = event.state.visibleCount;
  applyHash();
  if (event.state && typeof event.state.scrollTop === "number") {
    const el = document.getElementById("content");
    if (el) el.scrollTop = event.state.scrollTop;
  }
  suppressPush = false;
});

populateFilters();
setCounts();
suppressPush = true;
if (location.hash) {
  applyHash();
} else {
  switchTab("actors_en");
}
suppressPush = false;
