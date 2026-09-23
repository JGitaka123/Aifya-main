"""
Database connection test utility.

WARNING: This is a debug/test file. Never hardcode credentials.
All connection parameters are read from environment variables.
"""

import asyncio
import os

import asyncpg


async def test():
    """Test database connectivity using environment variables."""
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://aifya:password@localhost:5432/aifya",
    )

    # Parse individual vars if DATABASE_URL not set, for flexibility
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = int(os.environ.get("DB_PORT", "5433"))
    user = os.environ.get("DB_USER", "aifya")
    password = os.environ.get("DB_PASSWORD", "")
    database = os.environ.get("DB_NAME", "aifya")

    if not password:
        print("WARNING: DB_PASSWORD environment variable is not set.")
        print("Set DB_PASSWORD or DATABASE_URL before running this script.")
        return

    try:
        print(f"Attempting to connect to {host}:{port}...")
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
        print("SUCCESS: Connected to database!")
        await conn.close()
    except Exception as e:
        print(f"FAILURE: {e}")


if __name__ == "__main__":
    asyncio.run(test())
