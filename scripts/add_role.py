"""
Interactive helper for adding a new actor/character/work/language entry
to data/voice_roles.json (and, if the work is new, data/work_metadata.json)
without hand-editing JSON.

Run it, answer the prompts, and at the end it offers to rebuild the
database and regenerate the dashboard for you.

    python scripts/add_role.py
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import connect

VOICE_ROLES_PATH = Path("data/voice_roles.json")
WORK_METADATA_PATH = Path("data/work_metadata.json")

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

    # Append to voice_roles.json
    roles = json.loads(VOICE_ROLES_PATH.read_text(encoding="utf-8"))
    roles.append(entry)
    VOICE_ROLES_PATH.write_text(json.dumps(roles, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Appended to {VOICE_ROLES_PATH}")

    # Append/update work_metadata.json if this work is new and has metadata
    if is_new_work and (franchise or studios or parent_work):
        metadata = json.loads(WORK_METADATA_PATH.read_text(encoding="utf-8"))
        meta_entry = {"title": work, "year": year}
        if franchise:
            meta_entry["franchise"] = franchise
        if studios:
            meta_entry["studios"] = studios
        if parent_work:
            meta_entry["parent_work"] = parent_work
            meta_entry["relationship_type"] = relationship_type
        metadata.append(meta_entry)
        WORK_METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Appended to {WORK_METADATA_PATH}")

    if ask_yes_no("\nRebuild the database now?", default_yes=True):
        subprocess.run([sys.executable, "scripts/create_db.py"], check=True)
        subprocess.run([sys.executable, "scripts/import_data.py"], check=True)
        if ask_yes_no("Regenerate the dashboard too?", default_yes=True):
            subprocess.run([sys.executable, "scripts/generate_dashboard.py"], check=True)
        print("\nDone.")
    else:
        print("\nSkipped rebuild -- run `python scripts/create_db.py && python scripts/import_data.py` when ready.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
