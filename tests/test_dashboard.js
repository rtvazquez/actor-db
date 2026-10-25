/**
 * Lightweight smoke test for database/dashboard.html.
 *
 * Requires jsdom (not a hard dependency of the project -- run
 * `npm install` in this directory once, using the package.json here,
 * before running this test). Loads the actual generated dashboard.html
 * (not a synthetic fixture) and drives its real functions the same way a
 * browser click would, asserting on the resulting DOM/state.
 *
 * Run from the repo root with:
 *   node tests/test_dashboard.js
 */

const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const DASHBOARD_PATH = process.env.ACTORDB_DASHBOARD || path.join(__dirname, "..", "database", "dashboard.html");

let failures = [];

function check(label, condition) {
  if (condition) {
    console.log(`  [pass] ${label}`);
  } else {
    console.log(`  [FAIL] ${label}`);
    failures.push(label);
  }
}

function loadDashboard() {
  const html = fs.readFileSync(DASHBOARD_PATH, "utf-8");
  const jsErrors = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", (e) => jsErrors.push(e.message));
  const dom = new JSDOM(html, {
    runScripts: "dangerously",
    resources: "usable",
    virtualConsole: vc,
    url: "https://example.org/dashboard.html",
  });
  return { dom, jsErrors };
}

// Runs `code` inside the dashboard's own script realm (so it can see DATA,
// currentView, etc., which are lexical `const`/`let` and not window
// properties) and returns whatever it assigns to `window.__T`.
function evalInPage(win, code) {
  const doc = win.document;
  const script = doc.createElement("script");
  script.textContent = `window.__T = (function() { ${code} })();`;
  doc.body.appendChild(script);
  const result = win.__T;
  delete win.__T;
  return result;
}

