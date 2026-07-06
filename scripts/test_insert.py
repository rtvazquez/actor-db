import sqlite3
from pathlib import Path

DB_PATH = Path("db/voice_actors.db")


def run():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        cur = conn.cursor()

        # -----------------------
        # Actor
        # -----------------------
        cur.execute(
            "INSERT INTO Actors (name, birth_year) VALUES (?, ?)",
            ("Troy Baker", 1976)
        )
        actor_id = cur.lastrowid

        # -----------------------
        # Work
        # -----------------------
        cur.execute(
            "INSERT INTO Works (title, release_year, media_type) VALUES (?, ?, ?)",
            ("The Last of Us Part II", 2020, "Video Game")
        )
        work_id = cur.lastrowid

        # -----------------------
        # Character
        # -----------------------
        cur.execute(
            "INSERT INTO Characters (canonical_name) VALUES (?)",
            ("Joel",)
        )
        character_id = cur.lastrowid

        # -----------------------
        # Appearance
        # -----------------------
        cur.execute(
            "INSERT INTO CharacterAppearances (character_id, work_id) VALUES (?, ?)",
            (character_id, work_id)
        )
        appearance_id = cur.lastrowid

        # -----------------------
        # Language (STRICT: no OR IGNORE)
        # -----------------------
        cur.execute(
            "INSERT INTO Languages (name) VALUES (?)",
            ("English",)
        )
        language_id = cur.lastrowid

        # -----------------------
        # Role
        # -----------------------
        cur.execute(
            """
            INSERT INTO Roles (appearance_id, actor_id, language_id, role_type)
            VALUES (?, ?, ?, ?)
            """,
            (appearance_id, actor_id, language_id, "Main")
        )

        conn.commit()

        # -----------------------
        # Full-chain verification query
        # -----------------------
        rows = cur.execute("""
            SELECT
                a.name,
                c.canonical_name,
                w.title,
                r.role_type,
                l.name
            FROM Roles r
            JOIN Actors a ON r.actor_id = a.actor_id
            JOIN CharacterAppearances ca ON r.appearance_id = ca.appearance_id
            JOIN Characters c ON ca.character_id = c.character_id
            JOIN Works w ON ca.work_id = w.work_id
            JOIN Languages l ON r.language_id = l.language_id;
        """).fetchall()

        for row in rows:
            print(row)


if __name__ == "__main__":
    run()