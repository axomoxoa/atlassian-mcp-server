from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import AtlassianClient
from ..config import AtlassianConfig


def _get_client() -> AtlassianClient:
    return AtlassianClient(AtlassianConfig.from_env())


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def atlassian_check_connection() -> dict[str, Any]:
        """Verify Jira and Confluence connectivity with the current configuration."""
        client = _get_client()
        result: dict[str, Any] = {
            "jira": {"status": "ok"},
            "confluence": {"status": "ok"},
        }

        try:
            me = await client.get_myself()
            result["jira"]["display_name"] = me.get("displayName")
        except Exception as exc:
            result["jira"] = {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }

        try:
            pages = await client.search_confluence(cql="type = page order by lastmodified desc", limit=1)
            result["confluence"]["result_count"] = len(pages)
        except Exception as exc:
            result["confluence"] = {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }

        result["status"] = "ok" if result["jira"]["status"] == "ok" and result["confluence"]["status"] == "ok" else "error"
        return result

    @mcp.tool()
    async def atlassian_get_myself() -> dict[str, str | None]:
        """Return the authenticated Atlassian account profile."""
        data = await _get_client().get_myself()
        return {
            "account_id": data.get("accountId"),
            "display_name": data.get("displayName"),
            "email_address": data.get("emailAddress"),
            "active": data.get("active"),
            "time_zone": data.get("timeZone"),
        }
