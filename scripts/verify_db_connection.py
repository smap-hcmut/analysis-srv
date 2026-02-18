"""Verify DB connectivity and schema/table access for the analytics service."""
import asyncio

from sqlalchemy import text

from config.config import load_config
from internal.model.constant import POSTGRES_SCHEMA
from pkg.postgre.postgres import PostgresDatabase
from pkg.postgre.type import PostgresConfig


async def verify():
    print("🔍 Starting Database Verification...")

    # 1. Load Config (same as apps/consumer)
    try:
        cfg = load_config()
        print("✅ Configuration loaded.")
    except Exception as e:
        print("❌ Failed to load config:", e)
        return

    # 2. Build PostgresConfig (schema: schema_analysis, same as app)
    schema = getattr(cfg.database, "schema", None) or POSTGRES_SCHEMA
    pg_config = PostgresConfig(
        database_url=cfg.database.url,
        schema=schema,
        pool_size=cfg.database.pool_size,
        max_overflow=cfg.database.max_overflow,
    )
    print(f"🔌 Connecting to DB (schema={schema})...")
    db = PostgresDatabase(pg_config)

    try:
        async with db.get_session() as session:
            # 3. Check search_path
            print("   Session created. Checking search_path...")
            result = await session.execute(text("SHOW search_path"))
            search_path = result.scalar()
            print(f"   Current search_path: {search_path}")

            if schema not in (search_path or ""):
                print(f"❌ '{schema}' NOT found in search_path!")
            else:
                print(f"✅ '{schema}' IS in search_path.")

            # 4. Check table access (implicit schema via search_path)
            print("   Checking access to 'post_insight' table...")
            count = None
            try:
                result = await session.execute(text("SELECT count(*) FROM post_insight"))
                count = result.scalar()
                print(f"✅ Access successful! Row count (post_insight): {count}")
            except Exception as e:
                if "does not exist" in str(e).lower() or "undefined_table" in str(e).lower():
                    print("⚠️  Table 'post_insight' not found. Run migrations to create it.")
                    await session.rollback()
                else:
                    raise

            # 5. Explicit schema qualified table (schema from config, safe)
            qualified = f"{schema}.post_insight"
            print(f"   Checking access to '{qualified}'...")
            try:
                result = await session.execute(text(f"SELECT count(*) FROM {qualified}"))
                count_explicit = result.scalar()
                print(f"✅ Explicit schema access successful! Count: {count_explicit}")
                if count is not None and count != count_explicit:
                    print("⚠️  Implicit and explicit counts differ (check search_path).")
            except Exception as e:
                if "does not exist" in str(e).lower() or "undefined_table" in str(e).lower():
                    print("⚠️  Table '%s' not found. Run migrations." % qualified)
                else:
                    raise
    except Exception as e:
        print("❌ Verification Failed:", e)
        import traceback

        traceback.print_exc()
    finally:
        await db.close()
        print("🔒 Database connection closed.")


if __name__ == "__main__":
    asyncio.run(verify())
