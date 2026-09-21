import asyncio
import json
import urllib.request
from mcp.client.sse import sse_client
from mcp import ClientSession

async def fetch_token(username: str) -> str:
    print(f"\n[Client] Logging in as {username}...")
    req = urllib.request.Request(
        "http://127.0.0.1:8000/login",
        data=json.dumps({"username": username}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        return data["token"]

async def ask_ai(username: str, query: str):
    token = await fetch_token(username)
    
    print(f"[AI Agent] Thinking about: '{query}'")
    print(f"[AI Agent] Deciding to use tool 'search_documents'...")
    
    async with sse_client("http://127.0.0.1:8000/mcp/sse") as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            
            # Call the tool
            result = await session.call_tool(
                "search_documents", 
                {"query": query, "token": token}
            )
            
            # Print the tool result
            print(f"\n--- TOOL RESULT (from Postgres RLS) ---")
            for content in result.content:
                print(content.text)
            print("---------------------------------------")
            
            if "Error" in result.content[0].text or "No documents found" in result.content[0].text:
                print(f"[AI Response] I'm sorry, but I don't have access to information about '{query}'.")
            else:
                print(f"[AI Response] Based on the internal documents I found:\n{result.content[0].text}")

async def main():
    print("===========================================")
    print(" MCP PERMISSION-AWARE CONTEXT SERVER DEMO ")
    print("===========================================")
    
    # Test 1: HR User
    await ask_ai("alice_hr", "salary")
    
    print("\n" + "="*43)
    
    # Test 2: Finance User
    await ask_ai("charlie_fin", "salary")

if __name__ == "__main__":
    asyncio.run(main())
