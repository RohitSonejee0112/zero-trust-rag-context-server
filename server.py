import jwt
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import asyncpg
from contextlib import asynccontextmanager
import os
import json
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from groq import AsyncGroq

load_dotenv()
groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

from mcp.server.mcpserver import MCPServer
from mcp.types import Tool, TextContent
from fastembed import TextEmbedding

# Load embedding model using lightweight ONNX backend (fastembed)
# all-MiniLM-L6-v2 produces 384-dimensional vectors
embedding_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

# WARNING: In production, always pull this from an environment variable!
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect using DATABASE_URL if provided (Cloud Deployments), otherwise use local docker defaults
    db_url = os.getenv("DATABASE_URL")
    
    async def init_connection(conn):
        # We must switch to the non-superuser 'app_user' role.
        # If we query as 'postgres' (the Supabase default), we bypass all RLS policies!
        await conn.execute("SET ROLE app_user")
        
    if db_url:
        app.state.db_pool = await asyncpg.create_pool(
            db_url, 
            setup=init_connection,
            min_size=1,
            max_size=5
        )
    else:
        app.state.db_pool = await asyncpg.create_pool(
            user='app_user',
            password='app_password',
            database='mcp_auth_db',
            host='127.0.0.1',
            port=5433,
            min_size=1,
            max_size=5
        )
    yield
    await app.state.db_pool.close()

app = FastAPI(lifespan=lifespan)
mcp = MCPServer("permission-aware-context-server")

class LoginRequest(BaseModel):
    username: str

class ChatRequest(BaseModel):
    username: str
    query: str

@app.post("/login")
async def login(req: LoginRequest):
    async with app.state.db_pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, department_id, clearance_level FROM users WHERE username = $1", 
            req.username
        )
        
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")
    
    token = jwt.encode(
        {
            "username": req.username, 
            "department_id": str(user['department_id']),
            "user_id": str(user['id']),
            "clearance_level": str(user['clearance_level'])
        },
        SECRET_KEY,
        algorithm="HS256"
    )
    return {"token": token}

@mcp.tool()
async def search_documents(query: str, token: str) -> list[TextContent]:
    """
    Search for documents in the organization.
    
    Args:
        query: The search string to look for in document titles or content.
        token: The JWT token obtained from the /login endpoint.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        department_id = payload.get("department_id")
        user_id = payload.get("user_id")
        clearance_level = payload.get("clearance_level")
    except jwt.InvalidTokenError:
        return [TextContent(type="text", text="Error: Invalid token")]

    if not department_id:
        return [TextContent(type="text", text="Error: Token missing department_id")]

    # 2. Convert the text query into a semantic vector using fastembed
    embeddings_gen = embedding_model.embed([query])
    query_vector = list(embeddings_gen)[0].tolist()
    
    async with app.state.db_pool.acquire() as conn:
        # 3. SET THE SESSION VARIABLES FOR ABAC RLS
        # Wrap in a transaction and use is_local=true to prevent concurrency leaks in connection pools
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.current_department_id', $1, true)", str(department_id))
            await conn.execute("SELECT set_config('app.current_user_id', $1, true)", str(user_id))
            await conn.execute("SELECT set_config('app.current_clearance_level', $1, true)", str(clearance_level))
            
            # 4. EXECUTE SEMANTIC SEARCH BOUNDED BY RLS
            # Postgres will ONLY evaluate distance on rows that pass the RLS policy!
            rows = await conn.fetch(
                """
                SELECT title, content, 
                       1 - (embedding <=> $1::vector) as similarity
                FROM documents
                ORDER BY embedding <=> $1::vector
                LIMIT 5
                """,
                "[" + ",".join(map(str, query_vector)) + "]"
            )

        if not rows:
            return [TextContent(type="text", text="No documents found matching your query.")]

        results = []
        for row in rows:
            results.append(f"Title: {row['title']}\nContent: {row['content']}\nSimilarity: {row['similarity']:.2f}")
        return [TextContent(type="text", text="\n---\n".join(results))]

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    # 1. Get the JWT for this user from the DB
    async with app.state.db_pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, department_id, clearance_level FROM users WHERE username = $1", 
            req.username
        )
        
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")
    
    token = jwt.encode(
        {
            "username": req.username, 
            "department_id": str(user['department_id']),
            "user_id": str(user['id']),
            "clearance_level": str(user['clearance_level'])
        },
        SECRET_KEY,
        algorithm="HS256"
    )
    
    # 2. Define the tool schema for Groq (Llama 3)
    tools = [{
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search for internal documents in the organization based on semantic meaning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look for in documents"
                    }
                },
                "required": ["query"]
            }
        }
    }]
    
    messages = [
        {"role": "system", "content": "You are an internal corporate AI assistant. You must ONLY answer using the information returned by the `search_documents` tool. If the tool returns no relevant documents, you MUST reply exactly with: 'I am sorry, but I do not have access to that information.' DO NOT use any outside knowledge."},
        {"role": "user", "content": req.query}
    ]
    
    # 3. Call Groq
    response = await groq_client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=messages,
        tools=tools
    )
    
    message = response.choices[0].message
    
    if not message.tool_calls:
        return {"response": message.content}
        
    # 4. Execute tool against Postgres
    tool_call = message.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    
    # Call the python function directly (bypassing SSE loopback)
    result_content = await search_documents(query=args["query"], token=token)
    tool_result_text = result_content[0].text
    
    # 5. Return results to Groq
    messages.append({
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments
                }
            }
        ]
    })
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": tool_result_text
    })
    
    final_response = await groq_client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=messages
    )
    
    return {"response": final_response.choices[0].message.content}

from fastapi import BackgroundTasks
from sync_kb import sync_knowledge_base

@app.post("/api/webhook/sync")
async def webhook_sync(background_tasks: BackgroundTasks, request: Request):
    """Triggered by GitHub Webhooks or manually to sync markdown docs"""
    auth_header = request.headers.get("Authorization")
    expected_token = os.getenv("SYNC_WEBHOOK_SECRET", "default-insecure-secret")
    
    if auth_header != f"Bearer {expected_token}":
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    background_tasks.add_task(sync_knowledge_base)
    return {"status": "Sync triggered"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

app.mount("/mcp", mcp.sse_app())
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Make sure we bind to 0.0.0.0 for external cloud deployments
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
