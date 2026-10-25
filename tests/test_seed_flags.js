/** Checks that favorites/watched flags stored in the database seed a fresh browser, and
 *  that un-starring sticks after a reload. Runs against the live dashboard.html. */
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const html = fs.readFileSync(process.env.ACTORDB_DASHBOARD || path.join(__dirname, "..", "database", "dashboard.html"), "utf-8");
const failures = [];
const check = (l, c) => { console.log(`  [${c ? "pass" : "FAIL"}] ${l}`); if (!c) failures.push(l); };

function load(storage) {
  const vc = new VirtualConsole();
  const dom = new JSDOM(html, { runScripts: "dangerously", virtualConsole: vc, url: "https://example.org/dashboard.html",
    beforeParse(w) { for (const k of Object.keys(storage)) w.localStorage.setItem(k, storage[k]); } });
  return dom.window;
}
const ev = (w, code) => w.eval(`(function(){${code}})()`);

setTimeout(() => {
  console.log("Seeded favorites / watched:");
  let w = load({});
  const flags = ev(w, "return DATA.flags");
  check("fresh browser has every database-favorite work starred",
    ev(w, "return DATA.flags.favorites.works.length > 0 && DATA.flags.favorites.works.every(t => isFavorite('works', t))"));
  check("fresh browser has every database-watched work checked",
    ev(w, "return DATA.flags.watched.length > 0 && DATA.flags.watched.every(t => isWatched(t))"));
  check("actors are not favorited unless the database says so",
    ev(w, "return favorites.actors.size === DATA.flags.favorites.actors.length"));
  const title = flags.favorites.works[0];
  ev(w, `toggleFavorite('works', ${JSON.stringify(title)}); toggleWatched(${JSON.stringify(title)});`);
  const stored = {};
  for (let i = 0; i < w.localStorage.length; i++) { const k = w.localStorage.key(i); stored[k] = w.localStorage.getItem(k); }
  w = load(stored);
  check("un-starring a seeded work persists across reload",
    ev(w, `return !isFavorite('works', ${JSON.stringify(title)}) && !isWatched(${JSON.stringify(title)})`));
  check("other seeded works stay starred after reload",
    ev(w, `return DATA.flags.favorites.works.filter(t => t !== ${JSON.stringify(title)}).every(t => isFavorite('works', t))`));
  console.log();
  if (failures.length) { console.log(`${failures.length} failed`); process.exit(1); }
  console.log("All checks passed.");
}, 300);
