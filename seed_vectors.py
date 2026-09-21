import asyncio
import asyncpg
from sentence_transformers import SentenceTransformer
import os

# Load the lightweight embedding model
# all-MiniLM-L6-v2 produces 384-dimensional vectors
model = SentenceTransformer('all-MiniLM-L6-v2')

async def main():
    print("Connecting to PostgreSQL to seed vectors...")
    
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        print("Using cloud DATABASE_URL...")
        conn = await asyncpg.connect(db_url)
    else:
        print("Using local docker database...")
        conn = await asyncpg.connect(
            user='app_user',
            password='app_password',
            database='mcp_auth_db',
            host='127.0.0.1',
            port=5433
        )
    
    rows = await conn.fetch("SELECT id, title, content FROM documents")
    
    print(f"Generating vectors for {len(rows)} documents...")
    for row in rows:
        # We embed both the title and the content to get rich semantic meaning
        text_to_embed = f"Title: {row['title']}\nContent: {row['content']}"
        embedding = model.encode(text_to_embed).tolist()
        
        # Format as string '[val1, val2, ...]' which Postgres vector extension accepts
        vector_str = "[" + ",".join(map(str, embedding)) + "]"
        
        await conn.execute(
            "UPDATE documents SET embedding = $1::vector WHERE id = $2",
            vector_str, row['id']
        )
        print(f" -> Embedded and updated Document {row['id']}: '{row['title']}'")
        
    await conn.close()
    print("Done! All documents are now semantically searchable.")

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(main())
