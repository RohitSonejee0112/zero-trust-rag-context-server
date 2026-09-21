import asyncio
import json
import urllib.request
from openai import AsyncOpenAI
from mcp.client.sse import sse_client
from mcp import ClientSession

# 1. Setup OpenAI client pointing to local Ollama
# We don't need a real API key since it's running locally
client = AsyncOpenAI(
    base_url='http://localhost:11434/v1',
    api_key='ollama'
)
MODEL = "llama3.1"

async def fetch_token(username: str) -> str:
    print(f"\n[Client] Logging in as {username}...")
    req = urllib.request.Request(
        "http://127.0.0.1:8000/login",
        data=json.dumps({"username": username}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())["token"]

async def run_agent(username: str, prompt: str):
    token = await fetch_token(username)
    
    print(f"[Agent] Starting session for {username}")
    print(f"[Agent] User Prompt: '{prompt}'")
    
    # 2. Connect to the MCP Server
    async with sse_client("http://127.0.0.1:8000/mcp/sse") as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            
            # 3. Define the tool schema for the LLM
            tools = [{
                "type": "function",
                "function": {
                    "name": "search_documents",
                    "description": "Search for documents in the organization based on semantic meaning.",
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
                {"role": "system", "content": "You are a corporate AI assistant. You must ONLY answer using the information returned by the `search_documents` tool. If the tool returns no relevant documents, or if the documents do not contain the answer, you MUST reply exactly with: 'I am sorry, but I do not have access to that information.' DO NOT use any outside knowledge."},
                {"role": "user", "content": prompt}
            ]
            
            # 4. Call Ollama
            print(f"[LLM] Thinking... (using local {MODEL})")
            response = await client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools
            )
            
            message = response.choices[0].message
            
            if not message.tool_calls:
                print(f"[LLM] Direct Response: {message.content}")
                return
                
            # 5. Process tool call autonomously
            tool_call = message.tool_calls[0]
            print(f"[LLM] Autonomously decided to use tool: {tool_call.function.name}")
            args = json.loads(tool_call.function.arguments)
            
            # 6. Execute against secure MCP server
            print(f"[MCP] Executing tool with query '{args['query']}' using {username}'s token...")
            mcp_args = {"query": args["query"], "token": token}
            
            try:
                result = await session.call_tool("search_documents", mcp_args)
                tool_result_text = result.content[0].text
            except Exception as e:
                tool_result_text = f"Error executing tool: {e}"
                
            print(f"[MCP] Returned {len(tool_result_text.splitlines())} lines of data.")
            
            # 7. Give RLS-filtered results back to the LLM to synthesize an answer
            messages.append(message)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result_text
            })
            
            print("[LLM] Synthesizing final answer...")
            final_response = await client.chat.completions.create(
                model=MODEL,
                messages=messages
            )
            
            print("\n===========================================")
            print(f"FINAL ANSWER for {username}:")
            print("===========================================")
            print(final_response.choices[0].message.content)
            print("===========================================\n")

async def main():
    print("==================================================")
    print(" REAL LLM AGENT LOOP DEMO (Ollama + llama3.1) ")
    print("==================================================\n")
    
    prompt = "What information do you have about engineering salary bands?"
    
    # Alice (HR) should get a rich summary
    await run_agent("alice_hr", prompt)
    
    # Charlie (Finance) should be blocked and the LLM should apologize
    await run_agent("charlie_fin", prompt)

if __name__ == "__main__":
    asyncio.run(main())
