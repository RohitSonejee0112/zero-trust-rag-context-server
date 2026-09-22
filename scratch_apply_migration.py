import asyncio
import asyncpg
import os

async def main():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        print("Using cloud DATABASE_URL...")
        conn = await asyncpg.connect(db_url)
    else:
        print("Using local database...")
        conn = await asyncpg.connect(user='admin', password='password123', database='mcp_auth_db', host='127.0.0.1', port=5433)
    
    await conn.execute('ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_file VARCHAR(255) UNIQUE;')
    await conn.execute('ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);')
    print("Migration applied!")
    await conn.close()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(main())
