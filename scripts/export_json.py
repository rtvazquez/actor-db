"""Export the database back to data/voice_roles.json + data/work_metadata.json.

The database is the source of truth; these JSON files are a diffable
snapshot / seed. Output ordering is deterministic so git diffs stay small.

    python scripts/export_json.py [--out DIR]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import connect, VOICE_ROLES_PATH, WORK_METADATA_PATH, USER_FLAGS_PATH, ACTOR_ALIASES_PATH


def export_roles(conn):
    rows = conn.execute(
        """
        SELECT a.name, a.native_name, a.birth_year, w.title, w.release_year,
               c.canonical_name, c.disambiguation, l.name, w.media_type,
               p.performance_type, p.role_type, p.source_url, p.verified
        FROM Performances p
        JOIN Actors a ON a.actor_id = p.actor_id
        JOIN CharacterAppearances ca ON ca.appearance_id = p.appearance_id
        JOIN Characters c ON c.character_id = ca.character_id
        JOIN Works w ON w.work_id = ca.work_id
        LEFT JOIN Languages l ON l.language_id = p.language_id
        ORDER BY w.title, w.release_year, c.canonical_name, c.disambiguation,
                 l.name, a.name, p.performance_type
        """
    ).fetchall()
    out = []
    for (actor, native, birth, work, year, char, note, lang, media,
         ptype, rtype, src, verified) in rows:
        e = {"actor": actor}
        if native:
            e["native_name"] = native
        e["birth_year"] = birth
        e.update({"work": work, "year": year, "character": char})
        if note:
            e["character_note"] = note
        e.update({"language": lang, "media_type": media, "performance_type": ptype})
        if rtype and rtype != "Main":
            e["role_type"] = rtype
        if src:
            e["source"] = src
        if bool(verified) != bool(src):
            e["verified"] = bool(verified)  # e.g. a source URL taken from a search snippet but not read
        out.append(e)
    return out


def export_metadata(conn):
    works = conn.execute(
        """
        SELECT w.work_id, w.title, w.release_year, f.name, w.parent_work_id,
               w.work_relationship_type, w.media_type
        FROM Works w LEFT JOIN Franchises f ON f.franchise_id = w.franchise_id
        ORDER BY w.title, w.release_year
        """
    ).fetchall()
    ident = {r[0]: (r[1], r[2]) for r in works}
    out = []
    for wid, title, year, franchise, parent, rel, media in works:
        studios = [
            ({"name": n, "role": r, "source": src} if src else {"name": n, "role": r})
            for n, r, src in conn.execute(
                """SELECT s.name, ws.studio_role, ws.source_url FROM WorkStudios ws
                   JOIN Studios s ON s.studio_id = ws.studio_id
                   WHERE ws.work_id = ? ORDER BY ws.studio_role, s.name""",
                (wid,),
            )
        ]
        e = {"title": title, "year": year, "media_type": media}
        if franchise:
            e["franchise"] = franchise
        if studios:
            e["studios"] = studios
        if parent:
            e["parent_work"] = {"title": ident[parent][0], "year": ident[parent][1]}
            e["relationship_type"] = rel
        out.append(e)
    return out


def export_flags(conn):
    """Favorites (per entity type, by name) and watched works."""
    q = lambda sql: [r[0] for r in conn.execute(sql)]
    return {
        "favorites": {
            "actors": q("SELECT name FROM Actors WHERE favorite = 1 ORDER BY name"),
            "works": q("SELECT title FROM Works WHERE favorite = 1 ORDER BY title"),
            "characters": q("SELECT canonical_name FROM Characters WHERE favorite = 1 ORDER BY canonical_name"),
            "studios": q("SELECT name FROM Studios WHERE favorite = 1 ORDER BY name"),
            "franchises": q("SELECT name FROM Franchises WHERE favorite = 1 ORDER BY name"),
        },
        "watched": q("SELECT title FROM Works WHERE watched = 1 ORDER BY title"),
    }


def export_aliases(conn):
    out = {}
    for name, alias in conn.execute(
        "SELECT a.name, al.alias FROM ActorAliases al JOIN Actors a ON a.actor_id = al.actor_id ORDER BY a.name, al.alias"
    ):
        out.setdefault(name, []).append(alias)
    return out


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(data)} entries to {path}")


def run(out_dir=None):
    roles_path = Path(out_dir) / VOICE_ROLES_PATH.name if out_dir else VOICE_ROLES_PATH
    meta_path = Path(out_dir) / WORK_METADATA_PATH.name if out_dir else WORK_METADATA_PATH
    conn = connect()
    try:
        write(roles_path, export_roles(conn))
        write(meta_path, export_metadata(conn))
        flags = export_flags(conn)
        aliases = export_aliases(conn)
        al_path = (Path(out_dir) / ACTOR_ALIASES_PATH.name) if out_dir else ACTOR_ALIASES_PATH
        al_path.write_text(json.dumps(aliases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        flags_path = (Path(out_dir) / USER_FLAGS_PATH.name) if out_dir else USER_FLAGS_PATH
        flags_path.write_text(json.dumps(flags, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote flags to {flags_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", help="write here instead of data/")
    run(ap.parse_args().out)
