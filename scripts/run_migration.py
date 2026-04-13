"""Script to run database migrations."""

import asyncio
import sys
from pathlib import Path
import asyncpg


async def run_migration(migration_file: str, db_url: str = None):
    """Run a SQL migration file.

    Args:
        migration_file: Path to SQL migration file
        db_url: Database URL (required — set via ANALYTICS_DATABASE_URL or --db-url flag)
    """


async def run_migration(migration_file: str, db_url: str = None):
    """Run a SQL migration file.

    Args:
        migration_file: Path to SQL migration file
        db_url: Database URL (required — set via ANALYTICS_DATABASE_URL or --db-url flag)
    """
    if db_url is None:
        import os

        db_url = os.environ.get("ANALYTICS_DATABASE_URL") or os.environ.get(
            "DATABASE_URL"
        )
    if not db_url:
        print(
            "❌ No database URL provided. Set ANALYTICS_DATABASE_URL env var or pass --db-url."
        )
        sys.exit(1)

    # Read migration file
    migration_path = Path(migration_file)
    if not migration_path.exists():
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)

    print(f"📄 Reading migration: {migration_file}")
    sql_content = migration_path.read_text()

    # Connect to database using asyncpg directly
    print(f"🔌 Connecting to database...")
    conn = None
    try:
        conn = await asyncpg.connect(db_url)

        # Execute migration
        print("🚀 Executing migration...")
        await conn.execute(sql_content)

        print("✅ Migration completed successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    finally:
        if conn:
            await conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python3 scripts/run_migration.py <migration_file> [--db-url <url>]"
        )
        print(
            "Example: python3 scripts/run_migration.py migration/001_create_analyzed_posts_table.sql"
        )
        print(
            "DB URL is read from ANALYTICS_DATABASE_URL or DATABASE_URL env vars if not passed."
        )
        sys.exit(1)

    migration_file = sys.argv[1]
    db_url_arg = None
    if "--db-url" in sys.argv:
        idx = sys.argv.index("--db-url")
        if idx + 1 < len(sys.argv):
            db_url_arg = sys.argv[idx + 1]
    asyncio.run(run_migration(migration_file, db_url_arg))
