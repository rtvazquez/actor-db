"""
Interactive helper for adding a new actor/character/work/language entry
straight into the database (the source of truth), then exporting the JSON
snapshot and optionally regenerating the dashboard.

    python scripts/add_role.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import connect
import db_ops
import export_json


MEDIA_TYPES = ["Video Game", "Anime", "TV Series", "Movie", "OVA", "Other"]
ROLE_TYPES = ["Main", "Supporting", "Minor", "Cameo"]
STUDIO_ROLES = ["Developer", "Publisher", "Animation Studio", "Localization Studio", "Distributor", "Production"]


def ask(prompt, default=None, choices=None):
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        if not raw and default is None and choices is None:
            return ""
        if choices and raw and raw not in choices:
            print(f"  Please choose one of: {', '.join(choices)}")
            continue
        return raw


def ask_int(prompt, default=None):
    raw = ask(prompt, default=str(default) if default is not None else None)
    return int(raw) if raw else None


def ask_yes_no(prompt, default_yes=True):
    suffix = " [Y/n]" if default_yes else " [y/N]"
    raw = input(f"{prompt}{suffix}: ").strip().lower()
    if not raw:
        return default_yes
    return raw.startswith("y")


def known_actor_names():
    conn = connect()
    names = [r[0] for r in conn.execute("SELECT name FROM Actors ORDER BY name")]
    conn.close()
    return names


def known_work_titles():
    conn = connect()
    rows = conn.execute("SELECT title, release_year FROM Works ORDER BY title").fetchall()
    conn.close()
    return rows


def main():
    print("=== Add a new performance to actor_db ===\n")

    actors = known_actor_names()
    actor = ask("Actor name")
    is_new_actor = actor not in actors
    birth_year = None
    if is_new_actor:
        print(f"  (new actor -- not currently in the database)")
        birth_year = ask_int("Birth year (blank if unknown)")
    else:
        print(f"  (found existing actor: {actor})")

    print()
    works = known_work_titles()
    work = ask("Work title")
    matching = [w for w in works if w[0] == work]
    is_new_work = not matching
    year = None
    media_type = None
    franchise = None
    studios = []
    parent_work = None
    relationship_type = None

    if is_new_work:
        print("  (new work -- not currently in the database)")
        year = ask_int("Release year")
        media_type = ask("Media type", default="Video Game", choices=MEDIA_TYPES)
        if ask_yes_no("Does this belong to a franchise?", default_yes=False):
            franchise = ask("Franchise name")
        if ask_yes_no("Add a studio credit (developer/publisher/animation studio)?", default_yes=False):
            while True:
                studio_name = ask("  Studio name")
                studio_role = ask("  Studio role", default="Developer", choices=STUDIO_ROLES)
                studios.append({"name": studio_name, "role": studio_role})
                if not ask_yes_no("  Add another studio credit?", default_yes=False):
                    break
        if ask_yes_no("Is this a sequel/remake/spin-off of a work already in the database?", default_yes=False):
            parent_work = ask("  Parent work title")
            parent_year = ask_int("  Parent work release year (blank if unsure)")
            relationship_type = ask(
                "  Relationship type", default="Sequel",
                choices=["Sequel", "Prequel", "Spin-off", "Remake", "Remaster", "Side Story"],
            )
            parent_work = {"title": parent_work, "year": parent_year}
    else:
        if len(matching) > 1:
            print("  Multiple releases with this title found:")
            for _, y in matching:
                print(f"    - {work} ({y})")
            year = ask_int("  Which release year?")
        else:
            year = matching[0][1]
            print(f"  (found existing work: {work} ({year}))")
        media_type = None  # unchanged, already set on the existing row

    print()
    character = ask("Character name")
    language = ask("Language (blank for none, e.g. live-action)", default="English")
    if language == "":
        language = None
    role_type = ask("Role type", default="Main", choices=ROLE_TYPES)

    entry = {
        "actor": actor,
        "birth_year": birth_year,
        "work": work,
        "year": year,
        "character": character,
        "language": language,
    }
    if is_new_work:
        entry["media_type"] = media_type

    print("\nAbout to add:")
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    if not ask_yes_no("Add this entry?", default_yes=True):
        print("Cancelled.")
        return

    conn = connect()
    try:
        pid = db_ops.add_performance(
            conn, actor=actor, work=work, character=character, year=year,
            language=language, media_type=media_type, role_type=role_type,
            birth_year=birth_year, franchise=franchise, studios=studios,
            parent_work=parent_work, relationship_type=relationship_type,
        )
    finally:
        conn.close()
    if pid is None:
        print("That exact performance already exists -- nothing added.")
        return
    print("Added to the database.")

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
