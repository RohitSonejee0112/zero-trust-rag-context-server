import asyncio
import asyncpg
from fastembed import TextEmbedding
import os

# Load the lightweight embedding model using ONNX backend (fastembed)
# all-MiniLM-L6-v2 produces 384-dimensional vectors
model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

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
        embeddings_gen = model.embed([text_to_embed])
        embedding = list(embeddings_gen)[0].tolist()
        
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
