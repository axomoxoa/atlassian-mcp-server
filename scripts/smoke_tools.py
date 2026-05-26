from __future__ import annotations

import asyncio
import sys

from atlassian_mcp_server.server import mcp


EXPECTED_TOOLS = {
    "atlassian_check_connection",
    "jira_list_templates",
    "jira_create_ticket_from_template",
    "jira_clone_ticket",
    "confluence_search",
}


async def main() -> None:
    tools = await mcp.list_tools()
    tool_names = {str(getattr(tool, "name", "")) for tool in tools}
    missing = sorted(EXPECTED_TOOLS - tool_names)

    print(f"Discovered {len(tool_names)} tools")
    print("Verified tools:")
    for name in sorted(EXPECTED_TOOLS & tool_names):
        print(f"- {name}")

    if missing:
        print("Missing tools:", file=sys.stderr)
        for name in missing:
            print(f"- {name}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())