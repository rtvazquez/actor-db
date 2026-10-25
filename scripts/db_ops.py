"""Database-level add / search / delete operations (the DB is the source of truth).

Interactive scripts (add_role.py, remove_role.py) are thin wrappers around these.
"""

from utils import (
    get_or_create_actor, get_or_create_appearance, get_or_create_character,
    get_or_create_franchise, get_or_create_language, get_or_create_studio,
    get_or_create_work, find_work,
)


def add_performance(conn, *, actor, work, character, year=None, language="English",
                    media_type=None, performance_type="Voice", role_type="Main",
                    source=None, verified=None, birth_year=None, native_name=None,
                    character_note="", franchise=None, studios=(),
                    parent_work=None, relationship_type=None):
    """Insert one performance (creating actor/work/character as needed).

    Returns the new performance_id, or None if an identical one already exists.
    Work metadata (franchise/studios/parent) is only applied when given.
    """
    cur = conn.cursor()
    actor_id = get_or_create_actor(cur, actor, birth_year)
    if native_name:
        cur.execute("UPDATE Actors SET native_name = ? WHERE actor_id = ? AND native_name IS NULL",
                    (native_name, actor_id))
    work_id = get_or_create_work(cur, work, year, media_type or "Other")
    character_id = get_or_create_character(cur, character, character_note)
    language_id = get_or_create_language(cur, language)
    appearance_id = get_or_create_appearance(cur, character_id, work_id)

    if cur.execute(
        """SELECT 1 FROM Performances WHERE appearance_id = ? AND actor_id = ?
           AND language_id IS ? AND performance_type = ?""",
        (appearance_id, actor_id, language_id, performance_type),
    ).fetchone():
        return None

    cur.execute(
        """INSERT INTO Performances (appearance_id, actor_id, language_id, performance_type,
                                     role_type, source_url, verified)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (appearance_id, actor_id, language_id, performance_type, role_type,
         source, (1 if source else 0) if verified is None else (1 if verified else 0)),
    )
    pid = cur.lastrowid

    franchise_id = get_or_create_franchise(cur, franchise)
    if franchise_id is not None:
        cur.execute("UPDATE Works SET franchise_id = ? WHERE work_id = ?", (franchise_id, work_id))
    for s in studios:
        sid = get_or_create_studio(cur, s["name"])
        cur.execute("INSERT OR IGNORE INTO WorkStudios (work_id, studio_id, studio_role, source_url) VALUES (?, ?, ?, ?)",
                    (work_id, sid, s["role"], s.get("source")))
    if parent_work:
        parent_id = find_work(cur, parent_work["title"], parent_work.get("year"))
        if parent_id is not None:
            cur.execute("UPDATE Works SET parent_work_id = ?, work_relationship_type = ? WHERE work_id = ?",
                        (parent_id, relationship_type, work_id))
    conn.commit()
    return pid


def add_work(conn, title, year, media_type, favorite=False, watched=False):
    """Create a work with no cast (or update flags if it already exists). Returns work_id."""
    cur = conn.cursor()
    work_id = get_or_create_work(cur, title, year, media_type)
    cur.execute("UPDATE Works SET favorite = ?, watched = ? WHERE work_id = ?",
                (1 if favorite else 0, 1 if watched else 0, work_id))
    conn.commit()
    return work_id


def search_performances(conn, query):
    """Partial, case-insensitive match on actor, character, or work title."""
    q = f"%{query.lower()}%"
    rows = conn.execute(
        """SELECT p.performance_id, a.name, c.canonical_name, w.title, w.release_year,
                  l.name, p.performance_type
           FROM Performances p
           JOIN Actors a ON a.actor_id = p.actor_id
           JOIN CharacterAppearances ca ON ca.appearance_id = p.appearance_id
           JOIN Characters c ON c.character_id = ca.character_id
           JOIN Works w ON w.work_id = ca.work_id
           LEFT JOIN Languages l ON l.language_id = p.language_id
           WHERE lower(a.name) LIKE ? OR lower(c.canonical_name) LIKE ? OR lower(w.title) LIKE ?
           ORDER BY w.title, w.release_year, c.canonical_name, l.name, a.name""",
        (q, q, q),
    ).fetchall()
    keys = ("id", "actor", "character", "work", "year", "language", "performance_type")
    return [dict(zip(keys, r)) for r in rows]


def delete_performances(conn, ids):
    """Delete performances, then clean up rows left with nothing attached.

    Auto-removes empty appearances, characters, actors, studios' links and franchises.
    Works left with no cast are NOT deleted; they're returned so the caller can ask.
    Returns {"deleted": n, "removed": {table: n}, "empty_works": [(work_id, title, year)]}.
    """
    ids = list(ids)
    cur = conn.cursor()
    # Remember which works these credits belong to; only those can become newly "empty".
    touched = {r[0] for i in ids for r in cur.execute(
        """SELECT ca.work_id FROM Performances p JOIN CharacterAppearances ca
           ON ca.appearance_id = p.appearance_id WHERE p.performance_id = ?""", (i,))}
    cur.executemany("DELETE FROM Performances WHERE performance_id = ?", [(i,) for i in ids])
    removed = {}

    def rm(label, sql):
        cur.execute(sql)
        removed[label] = cur.rowcount

    rm("appearances", """DELETE FROM CharacterAppearances WHERE appearance_id NOT IN
                         (SELECT appearance_id FROM Performances)""")
    rm("characters", """DELETE FROM Characters WHERE character_id NOT IN
                        (SELECT character_id FROM CharacterAppearances)""")
    rm("actors", "DELETE FROM Actors WHERE actor_id NOT IN (SELECT actor_id FROM Performances)")
    rm("franchises", "DELETE FROM Franchises WHERE franchise_id NOT IN "
                     "(SELECT franchise_id FROM Works WHERE franchise_id IS NOT NULL)")
    empty = [r for r in cur.execute(
        """SELECT work_id, title, release_year FROM Works
           WHERE work_id NOT IN (SELECT work_id FROM CharacterAppearances)"""
    ) if r[0] in touched]
    conn.commit()
    return {"deleted": len(ids), "removed": {k: v for k, v in removed.items() if v}, "empty_works": empty}


def delete_works(conn, work_ids):
    """Delete works (cascades to links), then drop now-unused studios and franchises."""
    cur = conn.cursor()
    cur.executemany("DELETE FROM Works WHERE work_id = ?", [(w,) for w in work_ids])
    cur.execute("DELETE FROM Studios WHERE studio_id NOT IN (SELECT studio_id FROM WorkStudios)")
    cur.execute("DELETE FROM Franchises WHERE franchise_id NOT IN "
                "(SELECT franchise_id FROM Works WHERE franchise_id IS NOT NULL)")
    conn.commit()
