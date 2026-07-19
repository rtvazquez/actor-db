"""Shared helpers for the actor_db scripts.

Every script in this folder is expected to be run from the repo root
(e.g. `python scripts/create_db.py`), which is why paths here are relative.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("database/voice_actors.db")
SCHEMA_PATH = Path("database/schema.sql")


def connect():
    """Open a connection with foreign key enforcement turned on."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# -------------------------
# lookup-or-create helpers
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


def get_or_create_work(cur, title, year=None, media_type="Other"):
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
    if name is None:
        return None

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


def get_or_create_appearance(cur, character_id, work_id):
    row = cur.execute(
        """
        SELECT appearance_id FROM CharacterAppearances
        WHERE character_id = ? AND work_id = ?
        """,
        (character_id, work_id)
    ).fetchone()
    if row:
        return row[0]

    cur.execute(
        "INSERT INTO CharacterAppearances (character_id, work_id) VALUES (?, ?)",
        (character_id, work_id)
    )
    return cur.lastrowid


def get_or_create_studio(cur, name, country=None):
    row = cur.execute(
        "SELECT studio_id FROM Studios WHERE name = ?",
        (name,)
    ).fetchone()
    if row:
        return row[0]

    cur.execute(
        "INSERT INTO Studios (name, country) VALUES (?, ?)",
        (name, country)
    )
    return cur.lastrowid


def get_or_create_franchise(cur, name):
    if name is None:
        return None

    row = cur.execute(
        "SELECT franchise_id FROM Franchises WHERE name = ?",
        (name,)
    ).fetchone()
    if row:
        return row[0]

    cur.execute(
        "INSERT INTO Franchises (name) VALUES (?)",
        (name,)
    )
    return cur.lastrowid


def find_work(cur, title, year=None):
    row = cur.execute(
        "SELECT work_id FROM Works WHERE title = ? AND release_year IS ?",
        (title, year)
    ).fetchone()
    return row[0] if row else None
