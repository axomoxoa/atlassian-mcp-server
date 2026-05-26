# Environment Variables

## Table of Contents

1. [Overview](#overview)
2. [Resolution Order](#resolution-order)
3. [File and Runtime Control](#file-and-runtime-control)
4. [Service Endpoints](#service-endpoints)
5. [Deployment Settings](#deployment-settings)
6. [Authentication Settings](#authentication-settings)
7. [Credentials](#credentials)
8. [Tool Visibility and Debug Flags](#tool-visibility-and-debug-flags)
9. [Examples](#examples)
10. [Related Documentation](#related-documentation)

## Overview

The server loads configuration from an external env file and from the current process environment.

Default env-file path:

```text
C:\Users\rober15\.mcp-secrets\atlassian.env
```

## Resolution Order

Configuration resolution works as follows:

1. Values are loaded from `ATLASSIAN_ENV_FILE` or the default env-file path.
2. Process environment variables override values from the file.
3. Per-service auth settings override shared auth settings.
4. Deployment-specific defaults are applied when explicit values are missing.

## File and Runtime Control

| Name | Description | Possible values | Default value |
| --- | --- | --- | --- |
| `ATLASSIAN_ENV_FILE` | Path to the external env file used for secrets and runtime config. | Any valid filesystem path. | `C:\Users\rober15\.mcp-secrets\atlassian.env` |

## Service Endpoints

| Name | Description | Possible values | Default value |
| --- | --- | --- | --- |
| `JIRA_URL` | Base URL for Jira. | Any valid Jira base URL. | None, required. |
| `CONFLUENCE_URL` | Base URL for Confluence. | Any valid Confluence base URL. | None, required. |
| `JIRA_API_BASE_PATH` | Override for the Jira REST API base path. | Any path beginning with `/`. | Auto-derived from deployment. |
| `CONFLUENCE_API_BASE_PATH` | Override for the Confluence REST API base path. | Any path beginning with `/`. | Auto-derived from deployment. |

## Deployment Settings

| Name | Description | Possible values | Default value |
| --- | --- | --- | --- |
| `JIRA_DEPLOYMENT` | Jira deployment type. | `cloud`, `server` | Auto-detected from URL. |
| `CONFLUENCE_DEPLOYMENT` | Confluence deployment type. | `cloud`, `server` | Auto-detected from URL. |

Deployment defaults:

- Jira Cloud uses `/rest/api/3`
- Jira Server or Data Center uses `/rest/api/2`
- Confluence Cloud uses `/wiki/rest/api`
- Confluence Server or Data Center uses `/rest/api`

## Authentication Settings

| Name | Description | Possible values | Default value |
| --- | --- | --- | --- |
| `AUTH_MODE` | Global auth-mode fallback for both services. | `bearer`, `basic` | Auto-detected from available credentials. |
| `ATLASSIAN_AUTH_MODE` | Shared Atlassian auth-mode override for both services. | `bearer`, `basic` | Unset. |
| `JIRA_AUTH_MODE` | Jira-specific auth mode. | `bearer`, `basic` | Inherited or auto-detected. |
| `CONFLUENCE_AUTH_MODE` | Confluence-specific auth mode. | `bearer`, `basic` | Inherited or auto-detected. |

Precedence:

- `JIRA_AUTH_MODE` or `CONFLUENCE_AUTH_MODE`
- `ATLASSIAN_AUTH_MODE`
- `AUTH_MODE`
- automatic detection from credentials

## Credentials

### Bearer-token credentials

| Name | Description | Possible values | Default value |
| --- | --- | --- | --- |
| `JIRA_BEARER_TOKEN` | Bearer token for Jira. | Any non-empty token string. | None when bearer auth is required. |
| `CONFLUENCE_BEARER_TOKEN` | Bearer token for Confluence. | Any non-empty token string. | None when bearer auth is required. |

### Basic-auth credentials

| Name | Description | Possible values | Default value |
| --- | --- | --- | --- |
| `JIRA_USERNAME` | Username for Jira basic auth. | Any non-empty username. | None when basic auth is required. |
| `JIRA_PASSWORD` | Password for Jira basic auth. | Any non-empty password. | None when basic auth is required. |
| `CONFLUENCE_USERNAME` | Username for Confluence basic auth. | Any non-empty username. | None when basic auth is required. |
| `CONFLUENCE_PASSWORD` | Password for Confluence basic auth. | Any non-empty password. | None when basic auth is required. |

## Tool Visibility and Debug Flags

| Name | Description | Possible values | Default value |
| --- | --- | --- | --- |
| `ATLASSIAN_MCP_TOOLSETS` | Controls which toolsets are exposed by the server. | `all`, `default`, or a comma-separated mix of `core`, `jira-read`, `jira-write`, `confluence-read`, `confluence-write` | `all` when unset. |
| `ATLASSIAN_MCP_DEBUG_HTTP` | Enables INFO-level HTTP dependency logs. | `1`, `true`, `yes`, `on` and other unset or falsey values. | Unset, HTTP logs stay at warning level. |
| `ATLASSIAN_MCP_DEBUG_MCP` | Enables INFO-level MCP framework logs. | `1`, `true`, `yes`, `on` and other unset or falsey values. | Unset, MCP logs stay at warning level. |

## Examples

### Atlassian Cloud with bearer tokens

```env
JIRA_URL=https://your-domain.atlassian.net
JIRA_DEPLOYMENT=cloud
JIRA_BEARER_TOKEN=your-jira-token

CONFLUENCE_URL=https://your-domain.atlassian.net
CONFLUENCE_DEPLOYMENT=cloud
CONFLUENCE_BEARER_TOKEN=your-confluence-token
```

### On-premise setup with basic auth

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

### Read-only tool exposure

```env
ATLASSIAN_MCP_TOOLSETS=default
```

### Explicit mixed tool exposure

```env
ATLASSIAN_MCP_TOOLSETS=core,jira-write,confluence-read
```

## Related Documentation

- [documentation/installatiion.md](installatiion.md)
- [documentation/implementation.md](implementation.md)
- [documentation/tools.md](tools.md)