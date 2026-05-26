# Installation

## Table of Contents

1. [Overview](#overview)
2. [Canonical Location](#canonical-location)
3. [Prerequisites](#prerequisites)
4. [Clone and Install](#clone-and-install)
5. [Configure Secrets](#configure-secrets)
6. [Run Validation Checks](#run-validation-checks)
7. [Run the Server](#run-the-server)
8. [Docker Desktop Deployment](#docker-desktop-deployment)
9. [Claude Desktop Configuration](#claude-desktop-configuration)
10. [MCP Inspector](#mcp-inspector)
11. [Related Documentation](#related-documentation)

## Overview

This file mirrors the project installation guide so older links remain useful.

The canonical instruction-matched path is [documentation/installatiion.md](installatiion.md).

## Canonical Location

The project instructions currently refer to:

- [documentation/installatiion.md](installatiion.md)

This file keeps the same installation content under the conventional spelling so both paths stay valid.

## Prerequisites

You need the following before running the server:

- Python 3.11 or later
- `uv` recommended, or `pip` plus a virtual environment
- Docker Desktop, if you want to run the server in a container
- Access to a Jira and/or Confluence instance
- Valid credentials for that instance

## Clone and Install

Clone the repository:

```bash
git clone https://github.com/axomoxoa/atlassian-mcp-server.git
cd atlassian-mcp-server
```

Install with `uv`:

```bash
uv sync
```

Or install with `pip`:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## Configure Secrets

By default, the server reads secrets from:

```text
C:\Users\<you>\.mcp-secrets\atlassian.env
```

You can override the location with:

```env
ATLASSIAN_ENV_FILE=C:\path\to\your\secrets.env
```

Minimal Atlassian Cloud example:

```env
JIRA_URL=https://your-domain.atlassian.net
JIRA_BEARER_TOKEN=your-jira-token

CONFLUENCE_URL=https://your-domain.atlassian.net
CONFLUENCE_BEARER_TOKEN=your-confluence-token
```

Minimal on-premise example:

```env
JIRA_URL=https://jira.example.corp
JIRA_DEPLOYMENT=server
JIRA_AUTH_MODE=basic
JIRA_USERNAME=your-jira-username
JIRA_PASSWORD=your-jira-password

CONFLUENCE_URL=https://confluence.example.corp
CONFLUENCE_DEPLOYMENT=server
CONFLUENCE_AUTH_MODE=basic
CONFLUENCE_USERNAME=your-confluence-username
CONFLUENCE_PASSWORD=your-confluence-password
```

For the full variable reference, see [documentation/environment-variables.md](environment-variables.md).

## Run Validation Checks

Run the automated tests:

```bash
uv run pytest
```

Or with Poe:

```bash
uv run poe test
```

Run the smoke test against your configured live environment:

```bash
uv run poe smoke
```

## Run the Server

STDIO transport:

```bash
uv run atlassian-mcp-server
```

Skip startup connectivity checks if needed:

```bash
uv run atlassian-mcp-server --skip-startup-check
```

Streamable HTTP transport:

```bash
uv run atlassian-mcp-server --transport streamable-http --port 8000
```

SSE transport:

```bash
uv run atlassian-mcp-server --transport sse --port 8000
```

## Docker Desktop Deployment

The repository includes a `Dockerfile` and `compose.yaml` for Docker Desktop.

Set the host path to your Atlassian env file before starting the container:

```powershell
$env:ATLASSIAN_HOST_ENV_FILE = "C:/Users/<you>/.mcp-secrets/atlassian.env"
```

Build the image:

```bash
uv run poe docker-build
```

Start the container:

```bash
uv run poe docker-up
```

Stop and remove it:

```bash
uv run poe docker-down
```

The server is exposed on `http://localhost:8000/mcp` and uses `ATLASSIAN_MCP_TOOLSETS=all` by default unless you override it in your shell.

## Claude Desktop Configuration

Example `claude_desktop_config.json` entry:

```json
{
  "mcpServers": {
    "atlassian": {
      "command": "uv",
      "args": [
        "--directory",
        "c:/Data/github-cloud-repos/ai/atlassian-mcp-server",
        "run",
        "atlassian-mcp-server"
      ],
      "env": {
        "ATLASSIAN_ENV_FILE": "C:/Users/<you>/.mcp-secrets/atlassian.env"
      }
    }
  }
}
```

Update the repository path and env-file path for your machine.

## MCP Inspector

Launch MCP Inspector locally with:

```bash
uv run poe inspector
```

That command starts the development inspector against `src/atlassian_mcp_server/server.py`.

## Related Documentation

- [documentation/installatiion.md](installatiion.md)
- [documentation/environment-variables.md](environment-variables.md)
- [documentation/dependencies.md](dependencies.md)
- [documentation/tools.md](tools.md)
- [documentation/tests.md](tests.md)