"""
Builds database/dashboard.html -- a self-contained, offline GUI for browsing
the database (no server; just open the file in a browser).

The UI source lives in dashboard/ as real files you can lint and edit:
    dashboard/template.html   page skeleton (sidebar, filter bar)
    dashboard/style.css       styles
    dashboard/app.js          all behavior
This script queries the database and inlines those three files plus the data
into one HTML file. Re-run it after any data or UI change:

    python scripts/actordb.py dashboard
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import connect, DASHBOARD_PATH, ROOT

UI_DIR = ROOT / "dashboard"

OUTPUT_PATH = DASHBOARD_PATH


def build_data():
    conn = connect()
    cur = conn.cursor()

    def col(table, name, fallback):
        # Older databases (e.g. the archive) may predate a column; use a fallback expression.
        return name if name in {r[1] for r in cur.execute(f"PRAGMA table_info({table})")} else fallback

    actors = {}
    for actor_id, name, birth_year, native_name in cur.execute(
        f"SELECT actor_id, name, birth_year, {col('Actors', 'native_name', 'NULL')} FROM Actors ORDER BY name"
    ):
        actors[actor_id] = {"id": actor_id, "name": name, "birth_year": birth_year,
                            "native_name": native_name, "roles": []}

    works = {}
    for row in cur.execute("""
        SELECT w.work_id, w.title, w.release_year, w.media_type,
               f.name, pw.title, w.work_relationship_type
        FROM Works w
        LEFT JOIN Franchises f ON w.franchise_id = f.franchise_id
        LEFT JOIN Works pw ON w.parent_work_id = pw.work_id
        ORDER BY w.title
    """):
        work_id, title, year, media_type, franchise, parent_title, rel_type = row
        works[work_id] = {
            "id": work_id, "title": title, "year": year, "media_type": media_type,
            "franchise": franchise, "parent_title": parent_title, "relationship_type": rel_type,
            "studios": [], "cast": [],
        }

    studio_src_col = "ws.source_url" if col("WorkStudios", "source_url", None) else "NULL"
    for work_id, studio_name, studio_role, studio_src in cur.execute(f"""
        SELECT ws.work_id, s.name, ws.studio_role, {studio_src_col}
        FROM WorkStudios ws JOIN Studios s ON ws.studio_id = s.studio_id
        ORDER BY s.name
    """):
        works[work_id]["studios"].append({"name": studio_name, "role": studio_role, "source": studio_src})

    characters = {}
    for char_id, name in cur.execute(
        "SELECT character_id, canonical_name FROM Characters ORDER BY canonical_name"
    ):
        characters[char_id] = {"id": char_id, "name": name, "appearances": []}

    studios = {}
    for studio_id, name in cur.execute(
        "SELECT studio_id, name FROM Studios ORDER BY name"
    ):
        studios[studio_id] = {"id": studio_id, "name": name, "works": []}
    for studio_id, work_id, studio_role in cur.execute("SELECT studio_id, work_id, studio_role FROM WorkStudios"):
        w = works[work_id]
        studios[studio_id]["works"].append({
            "title": w["title"], "year": w["year"], "media_type": w["media_type"], "role": studio_role,
        })

    franchises = {}
    for franchise_id, name in cur.execute("SELECT franchise_id, name FROM Franchises ORDER BY name"):
        franchises[franchise_id] = {"id": franchise_id, "name": name, "works": []}
    for row in cur.execute("""
        SELECT w.franchise_id, w.title, w.release_year, w.media_type, pw.title, w.work_relationship_type
        FROM Works w LEFT JOIN Works pw ON w.parent_work_id = pw.work_id
        WHERE w.franchise_id IS NOT NULL
        ORDER BY w.release_year
    """):
        franchise_id, title, year, media_type, parent_title, rel_type = row
        franchises[franchise_id]["works"].append({
            "title": title, "year": year, "media_type": media_type,
            "parent_title": parent_title, "relationship_type": rel_type,
        })

    # Performances tie everything together. Cast/appearances are grouped so
    # that an English + Japanese performance of the same role in the same
    # work count as ONE appearance/cast slot, not two -- with both actors
    # shown side by side within it.
    work_cast_groups = {}    # work_id -> {character_id: group}
    char_appear_groups = {}  # character_id -> {work_id: group}

    for row in cur.execute(f"""
        SELECT p.actor_id, ca.work_id, c.character_id, c.canonical_name,
               l.name, p.role_type, p.performance_type, p.source_url, {"p.verified" if col("Performances", "verified", None) else "0"}
        FROM Performances p
        JOIN CharacterAppearances ca ON p.appearance_id = ca.appearance_id
        JOIN Characters c ON ca.character_id = c.character_id
        LEFT JOIN Languages l ON p.language_id = l.language_id
    """):
        actor_id, work_id, char_id, char_name, lang, role_type, perf_type, source_url, verified = row
        w = works[work_id]
        a = actors[actor_id]

        perf_entry = {
            "actor": a["name"], "actor_id": actor_id, "language": lang,
            "role_type": role_type, "performance_type": perf_type, "source": source_url,
            "verified": bool(verified),
        }

        a["roles"].append({
            "character": char_name, "character_id": char_id, "work": w["title"], "work_id": work_id,
            "work_year": w["year"], "media_type": w["media_type"], "language": lang,
            "role_type": role_type, "performance_type": perf_type, "source": source_url,
            "verified": bool(verified),
        })

        wc = work_cast_groups.setdefault(work_id, {})
        cg = wc.setdefault(char_id, {"character": char_name, "character_id": char_id, "performances": []})
        cg["performances"].append(perf_entry)

        cag = char_appear_groups.setdefault(char_id, {})
        wg = cag.setdefault(work_id, {
            "work": w["title"], "work_id": work_id, "work_year": w["year"], "media_type": w["media_type"],
            "performances": [],
        })
        wg["performances"].append(perf_entry)

    for work_id, groups in work_cast_groups.items():
        works[work_id]["cast"] = sorted(groups.values(), key=lambda g: g["character"])

    for char_id, groups in char_appear_groups.items():
        characters[char_id]["appearances"] = sorted(groups.values(), key=lambda g: (g["work_year"] or 0))

    def flagged(table, col, flag):
        # Older databases (e.g. the archive) predate the favorite/watched columns.
        have = {r[1] for r in cur.execute(f"PRAGMA table_info({table})")}
        if flag not in have:
            return []
        return [r[0] for r in cur.execute(f"SELECT {col} FROM {table} WHERE {flag} = 1")]

    flags = {
        "favorites": {
            "actors": flagged("Actors", "name", "favorite"),
            "works": flagged("Works", "title", "favorite"),
            "characters": flagged("Characters", "canonical_name", "favorite"),
            "studios": flagged("Studios", "name", "favorite"),
            "franchises": flagged("Franchises", "name", "favorite"),
        },
        "watched": flagged("Works", "title", "watched"),
    }
    media_types = [r[0] for r in cur.execute("SELECT DISTINCT media_type FROM Works ORDER BY media_type")]
    conn.close()

    return {
        "actors": sorted(actors.values(), key=lambda x: x["name"]),
        "works": sorted(works.values(), key=lambda x: x["title"]),
        "characters": sorted(characters.values(), key=lambda x: x["name"]),
        "studios": sorted(studios.values(), key=lambda x: x["name"]),
        "franchises": sorted(franchises.values(), key=lambda x: x["name"]),
        "media_types": media_types,
        "flags": flags,
    }


def render(data):
    read = lambda name: (UI_DIR / name).read_text(encoding="utf-8")
    js = read("app.js").replace("/*__DATA__*/null", json.dumps(data), 1)
    return (read("template.html")
            .replace("/*__STYLE__*/", read("style.css"), 1)
            .replace("/*__SCRIPT__*/", js, 1))


def generate():
    OUTPUT_PATH.write_text(render(build_data()), encoding="utf-8")
    print(f"Dashboard written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    generate()
