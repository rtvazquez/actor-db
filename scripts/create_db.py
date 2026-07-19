import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import DB_PATH, SCHEMA_PATH


def create_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if DB_PATH.exists():
        DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Enable FK enforcement (must be per connection)
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Verify it actually enabled (important sanity check)
        fk_status = cursor.execute("PRAGMA foreign_keys;").fetchone()[0]
        if fk_status != 1:
            raise RuntimeError("Foreign key enforcement is NOT enabled")

        # Read schema safely using Path
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

        # Execute full schema
        cursor.executescript(schema_sql)

        conn.commit()

    print(f"Database created at: {DB_PATH}")


if __name__ == "__main__":
    create_database()
