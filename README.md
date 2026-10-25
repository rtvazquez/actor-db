# Actor Database

A relational SQLite database for tracking who voiced (or played) which
character, in which work, for which studio -- built mainly as a personal
reference tool, with an eye toward eventually publishing it.

## Current state: rebuilding from an archive

The original dataset (440 actors, 126 works, 841 credits) is preserved in
`archive/full_20261025/` for reference. The live database was reset to
empty and is being rebuilt by hand, adding only what's wanted -- either
through `actordb.py add` or by pulling specific works/franchises/actors
back from the archive with `actordb.py readd` (see `archive/README.md`).

## Verified credits

Each credit has a `verified` flag (1 = checked against a source page that was
actually read) plus an optional `source_url`. Credits imported from search
snippets keep their URL but stay unverified; the "Needs work" tab ranks works
by unsourced credits. `staging/` holds raw research output and
`staging/REVIEW.md` lists open questions (it's gitignored).

Studio credits (`WorkStudios.source_url`) are only kept when they have a
source; unsourced studio info is removed rather than guessed. The `readd`
command therefore re-adds archive casts but not archive studios.

## Favorites and watched

Favorites (any entity type) and watched works are stored in the database
(`favorite` / `watched` columns) and exported to `data/user_flags.json`. The
dashboard applies them to your browser once, as starting values: anything you
later star or un-star in the browser sticks (browser state lives in
`localStorage`, so it doesn't flow back into the database).

## Schema

- **Actors** -- performers.
- **Works** -- games, anime, movies, TV series. Each has a `media_type`,
  optional `franchise_id`, and an optional `parent_work_id` +
  `work_relationship_type` (Sequel, Remake, Spin-off, ...) for linking
  related entries.
- **Franchises** -- Persona, Danganronpa, Final Fantasy, etc. A work
  belongs to at most one.
- **Studios** + **WorkStudios** -- developers, publishers, animation
  studios, localization studios. A work can have several studios, each
  in a different capacity (`studio_role`).
- **Characters** + **CharacterAppearances** -- a character can appear in
  multiple works; this bridge table tracks that.
- **Languages** -- English, Japanese, etc.
- **Performances** -- the actual link: one actor playing one character
  in one work, in one language, with a `performance_type` (Voice,
  Live-Action, Motion-Capture) and `role_type` (Main, Supporting, Minor,
  Cameo). Language is optional so this table can hold live-action
  performances later without a schema change. Multiple performances can
  point at the same appearance, which is how recasts and dual-language
  casts are represented. An optional `source_url` records the page used
  to verify the credit -- shown as a small 🔗 link in the dashboard next
  to any role that has one. It's populated for recently-added batches,
  not retroactively for the whole dataset.

Enum-like columns (`media_type`, `studio_role`, `work_relationship_type`,
`performance_type`, `role_type`) are enforced with `CHECK` constraints so
typos can't silently fragment the data.

See `database/schema.sql` for the full DDL and `docs/schema.png` for a
diagram.

## Folder layout

```
database/          schema.sql (DDL) + voice_actors.db (the actual SQLite file) + dashboard.html (generated GUI)
dashboard/         GUI source: template.html, style.css, app.js (inlined into dashboard.html by generate_dashboard.py)
data/               source JSON used to seed the database
  voice_roles.json     one row per actor/character/work/language performance
  work_metadata.json   one row per work: franchise, studios, parent work
scripts/
  actordb.py                single entry point (see Usage)
  db_ops.py                  add/search/delete logic used by add_role/remove_role
  export_json.py             DB -> data/*.json
  create_db.py            (re)builds database/voice_actors.db from schema.sql
  import_data.py           loads data/*.json into the database
  query.py                  CLI for querying the database
  generate_dashboard.py      builds database/dashboard.html, a browsable GUI
  check_consistency.py        cross-validates the two JSON files, read-only
  check_singles.py             reports singleton actors/works/studios worth reviewing, read-only
  add_role.py                  interactive prompt for adding a new entry (writes to the DB)
  utils.py                      shared DB connection + lookup-or-create helpers
  remove_role.py            interactive prompt for removing entries (from the DB)
tests/
  test_smoke.py         stdlib-only sanity checks against an in-memory copy
  test_dashboard.js      drives the real generated dashboard.html with jsdom
package.json          declares jsdom as a dev dependency for test_dashboard.js only --
                       the dashboard itself stays a dependency-free single HTML file
```

## Usage

The **database is the source of truth**. `data/*.json` is a diffable
snapshot (and seed) exported from it. Everything runs through one command,
from any directory:

```bash
python scripts/actordb.py menu        # interactive menu
python scripts/actordb.py add         # add a role (writes to the DB, exports JSON)
python scripts/actordb.py remove      # search + delete roles, cleaning up orphans
python scripts/actordb.py export      # DB -> data/*.json
python scripts/actordb.py build       # rebuild DB from JSON + dashboard (refuses if the DB has unexported changes; --force to override)
python scripts/actordb.py dashboard   # regenerate database/dashboard.html
python scripts/actordb.py check       # consistency check of the JSON files (read-only)
python scripts/actordb.py singles     # thin-corner report (read-only)
python scripts/actordb.py add-work "Title" --year 2020 --type "Video Game" --favorite --watched   # work with no cast yet
python scripts/actordb.py readd work "Persona 5 Royal"   # pull credits back from archive/ (also: search, franchise, actor)
python scripts/actordb.py query actor "Troy Baker"
python tests/test_smoke.py && python tests/test_db_ops.py
```

`check_consistency.py` catches things that would otherwise fail silently on
import: duplicate rows, actor/character names that differ only by case or
whitespace (which would fragment one real person into two DB rows),
`work_metadata.json` entries with no matching cast, and `parent_work`
references that don't resolve to anything.

`check_singles.py` isn't about errors -- it's a review tool. It reports
actors with only 1 role anywhere in the database, actors whose multiple
roles are all bunched into one single work, works with only 1 recorded
performance, works credited to only 1 actor, and studios credited on
only 1 work -- the thinnest, most easily-cut corners of the dataset, for
whenever you want to prune down to what you actually recognize.

`tests/test_dashboard.js` is a browser-behavior test suite for
`database/dashboard.html` itself -- it loads the actual generated file
into jsdom and drives its real functions (sorting, favoriting,
cross-highlighting, Co-stars/Counterparts/Connections/Compare, URL
routing, the media filter) the same way a click would, rather than
re-deriving the logic. One-time setup, then run any time after
regenerating the dashboard:

```bash
npm install                          # installs jsdom (dev dependency only)
python tests/run_dashboard_test.py   # builds a dashboard from archive/ data, then runs the jsdom suite
```

(The suite needs real data, so it runs against the archive rather than the live DB.)

Query modes:

```bash
python scripts/query.py actor "Troy Baker"
python scripts/query.py work "Persona 5 Royal"
python scripts/query.py character "Joker"
python scripts/query.py studio "Atlus"
python scripts/query.py franchise "Persona"
python scripts/query.py costars "Yuri Lowenthal"
```

## Browsing the data

`database/dashboard.html` is a self-contained, offline GUI -- just open
it in any browser (double-click it, or drag it into a browser window).

Actors get two separate letterboxd-style tile grids -- **Actors (EN)**
and **Actors (JA)** -- split by which language each actor has performed
in, rather than one mixed list. Works, Characters, Studios, and
Franchises are their own tile grids too, and every cross-link is
clickable in both directions: a studio's works, a work's cast *and*
studios *and* franchise *and* sequel/remake links, a character's
actors, an actor's roles -- click through any of them to jump to that
entity's page.

Character and Work pages use a BTVA-style layout: cast is grouped one
block per role, with each language's actor shown as its own clickable
square (name + colored language tag) side by side within that block --
so an English and Japanese actor sharing one role read as one
appearance/cast slot with two squares, not two separate entries. Studio
pages group their credits under medium subheadings (Video Game, Anime,
TV Series, ...).

That cast list also has its own **Grid/List** toggle, independent of the
one on the browse tabs -- Grid (the default) packs several character
cards per row so a large cast doesn't turn into one long vertical
scroll; List keeps the older full-width-row layout. The choice is
remembered in `localStorage` and applies to both Work and Character
detail pages.

There's no separate language filter -- language is already handled by
having two Actors tabs, and by always showing every language's actor
side by side on Character/Work pages. Instead the search bar has one
**media type** filter (Video Game/Anime/TV Series/Movie/OVA/all) that
actually removes non-matching tiles from whichever grid you're on
(Works, Characters, Studios, Franchises, or either Actors tab), not
just from a detail page -- e.g. picking "Anime" on the Characters tab
drops every character who's never appeared in an anime.

Each of those six grids also has a **sort** dropdown, with the choices
tailored to what makes sense for that tab: actors sort by first name,
last name, most roles, or fewest roles; works sort by title, oldest,
newest, or largest cast; characters/studios/franchises sort by name or
by count (appearances/credits/works).

Search, media filter, sort, view toggle, and the favorites/watched
checkboxes are consolidated into one two-row filter bar above each
grid, rather than scattered controls. A **Grid/List** toggle switches
between the tile view and a denser one-line-per-item list view (same
data, same click targets, just more rows on screen at once -- handy
now that some tabs run into the hundreds of entries). Grids also load
**60 items at a time** with a "Load more" button at the bottom instead
of rendering everything up front; changing the search text, media
filter, sort, or either checkbox resets back to the first 60. A work
added from watch-history with no cast entered yet shows a small "no
cast yet" badge (in both grid and list view) instead of an empty cast
section, so bulk-imported titles are visually distinct from fully
researched ones.

Co-stars, Counterparts, and Connections no longer have sidebar tabs; they
are reached from an actor's page ("View co-stars / counterparts /
connections") or by URL hash, e.g. `dashboard.html#costars/Yuri%20Lowenthal`.

A **Needs work** tab lists the gaps in the data, worst first: works whose
credits have no source link, works with no studio, thin casts, works with
no franchise, and actors missing a birth year. Click any entry to open it.

The **Co-stars** view reproduces `query.py costars`, showing which
character each side played (with a colored language tag next to each
name), not just the actor names -- and the actor name lookup is
case-insensitive, so "yuri lowenthal" works the same as "Yuri
Lowenthal". Results are split into two sections: **Co-starred with
(same dub)** -- people who shared a language track with the actor you
searched -- and **Cast in the other language version** -- people who
played opposite them in the *other* language's dub/sub, since an
English and Japanese cast technically co-star too but read very
differently. A link on that page jumps to the **Counterparts** view,
which is a more precise lookup: for one actor, it shows every
character they've played and who voiced that *exact same character*
in the other language, rather than the whole other-language cast.

The **Connections** view draws an actor's co-star network as a small
radial graph: the searched actor sits in the center, every distinct
co-star is a surrounding node (sized and connected by a line whose
thickness reflects how many credits they share), and clicking any node
jumps to that actor's page. Both the actor detail page and the
Co-stars results page link straight into it. For actors with a lot of
co-stars, it shows the top 40 by shared-credit count and says so.

A **Compare** tab answers "who's been in both/all of these
franchises or works" -- list two or more franchise names and/or work
titles (case-insensitive) and it intersects the actor sets, showing
which character satisfied each one, with the same language tag next to
each actor's name.

A **Stats** tab gives a snapshot of the whole database regardless of
the current media filter: total counts, the most prolific actors on
each of the EN/JA tabs, how many actors have roles in both languages,
a works-by-decade bar chart, the top studios/franchises by work count,
and a "most-connected actor" callout (whoever shares a work with the
most other actor credits overall).

Favoriting (the star icon on a tile or detail page) works for every
entity type -- actors, works, characters, studios, and franchises, each
saved separately in your browser via `localStorage` -- and a
"Favorites only" checkbox filters whichever grid you're on down to just
those. Favoriting also cross-highlights: if you favorite a work, it's
flagged (gold accent + star) everywhere it's referenced from another
page, e.g. on the detail page of anyone in its cast; if you favorite an
actor, their cast square is flagged on every work/character page they
show up on, in Co-stars/Counterparts/Compare rows, and so on. Separately, Works also get a **watched/played** checkmark (green,
distinct from the gold favorite star) -- a personal progress tracker
independent of favoriting, saved in `localStorage`, with its own
"Watched/played only" checkbox that appears only on the Works tab.

Regenerate the dashboard after any data or UI change with
`python scripts/actordb.py dashboard`.

**Search box examples:**

```
Actors (EN/JA) tabs: type "troy baker"     -> live-filters the grid as you type (case doesn't matter)
                     press Enter/Search    -> jumps straight to his page on an exact match
Works tab:           "Persona 5 Royal"     -> same live-filter/jump behavior; media filter narrows further
Characters tab:      "Joker"
Studios tab:         "Atlus"
Franchises tab:      "Persona"
Co-stars view:       "yuri lowenthal" + Enter -> lists co-stars split into "same dub" and
                                                  "other language version", with character + work
Counterparts view:   "yui ishikawa" + Enter -> for each role, shows who voiced that exact
                                                 character in the other language
Connections view:    "yuri lowenthal" + Enter -> draws his co-star network as a graph
Compare tab:         "persona" + "danganronpa" -> lists every actor who's been in both,
                                                   and which character(s) in each
```

Partial text always live-filters the grid (e.g. typing "danga" on the
Works tab shows every Danganronpa entry); only an exact, full-name
match jumps straight to a detail page. All of this is case-insensitive
-- Co-stars, Compare, and the exact-match jump all match regardless of
capitalization.

Franchises only show up as their own tab entry once **two or more**
works are catalogued under them -- a single catalogued work stays
franchise-less until a second one (sequel, other season, spin-off...)
is added, even if it's part of a bigger series in real life.

Every tab, detail page, Co-stars/Counterparts query, and Compare
comparison is mirrored into the page's URL hash (e.g.
`dashboard.html#actors/Yuri%20Lowenthal` or
`dashboard.html#compare/Persona|Danganronpa`), so any page can be
bookmarked or shared as a link, and the browser's back/forward buttons
step through whatever you've visited -- restoring not just which page
you were on, but also your scroll position and however far you'd
paged with "Load more," so going back doesn't dump you back at the top
of a long list you'd already scrolled through.

For poking at raw tables or writing your own SQL, `database/voice_actors.db`
is a normal SQLite file -- see "SQLite clients" in this README's project
notes, or just use the SQLite Viewer / SQLite / SQLTools extensions
already installed in VS Code.

## Adding and removing data

**Adding:** `python scripts/actordb.py add` and answer the prompts. It writes
straight to the database (creating the actor/work/character as needed,
plus franchise, studio and sequel links for a new work), then exports the
JSON snapshot and offers to regenerate the dashboard. Exact duplicates are
refused.

**Removing:** `python scripts/actordb.py remove`. Type a partial,
case-insensitive search (actor, character, or work title), pick matches
(`1`, `1,3`, `2-5`, `all`), confirm. It deletes from the database, removes
actors/characters/franchises left with nothing attached, and asks before
deleting a work that's left with no cast.

**Bulk edits:** edit the DB directly (any SQLite client), then run
`actordb.py export`. Or edit `data/voice_roles.json` by hand and run
`actordb.py build`; the optional keys are `source`, `character_note`
(disambiguates same-named characters), `role_type`, and `native_name`.

## Goals

- Search actors, characters, works, studios, and franchises.
- See what studios released what, and in what capacity (developer vs.
  publisher vs. animation studio vs. localization).
- See which actors have worked together (shared a work), and as which
  characters.
- Track franchises and sequel/remake relationships between works.
- Support English and Japanese casts (dual-language roles), browsable
  as separate actor pages and shown side by side wherever a role has both.
- Favorite actors for quick access in the dashboard.
- Schema covers live-action / motion-capture acting alongside voice work --
  e.g. Steven Yeun's live-action Glenn Rhee (*The Walking Dead*) sits next
  to his Mark Grayson voice role (*Invincible*) on the same actor page, and
  *The Last of Us* cast is tagged Voice+Motion-Capture rather than plain
  Voice. Roles other than plain Voice show their performance type inline.
