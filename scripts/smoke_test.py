from __future__ import annotations

import asyncio
import sys

import httpx
from atlassian_mcp_server.client import AtlassianClient
from atlassian_mcp_server.config import AtlassianConfig, ConfigurationError


def _print_configuration_help(error: ConfigurationError) -> None:
    message = str(error)
    print(f"Configuration error: {message}", file=sys.stderr)

    if "Unable to determine auth mode" in message:
        print("Set one of these auth setups per service:", file=sys.stderr)
        print("- Bearer: JIRA_BEARER_TOKEN and CONFLUENCE_BEARER_TOKEN", file=sys.stderr)
        print("- Basic: JIRA_USERNAME/JIRA_PASSWORD and CONFLUENCE_USERNAME/CONFLUENCE_PASSWORD", file=sys.stderr)
        print("Optional: AUTH_MODE=bearer or AUTH_MODE=basic", file=sys.stderr)

    if "API_TOKEN" in message:
        print("API token variables are no longer supported in this project.", file=sys.stderr)
        print("Use JIRA_BEARER_TOKEN and CONFLUENCE_BEARER_TOKEN instead.", file=sys.stderr)


async def main() -> None:
    try:
        config = AtlassianConfig.from_env()
    except ConfigurationError as error:
        _print_configuration_help(error)
        raise SystemExit(1) from error

    client = AtlassianClient(config)

    try:
        me = await client.get_myself()
    except httpx.HTTPStatusError as error:
        print(f"Jira request failed: {error}", file=sys.stderr)
        if error.response.status_code in {401, 403}:
            print("Check Jira credentials and auth mode in your env file.", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"Jira auth ok as: {me.get('displayName')}")

    try:
        results = await client.search_confluence(cql="type = page order by lastmodified desc", limit=1)
    except httpx.HTTPStatusError as error:
        print(f"Confluence request failed: {error}", file=sys.stderr)
        if error.response.status_code in {401, 403}:
            print("Check Confluence credentials and auth mode in your env file.", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"Confluence auth ok, results: {len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
