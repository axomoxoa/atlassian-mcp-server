# Tests

## Table of Contents

1. [Overview](#overview)
2. [How to Run the Tests](#how-to-run-the-tests)
3. [Test Inventory](#test-inventory)
4. [Related Documentation](#related-documentation)

## Overview

The repository currently contains 30 automated tests across two files:

- `tests/test_config.py` with 24 tests focused on configuration, client helpers, JQL helpers, and Jira template helpers
- `tests/test_schema_compatibility.py` with 6 tests focused on tool exposure and schema compatibility

The tests are designed to run locally without requiring live Atlassian network access.

## How to Run the Tests

Run the full suite:

```bash
uv run pytest
```

Run a focused file:

```bash
uv run pytest tests/test_config.py
uv run pytest tests/test_schema_compatibility.py
```

Run via Poe:

```bash
uv run poe test
```

## Test Inventory

### `tests/test_config.py`

| Test                                                                               | What it tests                                                 | Setup required                                                            | Assertions made                                                                                                                   |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `test_config_from_env_reads_values_from_env_file`                                  | Env-file loading for a Cloud-style bearer-token setup.        | Temporary env file plus `ATLASSIAN_ENV_FILE`.                             | Base URLs are normalized, deployments auto-detect as cloud, auth mode resolves to bearer, and default API base paths are correct. |
| `test_config_from_env_raises_for_missing_values`                                   | Missing required configuration is rejected.                   | Missing env file and cleared Jira and Confluence variables.               | `AtlassianConfig.from_env()` raises `ConfigurationError`.                                                                         |
| `test_client_builds_bearer_auth_headers_without_email`                             | Bearer auth header construction.                              | In-memory config with bearer credentials.                                 | Jira and Confluence headers use `Authorization: Bearer ...`.                                                                      |
| `test_client_builds_basic_auth_header_when_username_password_present`              | Basic auth header construction.                               | In-memory config with Jira username and password.                         | Jira header equals the expected base64-encoded basic auth string.                                                                 |
| `test_config_supports_basic_auth_from_username_and_password`                       | Basic-auth resolution from env vars.                          | Temporary env file with Jira basic auth and Confluence bearer auth.       | Jira resolves to basic auth and server defaults, Confluence resolves to cloud bearer defaults.                                    |
| `test_config_supports_api_base_path_override`                                      | API base-path overrides are honored.                          | Temporary env file with explicit Jira and Confluence base-path overrides. | The parsed config uses the override values.                                                                                       |
| `test_client_uses_deployment_specific_paths`                                       | Internal path helpers use service-specific API prefixes.      | In-memory config with explicit base paths.                                | `_jira_path()` and `_confluence_path()` prepend the correct prefixes.                                                             |
| `test_client_search_issues_supports_pagination_and_validation`                     | Search payload construction for paginated Jira issue queries. | In-memory config and a monkey-patched `_request` method.                  | The client emits the expected REST path and JSON body and preserves the returned `startAt`.                                       |
| `test_build_common_jql_with_multiple_filters`                                      | Structured filter conversion into JQL.                        | Direct call to `build_common_jql()`.                                      | Generated JQL includes project, assignee, status, issue type, priority, date, and ordering filters.                               |
| `test_build_common_jql_with_multiple_project_keys`                                 | Multi-project JQL generation.                                 | Direct call to `build_common_jql()`.                                      | Generated JQL uses `project in (...)` and the default updated ordering.                                                           |
| `test_build_common_jql_rejects_empty_filters`                                      | Guard against empty JQL builder input.                        | Direct call with no filters.                                              | `build_common_jql()` raises `ValueError`.                                                                                         |
| `test_looks_like_jql_detects_valid_expression`                                     | JQL detection helper accepts valid JQL.                       | Direct call to `_looks_like_jql()`.                                       | A syntactically JQL-like expression returns `True`.                                                                               |
| `test_looks_like_jql_rejects_natural_language_text`                                | JQL detection helper rejects natural-language requests.       | Direct call to `_looks_like_jql()`.                                       | A plain-language sentence returns `False`.                                                                                        |
| `test_extract_error_message_prefers_error_messages_list`                           | Jira-style error extraction.                                  | Constructed `httpx.Response` with `errorMessages`.                        | `_extract_error_message()` returns the first Jira error message.                                                                  |
| `test_extract_error_message_uses_detail_for_non_jira_payload`                      | Generic error extraction fallback.                            | Constructed `httpx.Response` with a `detail` field.                       | `_extract_error_message()` returns `detail`.                                                                                      |
| `test_retry_delay_uses_retry_after_header`                                         | Retry delay calculation from HTTP headers.                    | Constructed `httpx.Response` with `Retry-After`.                          | `_retry_delay_seconds()` returns the header value.                                                                                |
| `test_parse_toolsets_all_and_default_aliases`                                      | Toolset alias handling.                                       | Direct calls to `AtlassianConfig.parse_toolsets()`.                       | `all`, `default`, and `None` resolve to the expected frozensets.                                                                  |
| `test_parse_toolsets_supports_explicit_mix`                                        | Explicit toolset parsing.                                     | Direct call with a comma-separated subset.                                | The parsed result contains only the requested toolsets.                                                                           |
| `test_parse_toolsets_rejects_unknown_values`                                       | Validation of unsupported toolset names.                      | Direct call with an invalid toolset value.                                | `parse_toolsets()` raises `ConfigurationError`.                                                                                   |
| `test_extract_placeholders_supports_nested_ticket_content`                         | Placeholder extraction from nested Jira content.              | Direct call to `_extract_placeholders()`.                                 | Placeholders are found in summary text and nested rich-text payloads.                                                             |
| `test_replace_placeholders_supports_nested_ticket_content`                         | Placeholder replacement in nested Jira content.               | Direct call to `_replace_placeholders()`.                                 | Placeholder tokens are replaced in summary text and nested rich-text payloads.                                                    |
| `test_issue_matches_template_marker_supports_labels_only`                          | Template issue detection.                                     | Direct call to `_issue_matches_template_marker()`.                        | Template markers are detected from labels only.                                                                                   |
| `test_collect_template_placeholders_includes_custom_text_fields`                   | Placeholder collection across template fields.                | Direct call to `_collect_template_placeholders()`.                        | Summary, description, and copied custom text fields contribute placeholders.                                                      |
| `test_build_issue_blueprint_copies_acceptance_criteria_and_removes_template_label` | Template and clone field shaping.                             | Direct call to `_build_issue_blueprint()`.                                | Template labels are removed, copied text fields are preserved, replacements are applied, and parent linkage is added.             |

### `tests/test_schema_compatibility.py`

| Test                                                        | What it tests                              | Setup required                                                 | Assertions made                                                             |
| ----------------------------------------------------------- | ------------------------------------------ | -------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `test_all_tool_schemas_have_no_anyof`                       | Compatibility schema sanitization.         | Load all tools from the MCP server.                            | No exposed tool schema still contains `anyOf`.                              |
| `test_all_tools_have_at_least_one_parameter`                | Zero-argument tool compatibility handling. | Load all tools from the MCP server.                            | Every exposed tool schema has at least one property.                        |
| `test_all_schema_properties_have_explicit_type`             | Explicit typing for schema properties.     | Load all tools from the MCP server.                            | Every exposed property schema is an object with a `type`.                   |
| `test_default_toolsets_hide_jira_write_tools`               | Safe default tool visibility.              | Set `ATLASSIAN_MCP_TOOLSETS=default`.                          | Jira and Confluence write tools are hidden while read tools remain exposed. |
| `test_custom_toolsets_can_expose_only_core_and_write_tools` | Selective toolset exposure.                | Set `ATLASSIAN_MCP_TOOLSETS=core,jira-write,confluence-write`. | Only the expected core and write tools are exposed.                         |
| `test_all_toolsets_expose_every_mapped_tool`                | Exhaustive registry coverage.              | Set `ATLASSIAN_MCP_TOOLSETS=all`.                              | The loaded tool set exactly matches the mapped tool registry.               |

## Related Documentation

- [documentation/implementation.md](implementation.md)
- [documentation/environment-variables.md](environment-variables.md)
- [documentation/tools.md](tools.md)
