"""Checks add/search/delete logic in scripts/db_ops.py against an in-memory DB."""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import db_ops

failures = []


def check(label, cond):
    print(f"  [{'pass' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)


def count(conn, t):
    return conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]


conn = sqlite3.connect(":memory:")
conn.executescript((ROOT / "database" / "schema.sql").read_text(encoding="utf-8"))

pid = db_ops.add_performance(conn, actor="A", work="W", year=2020, media_type="Video Game",
                             character="C", franchise="F",
                             studios=[{"name": "S", "role": "Developer"}])
check("add returns an id", pid is not None)
check("duplicate add is refused", db_ops.add_performance(
    conn, actor="A", work="W", year=2020, character="C") is None)
check("same name, different disambiguation = distinct characters", (
    db_ops.add_performance(conn, actor="B", work="W", year=2020, character="C", character_note="other") is not None
    and count(conn, "Characters") == 2))
check("source marks credit verified", (
    db_ops.add_performance(conn, actor="D", work="W", year=2020, character="E", source="http://x") is not None
    and conn.execute("SELECT verified FROM Performances WHERE source_url='http://x'").fetchone()[0] == 1))
check("search is partial + case-insensitive", len(db_ops.search_performances(conn, "w")) == 3)

hits = db_ops.search_performances(conn, "D")
report = db_ops.delete_performances(conn, [h["id"] for h in hits if h["actor"] == "D"])
check("delete cleans orphan actor/appearance/character",
      report["removed"].get("actors") == 1 and report["removed"].get("characters") == 1)
all_ids = [h["id"] for h in db_ops.search_performances(conn, "w")]
report = db_ops.delete_performances(conn, all_ids)
check("work with no cast is reported, not auto-deleted", len(report["empty_works"]) == 1)
db_ops.delete_works(conn, [w[0] for w in report["empty_works"]])
check("deleting empty work drops unused studio + franchise",
      count(conn, "Studios") == 0 and count(conn, "Franchises") == 0 and count(conn, "Works") == 0)

print("\nAll checks passed." if not failures else f"\n{len(failures)} FAILED")
sys.exit(1 if failures else 0)
