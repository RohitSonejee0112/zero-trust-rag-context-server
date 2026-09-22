import os
import glob
import yaml
import hashlib
import asyncpg
from fastembed import TextEmbedding

# Initialize embedding model (reuses the same one as server)
embedding_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

async def sync_knowledge_base():
    """
    Scans the docs/ directory, detects changes, and incrementally updates the database.
    Connects as admin to bypass RLS and perform INSERT/UPDATE/DELETE operations.
    """
    print("[Sync Engine] Starting Knowledge Base Sync...")
    
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        conn = await asyncpg.connect(db_url)
    else:
        # Connect as admin locally
        conn = await asyncpg.connect(
            user='admin',
            password='password123',
            database='mcp_auth_db',
            host='127.0.0.1',
            port=5433
        )

    # 1. Read all markdown files
    current_files = {}
    for filepath in glob.glob("docs/*.md"):
        with open(filepath, "r", encoding="utf-8") as f:
            raw_content = f.read()
            
        # Parse Frontmatter (very basic parser)
        parts = raw_content.split("---")
        if len(parts) >= 3:
            frontmatter_text = parts[1]
            markdown_content = "---".join(parts[2:]).strip()
            metadata = yaml.safe_load(frontmatter_text)
        else:
            print(f"[Sync Engine] Skipping {filepath} (no valid YAML frontmatter)")
            continue
            
        content_hash = hashlib.sha256(raw_content.encode('utf-8')).hexdigest()
        
        current_files[filepath] = {
            "title": metadata.get("title", "Untitled"),
            "department_id": metadata.get("department_id", 4), # Default public
            "sensitivity_level": metadata.get("sensitivity_level", 1),
            "content": markdown_content,
            "hash": content_hash
        }

    # 2. Get existing documents from database
    rows = await conn.fetch("SELECT id, source_file, content_hash FROM documents WHERE source_file IS NOT NULL")
    existing_docs = {row['source_file']: row for row in rows}

    # 3. Detect Deletions
    deleted_files = set(existing_docs.keys()) - set(current_files.keys())
    for file in deleted_files:
        print(f"[Sync Engine] Deleting removed file: {file}")
        await conn.execute("DELETE FROM documents WHERE source_file = $1", file)

    # 4. Detect Additions & Modifications
    for filepath, data in current_files.items():
        existing = existing_docs.get(filepath)
        
        if existing and existing['content_hash'] == data['hash']:
            # No changes
            continue
            
        print(f"[Sync Engine] Generating vector for changed/new file: {filepath}")
        # Embed title + content for better semantics
        text_to_embed = f"Title: {data['title']}\nContent: {data['content']}"
        embedding = list(embedding_model.embed([text_to_embed]))[0].tolist()
        vector_str = "[" + ",".join(map(str, embedding)) + "]"
        
        if not existing:
            print(f"[Sync Engine] Inserting new file: {filepath}")
            await conn.execute(
                """
                INSERT INTO documents (title, content, department_id, sensitivity_level, embedding, source_file, content_hash)
                VALUES ($1, $2, $3, $4, $5::vector, $6, $7)
                """,
                data['title'], data['content'], data['department_id'], data['sensitivity_level'], vector_str, filepath, data['hash']
            )
        else:
            print(f"[Sync Engine] Updating modified file: {filepath}")
            await conn.execute(
                """
                UPDATE documents SET 
                    title = $1, content = $2, department_id = $3, sensitivity_level = $4, embedding = $5::vector, content_hash = $6
                WHERE source_file = $7
                """,
                data['title'], data['content'], data['department_id'], data['sensitivity_level'], vector_str, data['hash'], filepath
            )

    await conn.close()
    print("[Sync Engine] Knowledge Base Sync Complete!")

if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(sync_knowledge_base())
