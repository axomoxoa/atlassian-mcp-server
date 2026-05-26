import base64
from pathlib import Path

import httpx
import pytest

from atlassian_mcp_server.client import AtlassianClient
from atlassian_mcp_server.config import AtlassianConfig, ConfigurationError, ServiceConfig
from atlassian_mcp_server.tools.jira import (
    COPIED_TEXT_FIELD_NAMES,
    _build_issue_blueprint,
    _component_tokens,
    _collect_template_placeholders,
    _extract_placeholders,
    _find_field_ids_by_names,
    _issue_matches_template_marker,
    _looks_like_jql,
    _normalize_components,
    _replace_placeholders,
    build_common_jql,
)


def test_config_from_env_reads_values_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / "atlassian.env"
    env_file.write_text(
        "\n".join(
            [
                "JIRA_URL=https://jira.example.atlassian.net/",
                "JIRA_BEARER_TOKEN=jira-secret",
                "CONFLUENCE_URL=https://conf.example.atlassian.net/",
                "CONFLUENCE_BEARER_TOKEN=conf-secret",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ATLASSIAN_ENV_FILE", str(env_file))

    config = AtlassianConfig.from_env()

    assert config.jira.base_url == "https://jira.example.atlassian.net"
    assert config.jira.deployment == "cloud"
    assert config.jira.auth_mode == "bearer"
    assert config.jira.api_base_path == "/rest/api/3"
    assert config.jira.bearer_token == "jira-secret"
    assert config.jira.username is None
    assert config.confluence.base_url == "https://conf.example.atlassian.net"
    assert config.confluence.deployment == "cloud"
    assert config.confluence.auth_mode == "bearer"
    assert config.confluence.api_base_path == "/wiki/rest/api"
    assert config.confluence.bearer_token == "conf-secret"


def test_config_from_env_raises_for_missing_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLASSIAN_ENV_FILE", str(Path("missing.env")))
    monkeypatch.delenv("JIRA_URL", raising=False)
    monkeypatch.delenv("JIRA_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("JIRA_USERNAME", raising=False)
    monkeypatch.delenv("JIRA_PASSWORD", raising=False)
    monkeypatch.delenv("CONFLUENCE_URL", raising=False)
    monkeypatch.delenv("CONFLUENCE_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("CONFLUENCE_USERNAME", raising=False)
    monkeypatch.delenv("CONFLUENCE_PASSWORD", raising=False)

    with pytest.raises(ConfigurationError):
        AtlassianConfig.from_env()


def test_client_builds_bearer_auth_headers_without_email() -> None:
    config = AtlassianConfig(
        jira=ServiceConfig(
            base_url="https://jira.example.atlassian.net",
            deployment="cloud",
            auth_mode="bearer",
            api_base_path="/rest/api/3",
            bearer_token="jira-secret",
        ),
        confluence=ServiceConfig(
            base_url="https://conf.example.atlassian.net",
            deployment="server",
            auth_mode="bearer",
            api_base_path="/rest/api",
            bearer_token="conf-secret",
        ),
    )

    client = AtlassianClient(config)

    assert client.jira_headers["Authorization"] == "Bearer jira-secret"
    assert client.confluence_headers["Authorization"] == "Bearer conf-secret"


def test_client_builds_basic_auth_header_when_username_password_present() -> None:
    config = AtlassianConfig(
        jira=ServiceConfig(
            base_url="https://jira.example.atlassian.net",
            deployment="cloud",
            auth_mode="basic",
            api_base_path="/rest/api/3",
            username="my-user",
            password="secret",
        ),
        confluence=ServiceConfig(
            base_url="https://conf.example.atlassian.net",
            deployment="server",
            auth_mode="bearer",
            api_base_path="/rest/api",
            bearer_token="other-secret",
        ),
    )

    client = AtlassianClient(config)
    encoded = base64.b64encode(b"my-user:secret").decode("ascii")

    assert client.jira_headers["Authorization"] == f"Basic {encoded}"


def test_config_supports_basic_auth_from_username_and_password(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / "atlassian.env"
    env_file.write_text(
        "\n".join(
            [
                "JIRA_URL=https://jira.example.atlassian.net/",
                "JIRA_DEPLOYMENT=server",
                "JIRA_AUTH_MODE=basic",
                "JIRA_USERNAME=my-user",
                "JIRA_PASSWORD=secret",
                "CONFLUENCE_URL=https://conf.example.atlassian.net/",
                "CONFLUENCE_DEPLOYMENT=cloud",
                "CONFLUENCE_BEARER_TOKEN=conf-secret",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ATLASSIAN_ENV_FILE", str(env_file))

    config = AtlassianConfig.from_env()

    assert config.jira.deployment == "server"
    assert config.jira.auth_mode == "basic"
    assert config.jira.api_base_path == "/rest/api/2"
    assert config.jira.username == "my-user"
    assert config.jira.password == "secret"
    assert config.confluence.deployment == "cloud"
    assert config.confluence.auth_mode == "bearer"
    assert config.confluence.api_base_path == "/wiki/rest/api"


def test_config_supports_api_base_path_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / "atlassian.env"
    env_file.write_text(
        "\n".join(
            [
                "JIRA_URL=https://jira.internal.example.com",
                "JIRA_BEARER_TOKEN=jira-secret",
                "JIRA_API_BASE_PATH=/custom-jira/rest/api/latest",
                "CONFLUENCE_URL=https://conf.internal.example.com",
                "CONFLUENCE_BEARER_TOKEN=conf-secret",
                "CONFLUENCE_API_BASE_PATH=/confluence/rest/api",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ATLASSIAN_ENV_FILE", str(env_file))

    config = AtlassianConfig.from_env()

    assert config.jira.api_base_path == "/custom-jira/rest/api/latest"
    assert config.confluence.api_base_path == "/confluence/rest/api"


def test_client_uses_deployment_specific_paths() -> None:
    config = AtlassianConfig(
        jira=ServiceConfig(
            base_url="https://jira.example.atlassian.net",
            deployment="server",
            auth_mode="bearer",
            api_base_path="/rest/api/2",
            bearer_token="jira-secret",
        ),
        confluence=ServiceConfig(
            base_url="https://conf.example.atlassian.net",
            deployment="cloud",
            auth_mode="bearer",
            api_base_path="/wiki/rest/api",
            bearer_token="conf-secret",
        ),
    )

    client = AtlassianClient(config)

    assert client._jira_path("/search") == "/rest/api/2/search"
    assert client._confluence_path("/content/123") == "/wiki/rest/api/content/123"


@pytest.mark.anyio
async def test_client_search_issues_supports_pagination_and_validation() -> None:
    config = AtlassianConfig(
        jira=ServiceConfig(
            base_url="https://jira.example.atlassian.net",
            deployment="cloud",
            auth_mode="bearer",
            api_base_path="/rest/api/3",
            bearer_token="jira-secret",
        ),
        confluence=ServiceConfig(
            base_url="https://conf.example.atlassian.net",
            deployment="cloud",
            auth_mode="bearer",
            api_base_path="/wiki/rest/api",
            bearer_token="conf-secret",
        ),
    )
    client = AtlassianClient(config)

    captured: dict[str, object] = {}

    async def fake_request(service: str, method: str, path: str, *, params=None, json_body=None):
        captured["service"] = service
        captured["method"] = method
        captured["path"] = path
        captured["json_body"] = json_body
        return {"issues": [], "total": 0, "startAt": 5, "maxResults": 20}

    client._request = fake_request  # type: ignore[method-assign]

    result = await client.search_issues(
        "project = TEST ORDER BY updated DESC",
        limit=20,
        fields=["summary"],
        start_at=5,
        validate_query=False,
    )

    assert captured["service"] == "jira"
    assert captured["method"] == "POST"
    assert captured["path"] == "/rest/api/3/search/jql"
    assert captured["json_body"] == {
        "jql": "project = TEST ORDER BY updated DESC",
        "maxResults": 20,
        "startAt": 5,
        "validateQuery": False,
        "fields": ["summary"],
    }
    assert result["startAt"] == 5


def test_build_common_jql_with_multiple_filters() -> None:
    jql = build_common_jql(
        project_keys=["envcomp"],
        assignee="alice",
        statuses=["In Progress", "To Do"],
        issue_types=["Bug"],
        priorities=["High"],
        updated_since="-7d",
        order_by="created",
        order_direction="ASC",
    )

    assert jql == (
        'project = ENVCOMP AND assignee = "alice" AND status in ("In Progress", "To Do") '
        'AND issuetype in ("Bug") AND priority in ("High") AND updated >= "-7d" ORDER BY created ASC'
    )


def test_build_common_jql_with_multiple_project_keys() -> None:
    jql = build_common_jql(
        project_keys=["FLIP", "ENVCOMP"],
        updated_since="-1w",
    )

    assert jql == 'project in (FLIP, ENVCOMP) AND updated >= "-1w" ORDER BY updated DESC'


def test_build_common_jql_rejects_empty_filters() -> None:
    with pytest.raises(ValueError):
        build_common_jql()


def test_looks_like_jql_detects_valid_expression() -> None:
    assert _looks_like_jql("project in (FLIP, ENVCOMP) AND updated >= startOfDay() ORDER BY updated DESC") is True


def test_looks_like_jql_rejects_natural_language_text() -> None:
    assert _looks_like_jql("show me all tickets updated today") is False


def test_extract_error_message_prefers_error_messages_list() -> None:
    request = httpx.Request("GET", "https://example.test")
    response = httpx.Response(
        status_code=400,
        request=request,
        json={"errorMessages": ["Invalid JQL"]},
    )

    assert AtlassianClient._extract_error_message(response) == "Invalid JQL"


def test_extract_error_message_uses_detail_for_non_jira_payload() -> None:
    request = httpx.Request("GET", "https://example.test")
    response = httpx.Response(
        status_code=500,
        request=request,
        json={"detail": "Internal server error"},
    )

    assert AtlassianClient._extract_error_message(response) == "Internal server error"


def test_retry_delay_uses_retry_after_header() -> None:
    request = httpx.Request("GET", "https://example.test")
    response = httpx.Response(
        status_code=429,
        request=request,
        headers={"Retry-After": "7"},
    )

    assert AtlassianClient._retry_delay_seconds(response, attempt=0) == 7.0


def test_parse_toolsets_all_and_default_aliases() -> None:
    assert AtlassianConfig.parse_toolsets("all") == AtlassianConfig.SUPPORTED_TOOLSETS
    assert AtlassianConfig.parse_toolsets("default") == AtlassianConfig.DEFAULT_TOOLSETS
    assert AtlassianConfig.parse_toolsets(None) == AtlassianConfig.SUPPORTED_TOOLSETS


def test_parse_toolsets_supports_explicit_mix() -> None:
    assert AtlassianConfig.parse_toolsets("core,jira-write") == frozenset({"core", "jira-write"})


def test_parse_toolsets_rejects_unknown_values() -> None:
    with pytest.raises(ConfigurationError):
        AtlassianConfig.parse_toolsets("jira-admin")


def test_extract_placeholders_supports_nested_ticket_content() -> None:
    payload = {
        "summary": "Provision {system_name}",
        "description": {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Owner: {owner}"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Region: {region}"}]},
            ],
        },
    }

    assert _extract_placeholders(payload) == {"system_name", "owner", "region"}


def test_replace_placeholders_supports_nested_ticket_content() -> None:
    payload = {
        "summary": "Provision {system_name}",
        "description": {
            "type": "doc",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Owner: {owner}"}]}],
        },
    }

    result = _replace_placeholders(payload, {"system_name": "FLICA", "owner": "Jane Doe"})

    assert result["summary"] == "Provision FLICA"
    text_node = result["description"]["content"][0]["content"][0]["text"]
    assert text_node == "Owner: Jane Doe"


def test_replace_placeholders_removes_escape_prefix_in_description_text() -> None:
    payload = {
        "summary": "Provision {system_name}",
        "description": {
            "type": "doc",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Owner: \\{owner}"}]}],
        },
    }

    result = _replace_placeholders(payload, {"system_name": "FLICA", "owner": "Jane Doe"})

    text_node = result["description"]["content"][0]["content"][0]["text"]
    assert text_node == "Owner: Jane Doe"


def test_issue_matches_template_marker_supports_labels_only() -> None:
    fields = {
        "labels": ["customer-facing", "template"],
        "customfield_10001": [{"value": "Template"}],
    }

    assert _issue_matches_template_marker(fields, marker_value="template") is True
    assert _issue_matches_template_marker(fields, marker_value="other") is False

    no_label_fields = {
        "labels": ["customer-facing"],
        "customfield_10001": [{"value": "Template"}],
    }
    assert _issue_matches_template_marker(no_label_fields, marker_value="template") is False


def test_collect_template_placeholders_includes_custom_text_fields() -> None:
    fields = {
        "summary": "Provision {system_name}",
        "description": "Owner {owner}",
        "customfield_10001": "Definition of done for {system_name}",
    }

    assert _collect_template_placeholders(fields, copied_text_field_ids={"customfield_10001"}) == [
        "owner",
        "system_name",
    ]


def test_find_field_ids_by_names_includes_all_checklist_aliases() -> None:
    field_definitions = [
        {"id": "customfield_10001", "name": "Acceptance Criteria"},
        {"id": "customfield_10002", "name": "Definition of Done"},
        {"id": "customfield_10003", "name": "Definition of Ready"},
        {"id": "customfield_10004", "name": "Definition of Read"},
    ]

    matched_ids = _find_field_ids_by_names(field_definitions, set(COPIED_TEXT_FIELD_NAMES))

    assert matched_ids == {
        "customfield_10001",
        "customfield_10002",
        "customfield_10003",
        "customfield_10004",
    }


def test_find_field_ids_by_names_matches_checklist_name_variants() -> None:
    field_definitions = [
        {"id": "customfield_20001", "name": "Acceptance Criteria Checklist"},
        {"id": "customfield_20002", "name": "Definition of Done (Checklist)"},
        {"id": "customfield_20003", "name": "Team Definition of Ready Checklist"},
        {"id": "customfield_20004", "name": "Random Field"},
    ]

    matched_ids = _find_field_ids_by_names(field_definitions, set(COPIED_TEXT_FIELD_NAMES))

    assert matched_ids == {
        "customfield_20001",
        "customfield_20002",
        "customfield_20003",
    }


def test_build_issue_blueprint_copies_acceptance_criteria_and_removes_template_label() -> None:
    source_fields = {
        "summary": "Provision {system_name}",
        "description": "Owner {owner}",
        "issuetype": {"name": "Story"},
        "labels": ["template", "platform"],
        "priority": {"name": "High"},
        "components": [{"id": "11", "name": "Platform"}],
        "fixVersions": [{"id": "22", "name": "Sprint 24"}],
        "customfield_10001": "Acceptance: {system_name}",
    }

    blueprint = _build_issue_blueprint(
        source_fields,
        copied_text_field_ids={"customfield_10001"},
        replacements={"system_name": "FLICA", "owner": "Jane"},
        parent_issue_key="FLICA-999",
    )

    assert blueprint["summary"] == "Provision FLICA"
    assert blueprint["description"] == "Owner Jane"
    assert blueprint["issue_type"] == "Story"
    assert blueprint["additional_fields"]["labels"] == ["platform"]
    assert blueprint["additional_fields"]["customfield_10001"] == "Acceptance: FLICA"
    assert blueprint["additional_fields"]["parent"] == {"key": "FLICA-999"}


def test_normalize_components_prefers_id_and_filters_invalid_values() -> None:
    raw_components = [
        {"id": 10123, "name": "Platform"},
        {"name": "Backend"},
        {"id": "", "name": ""},
        "not-a-dict",
    ]

    assert _normalize_components(raw_components) == [
        {"id": "10123"},
        {"name": "Backend"},
    ]


def test_component_tokens_normalizes_name_case() -> None:
    components = [{"name": "Platform"}, {"name": "platform"}, {"id": "12345"}]

    assert _component_tokens(components) == {"name:platform", "id:12345"}