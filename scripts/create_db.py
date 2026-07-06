import sqlite3
from pathlib import Path

DB_PATH = Path("db/voice_actors.db")
SCHEMA_PATH = Path("database/schema.sql")


def create_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

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