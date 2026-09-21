import asyncio
from mcp.client.sse import sse_client
from mcp import ClientSession

async def main():
    async with sse_client("http://127.0.0.1:8000/mcp/sse") as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            print("Connected to MCP server!")
            tools = await session.list_tools()
            print("Tools:", tools)

asyncio.run(main())
