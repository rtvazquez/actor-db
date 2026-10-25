"""Runs tests/test_dashboard.js against a dashboard generated from the archived
dataset (the live DB may be empty or tiny, but the test needs real data).

    python tests/run_dashboard_test.py        (needs `npm install` once for jsdom)
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
archives = sorted(p for p in (ROOT / "archive").iterdir() if (p / "voice_actors.db").exists())
if not archives:
    sys.exit("No archive/ dataset to test against.")

with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "dashboard.html"
    env = dict(os.environ, ACTORDB_DB=str(archives[-1] / "voice_actors.db"), ACTORDB_DASHBOARD=str(out))
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_dashboard.py")], check=True, env=env)
    sys.exit(subprocess.run(["node", str(ROOT / "tests" / "test_dashboard.js")], env=env, cwd=ROOT).returncode)
