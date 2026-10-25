"""
Reports "singleton" actors/works/studios -- not data errors (see
check_consistency.py for those), just candidates worth a human glance
since they're the thinnest, most easily-fragmented parts of the dataset.
Read-only -- prints a report, changes nothing.

Categories:
  1. Actors with exactly 1 role in the whole database.
  2. Actors who appear in only 1 distinct work (may have >1 role there,
     e.g. two characters or two languages in that one work).
  3. Works with only 1 performance row recorded.
  4. Works with only 1 distinct actor credited (may have >1 row, e.g. the
     same actor across two languages for one character).
  5. Studios credited on only 1 work.

Run any time you want a fresh list to review:
    python scripts/check_singles.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import ROOT, VOICE_ROLES_PATH, WORK_METADATA_PATH

VR_PATH = VOICE_ROLES_PATH
WM_PATH = WORK_METADATA_PATH


def load():
    with open(VR_PATH, encoding="utf-8") as f:
        vr = json.load(f)
    with open(WM_PATH, encoding="utf-8") as f:
        wm = json.load(f)
    return vr, wm


def describe_row(e):
    lang = f" ({e['language']})" if e.get("language") else ""
    return f"{e.get('actor')} as {e.get('character')}{lang}"


def single_role_actors(vr):
    """Actors with exactly 1 performance row total, grouped by work."""
    counts = defaultdict(int)
    for e in vr:
        counts[e.get("actor")] += 1
    singles = {a for a, c in counts.items() if c == 1}

    by_work = defaultdict(list)
    for e in vr:
        if e.get("actor") in singles:
            by_work[(e.get("work"), e.get("year"))].append(e)
    return singles, by_work


def single_work_actors(vr, already_single_role):
    """Actors credited in only 1 distinct work, excluding ones already
    caught by single_role_actors (those are a strict subset -- this finds
    actors with >1 role that are all bunched into the same one work,
    e.g. two characters or a dual-language role)."""
    works_by_actor = defaultdict(set)
    rows_by_actor = defaultdict(list)
    for e in vr:
        works_by_actor[e.get("actor")].add((e.get("work"), e.get("year")))
        rows_by_actor[e.get("actor")].append(e)
    result = {}
    for actor, works in works_by_actor.items():
        if len(works) == 1 and actor not in already_single_role:
            result[actor] = rows_by_actor[actor]
    return result


def single_row_works(vr):
    """Works with exactly 1 performance row recorded at all."""
    by_work = defaultdict(list)
    for e in vr:
        by_work[(e.get("work"), e.get("year"))].append(e)
    return {k: v for k, v in by_work.items() if len(v) == 1}


def single_actor_works(vr, already_single_row):
    """Works credited to only 1 distinct actor, excluding ones already
    caught by single_row_works (this finds works with >1 row but all from
    the same one actor -- e.g. dual-cast or dual-language by one person)."""
    actors_by_work = defaultdict(set)
    rows_by_work = defaultdict(list)
    for e in vr:
        key = (e.get("work"), e.get("year"))
        actors_by_work[key].add(e.get("actor"))
        rows_by_work[key].append(e)
    result = {}
    for work, actors in actors_by_work.items():
        if len(actors) == 1 and work not in already_single_row:
            result[work] = rows_by_work[work]
    return result


def single_work_studios(wm):
    """Studios credited on only 1 work in work_metadata.json."""
    works_by_studio = defaultdict(list)
    for w in wm:
        for s in w.get("studios", []):
            works_by_studio[s.get("name")].append((w.get("title"), w.get("year")))
    return {s: works for s, works in works_by_studio.items() if len(works) == 1}


def run():
    vr, wm = load()

    singles, by_work = single_role_actors(vr)
    print(f"\n1) Actors with exactly 1 role in the whole database: {len(singles)}")
    for (title, year) in sorted(by_work.keys(), key=lambda t: (-len(by_work[t]), t[0] or "")):
        rows = by_work[(title, year)]
        print(f"  {title} ({year}) -- {len(rows)}:")
        print("    " + ", ".join(describe_row(e) for e in rows))

    sw_actors = single_work_actors(vr, singles)
    print(f"\n2) Actors with >1 role but all in the same single work: {len(sw_actors)}")
    for actor, rows in sorted(sw_actors.items()):
        work, year = rows[0].get("work"), rows[0].get("year")
        print(f"  {actor} -- {work} ({year}): " + "; ".join(describe_row(e) for e in rows))

    sr_works = single_row_works(vr)
    print(f"\n3) Works with only 1 performance row recorded: {len(sr_works)}")
    for (title, year), rows in sorted(sr_works.items(), key=lambda kv: (kv[0][0] or "")):
        print(f"  {title} ({year}): {describe_row(rows[0])}")

    sa_works = single_actor_works(vr, sr_works)
    print(f"\n4) Works with >1 row but all from the same single actor: {len(sa_works)}")
    for (title, year), rows in sorted(sa_works.items(), key=lambda kv: (kv[0][0] or "")):
        print(f"  {title} ({year}): " + "; ".join(describe_row(e) for e in rows))

    studios = single_work_studios(wm)
    print(f"\n5) Studios credited on only 1 work: {len(studios)}")
    for studio, works in sorted(studios.items(), key=lambda kv: kv[0] or ""):
        w = works[0]
        print(f"  {studio} -- {w[0]} ({w[1]})")

    print(f"\n{'=' * 60}")
    print(
        f"Totals: {len(singles)} single-role actors, {len(sw_actors)} single-work actors (multi-role), "
        f"{len(sr_works)} single-row works, {len(sa_works)} single-actor works (multi-row), "
        f"{len(studios)} single-work studios."
    )


if __name__ == "__main__":
    run()