function main() {
  if (!fs.existsSync(DASHBOARD_PATH)) {
    console.log(`database/dashboard.html not found -- run 'python scripts/generate_dashboard.py' first.`);
    process.exit(1);
  }

  const { dom, jsErrors } = loadDashboard();
  const win = dom.window;

  console.log("Loading database/dashboard.html...");
  check("no uncaught JS errors on load", jsErrors.length === 0);
  if (jsErrors.length) console.log("   " + jsErrors.join("\n   "));

  console.log("\nData:");
  check("DATA has actors/works/characters/studios/franchises",
    evalInPage(win, `return DATA.actors.length > 0 && DATA.works.length > 0 && DATA.characters.length > 0 && DATA.studios.length > 0 && DATA.franchises.length > 0;`));
  check("actors_en / actors_ja split is non-empty and disjoint from full overlap",
    evalInPage(win, `return DATA.actors_en.length > 0 && DATA.actors_ja.length > 0 && DATA.actors_en.length <= DATA.actors.length;`));

  console.log("\nSearch / lookup:");
  check("findByName is case-insensitive",
    evalInPage(win, `return !!findByName('actors', 'yuri lowenthal');`));
  check("findByName returns null for a nonexistent name",
    evalInPage(win, `return findByName('actors', 'Definitely Not A Real Actor Name Xyz') === undefined;`));

  console.log("\nSort:");
  check("sortItems name_last actually sorts by last name",
    evalInPage(win, `
      var sorted = sortItems('actors_en', DATA.actors_en, 'name_last');
      var lastNames = sorted.map(a => a.name.trim().split(/\\s+/).slice(-1)[0]);
      var isSorted = lastNames.every((n, i) => i === 0 || lastNames[i-1].localeCompare(n) <= 0);
      return isSorted;
    `));
  check("sortItems count_desc puts the highest-count item first",
    evalInPage(win, `
      var sorted = sortItems('works', DATA.works, 'count_desc');
      return sorted[0].cast.length >= sorted[sorted.length - 1].cast.length;
    `));

  console.log("\nFavorites + cross-highlighting:");
  check("toggling a favorite actor round-trips through isFavorite",
    evalInPage(win, `
      var name = DATA.actors[0].name;
      var before = isFavorite('actors', name);
      toggleFavorite('actors', name);
      var after = isFavorite('actors', name);
      toggleFavorite('actors', name); // restore
      return before !== after;
    `));
  check("favoriting a work highlights it on an actor's detail page (fav-ref)",
    evalInPage(win, `
      var work = DATA.works.find(w => w.cast.length > 0);
      var actorName = work.cast[0].performances[0].actor;
      var actor = DATA.actors.find(a => a.name === actorName);
      toggleFavorite('works', work.title);
      showDetail('actors', actor.id);
      var html = document.getElementById('content').innerHTML;
      toggleFavorite('works', work.title); // restore
      return html.includes('fav-ref');
    `));

  console.log("\nWatched/played tracker:");
  check("toggling watched round-trips and filters the Works grid",
    evalInPage(win, `
      var title = DATA.works[0].title;
      toggleWatched(title);
      var isW = isWatched(title);
      toggleWatched(title); // restore
      return isW === true;
    `));

  console.log("\nCo-stars / Counterparts / Connections:");
  check("computeCostars returns same-language and other-language buckets",
    evalInPage(win, `
      var r = computeCostars('Yuri Lowenthal');
      return r && Array.isArray(r.sameLanguage) && Array.isArray(r.otherLanguage);
    `));
  check("computeConnections aggregates repeat co-stars into one weighted node",
    evalInPage(win, `
      var r = computeConnections('Yuri Lowenthal');
      return r && r.nodes.length > 0 && r.nodes.every(n => n.weight >= 1);
    `));
  check("counterparts rows never render the literal word 'you'",
    evalInPage(win, `
      runCounterpartsQuery('Yui Ishikawa');
      var html = document.getElementById('content').innerHTML;
      return !/>\\s*you\\s*</i.test(html);
    `));

  console.log("\nCompare:");
  check("runCompare finds actors shared across two franchises",
    evalInPage(win, `
      switchTab('compare');
      var inputs = document.querySelectorAll('.compare-item');
      inputs[0].value = 'Persona';
      inputs[1].value = 'Danganronpa';
      runCompare();
      return document.getElementById('compareResults').innerHTML.includes('detail-row');
    `));

  console.log("\nStats:");
  check("computeStats totals match DATA lengths",
    evalInPage(win, `
      var s = computeStats();
      return s.totals.Actors === DATA.actors.length && s.totals.Works === DATA.works.length;
    `));

  console.log("\nURL routing:");
  check("navigating to a detail page updates location.hash",
    evalInPage(win, `
      var actor = DATA.actors[0];
      showDetail('actors', actor.id);
      return location.hash === '#actors/' + encodeURIComponent(actor.name);
    `));
  check("applyHash restores a detail page from a hash (simulated shared link)",
    evalInPage(win, `
      var work = DATA.works[0];
      history.pushState(null, '', '#works/' + encodeURIComponent(work.title));
      applyHash();
      return currentView === 'works' && currentDetail && String(currentDetail.id) === String(work.id);
    `));
  check("applyHash restores a costars query with the search box populated",
    evalInPage(win, `
      history.pushState(null, '', '#costars/' + encodeURIComponent('Yuri Lowenthal'));
      applyHash();
      return currentView === 'costars' && document.getElementById('search').value === 'Yuri Lowenthal';
    `));

  console.log("\nView mode + pagination:");
  check("setViewMode('list') renders list rows, toggles button state",
    evalInPage(win, `
      switchTab('works');
      setViewMode('list');
      var html = document.getElementById('content').innerHTML;
      var ok = html.includes('list-row') && document.getElementById('viewListBtn').classList.contains('active');
      setViewMode('grid'); // restore
      return ok;
    `));
  check("Works grid paginates instead of rendering everything at once",
    evalInPage(win, `
      switchTab('works');
      var tileCount = (document.getElementById('content').innerHTML.match(/class="tile"/g) || []).length;
      return tileCount <= PAGE_SIZE && tileCount === Math.min(PAGE_SIZE, DATA.works.length);
    `));
  check("changing the media filter resets pagination back to page 1",
    evalInPage(win, `
      switchTab('works');
      loadMoreItems();
      var grew = visibleCount > PAGE_SIZE;
      mediaFilter = 'Anime';
      showList('works', '');
      var reset = visibleCount === PAGE_SIZE;
      mediaFilter = 'all';
      showList('works', '');
      return grew && reset;
    `));
  check("a work with no recorded cast gets a 'no cast yet' badge in both view modes",
    evalInPage(win, `
      var fakeWork = { id: -1, title: '__Test Work With No Cast__', year: 2024, media_type: 'Movie', franchise: null, parent_title: null, relationship_type: null, studios: [], cast: [] };
      return renderTile('works', fakeWork).includes('no-cast-badge') && renderListRow('works', fakeWork).includes('no-cast-badge');
    `));

  console.log("\nCast grid/list toggle (Work/Character detail pages):");
  check("Work detail page cast defaults to a card grid, not a forced vertical list",
    evalInPage(win, `
      var w = DATA.works.find(w => w.cast.length >= 2);
      showDetail('works', w.id);
      return castViewMode === 'grid' && document.getElementById('content').innerHTML.includes('appearance-grid');
    `));
  check("setCastViewMode('list') switches to the full-width list layout and persists via localStorage",
    evalInPage(win, `
      var w = DATA.works.find(w => w.cast.length >= 2);
      showDetail('works', w.id);
      setCastViewMode('list');
      var html = document.getElementById('content').innerHTML;
      var ok = html.includes('appearance-list') && !html.includes('grid-card') && localStorage.getItem('actordb_cast_view') === 'list';
      setCastViewMode('grid'); // restore
      return ok;
    `));
  check("Character detail page also gets the cast grid/list toggle",
    evalInPage(win, `
      var c = DATA.characters.find(c => c.appearances.length >= 1);
      showDetail('characters', c.id);
      return document.getElementById('content').innerHTML.includes('cast-view-toggle');
    `));

  console.log("\nBack/forward preserves scroll position and pagination:");
  check("popstate restores the pagination depth (visibleCount) the user had reached, not page 1",
    evalInPage(win, `
      switchTab('works');
      loadMoreItems();
      var grownCount = visibleCount;
      var w = DATA.works[0];
      showDetail('works', w.id);
      history.back();
      return visibleCount === grownCount;
    `));
  check("popstate restores the scroll position of the page being returned to",
    evalInPage(win, `
      switchTab('works');
      document.getElementById('content').scrollTop = 321;
      var w = DATA.works[0];
      showDetail('works', w.id);
      history.back();
      return document.getElementById('content').scrollTop === 321;
    `));

  console.log("\nMedia filter:");
  check("media filter removes non-matching characters from the Characters grid, not just detail rows",
    evalInPage(win, `
      switchTab('characters');
      var before = document.querySelectorAll('.tile').length;
      mediaFilter = 'Movie';
      showList('characters', '');
      var after = document.querySelectorAll('.tile').length;
      mediaFilter = 'all';
      showList('characters', '');
      return after <= before;
    `));

  console.log("\nNeeds work + retired tabs:");
  check("sidebar no longer lists Co-stars/Counterparts/Connections but has Needs work",
    evalInPage(win, `
      var views = Array.from(document.querySelectorAll('.navtab')).map(function (e) { return e.dataset.view; });
      return !views.includes('costars') && !views.includes('counterparts') && !views.includes('connections') && views.includes('todo');
    `));
  check("Needs work tab renders every section and links into detail pages",
    evalInPage(win, `
      switchTab('todo');
      var html = document.getElementById('content').innerHTML;
      return html.includes('Unverified credits') && html.includes('Works with no studio') && html.includes('Thin casts')
        && html.includes('Actors missing a birth year') && html.includes("jumpTo('");
    `));
  check("#todo hash restores the Needs work view",
    evalInPage(win, `
      history.pushState(null, '', '#todo');
      applyHash();
      return currentView === 'todo';
    `));
  check("co-stars page still reachable from an actor page (link, hash)",
    evalInPage(win, `
      showDetail('actors', DATA.actors[0].id);
      var linked = document.getElementById('content').innerHTML.includes('queryCostars(');
      history.pushState(null, '', '#costars/' + encodeURIComponent(DATA.actors[0].name));
      applyHash();
      return linked && currentView === 'costars';
    `));

  console.log("\nDefault sorts + cast sorting:");
  check("every browse tab defaults to most-to-least",
    evalInPage(win, `
      return ['actors_en','actors_ja','works','characters','studios','franchises'].every(function (v) {
        switchTab(v);
        return currentSort === 'count_desc' && document.getElementById('sortSelect').value === 'count_desc';
      });
    `));
  check("works grid is ordered by largest cast first",
    evalInPage(win, `
      switchTab('works');
      var items = sortItems('works', listSource('works'), currentSort);
      return items.every(function (w, i) { return i === 0 || items[i - 1].cast.length >= w.cast.length; });
    `));
  check("work cast sorts by role importance by default and re-sorts via setCastSort",
    evalInPage(win, `
      var w = DATA.works.filter(function (x) { return x.cast.length > 3; })[0];
      var rank = function (g) { return Math.min.apply(null, g.performances.map(function (p) { return ROLE_RANK[p.role_type] === undefined ? 4 : ROLE_RANK[p.role_type]; })); };
      var byImportance = sortWorkCast(w.cast);
      var ok = byImportance.every(function (g, i) { return i === 0 || rank(byImportance[i - 1]) <= rank(g); });
      showDetail('works', w.id);
      var hasSelect = document.getElementById('content').innerHTML.includes('setCastSort(');
      setCastSort('work', 'character');
      var names = sortWorkCast(w.cast).map(function (g) { return g.character; });
      var sorted = names.slice().sort(function (a, b) { return a.localeCompare(b); });
      var alpha = JSON.stringify(names) === JSON.stringify(sorted);
      setCastSort('work', 'importance');
      return ok && hasSelect && alpha;
    `));
  check("character page has its own appearance sort (newest first by default)",
    evalInPage(win, `
      var c = DATA.characters.filter(function (x) { return x.appearances.length > 1; })[0];
      showDetail('characters', c.id);
      var s = sortCharacterAppearances(c.appearances);
      return document.getElementById('content').innerHTML.includes("setCastSort('character'")
        && s.every(function (g, i) { return i === 0 || (s[i - 1].work_year || 9999) >= (g.work_year || 9999); });
    `));

  console.log();
  if (failures.length) {
    console.log(`${failures.length} check(s) failed: ${JSON.stringify(failures)}`);
    process.exit(1);
  } else {
    console.log("All checks passed.");
  }
}

main();
