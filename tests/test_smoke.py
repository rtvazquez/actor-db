"""
Lightweight smoke test for the actor_db schema and query logic.

Stdlib only (no pytest) -- run with:
    python tests/test_smoke.py

Builds a throwaway in-memory database from database/schema.sql, inserts a
small hand-crafted dataset that exercises every table (including the
Studios/Franchises/parent-work additions), and asserts that the query
patterns used by scripts/query.py return the expected rows. The temp
database only lives for the duration of the run -- nothing touches
database/voice_actors.db.
"""

import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "database" / "schema.sql"

failures = []


def check(label, condition):
    if condition:
        print(f"  [pass] {label}")
    else:
        print(f"  [FAIL] {label}")
        failures.append(label)


def build_test_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def seed(conn):
    cur = conn.cursor()

    # Franchise + studio
    cur.execute("INSERT INTO Franchises (name) VALUES ('Test Saga')")
    franchise_id = cur.lastrowid
    cur.execute("INSERT INTO Studios (name, country) VALUES ('Test Studio', 'JP')")
    studio_id = cur.lastrowid

    # Two works, one a sequel of the other, same franchise, same studio
    cur.execute("""
        INSERT INTO Works (title, release_year, media_type, franchise_id)
        VALUES ('Test Game', 2020, 'Video Game', ?)
    """, (franchise_id,))
    work1_id = cur.lastrowid

    cur.execute("""
        INSERT INTO Works (title, release_year, media_type, franchise_id, parent_work_id, work_relationship_type)
        VALUES ('Test Game II', 2022, 'Video Game', ?, ?, 'Sequel')
    """, (franchise_id, work1_id))
    work2_id = cur.lastrowid

    cur.execute("""
        INSERT INTO WorkStudios (work_id, studio_id, studio_role) VALUES (?, ?, 'Developer')
    """, (work1_id, studio_id))
    cur.execute("""
        INSERT INTO WorkStudios (work_id, studio_id, studio_role) VALUES (?, ?, 'Developer')
    """, (work2_id, studio_id))

    # Two actors, one character, English language
    cur.execute("INSERT INTO Actors (name, birth_year) VALUES ('Actor A', 1980)")
    actor_a = cur.lastrowid
    cur.execute("INSERT INTO Actors (name, birth_year) VALUES ('Actor B', 1985)")
    actor_b = cur.lastrowid

    cur.execute("INSERT INTO Characters (canonical_name) VALUES ('Hero')")
    hero_id = cur.lastrowid
    cur.execute("INSERT INTO Characters (canonical_name) VALUES ('Sidekick')")
    sidekick_id = cur.lastrowid

    cur.execute("INSERT INTO Languages (name) VALUES ('English')")
    english_id = cur.lastrowid

    # Both characters appear in work1; Actor A plays Hero, Actor B plays Sidekick
    # -> they should show up as each other's co-stars.
    cur.execute("INSERT INTO CharacterAppearances (character_id, work_id) VALUES (?, ?)", (hero_id, work1_id))
    appearance_hero = cur.lastrowid
    cur.execute("INSERT INTO CharacterAppearances (character_id, work_id) VALUES (?, ?)", (sidekick_id, work1_id))
    appearance_sidekick = cur.lastrowid

    cur.execute("""
        INSERT INTO Performances (appearance_id, actor_id, language_id, role_type)
        VALUES (?, ?, ?, 'Main')
    """, (appearance_hero, actor_a, english_id))
    cur.execute("""
        INSERT INTO Performances (appearance_id, actor_id, language_id, role_type)
        VALUES (?, ?, ?, 'Supporting')
    """, (appearance_sidekick, actor_b, english_id))

    # Live-action performance with no language, to prove language_id is
    # genuinely optional now (future-proofing for non-voice acting).
    cur.execute("""
        INSERT INTO Performances (appearance_id, actor_id, performance_type, role_type)
        VALUES (?, ?, 'Live-Action', 'Cameo')
    """, (appearance_hero, actor_b))

    conn.commit()


def test_media_type_is_enforced(conn):
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO Works (title, media_type) VALUES ('Bad Work', 'Not A Real Type')")
        conn.commit()
        check("media_type CHECK constraint rejects invalid values", False)
    except sqlite3.IntegrityError:
        conn.rollback()
        check("media_type CHECK constraint rejects invalid values", True)


def test_franchise_query(conn):
    rows = conn.execute("""
        SELECT w.title FROM Works w
        JOIN Franchises f ON w.franchise_id = f.franchise_id
        WHERE f.name = 'Test Saga'
        ORDER BY w.release_year
    """).fetchall()
    titles = [r[0] for r in rows]
    check("franchise query returns both works in release order",
          titles == ["Test Game", "Test Game II"])


def test_studio_query(conn):
    rows = conn.execute("""
        SELECT w.title FROM WorkStudios ws
        JOIN Studios s ON ws.studio_id = s.studio_id
        JOIN Works w ON ws.work_id = w.work_id
        WHERE s.name = 'Test Studio'
        ORDER BY w.release_year
    """).fetchall()
    check("studio query finds both works", len(rows) == 2)


def test_parent_work_relationship(conn):
    row = conn.execute("""
        SELECT pw.title, w.work_relationship_type
        FROM Works w JOIN Works pw ON w.parent_work_id = pw.work_id
        WHERE w.title = 'Test Game II'
    """).fetchone()
    check("sequel links back to its parent work with the right relationship type",
          row == ("Test Game", "Sequel"))


def test_costars_query(conn):
    rows = conn.execute("""
        SELECT DISTINCT a2.name
        FROM Performances p1
        JOIN Actors a1 ON p1.actor_id = a1.actor_id
        JOIN CharacterAppearances ca1 ON p1.appearance_id = ca1.appearance_id
        JOIN Works w ON ca1.work_id = w.work_id
        JOIN CharacterAppearances ca2 ON ca2.work_id = w.work_id
        JOIN Performances p2 ON p2.appearance_id = ca2.appearance_id
        JOIN Actors a2 ON p2.actor_id = a2.actor_id
        WHERE a1.name = 'Actor A' AND a2.actor_id != a1.actor_id
    """).fetchall()
    names = {r[0] for r in rows}
    check("co-star query finds Actor B as a co-star of Actor A", names == {"Actor B"})


def test_nullable_language(conn):
    row = conn.execute("""
        SELECT performance_type, language_id FROM Performances
        WHERE performance_type = 'Live-Action'
    """).fetchone()
    check("live-action performance stored with no language required",
          row is not None and row[1] is None)


def main():
    print("Building in-memory test database from database/schema.sql...")
    conn = build_test_db()
    seed(conn)

    print("\nRunning checks:")
    test_media_type_is_enforced(conn)
    test_franchise_query(conn)
    test_studio_query(conn)
    test_parent_work_relationship(conn)
    test_costars_query(conn)
    test_nullable_language(conn)

    conn.close()

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {failures}")
        sys.exit(1)
    else:
        print("All checks passed.")


if __name__ == "__main__":
    main()
