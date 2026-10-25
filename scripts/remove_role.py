"""
Interactive helper for finding and removing performances directly from the
database (the source of truth), cleaning up anything left orphaned, then
exporting the JSON snapshot and optionally regenerating the dashboard.

Search by actor, character, or work title (partial, case-insensitive);
review the matches; pick which to delete; confirm.

    python scripts/remove_role.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import connect
import db_ops
import export_json


def ask_yes_no(prompt, default_yes=True):
    suffix = " [Y/n]" if default_yes else " [y/N]"
    raw = input(f"{prompt}{suffix}: ").strip().lower()
    if not raw:
        return default_yes
    return raw.startswith("y")


def describe(e):
    lang = f" ({e['language']})" if e.get("language") else ""
    perf = e.get("performance_type")
    perf_tag = f" -- {perf}" if perf and perf != "Voice" else ""
    return f"{e['actor']} as {e['character']} in {e['work']} ({e['year']}){lang}{perf_tag}"


def parse_selection(raw, n):
    """Parses '1,3-5,8' or 'all' into a set of 0-based indices, bounded to
    [0, n). Raises ValueError on unparseable input."""
    raw = raw.strip().lower()
    if raw == "all":
        return set(range(n))
    indices = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            indices.update(range(int(a) - 1, int(b)))
        else:
            indices.add(int(part) - 1)
    return {i for i in indices if 0 <= i < n}


def main():
    print("=== Remove roles from actor_db ===\n")
    conn = connect()
    any_deleted = False

    try:
        while True:
            query = input("Search actor / character / work (blank to finish): ").strip()
            if not query:
                break

            matches = db_ops.search_performances(conn, query)
            if not matches:
                print("  No matches.\n")
                continue

            print(f"\n  {len(matches)} match(es):")
            for n, e in enumerate(matches, start=1):
                print(f"    [{n}] {describe(e)}")

            raw = input("\nDelete which? (e.g. '1,3', '2-4', 'all', blank to search again): ").strip()
            if not raw:
                print()
                continue
            try:
                selected = parse_selection(raw, len(matches))
            except ValueError:
                print("  Couldn't parse that -- try again.\n")
                continue
            if not selected:
                print("  Nothing selected.\n")
                continue

            to_delete = [matches[i] for i in sorted(selected)]
            print("\nAbout to permanently remove:")
            for e in to_delete:
                print(f"    - {describe(e)}")
            if not ask_yes_no("Confirm delete?", default_yes=False):
                print("Cancelled.\n")
                continue

            report = db_ops.delete_performances(conn, [e["id"] for e in to_delete])
            any_deleted = True
            print(f"Removed {report['deleted']} performance(s).")
            if report["removed"]:
                print("  Also cleaned up: " + ", ".join(f"{v} {k}" for k, v in report["removed"].items()))
            if report["empty_works"]:
                print(f"  {len(report['empty_works'])} work(s) now have no cast:")
                for _, title, year in report["empty_works"]:
                    print(f"    - {title} ({year})")
                if ask_yes_no("  Remove them too?", default_yes=True):
                    db_ops.delete_works(conn, [w[0] for w in report["empty_works"]])
                    print("  Removed.")
            print()
    finally:
        conn.close()

    if not any_deleted:
        print("Nothing removed.")
        return

    export_json.run()
    if ask_yes_no("Regenerate the dashboard now?", default_yes=True):
        import generate_dashboard
        generate_dashboard.generate()
    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
