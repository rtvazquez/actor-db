"""Pull credits from the archive back into the live database.

    python scripts/actordb.py readd search "<text>"     list matching archive credits (no changes)
    python scripts/actordb.py readd work "<title>"      re-add every credit of a work (all matching titles)
    python scripts/actordb.py readd franchise "<name>"  re-add every work/credit in a franchise
    python scripts/actordb.py readd actor "<name>"      re-add every credit of an actor
    options: --archive DIR  (default: newest folder in archive/)  --yes  (skip confirmation)

Matches are exact (case-insensitive) for work/franchise/actor; `search` is partial.
Re-adding is idempotent: credits already in the live DB are skipped. Work
metadata (franchise, studios, sequel links) comes along with each work.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import ROOT, connect
import db_ops
import export_json

SELECT = """
SELECT p.performance_id, a.name, a.native_name, a.birth_year, w.work_id, w.title, w.release_year,
       w.media_type, c.canonical_name, c.disambiguation, l.name, p.performance_type,
       p.role_type, p.source_url
FROM Performances p
JOIN Actors a ON a.actor_id = p.actor_id
JOIN CharacterAppearances ca ON ca.appearance_id = p.appearance_id
JOIN Characters c ON c.character_id = ca.character_id
JOIN Works w ON w.work_id = ca.work_id
LEFT JOIN Languages l ON l.language_id = p.language_id
LEFT JOIN Franchises f ON f.franchise_id = w.franchise_id
"""


def default_archive():
    dirs = sorted(p for p in (ROOT / "archive").iterdir() if (p / "voice_actors.db").exists())
    if not dirs:
        sys.exit("No archive found in archive/.")
    return dirs[-1]


def work_meta(arch, work_id):
    franchise = arch.execute(
        "SELECT f.name FROM Works w LEFT JOIN Franchises f ON f.franchise_id = w.franchise_id WHERE w.work_id = ?",
        (work_id,)).fetchone()[0]
    # Archive studio credits carry no source, and unsourced studio credits are not kept in the live DB.
    studios = []
    parent = arch.execute(
        "SELECT p.title, p.release_year, w.work_relationship_type FROM Works w JOIN Works p ON p.work_id = w.parent_work_id WHERE w.work_id = ?",
        (work_id,)).fetchone()
    return franchise, studios, parent


def rows_for(arch, mode, value):
    v = value.lower()
    where = {
        "search": ("lower(a.name) LIKE ? OR lower(c.canonical_name) LIKE ? OR lower(w.title) LIKE ?", (f"%{v}%",) * 3),
        "work": ("lower(w.title) = ?", (v,)),
        "franchise": ("lower(f.name) = ?", (v,)),
        "actor": ("lower(a.name) = ?", (v,)),
    }[mode]
    return arch.execute(SELECT + " WHERE " + where[0] + " ORDER BY w.title, w.release_year, c.canonical_name, l.name, a.name",
                        where[1]).fetchall()


def readd(arch, live, rows):
    """Copy archive credit rows into the live DB. Returns (added, skipped)."""
    added = skipped = 0
    parents = []
    for (_, actor, native, birth, wid, title, year, media, char, note, lang, ptype, rtype, src) in rows:
        franchise, studios, parent = work_meta(arch, wid)
        pid = db_ops.add_performance(
            live, actor=actor, work=title, year=year, media_type=media, character=char,
            character_note=note, language=lang, performance_type=ptype, role_type=rtype,
            source=src, birth_year=birth, native_name=native, franchise=franchise, studios=studios)
        added, skipped = (added + 1, skipped) if pid else (added, skipped + 1)
        if parent:
            parents.append((title, year, parent))
    # Sequel links last, so a parent re-added in the same batch resolves; otherwise it's skipped.
    from utils import find_work
    cur = live.cursor()
    for title, year, (ptitle, pyear, rel) in parents:
        child, par = find_work(cur, title, year), find_work(cur, ptitle, pyear)
        if child and par:
            cur.execute("UPDATE Works SET parent_work_id = ?, work_relationship_type = ? WHERE work_id = ?",
                        (par, rel, child))
    live.commit()
    return added, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description="Re-add credits from the archive")
    ap.add_argument("mode", choices=["search", "work", "franchise", "actor"])
    ap.add_argument("value", nargs="+")
    ap.add_argument("--archive")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)
    value = " ".join(args.value)

    arch_dir = Path(args.archive) if args.archive else default_archive()
    arch = sqlite3.connect(f"file:{arch_dir / 'voice_actors.db'}?mode=ro", uri=True)
    rows = rows_for(arch, args.mode, value)
    if not rows:
        print(f"No archive credits match {args.mode} '{value}'.")
        return 1

    works = sorted({(r[5], r[6]) for r in rows})
    print(f"{len(rows)} credit(s) across {len(works)} work(s) in {arch_dir.name}:")
    for r in rows[:60]:
        lang = f" ({r[10]})" if r[10] else ""
        print(f"  {r[1]} as {r[8]} in {r[5]} ({r[6]}){lang}")
    if len(rows) > 60:
        print(f"  ... and {len(rows) - 60} more")
    if args.mode == "search":
        return 0
    if not args.yes and input("Add these to the live database? [y/N]: ").strip().lower() != "y":
        print("Cancelled.")
        return 0

    live = connect()
    try:
        added, skipped = readd(arch, live, rows)
    finally:
        live.close()
    print(f"Added {added}, skipped {skipped} already present.")
    export_json.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
