from mcp.server import Server
from mcp.types import Tool, TextContent

mcp = Server("test")

@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return []

@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    return []

print("success!")
