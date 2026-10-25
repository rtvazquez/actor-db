"""Single entry point for all actor_db tasks. Works from any directory.

    python scripts/actordb.py <command> [args]

Commands:
  build [--force]   rebuild the DB from data/*.json, then the dashboard
                    (refuses if the DB has changes not in the JSON -- run export first)
  export            write the DB out to data/*.json (DB is the source of truth)
  dashboard         regenerate database/dashboard.html
  add / remove      interactive add / remove of roles
  check             consistency check of the JSON files (read-only)
  singles           report thin corners of the dataset (read-only)
  add-work <title> --year Y --type T [--favorite] [--watched]   add a work with no cast
  readd <mode> <name>   pull credits back from archive/ (search | work | franchise | actor)
  query <mode> <name>   actor | work | character | studio | franchise | costars
  menu              interactive menu
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import DB_PATH, VOICE_ROLES_PATH, WORK_METADATA_PATH


def _key(e):
    return (e["actor"], e["work"], e.get("year"), e["character"],
            e.get("character_note", ""), e.get("language"),
            e.get("performance_type", "Voice"))


def unexported_changes():
    """Compare DB vs data/*.json. Returns (db_only, json_only) sets of comparable keys;
    a non-empty db_only means a rebuild would lose something."""
    import export_json
    from utils import connect, USER_FLAGS_PATH
    conn = connect()
    try:
        db = {("perf",) + _key(e) for e in export_json.export_roles(conn)}
        db |= {("work", e["title"], e["year"], e["media_type"], e.get("franchise")) for e in export_json.export_metadata(conn)}
        flags = export_json.export_flags(conn)
    finally:
        conn.close()
    js = {("perf",) + _key(e) for e in json.loads(VOICE_ROLES_PATH.read_text(encoding="utf-8"))}
    js |= {("work", e["title"], e["year"], e.get("media_type"), e.get("franchise"))
           for e in json.loads(WORK_METADATA_PATH.read_text(encoding="utf-8"))}
    saved = json.loads(USER_FLAGS_PATH.read_text(encoding="utf-8")) if USER_FLAGS_PATH.exists() else {}
    def flat(f):
        return ({("fav", k, n) for k, v in f.get("favorites", {}).items() for n in v}
                | {("watched", n) for n in f.get("watched", [])})
    return (db | flat(flags)) - (js | flat(saved)), (js | flat(saved)) - (db | flat(flags))


def build(force=False):
    if DB_PATH.exists() and not force:
        db_only, json_only = unexported_changes()
        # Anything only in the DB would be lost. Anything only in the JSON is normal after a hand
        # edit of the JSON -- unless the DB is newer than the JSON, meaning the DB was edited
        # (e.g. an un-favorite or delete via SQL) and the JSON snapshot is stale.
        db_newer = DB_PATH.stat().st_mtime > max(p.stat().st_mtime for p in (VOICE_ROLES_PATH, WORK_METADATA_PATH))
        if db_only or (json_only and db_newer):
            db_only = db_only or json_only
            print(f"Refusing to rebuild: the database has {len(db_only)} change(s) "
                  "(credits, works or favorite/watched flags) that are not in data/*.json (they'd be lost).")
            print("Run `actordb.py export` first, or pass --force to discard them.")
            return 1
    import create_db, import_data, generate_dashboard
    create_db.create_database()
    import_data.run()
    generate_dashboard.generate()
    return 0


def menu():
    items = [("Add a role", ["add"]), ("Remove roles", ["remove"]),
             ("Consistency check", ["check"]), ("Singles report", ["singles"]),
             ("Export DB to JSON", ["export"]), ("Rebuild DB + dashboard", ["build"])]
    while True:
        print("\n=== actor_db ===")
        for i, (label, _) in enumerate(items, 1):
            print(f"  {i}) {label}")
        print("  q) Quit")
        c = input("Choice: ").strip().lower()
        if c in ("q", ""):
            return 0
        if c.isdigit() and 1 <= int(c) <= len(items):
            main(items[int(c) - 1][1])
        else:
            print("Invalid choice.")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "build":
        return build("--force" in rest)
    if cmd == "export":
        import export_json
        export_json.run()
    elif cmd == "dashboard":
        import generate_dashboard
        generate_dashboard.generate()
    elif cmd == "add":
        import add_role
        add_role.main()
    elif cmd == "remove":
        import remove_role
        remove_role.main()
    elif cmd == "check":
        import check_consistency
        check_consistency.run()
    elif cmd == "singles":
        import check_singles
        check_singles.run()
    elif cmd == "add-work":
        import argparse, db_ops, export_json
        from utils import connect
        ap = argparse.ArgumentParser(prog="actordb.py add-work")
        ap.add_argument("title"); ap.add_argument("--year", type=int, required=True)
        ap.add_argument("--type", required=True, dest="media",
                        choices=["Video Game", "Anime", "TV Series", "Movie", "OVA", "Other"])
        ap.add_argument("--favorite", action="store_true"); ap.add_argument("--watched", action="store_true")
        a = ap.parse_args(rest)
        conn = connect()
        try:
            db_ops.add_work(conn, a.title, a.year, a.media, a.favorite, a.watched)
        finally:
            conn.close()
        export_json.run()
    elif cmd == "readd":
        import readd
        return readd.main(rest)
    elif cmd == "query":
        import query
        sys.argv = ["query.py"] + rest
        query.main()
    elif cmd == "menu":
        return menu()
    else:
        print(f"Unknown command: {cmd}\n{__doc__}")
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
