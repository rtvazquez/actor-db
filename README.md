# Actor Database

A relational SQLite database for tracking who voiced (or played) which
character, in which work, for which studio -- built mainly as a personal
reference tool, with an eye toward eventually publishing it.

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
  casts are represented.

Enum-like columns (`media_type`, `studio_role`, `work_relationship_type`,
`performance_type`, `role_type`) are enforced with `CHECK` constraints so
typos can't silently fragment the data.

See `database/schema.sql` for the full DDL and `docs/schema.png` for a
diagram.

## Folder layout

```
database/          schema.sql (DDL) + voice_actors.db (the actual SQLite file) + dashboard.html (generated GUI)
data/               source JSON used to seed the database
  voice_roles.json     one row per actor/character/work/language performance
  work_metadata.json   one row per work: franchise, studios, parent work
scripts/
  create_db.py            (re)builds database/voice_actors.db from schema.sql
  import_data.py           loads data/*.json into the database
  query.py                  CLI for querying the database
  generate_dashboard.py      builds database/dashboard.html, a browsable GUI
  add_role.py                 interactive prompt for adding a new entry
  utils.py                     shared DB connection + lookup-or-create helpers
tests/
  test_smoke.py         stdlib-only sanity checks against an in-memory copy
```

## Usage

```bash
python scripts/create_db.py          # (re)creates database/voice_actors.db from schema.sql
python scripts/import_data.py        # loads data/voice_roles.json + data/work_metadata.json
python scripts/generate_dashboard.py # builds database/dashboard.html
python tests/test_smoke.py           # sanity-check the schema and query logic
```

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
Actors, works, characters, studios, and franchises are browsable as a
letterboxd-style tile grid, and every cross-link is clickable in both
directions: a studio's works, a work's cast *and* studios *and*
franchise *and* sequel/remake links, a character's actors, an actor's
roles -- click through any of them to jump to that entity's page. A
sixth "Co-stars" tab reproduces `query.py costars`, and shows which
character each side played, not just the actor names. A language
filter (English/Japanese/...) narrows cast lists and co-star results
to one dub at a time. Favoriting an actor (the star icon on their
tile or detail page) is saved in your browser via `localStorage`, and
an "Favorites only" checkbox filters the Actors tab down to just
those. Regenerate the dashboard after any data change with
`python scripts/generate_dashboard.py`.

**Search box examples:**

```
Actors tab:      type "Troy Baker"        -> live-filters the grid as you type
                  press Enter/Search       -> jumps straight to his page if it's an exact match
Works tab:        "Persona 5 Royal"        -> same live-filter/jump behavior
Characters tab:   "Joker"
Studios tab:      "Atlus"
Franchises tab:   "Persona"
Co-stars tab:     "Yuri Lowenthal" + Enter -> lists everyone he's shared a work with,
                                              which character each of you played, and the work
```

Partial text always live-filters the grid (e.g. typing "danga" on the
Works tab shows every Danganronpa entry); only an exact, full-name
match jumps straight to a detail page. The language dropdown applies
to whichever tab or detail page you're on, so e.g. picking "Japanese"
on Frieren's work page shows only the JP cast, and picking it before
a co-stars search only surfaces JP-side overlaps.

For poking at raw tables or writing your own SQL, `database/voice_actors.db`
is a normal SQLite file -- see "SQLite clients" in this README's project
notes, or just use the SQLite Viewer / SQLite / SQLTools extensions
already installed in VS Code.

## Adding new data

Easiest: `python scripts/add_role.py` and answer the prompts (actor,
work, character, language, and -- for a new work -- media type,
franchise, studio credits, and sequel/remake links). It appends to the
JSON files for you and offers to rebuild the database and dashboard at
the end.

Manual alternative: add entries directly to `data/voice_roles.json` (one
object per actor/character/work/language performance, including
`media_type`). If the work belongs to a franchise, has known studios, or
is a sequel/remake of something already in the database, add or update
its entry in `data/work_metadata.json` too. Then re-run `create_db.py` +
`import_data.py`.

## Goals

- Search actors, characters, works, studios, and franchises.
- See what studios released what, and in what capacity (developer vs.
  publisher vs. animation studio vs. localization).
- See which actors have worked together (shared a work), and as which
  characters.
- Track franchises and sequel/remake relationships between works.
- Support English and Japanese casts (dual-language roles), filterable
  in the dashboard.
- Favorite actors for quick access in the dashboard.
- Schema is general enough to eventually cover live-action / motion-capture
  acting, not just voice work.
