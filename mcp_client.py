"""Talk to the Neo4j Aura MCP server through `npx mcp-remote` (same setup as mcp.json).

The first connection opens a browser window to authorize access; mcp-remote caches
the token in ~/.mcp-auth afterwards.

    uv run mcp_client.py tools                      # list the server's tools
    uv run mcp_client.py query "MATCH (n) RETURN count(n) AS nodes"
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MCP_URL = "https://c47ba44c.mcp-instances.neo4j.io"


@asynccontextmanager
async def mcp_session(url: str = MCP_URL):
    npx = shutil.which("npx") or "npx"
    params = StdioServerParameters(command=npx, args=["-y", "mcp-remote", url])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _attr(obj, *names):
    """Field names differ between mcp SDK versions (inputSchema vs input_schema)."""
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def tool_text(result) -> str:
    if _attr(result, "is_error", "isError"):
        raise RuntimeError("".join(getattr(c, "text", "") for c in result.content))
    return "".join(getattr(c, "text", "") for c in result.content)


async def _main(argv: list[str]) -> None:
    async with mcp_session() as session:
        if argv[:1] == ["tools"]:
            for tool in (await session.list_tools()).tools:
                schema = _attr(tool, "input_schema", "inputSchema")
                print(f"## {tool.name}\n{tool.description}\n{json.dumps(schema, indent=2)}\n")
        elif argv[:1] == ["query"] and len(argv) == 2:
            print(tool_text(await session.call_tool("read-cypher", {"query": argv[1]})))
        else:
            print(__doc__)


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
