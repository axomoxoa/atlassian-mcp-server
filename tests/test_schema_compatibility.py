import asyncio
import json
from collections.abc import Iterator

import pytest

from atlassian_mcp_server.server import mcp


def _load_tools() -> list[object]:
    async def _run() -> list[object]:
        return await mcp.list_tools()

    return asyncio.run(_run())


@pytest.fixture(autouse=True)
def clear_toolset_override(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("ATLASSIAN_MCP_TOOLSETS", raising=False)
    yield


def test_all_tool_schemas_have_no_anyof() -> None:
    tools = _load_tools()
    for tool in tools:
        name = getattr(tool, "name", "unknown")
        schema = getattr(tool, "inputSchema", {}) or {}
        schema_json = json.dumps(schema)
        assert "anyOf" not in schema_json, f"Schema for {name} still contains anyOf"


def test_all_tools_have_at_least_one_parameter() -> None:
    tools = _load_tools()
    for tool in tools:
        name = getattr(tool, "name", "unknown")
        schema = getattr(tool, "inputSchema", {}) or {}
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        assert properties, f"Tool {name} has zero parameters"


def test_all_schema_properties_have_explicit_type() -> None:
    tools = _load_tools()
    for tool in tools:
        name = getattr(tool, "name", "unknown")
        schema = getattr(tool, "inputSchema", {}) or {}
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        for prop_name, prop_schema in properties.items():
            assert isinstance(prop_schema, dict), (
                f"Tool {name} property {prop_name} schema is not an object"
            )
            assert "type" in prop_schema, (
                f"Tool {name} property {prop_name} has no explicit type"
            )


def test_default_toolsets_hide_jira_write_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLASSIAN_MCP_TOOLSETS", "default")
    tool_names = {getattr(tool, "name", "unknown") for tool in _load_tools()}

    assert "jira_add_comment" not in tool_names
    assert "jira_create_issue" not in tool_names
    assert "jira_create_ticket_from_template" not in tool_names
    assert "jira_clone_ticket" not in tool_names
    assert "confluence_create_page" not in tool_names
    assert "jira_transition_issue" not in tool_names
    assert "jira_search_issues" in tool_names
    assert "jira_list_templates" in tool_names
    assert "confluence_search" in tool_names


def test_custom_toolsets_can_expose_only_core_and_write_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLASSIAN_MCP_TOOLSETS", "core,jira-write,confluence-write")
    tool_names = {getattr(tool, "name", "unknown") for tool in _load_tools()}

    assert tool_names == {
        "atlassian_check_connection",
        "atlassian_get_myself",
        "jira_create_issue",
        "jira_create_ticket_from_template",
        "jira_clone_ticket",
        "jira_update_issue",
        "jira_delete_issue",
        "jira_add_comment",
        "jira_edit_comment",
        "jira_add_worklog",
        "jira_create_issue_link",
        "jira_remove_issue_link",
        "jira_create_sprint",
        "jira_update_sprint",
        "jira_add_issues_to_sprint",
        "jira_add_watcher",
        "jira_remove_watcher",
        "jira_update_proforma_form_answers",
        "jira_transition_issue",
        "confluence_create_page",
        "confluence_update_page",
        "confluence_delete_page",
        "confluence_add_comment",
        "confluence_add_label",
        "confluence_upload_attachment",
        "confluence_upload_attachments",
        "confluence_delete_attachment",
    }


def test_all_toolsets_expose_every_mapped_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLASSIAN_MCP_TOOLSETS", "all")
    tool_names = {getattr(tool, "name", "unknown") for tool in _load_tools()}

    assert tool_names == {
        "atlassian_check_connection",
        "atlassian_get_myself",
        "jira_list_projects",
        "jira_list_fields",
        "jira_search_fields",
        "jira_get_field_options",
        "jira_list_statuses",
        "jira_list_issue_types",
        "jira_build_jql",
        "jira_search_issues",
        "jira_validate_jql",
        "jira_query_issues_from_text",
        "jira_get_issue",
        "jira_list_templates",
        "jira_get_transitions",
        "jira_create_issue",
        "jira_create_ticket_from_template",
        "jira_clone_ticket",
        "jira_update_issue",
        "jira_delete_issue",
        "jira_add_comment",
        "jira_edit_comment",
        "jira_get_worklog",
        "jira_add_worklog",
        "jira_get_project_versions",
        "jira_get_project_components",
        "jira_get_link_types",
        "jira_create_issue_link",
        "jira_remove_issue_link",
        "jira_get_agile_boards",
        "jira_get_board_issues",
        "jira_get_sprints_from_board",
        "jira_get_sprint_issues",
        "jira_create_sprint",
        "jira_update_sprint",
        "jira_add_issues_to_sprint",
        "jira_get_service_desk_for_project",
        "jira_get_service_desk_queues",
        "jira_get_queue_issues",
        "jira_get_issue_dates",
        "jira_get_issue_sla",
        "jira_get_user_profile",
        "jira_get_issue_watchers",
        "jira_add_watcher",
        "jira_remove_watcher",
        "jira_get_issue_proforma_forms",
        "jira_get_proforma_form_details",
        "jira_update_proforma_form_answers",
        "jira_get_issue_development_info",
        "jira_get_issues_development_info",
        "jira_download_attachments",
        "jira_get_issue_images",
        "jira_transition_issue",
        "confluence_search",
        "confluence_get_page",
        "confluence_get_page_children",
        "confluence_get_comments",
        "confluence_add_comment",
        "confluence_get_labels",
        "confluence_add_label",
        "confluence_search_user",
        "confluence_get_attachments",
        "confluence_download_attachment",
        "confluence_download_content_attachments",
        "confluence_get_page_images",
        "confluence_create_page",
        "confluence_update_page",
        "confluence_delete_page",
        "confluence_upload_attachment",
        "confluence_upload_attachments",
        "confluence_delete_attachment",
    }
