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

Actors get two separate letterboxd-style tile grids -- **Actors (EN)**
and **Actors (JA)** -- split by which language each actor has performed
in, rather than one mixed list. Works, Characters, Studios, and
Franchises are their own tile grids too, and every cross-link is
clickable in both directions: a studio's works, a work's cast *and*
studios *and* franchise *and* sequel/remake links, a character's
actors, an actor's roles -- click through any of them to jump to that
entity's page.

Character and Work pages use a BTVA-style layout: cast is grouped one
row per role, with each language's actor shown as its own clickable
square (name + colored language tag) side by side in that row -- so an
English and Japanese actor sharing one role read as one appearance/cast
slot with two squares, not two separate entries. Studio pages group
their credits under medium subheadings (Video Game, Anime, TV Series,
...).

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

A **Co-stars** tab reproduces `query.py costars`, showing which
character each side played (with a colored language tag next to each
name), not just the actor names -- and the actor name lookup is
case-insensitive, so "yuri lowenthal" works the same as "Yuri
Lowenthal". Results are split into two sections: **Co-starred with
(same dub)** -- people who shared a language track with the actor you
searched -- and **Cast in the other language version** -- people who
played opposite them in the *other* language's dub/sub, since an
English and Japanese cast technically co-star too but read very
differently. A link on that page jumps to the **Counterparts** tab,
which is a more precise lookup: for one actor, it shows every
character they've played and who voiced that *exact same character*
in the other language, rather than the whole other-language cast.

A **Compare** tab answers "who's been in both/all of these
franchises or works" -- list two or more franchise names and/or work
titles (case-insensitive) and it intersects the actor sets, showing
which character satisfied each one, with the same language tag next to
each actor's name.

Favoriting (the star icon on a tile or detail page) works for every
entity type -- actors, works, characters, studios, and franchises, each
saved separately in your browser via `localStorage` -- and a
"Favorites only" checkbox filters whichever grid you're on down to just
those. Favoriting also cross-highlights: if you favorite a work, it's
flagged (gold accent + star) everywhere it's referenced from another
page, e.g. on the detail page of anyone in its cast; if you favorite an
actor, their cast square is flagged on every work/character page they
show up on, in Co-stars/Counterparts/Compare rows, and so on. Regenerate
the dashboard after any data change with
`python scripts/generate_dashboard.py`.

**Search box examples:**

```
Actors (EN/JA) tabs: type "troy baker"     -> live-filters the grid as you type (case doesn't matter)
                     press Enter/Search    -> jumps straight to his page on an exact match
Works tab:           "Persona 5 Royal"     -> same live-filter/jump behavior; media filter narrows further
Characters tab:      "Joker"
Studios tab:         "Atlus"
Franchises tab:      "Persona"
Co-stars tab:        "yuri lowenthal" + Enter -> lists co-stars split into "same dub" and
                                                  "other language version", with character + work
Counterparts tab:    "yui ishikawa" + Enter -> for each role, shows who voiced that exact
                                                 character in the other language
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
- Support English and Japanese casts (dual-language roles), browsable
  as separate actor pages and shown side by side wherever a role has both.
- Favorite actors for quick access in the dashboard.
- Schema is general enough to eventually cover live-action / motion-capture
  acting, not just voice work.
