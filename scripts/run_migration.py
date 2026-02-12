"""Script to run database migrations."""

import asyncio
import sys
from pathlib import Path
import asyncpg


async def run_migration(migration_file: str, db_url: str = None):
    """Run a SQL migration file.
    
    Args:
        migration_file: Path to SQL migration file
        db_url: Database URL (optional, uses default if not provided)
    """
    # Read migration file
    migration_path = Path(migration_file)
    if not migration_path.exists():
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)
    
    print(f"📄 Reading migration: {migration_file}")
    sql_content = migration_path.read_text()
    
    # Use provided URL or default
    if db_url is None:
        db_url = "postgresql://analyst_master:analyst_master_pwd@172.16.19.10:5432/smap"
    
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
        print("Usage: python3 scripts/run_migration.py <migration_file>")
        print("Example: python3 scripts/run_migration.py migration/001_create_analyzed_posts_table.sql")
        sys.exit(1)
    
    migration_file = sys.argv[1]
    asyncio.run(run_migration(migration_file))
