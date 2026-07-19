"""
Generates database/dashboard.html -- a self-contained, offline GUI for
browsing the actor_db database. No server needed; just open the file in
any browser. Unlike a raw table viewer, this shows joined/human-readable
views (actor -> their roles with character/work names, not bare IDs) and
lets you click between actors, works, characters, studios, and franchises,
letterboxd-style grid browsing, English/Japanese actor pages, a media-type
filter (grouped by medium in the Studios tab), a BTVA-style side-by-side
cast layout on Work/Character pages, favorite actors (saved in the browser
via localStorage), a Co-stars tab, and a Compare tab for "who's been in
both of these franchises/works" queries.

Re-run this any time after re-importing data:
    python scripts/generate_dashboard.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import connect

OUTPUT_PATH = Path("database/dashboard.html")


def build_data():
    conn = connect()
    cur = conn.cursor()

    actors = {}
    for actor_id, name, birth_year in cur.execute(
        "SELECT actor_id, name, birth_year FROM Actors ORDER BY name"
    ):
        actors[actor_id] = {"id": actor_id, "name": name, "birth_year": birth_year, "roles": []}

    works = {}
    for row in cur.execute("""
        SELECT w.work_id, w.title, w.release_year, w.media_type,
               f.name, pw.title, w.work_relationship_type
        FROM Works w
        LEFT JOIN Franchises f ON w.franchise_id = f.franchise_id
        LEFT JOIN Works pw ON w.parent_work_id = pw.work_id
        ORDER BY w.title
    """):
        work_id, title, year, media_type, franchise, parent_title, rel_type = row
        works[work_id] = {
            "id": work_id, "title": title, "year": year, "media_type": media_type,
            "franchise": franchise, "parent_title": parent_title, "relationship_type": rel_type,
            "studios": [], "cast": [],
        }

    for work_id, studio_name, studio_role in cur.execute("""
        SELECT ws.work_id, s.name, ws.studio_role
        FROM WorkStudios ws JOIN Studios s ON ws.studio_id = s.studio_id
        ORDER BY s.name
    """):
        works[work_id]["studios"].append({"name": studio_name, "role": studio_role})

    characters = {}
    for char_id, name in cur.execute(
        "SELECT character_id, canonical_name FROM Characters ORDER BY canonical_name"
    ):
        characters[char_id] = {"id": char_id, "name": name, "appearances": []}

    studios = {}
    for studio_id, name, country in cur.execute(
        "SELECT studio_id, name, country FROM Studios ORDER BY name"
    ):
        studios[studio_id] = {"id": studio_id, "name": name, "country": country, "works": []}
    for studio_id, work_id, studio_role in cur.execute("SELECT studio_id, work_id, studio_role FROM WorkStudios"):
        w = works[work_id]
        studios[studio_id]["works"].append({
            "title": w["title"], "year": w["year"], "media_type": w["media_type"], "role": studio_role,
        })

    franchises = {}
    for franchise_id, name in cur.execute("SELECT franchise_id, name FROM Franchises ORDER BY name"):
        franchises[franchise_id] = {"id": franchise_id, "name": name, "works": []}
    for row in cur.execute("""
        SELECT w.franchise_id, w.title, w.release_year, w.media_type, pw.title, w.work_relationship_type
        FROM Works w LEFT JOIN Works pw ON w.parent_work_id = pw.work_id
        WHERE w.franchise_id IS NOT NULL
        ORDER BY w.release_year
    """):
        franchise_id, title, year, media_type, parent_title, rel_type = row
        franchises[franchise_id]["works"].append({
            "title": title, "year": year, "media_type": media_type,
            "parent_title": parent_title, "relationship_type": rel_type,
        })

    # Performances tie everything together. Cast/appearances are grouped so
    # that an English + Japanese performance of the same role in the same
    # work count as ONE appearance/cast slot, not two -- with both actors
    # shown side by side within it.
    work_cast_groups = {}    # work_id -> {character_id: group}
    char_appear_groups = {}  # character_id -> {work_id: group}

    for row in cur.execute("""
        SELECT p.actor_id, ca.work_id, c.character_id, c.canonical_name,
               l.name, p.role_type, p.performance_type
        FROM Performances p
        JOIN CharacterAppearances ca ON p.appearance_id = ca.appearance_id
        JOIN Characters c ON ca.character_id = c.character_id
        LEFT JOIN Languages l ON p.language_id = l.language_id
    """):
        actor_id, work_id, char_id, char_name, lang, role_type, perf_type = row
        w = works[work_id]
        a = actors[actor_id]

        perf_entry = {
            "actor": a["name"], "actor_id": actor_id, "language": lang,
            "role_type": role_type, "performance_type": perf_type,
        }

        a["roles"].append({
            "character": char_name, "character_id": char_id, "work": w["title"], "work_id": work_id,
            "work_year": w["year"], "media_type": w["media_type"], "language": lang,
            "role_type": role_type, "performance_type": perf_type,
        })

        wc = work_cast_groups.setdefault(work_id, {})
        cg = wc.setdefault(char_id, {"character": char_name, "character_id": char_id, "performances": []})
        cg["performances"].append(perf_entry)

        cag = char_appear_groups.setdefault(char_id, {})
        wg = cag.setdefault(work_id, {
            "work": w["title"], "work_id": work_id, "work_year": w["year"], "media_type": w["media_type"],
            "performances": [],
        })
        wg["performances"].append(perf_entry)

    for work_id, groups in work_cast_groups.items():
        works[work_id]["cast"] = sorted(groups.values(), key=lambda g: g["character"])

    for char_id, groups in char_appear_groups.items():
        characters[char_id]["appearances"] = sorted(groups.values(), key=lambda g: (g["work_year"] or 0))

    languages = [r[0] for r in cur.execute("SELECT name FROM Languages ORDER BY name")]
    media_types = [r[0] for r in cur.execute("SELECT DISTINCT media_type FROM Works ORDER BY media_type")]
    conn.close()

    return {
        "actors": sorted(actors.values(), key=lambda x: x["name"]),
        "works": sorted(works.values(), key=lambda x: x["title"]),
        "characters": sorted(characters.values(), key=lambda x: x["name"]),
        "studios": sorted(studios.values(), key=lambda x: x["name"]),
        "franchises": sorted(franchises.values(), key=lambda x: x["name"]),
        "languages": languages,
        "media_types": media_types,
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>actor_db dashboard</title>
<style>
  :root {
    --bg: #14161c; --panel: #1b1e27; --panel-2: #21242f; --border: #2c3040;
    --text: #e7e9ee; --text-dim: #9aa0b0; --accent: #6ea8fe; --accent-dim: #35507d;
    --tag-bg: #262b3a; --star: #ffd76b;
    --c-actor: #2c5aa0; --c-work: #c96f1c; --c-character: #4a5fc1;
    --c-studio: #1e8449; --c-franchise: #7d3c98; --c-costars: #b23b6b; --c-compare: #2a9d8f;
    --lang-en: #3a6fc4; --lang-ja: #c4463a; --lang-other: #6a6f80;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); display: flex; height: 100vh; overflow: hidden;
  }
  #sidebar {
    width: 210px; flex-shrink: 0; background: var(--panel); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; padding: 16px 0; overflow-y: auto;
  }
  #sidebar h1 { font-size: 15px; padding: 0 16px 12px; margin: 0; color: var(--text); border-bottom: 1px solid var(--border); }
  .navtab {
    padding: 10px 16px; cursor: pointer; color: var(--text-dim); font-size: 14px; border-left: 3px solid transparent;
  }
  .navtab:hover { background: var(--panel-2); color: var(--text); }
  .navtab.active { color: var(--accent); border-left-color: var(--accent); background: var(--panel-2); }
  .navtab .count { float: right; color: var(--text-dim); font-size: 12px; }
  .navtab.section-gap { margin-top: 10px; padding-top: 14px; border-top: 1px solid var(--border); }
  #main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  #searchbar {
    padding: 14px 24px; border-bottom: 1px solid var(--border); background: var(--panel);
    display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  }
  #searchbar input[type=text] {
    flex: 1; max-width: 480px; padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border);
    background: var(--panel-2); color: var(--text); font-size: 14px;
  }
  #searchbar button {
    padding: 8px 16px; border-radius: 6px; border: 1px solid var(--accent-dim); background: var(--accent-dim);
    color: var(--text); font-size: 13.5px; cursor: pointer;
  }
  #searchbar button:hover { background: var(--accent); border-color: var(--accent); }
  #searchhint { color: var(--text-dim); font-size: 12px; width: 100%; }
  #langFilter, #mediaFilter {
    padding: 7px 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--panel-2);
    color: var(--text); font-size: 13px;
  }
  #favOnlyWrap { display: none; align-items: center; gap: 6px; font-size: 13px; color: var(--text-dim); }
  #content { flex: 1; overflow-y: auto; padding: 20px 24px; }

  /* letterboxd-style tile grid */
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 14px; }
  .tile {
    background: var(--panel); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
    cursor: pointer; transition: transform .08s ease, border-color .08s ease; position: relative;
  }
  .tile:hover { border-color: var(--accent); transform: translateY(-2px); }
  .tile-badge {
    height: 64px; display: flex; align-items: center; justify-content: center;
    font-size: 24px; font-weight: 700; color: white; letter-spacing: 0.5px;
  }
  .tile-body { padding: 10px 12px 12px; }
  .tile-title { font-size: 13px; font-weight: 600; line-height: 1.3; }
  .tile-sub { font-size: 11px; color: var(--text-dim); margin-top: 4px; line-height: 1.3; }
  .fav-star {
    position: absolute; top: 6px; right: 6px; width: 26px; height: 26px; border-radius: 50%;
    border: none; background: rgba(0,0,0,0.4); color: rgba(255,255,255,0.55); font-size: 15px;
    cursor: pointer; line-height: 1;
  }
  .fav-star.active { color: var(--star); }
  .fav-star:hover { background: rgba(0,0,0,0.65); }
  .fav-star-detail {
    cursor: pointer; color: var(--text-dim); font-size: 13px; border: 1px solid var(--border);
    padding: 4px 10px; border-radius: 6px; display: inline-block;
  }
  .fav-star-detail.active { color: var(--star); border-color: var(--star); }

  .tag {
    display: inline-block; background: var(--tag-bg); color: var(--text-dim); font-size: 11.5px;
    padding: 2px 8px; border-radius: 10px; margin: 2px 4px 6px 0; cursor: pointer;
  }
  .tag:hover { color: var(--accent); }
  .lang-tag {
    display: inline-block; font-size: 10.5px; padding: 1px 7px; border-radius: 8px; color: white;
    margin-bottom: 4px;
  }
  .detail-row {
    display: flex; justify-content: space-between; gap: 12px; padding: 7px 0;
    border-bottom: 1px solid var(--border); font-size: 13.5px;
  }
  .detail-row:last-child { border-bottom: none; }
  .detail-row .left a, .detail-row .right a, .detail-meta a { color: var(--accent); text-decoration: none; cursor: pointer; }
  .detail-row .left a:hover, .detail-row .right a:hover, .detail-meta a:hover { text-decoration: underline; }
  .detail-row .right { color: var(--text-dim); text-align: right; white-space: nowrap; }
  .back-link { color: var(--accent); cursor: pointer; font-size: 13px; margin-bottom: 14px; display: inline-block; }
  .empty { color: var(--text-dim); font-size: 13px; padding: 40px 20px; text-align: center; }
  h2.detail-heading { margin: 0 0 4px; font-size: 20px; display: inline-block; margin-right: 10px; }
  .detail-meta { color: var(--text-dim); font-size: 13px; margin-bottom: 16px; }
  .costars-btn {
    display: inline-block; margin-top: 10px; padding: 6px 12px; border-radius: 6px;
    border: 1px solid var(--c-costars); color: var(--c-costars); font-size: 12.5px; cursor: pointer;
  }
  .costars-btn:hover { background: var(--c-costars); color: white; }

  /* BTVA-style side-by-side cast squares */
  .appearance-block { margin-bottom: 16px; }
  .appearance-title { font-size: 13.5px; font-weight: 600; margin-bottom: 8px; }
  .appearance-title .tag { cursor: default; }
  .va-square-row { display: flex; flex-wrap: wrap; gap: 10px; }
  .va-square {
    background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
    padding: 10px 12px; min-width: 120px; cursor: pointer; text-align: center;
  }
  .va-square:hover { border-color: var(--accent); }
  .va-square .va-name { font-size: 12.5px; font-weight: 600; margin-top: 2px; }
  .va-square .va-roletype { font-size: 10.5px; color: var(--text-dim); margin-top: 3px; }

  /* Studio: grouped by medium */
  .media-group-heading {
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dim);
    margin: 16px 0 6px; border-bottom: 1px solid var(--border); padding-bottom: 4px;
  }
  .media-group:first-child .media-group-heading { margin-top: 0; }

  /* Compare tab */
  .compare-intro { color: var(--text-dim); font-size: 13px; margin-bottom: 14px; }
  .compare-row { margin-bottom: 8px; display: flex; gap: 8px; }
  .compare-row input {
    flex: 1; max-width: 420px; padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border);
    background: var(--panel-2); color: var(--text); font-size: 13.5px;
  }
  .compare-actions { margin: 12px 0 20px; display: flex; gap: 10px; }
  .compare-actions button {
    padding: 8px 16px; border-radius: 6px; border: 1px solid var(--border); background: var(--panel-2);
    color: var(--text); font-size: 13px; cursor: pointer;
  }
  .compare-actions button:hover { border-color: var(--c-compare); color: var(--c-compare); }
  .compare-actions button.primary { border-color: var(--c-compare); background: var(--c-compare); color: white; }
  .compare-actions button.primary:hover { opacity: 0.9; }
</style>
</head>
<body>
<h2 class="sr-only" style="position:absolute;left:-9999px;">actor_db dashboard: browse and search actors, works, characters, studios, and franchises</h2>

<div id="sidebar">
  <h1>actor_db</h1>
  <div class="navtab active" data-view="actors_en">Actors (EN) <span class="count" id="count-actors_en"></span></div>
  <div class="navtab" data-view="actors_ja">Actors (JA) <span class="count" id="count-actors_ja"></span></div>
  <div class="navtab" data-view="works">Works <span class="count" id="count-works"></span></div>
  <div class="navtab" data-view="characters">Characters <span class="count" id="count-characters"></span></div>
  <div class="navtab" data-view="studios">Studios <span class="count" id="count-studios"></span></div>
  <div class="navtab" data-view="franchises">Franchises <span class="count" id="count-franchises"></span></div>
  <div class="navtab section-gap" data-view="costars">Co-stars</div>
  <div class="navtab" data-view="compare">Compare</div>
</div>

<div id="main">
  <div id="searchbar">
    <input type="text" id="search" placeholder="Search actors...">
    <button id="searchbtn" onclick="runQuery()">Search</button>
    <select id="langFilter"><option value="all">All languages</option></select>
    <select id="mediaFilter"><option value="all">All media</option></select>
    <span id="favOnlyWrap"><label><input type="checkbox" id="favOnly"> &#9733; Favorites only</label></span>
    <span id="searchhint"></span>
  </div>
  <div id="content"></div>
</div>

<script>
const DATA = __DATA_JSON__;
DATA.actors_en = DATA.actors.filter(a => a.roles.some(r => (r.language || "").toLowerCase() === "english"));
DATA.actors_ja = DATA.actors.filter(a => a.roles.some(r => (r.language || "").toLowerCase() === "japanese"));

const BADGE_COLOR = {
  actors_en: "var(--lang-en)", actors_ja: "var(--lang-ja)", works: "var(--c-work)", characters: "var(--c-character)",
  studios: "var(--c-studio)", franchises: "var(--c-franchise)",
};
const LANG_COLOR = { "english": "var(--lang-en)", "japanese": "var(--lang-ja)" };

let currentView = "actors_en";
let currentDetail = null; // {view, id, backView} while viewing a detail page, else null
let lastActorsTab = "actors_en";
let langFilter = "all";
let mediaFilter = "all";

const FAV_KEY = "actordb_favorite_actors";
function loadFavorites() {
  try { return new Set(JSON.parse(localStorage.getItem(FAV_KEY) || "[]")); } catch (e) { return new Set(); }
}
function saveFavorites() { localStorage.setItem(FAV_KEY, JSON.stringify(Array.from(favorites))); }
let favorites = loadFavorites();
function isFavorite(name) { return favorites.has(name); }
function toggleFavorite(name, evt) {
  if (evt) evt.stopPropagation();
  if (favorites.has(name)) favorites.delete(name); else favorites.add(name);
  saveFavorites();
  if (currentDetail && currentDetail.view === "actors") {
    showDetail("actors", currentDetail.id);
  } else if (currentView === "actors_en" || currentView === "actors_ja") {
    showList(currentView, document.getElementById("search").value.trim().toLowerCase());
  }
}

function esc(s) { return (s ?? "").toString().replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function jsStr(s) { return esc(s).replace(/'/g, "\\\\'"); }

function initials(name) {
  const parts = (name || "?").trim().split(/\\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function langBadge(lang) {
  if (!lang) return "";
  const color = LANG_COLOR[lang.toLowerCase()] || "var(--lang-other)";
  return `<span class="lang-tag" style="background:${color}">${esc(lang)}</span>`;
}

function matchesLang(rowLang) {
  return langFilter === "all" || (rowLang || "").toLowerCase() === langFilter.toLowerCase();
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

function setCounts() {
  document.getElementById("count-actors_en").textContent = DATA.actors_en.length;
  document.getElementById("count-actors_ja").textContent = DATA.actors_ja.length;
  for (const k of ["works", "characters", "studios", "franchises"]) {
    document.getElementById("count-" + k).textContent = DATA[k].length;
  }
}

function populateFilters() {
  const langSel = document.getElementById("langFilter");
  for (const lang of (DATA.languages || [])) {
    const opt = document.createElement("option");
    opt.value = lang;
    opt.textContent = lang;
    langSel.appendChild(opt);
  }
  const mediaSel = document.getElementById("mediaFilter");
  for (const mt of (DATA.media_types || [])) {
    const opt = document.createElement("option");
    opt.value = mt;
    opt.textContent = mt;
    mediaSel.appendChild(opt);
  }
}

function setSearchUI(view) {
  const input = document.getElementById("search");
  const btn = document.getElementById("searchbtn");
  const langSel = document.getElementById("langFilter");
  const mediaSel = document.getElementById("mediaFilter");
  const hint = document.getElementById("searchhint");
  const favWrap = document.getElementById("favOnlyWrap");
  const placeholders = {
    actors_en: 'Search English VAs, e.g. "Troy Baker"',
    actors_ja: 'Search Japanese VAs, e.g. "Jun Fukuyama"',
    works: 'Search works, e.g. "Persona 5 Royal"',
    characters: 'Search characters, e.g. "Joker"',
    studios: 'Search studios, e.g. "Atlus"',
    franchises: 'Search franchises, e.g. "Persona"',
    costars: 'Actor name, e.g. "Yuri Lowenthal"',
  };
  const hints = {
    actors_en: 'Type to filter the grid live, or press Enter/Search to jump straight to an exact match.',
    actors_ja: 'Type to filter the grid live, or press Enter/Search to jump straight to an exact match.',
    works: 'Type to filter, or press Enter/Search for an exact title match. Use the media filter to narrow by type.',
    characters: 'Type to filter, or press Enter/Search for an exact match.',
    studios: 'Type to filter, or press Enter/Search for an exact match. Works are grouped by medium below.',
    franchises: 'Type to filter, or press Enter/Search for an exact match.',
    costars: 'Type a full actor name and press Enter/Search to see everyone they have shared a work with.',
    compare: '',
  };
  const isCompare = view === "compare";
  input.style.display = isCompare ? "none" : "";
  btn.style.display = isCompare ? "none" : "";
  langSel.style.display = isCompare ? "none" : "";
  mediaSel.style.display = (isCompare || view === "costars") ? "none" : "";
  input.placeholder = placeholders[view] || "Search...";
  hint.textContent = hints[view] || "";
  favWrap.style.display = isActorsView(view) && !isCompare ? "flex" : "none";
}

function switchTab(view) {
  currentView = view;
  currentDetail = null;
  if (view === "actors_en" || view === "actors_ja") lastActorsTab = view;
  document.querySelectorAll(".navtab").forEach(el => el.classList.toggle("active", el.dataset.view === view));
  setSearchUI(view);
  if (view === "costars") {
    showCostarsPrompt();
  } else if (view === "compare") {
    showCompareUI();
  } else {
    showList(view, "");
  }
}

function showList(view, filterText) {
  currentView = view;
  currentDetail = null;
  let items = listSource(view).filter(it => {
    const label = (it.name || it.title || "").toLowerCase();
    return !filterText || label.includes(filterText);
  });
  if (view === "works") items = items.filter(it => matchesMedia(it.media_type));
  if (isActorsView(view) && document.getElementById("favOnly").checked) {
    items = items.filter(it => isFavorite(it.name));
  }
  const content = document.getElementById("content");
  if (items.length === 0) {
    content.innerHTML = `<div class="empty">No results${filterText ? ` for "${esc(filterText)}"` : ""}.</div>`;
    return;
  }

  content.innerHTML = `<div class="grid">` + items.map(it => renderTile(view, it)).join("") + `</div>`;
}

function renderTile(view, it) {
  const color = BADGE_COLOR[view];
  const label = it.name || it.title;
  const actorsView = isActorsView(view);
  let sub = "";
  if (actorsView) sub = (it.birth_year ? "b. " + it.birth_year : "b. unknown") + " &middot; " + it.roles.length + " role" + (it.roles.length===1?"":"s");
  if (view === "works") sub = esc(it.media_type) + (it.year ? " &middot; " + it.year : "") + (it.franchise ? "<br>" + esc(it.franchise) : "");
  if (view === "characters") sub = it.appearances.length + " appearance" + (it.appearances.length===1?"":"s");
  if (view === "studios") sub = (it.country ? esc(it.country) + " &middot; " : "") + it.works.length + " credit" + (it.works.length===1?"":"s");
  if (view === "franchises") sub = it.works.length + " work" + (it.works.length===1?"":"s");

  const star = actorsView
    ? `<button class="fav-star ${isFavorite(label) ? "active" : ""}" onclick="toggleFavorite('${jsStr(label)}', event)" title="Toggle favorite">${isFavorite(label) ? "&#9733;" : "&#9734;"}</button>`
    : "";
  const detailView = actorsView ? "actors" : view;

  return `<div class="tile" onclick="showDetail('${detailView}','${it.id}')">
    ${star}
    <div class="tile-badge" style="background:${color}">${esc(initials(label))}</div>
    <div class="tile-body">
      <div class="tile-title">${esc(label)}</div>
      <div class="tile-sub">${sub}</div>
    </div>
  </div>`;
}

function findById(view, id) { return listSource(view === "actors" ? "actors" : view).find(x => String(x.id) === String(id)); }
function findByName(view, name) { return listSource(view === "actors" ? "actors" : view).find(x => x.name === name || x.title === name); }

function renderVASquares(performances) {
  return `<div class="va-square-row">` + performances.map(p => `
    <div class="va-square" onclick="jumpTo('actors','${jsStr(p.actor)}')">
      ${langBadge(p.language)}
      <div class="va-name">${esc(p.actor)}</div>
      <div class="va-roletype">${esc(p.role_type || "")}</div>
    </div>`).join("") + `</div>`;
}

function showDetail(view, id) {
  const it = findById(view, id);
  const backView = (view === "actors") ? lastActorsTab : view;
  currentView = view;
  currentDetail = { view, id, backView };
  document.querySelectorAll(".navtab").forEach(el => el.classList.toggle("active", el.dataset.view === backView));
  setSearchUI(backView);
  const content = document.getElementById("content");
  let html = `<span class="back-link" onclick="switchTab('${backView}')">&larr; back to ${backView.replace("_en"," (EN)").replace("_ja"," (JA)")}</span>`;

  if (view === "actors") {
    const fav = isFavorite(it.name);
    html += `<h2 class="detail-heading">${esc(it.name)}</h2>
      <span class="fav-star-detail ${fav ? "active" : ""}" onclick="toggleFavorite('${jsStr(it.name)}')">${fav ? "&#9733; Favorited" : "&#9734; Add to favorites"}</span>
      <div class="detail-meta">${it.birth_year ? "Born " + it.birth_year : "Birth year unknown"}
      &nbsp; <span class="costars-btn" onclick="queryCostars('${jsStr(it.name)}')">View co-stars</span></div>`;
    const roles = it.roles.filter(r => matchesLang(r.language) && matchesMedia(r.media_type));
    if (roles.length === 0) html += `<div class="empty">No roles match the current filters.</div>`;
    html += roles.map(r => `<div class="detail-row"><div class="left"><a onclick="jumpTo('characters','${jsStr(r.character)}')">${esc(r.character)}</a> in <a onclick="jumpTo('works','${jsStr(r.work)}')">${esc(r.work)}</a></div>
      <div class="right">${esc(r.media_type||"")} &middot; ${esc(r.role_type||"")}${langBadge(r.language)}</div></div>`).join("");
  } else if (view === "works") {
    html += `<h2 class="detail-heading">${esc(it.title)}${it.year ? " (" + it.year + ")" : ""}</h2>`;
    html += `<div class="detail-meta">${esc(it.media_type)}`
      + (it.franchise ? ` &middot; <a onclick="jumpTo('franchises','${jsStr(it.franchise)}')">${esc(it.franchise)}</a> franchise` : "")
      + (it.parent_title ? ` &middot; ${esc(it.relationship_type)} of <a onclick="jumpTo('works','${jsStr(it.parent_title)}')">${esc(it.parent_title)}</a>` : "")
      + `</div>`;
    if (it.studios.length) html += `<div style="margin-bottom:14px;">` + it.studios.map(s => `<span class="tag" onclick="jumpTo('studios','${jsStr(s.name)}')">${esc(s.name)} &middot; ${esc(s.role)}</span>`).join("") + `</div>`;
    const groups = it.cast
      .map(g => ({ ...g, performances: g.performances.filter(p => matchesLang(p.language)) }))
      .filter(g => g.performances.length > 0);
    if (groups.length === 0) html += `<div class="empty">No cast matches the current language filter.</div>`;
    html += groups.map(g => `<div class="appearance-block">
        <div class="appearance-title"><a onclick="jumpTo('characters','${jsStr(g.character)}')">${esc(g.character)}</a></div>
        ${renderVASquares(g.performances)}
      </div>`).join("");
  } else if (view === "characters") {
    html += `<h2 class="detail-heading">${esc(it.name)}</h2><div class="detail-meta">${it.appearances.length} appearance${it.appearances.length===1?"":"s"}</div>`;
    const groups = it.appearances
      .map(g => ({ ...g, performances: g.performances.filter(p => matchesLang(p.language)) }))
      .filter(g => matchesMedia(g.media_type) && g.performances.length > 0);
    if (groups.length === 0) html += `<div class="empty">No appearances match the current filters.</div>`;
    html += groups.map(g => `<div class="appearance-block">
        <div class="appearance-title"><a onclick="jumpTo('works','${jsStr(g.work)}')">${esc(g.work)}</a> ${g.work_year ? "("+g.work_year+")" : ""} <span class="tag">${esc(g.media_type)}</span></div>
        ${renderVASquares(g.performances)}
      </div>`).join("");
  } else if (view === "studios") {
    html += `<h2 class="detail-heading">${esc(it.name)}</h2><div class="detail-meta">${it.country ? esc(it.country) : "Country unknown"}</div>`;
    const filtered = it.works.filter(w => matchesMedia(w.media_type));
    if (filtered.length === 0) html += `<div class="empty">No credits match the current media filter.</div>`;
    const byMedia = {};
    for (const w of filtered) (byMedia[w.media_type] = byMedia[w.media_type] || []).push(w);
    html += Object.keys(byMedia).sort().map(mt => {
      const list = byMedia[mt].slice().sort((a, b) => (a.year || 0) - (b.year || 0));
      return `<div class="media-group">
        <div class="media-group-heading">${esc(mt)}</div>
        ${list.map(w => `<div class="detail-row"><div class="left"><a onclick="jumpTo('works','${jsStr(w.title)}')">${esc(w.title)}</a> ${w.year ? "("+w.year+")" : ""}</div>
          <div class="right">${esc(w.role)}</div></div>`).join("")}
      </div>`;
    }).join("");
  } else if (view === "franchises") {
    html += `<h2 class="detail-heading">${esc(it.name)}</h2><div class="detail-meta">${it.works.length} works</div>`;
    const filtered = it.works.filter(w => matchesMedia(w.media_type));
    if (filtered.length === 0) html += `<div class="empty">No works match the current media filter.</div>`;
    html += filtered.map(w => `<div class="detail-row"><div class="left"><a onclick="jumpTo('works','${jsStr(w.title)}')">${esc(w.title)}</a> ${w.year ? "("+w.year+")" : ""}</div>
      <div class="right">${w.parent_title ? esc(w.relationship_type) + " of " + esc(w.parent_title) : esc(w.media_type)}</div></div>`).join("");
  }
  content.innerHTML = html;
}

function jumpTo(view, name) {
  const it = findByName(view, name);
  if (!it) return;
  showDetail(view, it.id);
}

// -------------------------
// Co-stars (mirrors `python scripts/query.py costars "<name>"`)
// -------------------------
function showCostarsPrompt() {
  document.getElementById("content").innerHTML = `<div class="empty">Type an actor's name above and press Search (or Enter) to see everyone they've shared a work with -- including which characters were involved.</div>`;
}

function computeCostars(actorName) {
  const actor = findByName("actors", actorName);
  if (!actor) return null;

  const map = new Map();
  for (const role of actor.roles) {
    if (!matchesLang(role.language) || !matchesMedia(role.media_type)) continue;
    const work = findByName("works", role.work);
    if (!work) continue;
    for (const g of work.cast) {
      for (const p of g.performances) {
        if (p.actor === actor.name) continue;
        if (!matchesLang(p.language)) continue;
        const key = p.actor + "|" + g.character + "|" + work.title;
        if (!map.has(key)) {
          map.set(key, { costar: p.actor, costarCharacter: g.character, work: work.title, year: work.year, myCharacters: new Set() });
        }
        map.get(key).myCharacters.add(role.character);
      }
    }
  }
  const results = Array.from(map.values()).map(r => ({ ...r, myCharacters: Array.from(r.myCharacters).join(", ") }));
  results.sort((a, b) => (a.year || 0) - (b.year || 0) || a.costar.localeCompare(b.costar));
  return { actor, results };
}

function queryCostars(actorName) {
  switchTab("costars");
  document.getElementById("search").value = actorName;
  runCostarsQuery(actorName);
}

function runCostarsQuery(actorName) {
  const content = document.getElementById("content");
  const found = computeCostars(actorName);
  if (!found) {
    content.innerHTML = `<div class="empty">No actor found matching "${esc(actorName)}".</div>`;
    return;
  }
  if (found.results.length === 0) {
    content.innerHTML = `<div class="empty">${esc(found.actor.name)} has no shared works with anyone else matching the current filters.</div>`;
    return;
  }
  let html = `<h2 class="detail-heading">Co-stars of ${esc(found.actor.name)}</h2>
    <div class="detail-meta">${found.results.length} shared credit${found.results.length===1?"":"s"}</div>`;
  html += found.results.map(r => `<div class="detail-row"><div class="left"><a onclick="jumpTo('actors','${jsStr(r.costar)}')">${esc(r.costar)}</a> as ${esc(r.costarCharacter)}</div>
    <div class="right">as ${esc(r.myCharacters)} in <a onclick="jumpTo('works','${jsStr(r.work)}')">${esc(r.work)}</a> ${r.year ? "("+r.year+")" : ""}</div></div>`).join("");
  content.innerHTML = html;
}

// -------------------------
// Compare: "who has been in both/all of these franchises or works"
// -------------------------
function showCompareUI() {
  document.getElementById("content").innerHTML = `
    <div class="compare-intro">List two or more franchises and/or exact work titles, then find every actor who has a role in all of them.</div>
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
  const t = text.trim();
  const franchise = DATA.franchises.find(f => f.name.toLowerCase() === t.toLowerCase());
  if (franchise) {
    const workTitles = new Set(franchise.works.map(w => w.title));
    const matches = new Map();
    for (const a of DATA.actors) {
      const hits = a.roles.filter(r => workTitles.has(r.work));
      if (hits.length) matches.set(a.name, hits);
    }
    return { label: franchise.name, type: "franchise", matches };
  }
  const work = DATA.works.find(w => w.title.toLowerCase() === t.toLowerCase());
  if (work) {
    const matches = new Map();
    for (const a of DATA.actors) {
      const hits = a.roles.filter(r => r.work_id === work.id);
      if (hits.length) matches.set(a.name, hits);
    }
    return { label: work.title, type: "work", matches };
  }
  return { label: t, type: "unknown", matches: null };
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
    const perItem = resolved.map(r => {
      const hits = r.matches.get(name);
      const characters = [...new Set(hits.map(h => h.character))].join(", ");
      return `<a onclick="jumpTo('works','${jsStr(hits[0].work)}')">${esc(r.label)}</a>: ${esc(characters)}`;
    }).join(" &middot; ");
    return `<div class="detail-row"><div class="left"><a onclick="jumpTo('actors','${jsStr(name)}')">${esc(name)}</a></div><div class="right">${perItem}</div></div>`;
  }).join("");
  results.innerHTML = html;
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
  const exact = listSource(currentView).find(x => (x.name || x.title || "").toLowerCase() === value.toLowerCase());
  if (exact) {
    const detailView = isActorsView(currentView) ? "actors" : currentView;
    showDetail(detailView, exact.id);
  } else {
    showList(currentView, value.toLowerCase());
  }
}

document.querySelectorAll(".navtab").forEach(el => el.addEventListener("click", () => switchTab(el.dataset.view)));

document.getElementById("search").addEventListener("input", e => {
  if (currentView === "costars" || currentView === "compare" || currentDetail) return;
  showList(currentView, e.target.value.trim().toLowerCase());
});
document.getElementById("search").addEventListener("keydown", e => {
  if (e.key === "Enter") runQuery();
});
document.getElementById("favOnly").addEventListener("change", () => {
  showList(currentView, document.getElementById("search").value.trim().toLowerCase());
});
document.getElementById("langFilter").addEventListener("change", e => {
  langFilter = e.target.value;
  if (currentDetail) {
    showDetail(currentDetail.view, currentDetail.id);
  } else if (currentView === "costars") {
    const v = document.getElementById("search").value.trim();
    if (v) runCostarsQuery(v);
  }
});
document.getElementById("mediaFilter").addEventListener("change", e => {
  mediaFilter = e.target.value;
  if (currentDetail) {
    showDetail(currentDetail.view, currentDetail.id);
  } else if (currentView === "works") {
    showList("works", document.getElementById("search").value.trim().toLowerCase());
  } else if (currentView === "costars") {
    const v = document.getElementById("search").value.trim();
    if (v) runCostarsQuery(v);
  }
});

populateFilters();
setCounts();
setSearchUI("actors_en");
showList("actors_en", "");
</script>
</body>
</html>
"""


def generate():
    data = build_data()
    html = HTML_TEMPLATE.replace("__DATA_JSON__", json.dumps(data))
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    generate()
