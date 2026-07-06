import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("db/voice_actors.db")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# -------------------------
# QUERY: ACTOR
# -------------------------
def query_actor(conn, name):
    cur = conn.cursor()

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
        JOIN Languages l ON r.language_id = l.language_id
        WHERE a.name = ?
        ORDER BY w.title;
    """, (name,)).fetchall()

    print(f"\n🎭 Actor: {name}")
    print("-" * 60)

    if not rows:
        print("No results found.")
        return

    for actor, character, work, role_type, lang in rows:
        print(f"{actor} → {character} in {work} [{lang}] ({role_type})")


# -------------------------
# QUERY: WORK
# -------------------------
def query_work(conn, title):
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT
            w.title,
            c.canonical_name,
            a.name,
            r.role_type,
            l.name
        FROM Roles r
        JOIN Actors a ON r.actor_id = a.actor_id
        JOIN CharacterAppearances ca ON r.appearance_id = ca.appearance_id
        JOIN Characters c ON ca.character_id = c.character_id
        JOIN Works w ON ca.work_id = w.work_id
        JOIN Languages l ON r.language_id = l.language_id
        WHERE w.title = ?
        ORDER BY c.canonical_name;
    """, (title,)).fetchall()

    print(f"\n🎮 Work: {title}")
    print("-" * 60)

    if not rows:
        print("No results found.")
        return

    for work, character, actor, role_type, lang in rows:
        print(f"{character} → {actor} [{lang}] ({role_type})")


# -------------------------
# QUERY: CHARACTER
# -------------------------
def query_character(conn, name):
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT
            c.canonical_name,
            w.title,
            a.name,
            r.role_type,
            l.name
        FROM Roles r
        JOIN Actors a ON r.actor_id = a.actor_id
        JOIN CharacterAppearances ca ON r.appearance_id = ca.appearance_id
        JOIN Characters c ON ca.character_id = c.character_id
        JOIN Works w ON ca.work_id = w.work_id
        JOIN Languages l ON r.language_id = l.language_id
        WHERE c.canonical_name = ?
        ORDER BY w.title;
    """, (name,)).fetchall()

    print(f"\n🧍 Character: {name}")
    print("-" * 60)

    if not rows:
        print("No results found.")
        return

    for character, work, actor, role_type, lang in rows:
        print(f"{character} → {actor} in {work} [{lang}] ({role_type})")


# -------------------------
# MAIN CLI
# -------------------------
def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python query.py actor <name>")
        print("  python query.py work <title>")
        print("  python query.py character <name>")
        return

    mode = sys.argv[1]
    value = " ".join(sys.argv[2:])

    conn = connect()

    if mode == "actor":
        query_actor(conn, value)
    elif mode == "work":
        query_work(conn, value)
    elif mode == "character":
        query_character(conn, value)
    else:
        print("Unknown mode. Use: actor | work | character")

    conn.close()


if __name__ == "__main__":
    main()