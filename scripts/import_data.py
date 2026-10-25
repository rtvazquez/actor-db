"""Import pipeline for the actor_db database.

Two source files, two passes:

1. data/voice_roles.json -- one row per (actor, character, work, language)
   performance. Builds Actors / Works / Characters / CharacterAppearances /
   Languages / Performances.

2. data/work_metadata.json -- one row per work, keyed by (title, year).
   Enriches works already created in pass 1 with franchise, studio
   credits, and parent-work relationships. Kept separate from
   voice_roles.json so franchise/studio info isn't repeated on every
   single performance row.
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    DB_PATH,
    VOICE_ROLES_PATH,
    WORK_METADATA_PATH,
    USER_FLAGS_PATH,
    ACTOR_ALIASES_PATH,
    connect,
    get_or_create_actor,
    get_or_create_appearance,
    get_or_create_character,
    get_or_create_franchise,
    get_or_create_language,
    get_or_create_studio,
    get_or_create_work,
    find_work,
)



def import_performances(cur):
    with open(VOICE_ROLES_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    for entry in raw_data:
        actor_id = get_or_create_actor(cur, entry["actor"], entry.get("birth_year"))
        work_id = get_or_create_work(
            cur, entry["work"], entry.get("year"), entry.get("media_type", "Other")
        )
        character_id = get_or_create_character(
            cur, entry["character"], entry.get("character_note")
        )
        language_id = get_or_create_language(cur, entry.get("language"))
        appearance_id = get_or_create_appearance(cur, character_id, work_id)

        exists = cur.execute(
            """
            SELECT performance_id FROM Performances
            WHERE appearance_id = ? AND actor_id = ? AND language_id IS ?
            """,
            (appearance_id, actor_id, language_id)
        ).fetchone()

        if not exists:
            cur.execute(
                """
                INSERT INTO Performances (appearance_id, actor_id, language_id, role_type, performance_type, source_url, verified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (appearance_id, actor_id, language_id, entry.get("role_type", "Main"),
                 entry.get("performance_type", "Voice"), entry.get("source"),
                 int(entry["verified"]) if "verified" in entry else (1 if entry.get("source") else 0))
            )

    print(f"Imported {len(raw_data)} performance rows from {VOICE_ROLES_PATH}")


def import_work_metadata(cur):
    with open(WORK_METADATA_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    enriched = 0
    for entry in raw_data:
        work_id = find_work(cur, entry["title"], entry.get("year"))
        if work_id is None and entry.get("media_type"):
            # A work with no cast yet: metadata alone is enough to create it.
            work_id = get_or_create_work(cur, entry["title"], entry.get("year"), entry["media_type"])
        if work_id is None:
            print(f"  [skip] no matching Work for {entry['title']} ({entry.get('year')})")
            continue

        franchise_id = get_or_create_franchise(cur, entry.get("franchise"))
        if franchise_id is not None:
            cur.execute(
                "UPDATE Works SET franchise_id = ? WHERE work_id = ?",
                (franchise_id, work_id)
            )

        for studio in entry.get("studios", []):
            studio_id = get_or_create_studio(cur, studio["name"])
            cur.execute(
                """
                INSERT OR IGNORE INTO WorkStudios (work_id, studio_id, studio_role, source_url)
                VALUES (?, ?, ?, ?)
                """,
                (work_id, studio_id, studio["role"], studio.get("source"))
            )

        parent = entry.get("parent_work")
        if parent:
            parent_id = find_work(cur, parent["title"], parent.get("year"))
            if parent_id is not None:
                cur.execute(
                    """
                    UPDATE Works
                    SET parent_work_id = ?, work_relationship_type = ?
                    WHERE work_id = ?
                    """,
                    (parent_id, entry.get("relationship_type"), work_id)
                )

        enriched += 1

    print(f"Enriched {enriched} works from {WORK_METADATA_PATH}")


def import_aliases(cur):
    if not ACTOR_ALIASES_PATH.exists():
        return
    for name, aliases in json.loads(ACTOR_ALIASES_PATH.read_text(encoding="utf-8")).items():
        row = cur.execute("SELECT actor_id FROM Actors WHERE name = ?", (name,)).fetchone()
        if not row:
            continue
        for alias in aliases:
            cur.execute("INSERT OR IGNORE INTO ActorAliases (actor_id, alias) VALUES (?, ?)", (row[0], alias))


def import_flags(cur):
    if not USER_FLAGS_PATH.exists():
        return
    flags = json.loads(USER_FLAGS_PATH.read_text(encoding="utf-8"))
    cols = {"actors": ("Actors", "name"), "works": ("Works", "title"), "characters": ("Characters", "canonical_name"),
            "studios": ("Studios", "name"), "franchises": ("Franchises", "name")}
    n = 0
    for kind, names in flags.get("favorites", {}).items():
        table, col = cols[kind]
        for name in names:
            n += cur.execute(f"UPDATE {table} SET favorite = 1 WHERE {col} = ?", (name,)).rowcount
    for title in flags.get("watched", []):
        n += cur.execute("UPDATE Works SET watched = 1 WHERE title = ?", (title,)).rowcount
    print(f"Applied {n} favorite/watched flags from {USER_FLAGS_PATH}")


def run():
    with connect() as conn:
        cur = conn.cursor()
        import_performances(cur)
        import_work_metadata(cur)
        import_aliases(cur)
        import_flags(cur)
        conn.commit()

    print("Import complete.")


if __name__ == "__main__":
    run()
