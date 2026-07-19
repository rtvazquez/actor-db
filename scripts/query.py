import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import connect


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
            p.role_type,
            l.name
        FROM Performances p
        JOIN Actors a ON p.actor_id = a.actor_id
        JOIN CharacterAppearances ca ON p.appearance_id = ca.appearance_id
        JOIN Characters c ON ca.character_id = c.character_id
        JOIN Works w ON ca.work_id = w.work_id
        LEFT JOIN Languages l ON p.language_id = l.language_id
        WHERE a.name = ?
        ORDER BY w.title;
    """, (name,)).fetchall()

    print(f"\n🎭 Actor: {name}")
    print("-" * 60)

    if not rows:
        print("No results found.")
        return

    for actor, character, work, role_type, lang in rows:
        lang_str = lang or "—"
        print(f"{actor} → {character} in {work} [{lang_str}] ({role_type})")


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
            p.role_type,
            l.name
        FROM Performances p
        JOIN Actors a ON p.actor_id = a.actor_id
        JOIN CharacterAppearances ca ON p.appearance_id = ca.appearance_id
        JOIN Characters c ON ca.character_id = c.character_id
        JOIN Works w ON ca.work_id = w.work_id
        LEFT JOIN Languages l ON p.language_id = l.language_id
        WHERE w.title = ?
        ORDER BY c.canonical_name;
    """, (title,)).fetchall()

    print(f"\n🎮 Work: {title}")
    print("-" * 60)

    if not rows:
        print("No results found.")
        return

    for work, character, actor, role_type, lang in rows:
        lang_str = lang or "—"
        print(f"{character} → {actor} [{lang_str}] ({role_type})")


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
            p.role_type,
            l.name
        FROM Performances p
        JOIN Actors a ON p.actor_id = a.actor_id
        JOIN CharacterAppearances ca ON p.appearance_id = ca.appearance_id
        JOIN Characters c ON ca.character_id = c.character_id
        JOIN Works w ON ca.work_id = w.work_id
        LEFT JOIN Languages l ON p.language_id = l.language_id
        WHERE c.canonical_name = ?
        ORDER BY w.title;
    """, (name,)).fetchall()

    print(f"\n🧍 Character: {name}")
    print("-" * 60)

    if not rows:
        print("No results found.")
        return

    for character, work, actor, role_type, lang in rows:
        lang_str = lang or "—"
        print(f"{character} → {actor} in {work} [{lang_str}] ({role_type})")


# -------------------------
# QUERY: STUDIO
# -------------------------
def query_studio(conn, name):
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT
            s.name,
            ws.studio_role,
            w.title,
            w.release_year,
            w.media_type
        FROM WorkStudios ws
        JOIN Studios s ON ws.studio_id = s.studio_id
        JOIN Works w ON ws.work_id = w.work_id
        WHERE s.name = ?
        ORDER BY w.release_year;
    """, (name,)).fetchall()

    print(f"\n🏢 Studio: {name}")
    print("-" * 60)

    if not rows:
        print("No results found.")
        return

    for studio, studio_role, title, year, media_type in rows:
        print(f"{title} ({year}) [{media_type}] — {studio_role}")


# -------------------------
# QUERY: FRANCHISE
# -------------------------
def query_franchise(conn, name):
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT
            w.title,
            w.release_year,
            w.media_type,
            pw.title,
            w.work_relationship_type
        FROM Works w
        JOIN Franchises f ON w.franchise_id = f.franchise_id
        LEFT JOIN Works pw ON w.parent_work_id = pw.work_id
        WHERE f.name = ?
        ORDER BY w.release_year;
    """, (name,)).fetchall()

    print(f"\n🌐 Franchise: {name}")
    print("-" * 60)

    if not rows:
        print("No results found.")
        return

    for title, year, media_type, parent_title, rel_type in rows:
        if parent_title:
            print(f"{title} ({year}) [{media_type}] — {rel_type} of {parent_title}")
        else:
            print(f"{title} ({year}) [{media_type}]")


# -------------------------
# QUERY: CO-STARS
# -------------------------
def query_costars(conn, name):
    """Other actors who share a work with the given actor, and which
    characters were involved on both sides."""
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT
            GROUP_CONCAT(DISTINCT c1.canonical_name) AS my_characters,
            a2.name,
            c2.canonical_name,
            w.title,
            w.release_year
        FROM Performances p1
        JOIN Actors a1 ON p1.actor_id = a1.actor_id
        JOIN CharacterAppearances ca1 ON p1.appearance_id = ca1.appearance_id
        JOIN Characters c1 ON ca1.character_id = c1.character_id
        JOIN Works w ON ca1.work_id = w.work_id
        JOIN CharacterAppearances ca2 ON ca2.work_id = w.work_id
        JOIN Performances p2 ON p2.appearance_id = ca2.appearance_id
        JOIN Actors a2 ON p2.actor_id = a2.actor_id
        JOIN Characters c2 ON ca2.character_id = c2.character_id
        WHERE a1.name = ? AND a2.actor_id != a1.actor_id
        GROUP BY a2.actor_id, c2.character_id, w.work_id
        ORDER BY w.release_year, a2.name;
    """, (name,)).fetchall()

    print(f"\n🤝 Co-stars of: {name}")
    print("-" * 60)

    if not rows:
        print("No results found.")
        return

    for my_characters, costar, costar_character, work, year in rows:
        print(f"{costar} as {costar_character} — {work} ({year}) [you: {my_characters}]")


# -------------------------
# MAIN CLI
# -------------------------
def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python query.py actor <name>")
        print("  python query.py work <title>")
        print("  python query.py character <name>")
        print("  python query.py studio <name>")
        print("  python query.py franchise <name>")
        print("  python query.py costars <actor name>")
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
    elif mode == "studio":
        query_studio(conn, value)
    elif mode == "franchise":
        query_franchise(conn, value)
    elif mode == "costars":
        query_costars(conn, value)
    else:
        print("Unknown mode. Use: actor | work | character | studio | franchise | costars")

    conn.close()


if __name__ == "__main__":
    main()
