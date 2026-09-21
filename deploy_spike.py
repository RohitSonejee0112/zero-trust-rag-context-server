import asyncio
import asyncpg
import os
import sys

async def test_pgvector_support():
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("ERROR: DATABASE_URL environment variable is not set.")
        print("Please add your cloud Postgres URL to your .env file or export it.")
        sys.exit(1)
        
    print(f"Attempting to connect to the cloud database...")
    
    try:
        conn = await asyncpg.connect(db_url)
        print("SUCCESS! Successfully connected to the database!")
        
        print("Attempting to CREATE EXTENSION vector...")
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            print("SUCCESS! The cloud database supports pgvector.")
            print("You are clear to proceed with cloud deployment!")
        except Exception as e:
            print(f"ERROR: Failed to create pgvector extension. The database provider might not support it.")
            print(f"Details: {e}")
            
        finally:
            await conn.close()
            
    except Exception as e:
        print(f"ERROR: Failed to connect to the database.")
        print(f"Details: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(test_pgvector_support())
