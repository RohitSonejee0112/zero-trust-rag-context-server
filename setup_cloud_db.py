import asyncio
import asyncpg
import os
import sys

async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set in environment.")
        sys.exit(1)
        
    print("Connecting to cloud database...")
    try:
        conn = await asyncpg.connect(db_url)
        
        print("Reading init.sql...")
        with open("init.sql", "r", encoding="utf-8") as f:
            sql = f.read()
            
        print("Executing schema setup and data seeding...")
        await conn.execute(sql)
        print("SUCCESS! Tables, RLS policies, and base data created successfully.")
        
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        if 'conn' in locals():
            await conn.close()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(main())
