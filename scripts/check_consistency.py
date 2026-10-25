"""
Cross-validates data/voice_roles.json against data/work_metadata.json and
against itself. Read-only -- prints a report, changes nothing.

Run any time after editing the JSON source files, ideally before
re-running create_db.py + import_data.py:
    python scripts/check_consistency.py
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


def check_missing_required_fields(vr):
    problems = []
    for i, e in enumerate(vr):
        for field in ("actor", "work", "character"):
            if not e.get(field):
                problems.append(f"  row {i}: missing/empty '{field}' -- {e}")
    return problems


def check_duplicate_rows(vr):
    seen = {}
    problems = []
    for i, e in enumerate(vr):
        key = (e.get("actor"), e.get("work"), e.get("year"), e.get("character"), e.get("language"))
        if key in seen:
            problems.append(f"  rows {seen[key]} and {i}: exact duplicate {key}")
        else:
            seen[key] = i
    return problems


def check_case_variant_names(vr, field):
    """Flag names that differ only by case/whitespace. This matters because
    Actors.name and Characters.canonical_name are matched case-sensitively
    on import (and Actors.name is UNIQUE case-sensitively in SQLite), so
    'Kaiji Tang' and 'kaiji tang' would silently become two different rows
    for the same real person instead of one."""
    by_normalized = defaultdict(set)
    for e in vr:
        val = e.get(field)
        if not val:
            continue
        by_normalized[val.strip().lower()].add(val)
    problems = []
    for norm, variants in by_normalized.items():
        if len(variants) > 1:
            problems.append(f"  variants that normalize to the same name: {sorted(variants)}")
    return problems


def check_media_type_consistency(vr):
    by_work = defaultdict(set)
    for e in vr:
        by_work[(e.get("work"), e.get("year"))].add(e.get("media_type"))
    problems = []
    for (title, year), types in sorted(by_work.items(), key=lambda kv: (kv[0][0] or "")):
        if len(types) > 1:
            problems.append(f"  {title} ({year}): inconsistent media_type across rows: {sorted(t for t in types if t)}")
    return problems


def check_orphaned_metadata(vr, wm):
    """work_metadata.json entries with no matching rows in voice_roles.json --
    dead metadata that import_data.py would silently skip with a '[skip]' line."""
    vr_works = {(e.get("work"), e.get("year")) for e in vr}
    problems = []
    for w in wm:
        key = (w.get("title"), w.get("year"))
        if key not in vr_works and not w.get("media_type"):
            problems.append(f"  {w.get('title')} ({w.get('year')}): in work_metadata.json with no media_type and no matching voice_roles.json rows")
    return problems


def check_works_without_metadata(vr, wm):
    """Works with no work_metadata.json entry at all -- not necessarily a
    bug (not every work needs a franchise), but worth a glance."""
    wm_works = {(w.get("title"), w.get("year")) for w in wm}
    vr_works = {(e.get("work"), e.get("year")) for e in vr}
    missing = sorted(vr_works - wm_works, key=lambda t: (t[0] or ""))
    return [f"  {t} ({y})" for t, y in missing]


def check_franchise_studio_targets_exist(vr, wm):
    """work_metadata.json parent_work references that don't point at a real
    (title, year) pair in voice_roles.json -- would silently no-op the
    sequel/remake link on import."""
    vr_works = {(e.get("work"), e.get("year")) for e in vr} | {(w.get("title"), w.get("year")) for w in wm}
    problems = []
    for w in wm:
        parent = w.get("parent_work")
        if parent:
            key = (parent.get("title"), parent.get("year"))
            if key not in vr_works:
                problems.append(f"  {w.get('title')} ({w.get('year')}): parent_work {key} not found in voice_roles.json")
    return problems


def run():
    vr, wm = load()
    sections = [
        ("Missing required fields (actor/work/character)", check_missing_required_fields(vr)),
        ("Exact duplicate rows", check_duplicate_rows(vr)),
        ("Actor name case/whitespace variants", check_case_variant_names(vr, "actor")),
        ("Character name case/whitespace variants", check_case_variant_names(vr, "character")),
        ("Inconsistent media_type for the same work", check_media_type_consistency(vr)),
        ("Orphaned work_metadata.json entries (no voice_roles.json rows)", check_orphaned_metadata(vr, wm)),
        ("parent_work references that don't resolve", check_franchise_studio_targets_exist(vr, wm)),
        ("Works with no work_metadata.json entry (informational)", check_works_without_metadata(vr, wm)),
    ]

    total_findings = 0
    total_informational = 0
    for i, (title, problems) in enumerate(sections):
        is_informational = i == len(sections) - 1
        print(f"\n{title}: {len(problems)}")
        for p in problems[:20]:
            print(p)
        if len(problems) > 20:
            print(f"  ... and {len(problems) - 20} more")
        if is_informational:
            total_informational += len(problems)
        else:
            total_findings += len(problems)

    print(f"\n{'=' * 60}")
    if total_findings == 0:
        print(f"No consistency issues found. ({total_informational} informational note(s) above.)")
    else:
        print(f"{total_findings} finding(s) worth checking, plus {total_informational} informational note(s) above.")


if __name__ == "__main__":
    run()
