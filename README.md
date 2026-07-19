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
database/          schema.sql (DDL) + voice_actors.db (the actual SQLite file)
data/               source JSON used to seed the database
  voice_roles.json     one row per actor/character/work/language performance
  work_metadata.json   one row per work: franchise, studios, parent work
scripts/
  create_db.py        (re)builds database/voice_actors.db from schema.sql
  import_data.py       loads data/*.json into the database
  query.py              CLI for querying the database
  utils.py               shared DB connection + lookup-or-create helpers
tests/
  test_smoke.py         stdlib-only sanity checks against an in-memory copy
```

## Usage

```bash
python scripts/create_db.py      # (re)creates database/voice_actors.db from schema.sql
python scripts/import_data.py    # loads data/voice_roles.json + data/work_metadata.json
python tests/test_smoke.py       # sanity-check the schema and query logic
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

## Adding new data

Add entries to `data/voice_roles.json` (one object per actor/character/
work/language performance, including `media_type`). If the work belongs
to a franchise, has known studios, or is a sequel/remake of something
already in the database, add or update its entry in
`data/work_metadata.json` too. Then re-run `create_db.py` +
`import_data.py`.

## Goals

- Search actors, characters, works, studios, and franchises.
- See what studios released what, and in what capacity (developer vs.
  publisher vs. animation studio vs. localization).
- See which actors have worked together (shared a work).
- Track franchises and sequel/remake relationships between works.
- Support English and Japanese casts (dual-language roles).
- Schema is general enough to eventually cover live-action / motion-capture
  acting, not just voice work.
