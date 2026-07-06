import sqlite3
import json
from pathlib import Path

DB_PATH = Path("db/voice_actors.db")
DATA_PATH = Path("data/voice_roles.json")


# -------------------------
# Helper functions (lookup-or-create pattern)
# -------------------------

def get_or_create_actor(cur, name, birth_year=None):
    row = cur.execute(
        "SELECT actor_id FROM Actors WHERE name = ?",
        (name,)
    ).fetchone()

    if row:
        return row[0]

    cur.execute(
        "INSERT INTO Actors (name, birth_year) VALUES (?, ?)",
        (name, birth_year)
    )
    return cur.lastrowid


def get_or_create_work(cur, title, year=None, media_type=None):
    row = cur.execute(
        "SELECT work_id FROM Works WHERE title = ? AND release_year IS ?",
        (title, year)
    ).fetchone()

    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO Works (title, release_year, media_type)
        VALUES (?, ?, ?)
        """,
        (title, year, media_type)
    )
    return cur.lastrowid


def get_or_create_character(cur, name):
    row = cur.execute(
        "SELECT character_id FROM Characters WHERE canonical_name = ?",
        (name,)
    ).fetchone()

    if row:
        return row[0]

    cur.execute(
        "INSERT INTO Characters (canonical_name) VALUES (?)",
        (name,)
    )
    return cur.lastrowid


def get_or_create_language(cur, name):
    row = cur.execute(
        "SELECT language_id FROM Languages WHERE name = ?",
        (name,)
    ).fetchone()

    if row:
        return row[0]

    cur.execute(
        "INSERT INTO Languages (name) VALUES (?)",
        (name,)
    )
    return cur.lastrowid


# -------------------------
# Main import logic
# -------------------------

def run():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        cur = conn.cursor()

        # -------------------------
        # Example dataset rows
        # (replace later with file parsing)
        # -------------------------

        with open(DATA_PATH, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        for entry in raw_data:
            actor_name = entry["actor"]
            birth_year = entry["birth_year"]
            work_title = entry["work"]
            year = entry["year"]
            char_name = entry["character"]
            lang = entry["language"]

            actor_id = get_or_create_actor(cur, actor_name, birth_year)
            work_id = get_or_create_work(cur, work_title, year, "Video Game")
            character_id = get_or_create_character(cur, char_name)
            language_id = get_or_create_language(cur, lang)

            # appearance
            appearance = cur.execute(
                """
                SELECT appearance_id
                FROM CharacterAppearances
                WHERE character_id = ? AND work_id = ?
                """,
                (character_id, work_id)
            ).fetchone()

            if appearance:
                appearance_id = appearance[0]
            else:
                cur.execute(
                    """
                    INSERT INTO CharacterAppearances (character_id, work_id)
                    VALUES (?, ?)
                    """,
                    (character_id, work_id)
                )
                appearance_id = cur.lastrowid

            # role (final link)
            cur.execute(
                """
                SELECT role_id
                FROM Roles
                WHERE appearance_id = ?
                AND actor_id = ?
                AND language_id = ?
                """,
                (appearance_id, actor_id, language_id)
            )

            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO Roles (appearance_id, actor_id, language_id, role_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (appearance_id, actor_id, language_id, "Main")
                )

        conn.commit()

        print("Import complete.")

        # quick verification
        rows = cur.execute("""
            SELECT a.name, c.canonical_name, w.title
            FROM Roles r
            JOIN Actors a ON r.actor_id = a.actor_id
            JOIN CharacterAppearances ca ON r.appearance_id = ca.appearance_id
            JOIN Characters c ON ca.character_id = c.character_id
            JOIN Works w ON ca.work_id = w.work_id
        """).fetchall()

        for r in rows:
            print(r)


if __name__ == "__main__":
    run()