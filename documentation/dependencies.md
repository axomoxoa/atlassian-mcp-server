# Dependencies

## Table of Contents

1. [Overview](#overview)
2. [Runtime Dependencies](#runtime-dependencies)
3. [Development and Build Dependencies](#development-and-build-dependencies)
4. [Standard Library Usage](#standard-library-usage)
5. [Related Documentation](#related-documentation)

## Overview

This document lists the major dependencies currently used by the project and explains why each one exists.

The authoritative dependency declarations live in [pyproject.toml](../pyproject.toml).

## Runtime Dependencies

| Dependency | Where Declared | Purpose |
| --- | --- | --- |
| `mcp[cli]` | `project.dependencies` | Provides the FastMCP runtime, tool/resource registration, and local MCP development tooling. |
| `httpx` | `project.dependencies` | Performs async HTTP communication with Jira and Confluence APIs. |
| `python-dotenv` | `project.dependencies` | Loads environment values from the external secrets env file used by `AtlassianConfig`. |

## Development and Build Dependencies

| Dependency | Where Declared | Purpose |
| --- | --- | --- |
| `hatchling` | `build-system.requires` | Builds the package and wheel. |
| `pytest` | `project.optional-dependencies.dev` | Runs the automated test suite. |
| `poethepoet` | `project.optional-dependencies.dev` | Provides task-runner commands such as `uv run poe test` and `uv run poe smoke`. |

## Standard Library Usage

The project also relies heavily on the Python standard library for packaging, CLI handling, configuration, serialization, and encoding.

Common examples include:

- `argparse` for CLI parsing.
- `asyncio` for async orchestration and retry waits.
- `base64` and `json` for payload formatting.
- `dataclasses` for configuration models.
- `os` and `pathlib` for environment and filesystem handling.

## Related Documentation

- [README.md](../README.md)
- [documentation/implementation.md](implementation.md)
- [documentation/environment-variables.md](environment-variables.md)
- [documentation/tests.md](tests.md)
