from __future__ import annotations

import json
import base64
import re
import uuid
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator
from mcp.server.fastmcp import FastMCP

from ..client import (
    AtlassianClient,
    AtlassianRequestError,
    compact_issue,
    compact_jira_field,
    compact_jira_issue_type,
    compact_jira_status,
    compact_project,
)
from ..config import AtlassianConfig


def _get_client() -> AtlassianClient:
    return AtlassianClient(AtlassianConfig.from_env())


def _get_jira_base_url() -> str:
    config = AtlassianConfig.from_env()
    return config.jira.base_url.rstrip("/")


_FIELD_CANNOT_BE_SET_RE = re.compile(r"Field '([^']+)' cannot be set")


async def _create_issue_tolerant(
    client: AtlassianClient,
    *,
    project_key: str,
    summary: str,
    issue_type: str,
    description: str | None,
    additional_fields: dict[str, Any],
) -> dict[str, Any]:
    """Create a Jira issue, retrying after stripping fields the screen rejects."""
    fields = dict(additional_fields)
    for _ in range(20):  # at most 20 bad fields before giving up
        try:
            return await client.create_issue(
                project_key=project_key,
                summary=summary,
                issue_type=issue_type,
                description=description,
                additional_fields=fields or None,
            )
        except AtlassianRequestError as exc:
            match = _FIELD_CANNOT_BE_SET_RE.search(str(exc))
            if not match or match.group(1) not in fields:
                raise
            fields.pop(match.group(1))
    raise AtlassianRequestError("Too many unrecognized fields stripped during issue creation")


def _build_browse_url(issue_key: str) -> str:
    """Build a Jira browse URL from an issue key."""
    return f"{_get_jira_base_url()}/browse/{issue_key}"


def _build_parent_subtasks_table(
    *,
    parent_key: str | None,
    parent_url: str | None,
    subtasks: list[dict[str, Any]],
) -> str:
    parent_cell = parent_key or "-"
    if parent_key and parent_url:
        parent_cell = f"[{parent_key}]({parent_url})"

    subtask_links: list[str] = []
    for subtask in subtasks:
        if not isinstance(subtask, dict):
            continue
        issue = subtask.get("issue")
        if not isinstance(issue, dict):
            continue
        key = issue.get("key")
        url = issue.get("url")
        if isinstance(key, str) and key and isinstance(url, str) and url:
            subtask_links.append(f"[{key}]({url})")

    rows: list[str] = []
    for i, link in enumerate(subtask_links):
        cell = parent_cell if i == 0 else ""
        rows.append(f"| {cell} | {link} |")
    if not rows:
        rows.append(f"| {parent_cell} | - |")

    return "\n".join(
        [
            "| Parent | Sub Tasks |",
            "| --- | --- |",
            *rows,
        ]
    )


def _build_parent_subtasks_table_payload(
    *,
    parent_key: str | None,
    parent_url: str | None,
    subtasks: list[dict[str, Any]],
) -> dict[str, Any]:
    parent_cell = parent_url or "-"
    parent_link = (
        [{"text": parent_key, "url": parent_url}]
        if isinstance(parent_key, str) and parent_key and isinstance(parent_url, str) and parent_url
        else []
    )

    subtask_urls: list[str] = []
    subtask_link_objects: list[dict[str, str]] = []
    for subtask in subtasks:
        if not isinstance(subtask, dict):
            continue
        issue = subtask.get("issue")
        if not isinstance(issue, dict):
            continue
        key = issue.get("key")
        url = issue.get("url")
        if isinstance(key, str) and key and isinstance(url, str) and url:
            subtask_urls.append(url)
            subtask_link_objects.append({"text": key, "url": url})

    subtasks_cell = subtask_urls if subtask_urls else []
    return {
        "columns": ["Parent", "Sub Tasks"],
        "rows": [[parent_cell, subtasks_cell]],
        "table_rows": [{"Parent": parent_cell, "Sub Tasks": subtasks_cell}],
        "table_link_rows": [
            {
                "Parent": parent_link,
                "Sub Tasks": subtask_link_objects,
            }
        ],
    }


def _new_input_context_id() -> str:
    return uuid.uuid4().hex


def _quote_jql_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _looks_like_jql(query: str) -> bool:
    normalized = query.strip()
    if not normalized:
        return False

    lowered = normalized.lower()
    if lowered.startswith(("show ", "list ", "find ", "get ", "give me ", "what ", "which ")):
        return False

    jql_tokens = (
        "=",
        " in ",
        "~",
        ">",
        "<",
        " and ",
        " or ",
        "order by",
        "startofday(",
        "currentuser(",
    )
    return any(token in lowered for token in jql_tokens)


def _to_paginated_issue_result(data: dict[str, Any], *, default_start_at: int, default_limit: int) -> dict[str, Any]:
    issues = data.get("issues", [])
    return {
        "issues": [compact_issue(issue) for issue in issues],
        "total": data.get("total", len(issues)),
        "start_at": data.get("startAt", default_start_at),
        "max_results": data.get("maxResults", min(max(1, default_limit), 50)),
        "is_last": data.get("isLast"),
    }


def build_common_jql(
    *,
    project_keys: list[str] | None = None,
    assignee: str | None = None,
    reporter: str | None = None,
    statuses: list[str] | None = None,
    issue_types: list[str] | None = None,
    priorities: list[str] | None = None,
    text: str | None = None,
    updated_since: str | None = None,
    resolution: str | None = None,
    order_by: Literal["updated", "created", "priority", "status", "assignee"] = "updated",
    order_direction: Literal["ASC", "DESC"] = "DESC",
) -> str:
    clauses: list[str] = []

    if project_keys:
        valid_keys = [k.strip().upper() for k in project_keys if k.strip()]
        if len(valid_keys) == 1:
            clauses.append(f"project = {valid_keys[0]}")
        elif len(valid_keys) > 1:
            rendered = ", ".join(valid_keys)
            clauses.append(f"project in ({rendered})")
    if assignee and assignee.strip():
        clauses.append(f"assignee = {_quote_jql_value(assignee.strip())}")
    if reporter and reporter.strip():
        clauses.append(f"reporter = {_quote_jql_value(reporter.strip())}")
    if statuses:
        rendered = ", ".join(_quote_jql_value(status.strip()) for status in statuses if status.strip())
        if rendered:
            clauses.append(f"status in ({rendered})")
    if issue_types:
        rendered = ", ".join(_quote_jql_value(issue_type.strip()) for issue_type in issue_types if issue_type.strip())
        if rendered:
            clauses.append(f"issuetype in ({rendered})")
    if priorities:
        rendered = ", ".join(_quote_jql_value(priority.strip()) for priority in priorities if priority.strip())
        if rendered:
            clauses.append(f"priority in ({rendered})")
    if text and text.strip():
        clauses.append(f"text ~ {_quote_jql_value(text.strip())}")
    if updated_since and updated_since.strip():
        clauses.append(f"updated >= {_quote_jql_value(updated_since.strip())}")
    if resolution and resolution.strip():
        if resolution.strip().lower() == "unresolved":
            clauses.append("resolution = Unresolved")
        else:
            clauses.append(f"resolution = {_quote_jql_value(resolution.strip())}")

    if not clauses:
        raise ValueError("Provide at least one filter to build JQL")

    normalized_direction = order_direction.upper()
    if normalized_direction not in {"ASC", "DESC"}:
        raise ValueError("order_direction must be ASC or DESC")

    return f"{' AND '.join(clauses)} ORDER BY {order_by} {normalized_direction}"


PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
REPLACE_PLACEHOLDER_PATTERN = re.compile(r"\\?\{([A-Za-z_][A-Za-z0-9_]*)\}")
COPIED_TEXT_FIELD_NAMES = frozenset(
    {
        "acceptance criteria",
        "definition of done",
        "definition of ready",
        "definition of read",
        "checklist",
    }
)


def _extract_placeholders(value: Any) -> set[str]:
    if isinstance(value, str):
        return {match.group(1) for match in PLACEHOLDER_PATTERN.finditer(value)}
    if isinstance(value, list):
        found: set[str] = set()
        for item in value:
            found.update(_extract_placeholders(item))
        return found
    if isinstance(value, dict):
        found: set[str] = set()
        for item in value.values():
            found.update(_extract_placeholders(item))
        return found
    return set()


def _replace_placeholders(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        return REPLACE_PLACEHOLDER_PATTERN.sub(
            lambda match: replacements.get(match.group(1), match.group(0)),
            value,
        )
    if isinstance(value, list):
        return [_replace_placeholders(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_placeholders(item, replacements) for key, item in value.items()}
    return value


def _validate_no_unresolved_template_placeholders(summary: str, description: str | None) -> None:
    unresolved_placeholders = sorted(_extract_placeholders(summary) | _extract_placeholders(description))
    if unresolved_placeholders:
        rendered_placeholders = ", ".join(f"{{{placeholder}}}" for placeholder in unresolved_placeholders)
        raise ValueError(
            "jira_create_issue cannot be used with unresolved template placeholders "
            f"({rendered_placeholders}). Use jira_create_ticket_from_template instead."
        )


def _normalize_template_marker_values(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        normalized = value.strip().lower()
        return {normalized} if normalized else set()
    if isinstance(value, list):
        found: set[str] = set()
        for item in value:
            found.update(_normalize_template_marker_values(item))
        return found
    if isinstance(value, dict):
        found: set[str] = set()
        for key in ("value", "name", "label"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                found.add(candidate.strip().lower())
        return found
    return set()


def _issue_matches_template_marker(fields: dict[str, Any], *, marker_value: str) -> bool:
    normalized_marker = marker_value.strip().lower()
    if not normalized_marker:
        return False

    labels = fields.get("labels")
    return normalized_marker in _normalize_template_marker_values(labels)


def _parse_json_object_argument(raw_value: str | None, *, argument_name: str) -> dict[str, Any]:
    if raw_value is None or not raw_value.strip():
        return {}

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{argument_name} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{argument_name} must decode to a JSON object")
    return parsed


def _coerce_dict_to_json_string(value: Any) -> Any:
    if isinstance(value, dict):
        return json.dumps(value)
    return value


JsonObjectString = Annotated[str, BeforeValidator(_coerce_dict_to_json_string)]


def _parse_string_mapping(raw_value: str | None, *, argument_name: str) -> dict[str, str]:
    if raw_value is None or not raw_value.strip():
        return {}

    try:
        parsed = _parse_json_object_argument(raw_value, argument_name=argument_name)
    except ValueError as exc:
        raise ValueError(
            f"{exc} Pass {argument_name} as a JSON object string. "
            "Escape embedded double quotes as \\\" and backslashes/slashes when needed."
        ) from exc

    values: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            raise ValueError(f"{argument_name} keys must be strings")
        if isinstance(value, (str, int, float, bool)) or value is None:
            values[key] = "" if value is None else str(value)
            continue
        raise ValueError(f"{argument_name} values must be string-compatible scalars")
    return values


def _find_field_ids_by_names(field_definitions: list[dict[str, Any]], field_names: set[str]) -> set[str]:
    normalized_names = {name.strip().lower() for name in field_names if name.strip()}

    def _normalize_name(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

    def _is_checklist_alias_match(field_name: str) -> bool:
        normalized_field_name = _normalize_name(field_name)
        return any(
            checklist_name in normalized_field_name
            for checklist_name in normalized_names
        )

    return {
        str(field_definition.get("id"))
        for field_definition in field_definitions
        if field_definition.get("id")
        and (
            _normalize_name(str(field_definition.get("name") or "")) in normalized_names
            or _is_checklist_alias_match(str(field_definition.get("name") or ""))
        )
    }


def _resolve_template_marker_sources(fields: dict[str, Any], *, marker_value: str) -> list[str]:
    normalized_marker = marker_value.strip().lower()
    if not normalized_marker:
        return []

    sources: list[str] = []
    if normalized_marker in _normalize_template_marker_values(fields.get("labels")):
        sources.append("labels")
    return sources


def _collect_template_placeholders(source_fields: dict[str, Any], *, copied_text_field_ids: set[str]) -> list[str]:
    placeholders: set[str] = set()
    placeholders.update(_extract_placeholders(source_fields.get("summary")))
    placeholders.update(_extract_placeholders(source_fields.get("description")))
    for field_id in copied_text_field_ids:
        placeholders.update(_extract_placeholders(source_fields.get(field_id)))
    return sorted(placeholders)


def _normalize_components(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        component_id = item.get("id")
        component_name = item.get("name")
        if component_id is not None and str(component_id).strip():
            normalized.append({"id": str(component_id).strip()})
            continue
        if isinstance(component_name, str) and component_name.strip():
            normalized.append({"name": component_name.strip()})
    return normalized


def _component_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    for component in _normalize_components(value):
        if "id" in component:
            tokens.add(f"id:{component['id']}")
        elif "name" in component:
            tokens.add(f"name:{component['name'].lower()}")
    return tokens


async def _enforce_components_copied(
    client: AtlassianClient,
    *,
    target_issue_key: str,
    source_components: Any,
) -> None:
    desired_components = _normalize_components(source_components)
    if not desired_components:
        return

    desired_tokens = _component_tokens(desired_components)
    if not desired_tokens:
        return

    target_issue = await client.get_issue_fields(target_issue_key, fields=["components"])
    target_fields = target_issue.get("fields") or {}
    target_tokens = _component_tokens(target_fields.get("components") if isinstance(target_fields, dict) else None)
    if desired_tokens.issubset(target_tokens):
        return

    try:
        await client.update_issue(target_issue_key, {"components": desired_components})
    except Exception as exc:
        raise ValueError(
            f"Components could not be copied to {target_issue_key}. "
            "Ensure the Components field is available on the create/edit screens."
        ) from exc

    verified_issue = await client.get_issue_fields(target_issue_key, fields=["components"])
    verified_fields = verified_issue.get("fields") or {}
    verified_tokens = _component_tokens(verified_fields.get("components") if isinstance(verified_fields, dict) else None)
    if not desired_tokens.issubset(verified_tokens):
        raise ValueError(
            f"Components were not fully copied to {target_issue_key}. "
            "Ensure all source components exist in the target project and are selectable."
        )


def _build_issue_blueprint(
    source_fields: dict[str, Any],
    *,
    copied_text_field_ids: set[str],
    replacements: dict[str, str] | None = None,
    marker_value: str = "template",
    parent_issue_key: str | None = None,
) -> dict[str, Any]:
    issue_type_name = str((source_fields.get("issuetype") or {}).get("name") or "").strip()
    if not issue_type_name:
        raise ValueError("Source issue is missing issuetype.name")

    summary = source_fields.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Source issue is missing summary")

    effective_replacements = replacements or {}
    rendered_summary = _replace_placeholders(summary, effective_replacements)
    additional_fields: dict[str, Any] = {}

    description = source_fields.get("description")
    rendered_description = _replace_placeholders(description, effective_replacements) if description is not None else None
    if rendered_description is not None and not isinstance(rendered_description, str):
        additional_fields["description"] = rendered_description
        rendered_description = None

    labels = source_fields.get("labels")
    if isinstance(labels, list):
        filtered_labels = [
            label
            for label in labels
            if isinstance(label, str) and label.strip() and label.strip().lower() != marker_value.strip().lower()
        ]
        if filtered_labels:
            additional_fields["labels"] = filtered_labels

    components = _normalize_components(source_fields.get("components"))
    if components:
        additional_fields["components"] = components

    for field_name in ("fixVersions", "priority"):
        field_value = source_fields.get(field_name)
        if field_value:
            additional_fields[field_name] = field_value

    for field_id in copied_text_field_ids:
        field_value = source_fields.get(field_id)
        if field_value is not None:
            additional_fields[field_id] = _replace_placeholders(field_value, effective_replacements)

    if parent_issue_key:
        additional_fields["parent"] = {"key": parent_issue_key}

    return {
        "summary": rendered_summary,
        "issue_type": issue_type_name,
        "description": rendered_description,
        "additional_fields": additional_fields,
    }


async def _copy_issue_attachments(
    client: AtlassianClient,
    *,
    attachments: Any,
    target_issue_key: str,
) -> int:
    if not isinstance(attachments, list):
        return 0

    copied = 0
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        content_url = attachment.get("content")
        filename = attachment.get("filename")
        if not isinstance(content_url, str) or not content_url or not isinstance(filename, str) or not filename:
            continue
        content = await client.download_jira_attachment(content_url)
        await client.upload_jira_attachment(
            target_issue_key,
            filename=filename,
            content=content,
            media_type=str(attachment.get("mimeType") or "application/octet-stream"),
        )
        copied += 1
    return copied


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def jira_list_projects() -> list[dict[str, str | None]]:
        """List Jira projects visible to the configured Atlassian account."""
        projects = await _get_client().list_projects()
        return [compact_project(project) for project in projects]

    @mcp.tool()
    async def jira_list_fields() -> list[dict[str, str | bool | None]]:
        """List Jira fields available to the current account."""
        fields = await _get_client().list_fields()
        return [compact_jira_field(field) for field in fields]

    @mcp.tool()
    async def jira_search_fields(query: str, limit: int = 20) -> list[dict[str, str | bool | None]]:
        """Search Jira fields by field id or display name."""
        fields = await _get_client().search_fields(query=query, limit=limit)
        return [compact_jira_field(field) for field in fields]

    @mcp.tool()
    async def jira_get_field_options(
        field_id: str,
        context_id: str | None = None,
        project_key: str | None = None,
        issue_type: str | None = None,
    ) -> dict[str, Any]:
        """Get allowed values for a Jira field.

        For Jira Cloud, field options are loaded via field context APIs.
        For Jira Server/Data Center, provide project_key and issue_type to resolve options from createmeta.
        """
        return await _get_client().get_field_options(
            field_id=field_id,
            context_id=context_id,
            project_key=project_key,
            issue_type=issue_type,
        )

    @mcp.tool()
    async def jira_list_statuses() -> list[dict[str, str | None]]:
        """List Jira statuses visible to the current account."""
        statuses = await _get_client().list_statuses()
        return [compact_jira_status(status) for status in statuses]

    @mcp.tool()
    async def jira_list_issue_types() -> list[dict[str, str | bool | None]]:
        """List Jira issue types visible to the current account."""
        issue_types = await _get_client().list_issue_types()
        return [compact_jira_issue_type(issue_type) for issue_type in issue_types]

    @mcp.tool()
    async def jira_build_jql(
        project_keys: list[str] | None = None,
        assignee: str | None = None,
        reporter: str | None = None,
        statuses: list[str] | None = None,
        issue_types: list[str] | None = None,
        priorities: list[str] | None = None,
        text: str | None = None,
        updated_since: str | None = None,
        resolution: str | None = None,
        order_by: Literal["updated", "created", "priority", "status", "assignee"] = "updated",
        order_direction: Literal["ASC", "DESC"] = "DESC",
    ) -> dict[str, str]:
        """Build a Jira JQL query from structured filters.

        project_keys: one or more Jira project keys, e.g. ["FLIP", "ENVCOMP"].
          Single key produces 'project = X'; multiple produces 'project in (X, Y)'.
        updated_since: lower bound for the updated >= filter. Common relative date values:
          "-1w" or "-7d" (last 7 days / last week), "-1d" (yesterday),
          "-30d" (last 30 days), "startOfDay()" (today), "startOfWeek()" (this week),
          "startOfWeek(-1)" (last week from Monday), "startOfMonth()" (this month),
          "2026-01-01" (on or after a specific date).
        assignee: account name or "currentUser()" for the currently authenticated user.
        text: keyword search matched against issue summary and description.
          Use only for actual keyword lookups, NOT to express time or project filters.
        """
        return {
            "jql": build_common_jql(
                project_keys=project_keys,
                assignee=assignee,
                reporter=reporter,
                statuses=statuses,
                issue_types=issue_types,
                priorities=priorities,
                text=text,
                updated_since=updated_since,
                resolution=resolution,
                order_by=order_by,
                order_direction=order_direction,
            )
        }

    @mcp.tool()
    async def jira_search_issues(
        jql: str,
        limit: int = 10,
        fields: list[str] | None = None,
        start_at: int = 0,
        validate_query: bool = True,
    ) -> dict[str, Any]:
        """Search Jira issues using JQL with pagination support."""
        if not _looks_like_jql(jql):
            raise ValueError(
                "Expected a JQL query. Build JQL first with jira_build_jql or use jira_query_issues_from_text."
            )

        data = await _get_client().search_issues(
            jql=jql,
            limit=limit,
            fields=fields,
            start_at=start_at,
            validate_query=validate_query,
        )
        return _to_paginated_issue_result(data, default_start_at=start_at, default_limit=limit)

    @mcp.tool()
    async def jira_validate_jql(jql: str) -> dict[str, Any]:
        """Validate JQL syntax and permissions without returning a full result set."""
        if not _looks_like_jql(jql):
            return {
                "valid": False,
                "reason": "Input does not look like JQL",
                "hint": "Use jira_build_jql first, then validate and run jira_search_issues.",
            }

        try:
            data = await _get_client().search_issues(
                jql=jql,
                limit=1,
                start_at=0,
                validate_query=True,
            )
            return {
                "valid": True,
                "jql": jql,
                "total": data.get("total"),
            }
        except Exception as exc:
            return {
                "valid": False,
                "jql": jql,
                "reason": f"{type(exc).__name__}: {exc}",
            }

    @mcp.tool()
    async def jira_query_issues_from_text(
        project_keys: list[str] | None = None,
        assignee: str | None = None,
        reporter: str | None = None,
        statuses: list[str] | None = None,
        issue_types: list[str] | None = None,
        updated_since: str | None = None,
        text: str | None = None,
        limit: int = 10,
        start_at: int = 0,
    ) -> dict[str, Any]:
        """Build and run a Jira JQL query from structured filters derived from a natural-language request.

        Extract the user's intent into explicit parameters rather than passing raw natural language
        as a search query. The LLM should populate these fields from context:
        project_keys: one or more project keys mentioned by the user, e.g. ["FLIP", "ENVCOMP"].
        updated_since: relative or absolute date for the updated >= filter.
          Common patterns: "-1w" or "-7d" (last week / last 7 days), "-1d" (yesterday),
          "-30d" (last 30 days), "startOfDay()" (today), "startOfWeek()" (this week),
          "startOfWeek(-1)" (last week from Monday), "startOfMonth()" (this month),
          "2026-01-01" (on or after a specific date).
        assignee: account name or "currentUser()" for the authenticated user.
        statuses: list of status names, e.g. ["In Progress", "Open"].
        issue_types: list of issue types, e.g. ["Bug", "Story"].
        text: keyword search in issue summary and description.
          Use only for actual keyword lookups, NOT to express time, project, or status filters.
        """
        jql = build_common_jql(
            project_keys=project_keys,
            assignee=assignee,
            reporter=reporter,
            statuses=statuses,
            issue_types=issue_types,
            text=text,
            updated_since=updated_since,
            order_by="updated",
            order_direction="DESC",
        )

        data = await _get_client().search_issues(
            jql=jql,
            limit=limit,
            start_at=start_at,
            validate_query=True,
        )

        result = _to_paginated_issue_result(data, default_start_at=start_at, default_limit=limit)
        result["jql_used"] = jql
        return result

    @mcp.tool()
    async def jira_get_issue(issue_key: str) -> dict[str, object]:
        """Fetch a Jira issue by key, for example PROJ-123."""
        return await _get_client().get_issue(issue_key)

    @mcp.tool()
    async def jira_list_templates(project_key: str, marker_value: str = "template") -> dict[str, Any]:
        """List template issues in a Jira project. 
        Returns an additional columns the placeholders as found in subject, summary or checklists.
        Templates are detected via labels (default: template).
        """
        normalized_project_key = project_key.strip().upper()
        if not normalized_project_key:
            raise ValueError("project_key is required")

        client = _get_client()
        requested_fields = ["summary", "status", "issuetype", "labels"]

        templates: list[dict[str, Any]] = []
        start_at = 0
        scanned_issues = 0
        total_issues = 0
        jql = f"project = {normalized_project_key} ORDER BY updated DESC"

        while True:
            page = await client.search_issues(
                jql=jql,
                limit=50,
                fields=requested_fields,
                start_at=start_at,
                validate_query=True,
            )
            issues = page.get("issues", [])
            total_issues = int(page.get("total", total_issues))
            if not isinstance(issues, list) or not issues:
                break

            scanned_issues += len(issues)
            for issue in issues:
                if not isinstance(issue, dict):
                    continue
                fields = issue.get("fields") or {}
                if not isinstance(fields, dict):
                    continue
                if not _issue_matches_template_marker(fields, marker_value=marker_value):
                    continue
                templates.append(
                    {
                        "id": issue.get("id"),
                        "key": issue.get("key"),
                        "summary": fields.get("summary"),
                        "issue_type": (fields.get("issuetype") or {}).get("name"),
                        "status": (fields.get("status") or {}).get("name"),
                        "template_markers": _resolve_template_marker_sources(
                            fields,
                            marker_value=marker_value,
                        ),
                    }
                )

            start_at += len(issues)
            if start_at >= total_issues:
                break

        return {
            "project_key": normalized_project_key,
            "marker_value": marker_value,
            "template_count": len(templates),
            "scanned_issues": scanned_issues,
            "total_issues": total_issues,
            "templates": templates,
        }

    @mcp.tool()
    async def jira_create_issue(
        project_key: str,
        summary: str,
        issue_type: str,
        description: str | None = None,
        assignee: str | None = None,
        additional_fields: str | None = None,
    ) -> dict[str, Any]:
        """Create a Jira issue with optional description, assignee, and additional fields JSON.

        Use `jira_create_ticket_from_template` when placeholders such as
        `{integration}` are present in summary/description.
        """
        _validate_no_unresolved_template_placeholders(summary, description)

        parsed_additional_fields = _parse_json_object_argument(
            additional_fields,
            argument_name="additional_fields",
        ) or None

        issue = await _get_client().create_issue(
            project_key=project_key,
            summary=summary,
            issue_type=issue_type,
            description=description,
            assignee=assignee,
            additional_fields=parsed_additional_fields,
        )
        issue_key = str(issue.get("key") or "")
        return {
            "issue": {
                "id": issue.get("id"),
                "key": issue_key,
                "url": _build_browse_url(issue_key) if issue_key else None,
            },
            "status": "created",
        }

    @mcp.tool()
    async def jira_create_ticket_from_template(
        template_issue_key: str,
        project_key: str | None = None,
        placeholder_values: JsonObjectString | None = None,
        include_subtasks: bool | None = None,
        confirmation_token: str | None = None,
    ) -> dict[str, Any]:
        """Create a Jira ticket from a template issue.

        DIALOG:
        Run the dialog and invocation of this tool.
        First dialog: Do you want to includ subtasks from the template? (yes/no) Default value filled should be: yes
        Second dialog (optional when placeholders found): Show placeholder name and ask for value.

        VALIDATION: The template issue must exist, be marked with the "template"
        label, and be a parent task (not a sub-task). The tool validates this before
        proceeding. If validation fails, an actionable error is raised.
        
        Args:
            template_issue_key: Jira issue key for the template ticket.
            project_key: Target project key. Defaults to the template issue's project.
            placeholder_values: JSON object string mapping placeholder names to values.
                              Example: '{"integration":"myintegration","owner":"Jane Doe"}'
                              When generated by an LLM, ensure JSON escaping is valid
                              (e.g., embedded quotes escaped as \\\"\").
            include_subtasks: Whether to create subtasks from template (None asks user).

        Returns:
            - status="needs_subtask_confirmation" with questions if include_subtasks is None
            - status="needs_placeholder_values" if placeholder values incomplete
            - status="created" with issue details on success

        Post Tool Actions:
        - Show the Parent tasks in a table in column "Parent" and subtasks in column "Sub Tasks" with links to the created issues. If multiple subtasks are created, list them all in the "Sub Tasks" column each in new line. The values should be links to the real tickets.    
        """
        if not isinstance(confirmation_token, str) or not confirmation_token.strip():
            input_context_id = _new_input_context_id()
            return {
                "status": "needs_subtask_confirmation",
                "template_issue_key": template_issue_key,
                "project_key": project_key,
                "reset_previous_inputs": True,
                "input_context_id": input_context_id,
                "questions": [
                    {
                        "field": "include_subtasks",
                        "prompt": "Should subtasks be created from the template?",
                        "type": "boolean",
                        "remember": False,
                        "input_context_id": input_context_id,
                    },
                    {
                        "field": "confirmation_token",
                        "prompt": "Confirmation token (leave as-is)",
                        "default": input_context_id,
                        "value": input_context_id,
                        "type": "string",
                        "remember": False,
                        "input_context_id": input_context_id,
                    }
                ],
            }

        if include_subtasks is None:
            input_context_id = _new_input_context_id()
            return {
                "status": "needs_subtask_confirmation",
                "template_issue_key": template_issue_key,
                "project_key": project_key,
                "reset_previous_inputs": True,
                "input_context_id": input_context_id,
                "questions": [
                    {
                        "field": "include_subtasks",
                        "prompt": "Should subtasks be created from the template?",
                        "type": "boolean",
                        "remember": False,
                        "input_context_id": input_context_id,
                    },
                    {
                        "field": "confirmation_token",
                        "prompt": "Confirmation token (leave as-is)",
                        "default": input_context_id,
                        "value": input_context_id,
                        "type": "string",
                        "remember": False,
                        "input_context_id": input_context_id,
                    }
                ],
            }

        # EARLY VALIDATION: Verify template issue exists and is marked as a template
        client = _get_client()
        try:
            template_check_issue = await client.get_issue_fields(
                template_issue_key,
                fields=["labels", "key", "summary", "issuetype", "parent"],
            )
        except Exception as exc:
            raise ValueError(
                f"Template issue {template_issue_key} not found or inaccessible. "
                f"Verify the issue key exists and you have access to it. Error: {exc}"
            ) from exc

        template_check_fields = template_check_issue.get("fields") or {}
        if not _issue_matches_template_marker(template_check_fields, marker_value="template"):
            raise ValueError(
                f"Issue {template_issue_key} is not marked as a template. "
                f"Template issues must have the 'template' label. "
                f"To create a template, add the 'template' label to issue {template_issue_key}."
            )

        issue_type = template_check_fields.get("issuetype")
        parent = template_check_fields.get("parent")
        is_subtask = False
        if isinstance(issue_type, dict) and issue_type.get("subtask") is True:
            is_subtask = True
        if isinstance(parent, dict) and parent.get("key"):
            is_subtask = True
        if is_subtask:
            raise ValueError(
                f"Issue {template_issue_key} is a sub-task and cannot be used as a template source. "
                "Use a parent task (non-sub-task) that has the 'template' label."
            )

        field_definitions = await client.list_fields()
        copied_text_field_ids = _find_field_ids_by_names(field_definitions, set(COPIED_TEXT_FIELD_NAMES))
        source_issue = await client.get_issue_fields(
            template_issue_key,
            fields=[
                "summary",
                "description",
                "issuetype",
                "project",
                "labels",
                "components",
                "fixVersions",
                "priority",
                "subtasks",
                "attachment",
                *sorted(copied_text_field_ids),
            ],
        )
        source_fields = source_issue.get("fields") or {}
        if not isinstance(source_fields, dict):
            raise ValueError(f"Template issue {template_issue_key} returned no fields")

        replacements = _parse_string_mapping(placeholder_values, argument_name="placeholder_values")
        placeholders = _collect_template_placeholders(source_fields, copied_text_field_ids=copied_text_field_ids)
        missing_placeholders = [placeholder for placeholder in placeholders if placeholder not in replacements]
        target_project_key = str(project_key or (source_fields.get("project") or {}).get("key") or "").strip().upper()
        if not target_project_key:
            raise ValueError("project_key is required when the template issue has no project key")

        blueprint = _build_issue_blueprint(
            source_fields,
            copied_text_field_ids=copied_text_field_ids,
            replacements=replacements,
            marker_value="template",
        )

        if missing_placeholders:
            input_context_id = _new_input_context_id()
            return {
                "status": "needs_placeholder_values",
                "template_issue_key": template_issue_key,
                "project_key": target_project_key,
                "include_subtasks": include_subtasks,
                "placeholders": missing_placeholders,
                "reset_previous_inputs": True,
                "input_context_id": input_context_id,
                "questions": [
                    {
                        "placeholder": placeholder,
                        "prompt": f"Enter value for {{{placeholder}}} (used in ticket summary/description/checklists)",
                        "remember": False,
                        "input_context_id": input_context_id,
                    }
                    for placeholder in missing_placeholders
                ],
                "preview": {
                    "summary": blueprint["summary"],
                    "issue_type": blueprint["issue_type"],
                },
            }

        created_issue = await _create_issue_tolerant(
            client,
            project_key=target_project_key,
            summary=str(blueprint["summary"]),
            issue_type=str(blueprint["issue_type"]),
            description=blueprint["description"] if isinstance(blueprint["description"], str) else None,
            additional_fields=dict(blueprint["additional_fields"]),
        )
        issue_key = str(created_issue.get("key") or "")
        if issue_key:
            await _enforce_components_copied(
                client,
                target_issue_key=issue_key,
                source_components=source_fields.get("components"),
            )
        created_subtasks: list[dict[str, Any]] = []
        if include_subtasks:
            subtasks = source_fields.get("subtasks") or []
            if isinstance(subtasks, list):
                for subtask in subtasks:
                    if not isinstance(subtask, dict) or not subtask.get("key"):
                        continue
                    subtask_key = str(subtask.get("key"))
                    fields_to_copy = [
                        "summary",
                        "description",
                        "issuetype",
                        "labels",
                        "components",
                        "fixVersions",
                        "priority",
                        "attachment",
                        *sorted(copied_text_field_ids),
                    ]
                    subtask_issue = await client.get_issue_fields(subtask_key, fields=fields_to_copy)
                    subtask_fields = subtask_issue.get("fields") or {}
                    if not isinstance(subtask_fields, dict):
                        continue
                    subtask_blueprint = _build_issue_blueprint(
                        subtask_fields,
                        copied_text_field_ids=copied_text_field_ids,
                        replacements=replacements,
                        marker_value="template",
                        parent_issue_key=issue_key,
                    )
                    created_subtask = await _create_issue_tolerant(
                        client,
                        project_key=target_project_key,
                        summary=str(subtask_blueprint["summary"]),
                        issue_type=str(subtask_blueprint["issue_type"]),
                        description=(
                            subtask_blueprint["description"] if isinstance(subtask_blueprint["description"], str) else None
                        ),
                        additional_fields=dict(subtask_blueprint["additional_fields"]),
                    )
                    created_subtask_key = str(created_subtask.get("key") or "")
                    if created_subtask_key:
                        await _enforce_components_copied(
                            client,
                            target_issue_key=created_subtask_key,
                            source_components=subtask_fields.get("components"),
                        )
                        created_subtasks.append(
                            {
                                "source_issue_key": subtask_key,
                                "issue": {
                                    "id": created_subtask.get("id"),
                                    "key": created_subtask_key,
                                    "url": _build_browse_url(created_subtask_key),
                                },
                            }
                        )

        parent_task = {
            "id": created_issue.get("id"),
            "key": issue_key,
            "url": _build_browse_url(issue_key) if issue_key else None,
        }
        result_table = _build_parent_subtasks_table(
            parent_key=parent_task.get("key"),
            parent_url=parent_task.get("url"),
            subtasks=created_subtasks,
        )
        return {
            "status": "created",
            "template_issue_key": template_issue_key,
            "project_key": target_project_key,
            "result_display": "table",
            "result_display_note": "Render result_table as a markdown table.",
            "result_table": result_table,
            "placeholders_used": replacements,
        }

    @mcp.tool()
    async def jira_clone_ticket(
        source_issue_key: str,
        project_key: str | None = None,
        include_subtasks: bool | None = None,
        include_attachments: bool | None = None,
        confirmation_token: str | None = None,
    ) -> dict[str, Any]:
        """Clone a Jira issue, optionally including subtasks and attachments.

        Returns a confirmation dialog requesting clone preferences if not provided.
        Do NOT use this when cloning from a template issue; use jira_create_ticket_from_template.

        Args:
            source_issue_key: Issue key to clone (e.g., PROJ-123).
            project_key: Target project key; defaults to source project.
            include_subtasks: Clone subtasks (None asks user, default: yes).
            include_attachments: Copy attachments (None asks user, default: yes).

        Returns:
            - status="needs_clone_confirmation" with questions if preferences not provided
            - status="created" with cloned issue details on success
            Cloned issue is unassigned and does not include comments.
        """
        if not isinstance(confirmation_token, str) or not confirmation_token.strip():
            input_context_id = _new_input_context_id()
            return {
                "status": "needs_clone_confirmation",
                "source_issue_key": source_issue_key,
                "project_key": project_key,
                "reset_previous_inputs": True,
                "input_context_id": input_context_id,
                "questions": [
                    {
                        "field": "include_subtasks",
                        "prompt": "Should subtasks be cloned?",
                        "type": "boolean",
                        "remember": False,
                        "input_context_id": input_context_id,
                    },
                    {
                        "field": "include_attachments",
                        "prompt": "Should attachments be copied?",
                        "type": "boolean",
                        "remember": False,
                        "input_context_id": input_context_id,
                    },
                    {
                        "field": "confirmation_token",
                        "prompt": "Confirmation token (leave as-is)",
                        "default": input_context_id,
                        "value": input_context_id,
                        "type": "string",
                        "remember": False,
                        "input_context_id": input_context_id,
                    },
                ],
            }

        if include_subtasks is None or include_attachments is None:
            input_context_id = _new_input_context_id()
            return {
                "status": "needs_clone_confirmation",
                "source_issue_key": source_issue_key,
                "project_key": project_key,
                "reset_previous_inputs": True,
                "input_context_id": input_context_id,
                "questions": [
                    {
                        "field": "include_subtasks",
                        "prompt": "Should subtasks be cloned?",
                        "type": "boolean",
                        "remember": False,
                        "input_context_id": input_context_id,
                    },
                    {
                        "field": "include_attachments",
                        "prompt": "Should attachments be copied?",
                        "type": "boolean",
                        "remember": False,
                        "input_context_id": input_context_id,
                    },
                    {
                        "field": "confirmation_token",
                        "prompt": "Confirmation token (leave as-is)",
                        "default": input_context_id,
                        "value": input_context_id,
                        "type": "string",
                        "remember": False,
                        "input_context_id": input_context_id,
                    },
                ],
            }

        client = _get_client()
        field_definitions = await client.list_fields()
        copied_text_field_ids = _find_field_ids_by_names(field_definitions, set(COPIED_TEXT_FIELD_NAMES))
        fields_to_copy = [
            "summary",
            "description",
            "issuetype",
            "project",
            "labels",
            "components",
            "fixVersions",
            "priority",
            "parent",
            "subtasks",
            "attachment",
            *sorted(copied_text_field_ids),
        ]
        source_issue = await client.get_issue_fields(source_issue_key, fields=fields_to_copy)
        source_fields = source_issue.get("fields") or {}
        if not isinstance(source_fields, dict):
            raise ValueError(f"Source issue {source_issue_key} returned no fields")

        source_project_key = str((source_fields.get("project") or {}).get("key") or "").strip().upper()
        target_project_key = str(project_key or source_project_key).strip().upper()
        if not target_project_key:
            raise ValueError("project_key is required when the source issue has no project key")

        source_parent = source_fields.get("parent") or {}
        parent_issue_key: str | None = None
        if isinstance(source_parent, dict) and source_parent.get("key"):
            if project_key and target_project_key != source_project_key:
                raise ValueError("Cannot clone a sub-task into a different project without a target parent")
            parent_issue_key = str(source_parent.get("key"))

        blueprint = _build_issue_blueprint(
            source_fields,
            copied_text_field_ids=copied_text_field_ids,
            marker_value="template",
            parent_issue_key=parent_issue_key,
        )
        created_issue = await _create_issue_tolerant(
            client,
            project_key=target_project_key,
            summary=str(blueprint["summary"]),
            issue_type=str(blueprint["issue_type"]),
            description=blueprint["description"] if isinstance(blueprint["description"], str) else None,
            additional_fields=dict(blueprint["additional_fields"]),
        )
        cloned_issue_key = str(created_issue.get("key") or "")
        if not cloned_issue_key:
            raise ValueError(f"Clone creation for {source_issue_key} did not return an issue key")
        await _enforce_components_copied(
            client,
            target_issue_key=cloned_issue_key,
            source_components=source_fields.get("components"),
        )
        await client.clear_issue_assignee(cloned_issue_key)

        attachments_copied = 0
        if include_attachments:
            attachments_copied += await _copy_issue_attachments(
                client,
                attachments=source_fields.get("attachment"),
                target_issue_key=cloned_issue_key,
            )

        cloned_subtasks: list[dict[str, Any]] = []
        if include_subtasks:
            subtasks = source_fields.get("subtasks") or []
            if isinstance(subtasks, list):
                for subtask in subtasks:
                    if not isinstance(subtask, dict) or not subtask.get("key"):
                        continue
                    subtask_key = str(subtask.get("key"))
                    subtask_issue = await client.get_issue_fields(subtask_key, fields=fields_to_copy)
                    subtask_fields = subtask_issue.get("fields") or {}
                    if not isinstance(subtask_fields, dict):
                        continue
                    subtask_blueprint = _build_issue_blueprint(
                        subtask_fields,
                        copied_text_field_ids=copied_text_field_ids,
                        marker_value="template",
                        parent_issue_key=cloned_issue_key,
                    )
                    created_subtask = await _create_issue_tolerant(
                        client,
                        project_key=target_project_key,
                        summary=str(subtask_blueprint["summary"]),
                        issue_type=str(subtask_blueprint["issue_type"]),
                        description=(
                            subtask_blueprint["description"] if isinstance(subtask_blueprint["description"], str) else None
                        ),
                        additional_fields=dict(subtask_blueprint["additional_fields"]),
                    )
                    cloned_subtask_key = str(created_subtask.get("key") or "")
                    if cloned_subtask_key:
                        await _enforce_components_copied(
                            client,
                            target_issue_key=cloned_subtask_key,
                            source_components=subtask_fields.get("components"),
                        )
                        await client.clear_issue_assignee(cloned_subtask_key)
                        if include_attachments:
                            attachments_copied += await _copy_issue_attachments(
                                client,
                                attachments=subtask_fields.get("attachment"),
                                target_issue_key=cloned_subtask_key,
                            )
                    subtask_issue_key = str(created_subtask.get("key") or "")
                    if not subtask_issue_key:
                        continue
                    cloned_subtasks.append(
                        {
                            "source_issue_key": subtask_key,
                            "issue": {
                                "id": created_subtask.get("id"),
                                "key": subtask_issue_key,
                                "url": _build_browse_url(subtask_issue_key),
                            },
                        }
                    )

        clone_issue_key = str(created_issue.get("key") or "")
        parent_task = {
            "id": created_issue.get("id"),
            "key": clone_issue_key,
            "url": _build_browse_url(clone_issue_key) if clone_issue_key else None,
        }
        result_table = _build_parent_subtasks_table(
            parent_key=parent_task.get("key"),
            parent_url=parent_task.get("url"),
            subtasks=cloned_subtasks,
        )
        return {
            "status": "created",
            "source_issue_key": source_issue_key,
            "project_key": target_project_key,
            "include_subtasks": include_subtasks,
            "include_attachments": include_attachments,
            "result_display": "table",
            "result_display_note": "Render result_table as a markdown table.",
            "result_table": result_table,
            "attachments_copied": attachments_copied,
        }

    @mcp.tool()
    async def jira_update_issue(issue_key: str, fields: str) -> dict[str, Any]:
        """Update an existing Jira issue using a JSON object of fields."""
        try:
            parsed_fields = json.loads(fields)
        except json.JSONDecodeError as exc:
            raise ValueError(f"fields must be valid JSON: {exc}") from exc
        if not isinstance(parsed_fields, dict):
            raise ValueError("fields must decode to a JSON object")
        return await _get_client().update_issue(issue_key=issue_key, fields=parsed_fields)

    @mcp.tool()
    async def jira_delete_issue(issue_key: str) -> dict[str, Any]:
        """Delete a Jira issue by key."""
        return await _get_client().delete_issue(issue_key)

    @mcp.tool()
    async def jira_get_transitions(issue_key: str) -> list[dict[str, Any]]:
        """List available transitions for a Jira issue."""
        transitions = await _get_client().list_transitions(issue_key)
        return [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "to_status": (item.get("to") or {}).get("name"),
            }
            for item in transitions
        ]

    @mcp.tool()
    async def jira_add_comment(issue_key: str, comment: str) -> dict[str, str | None]:
        """Add a plain text comment to a Jira issue."""
        result = await _get_client().add_comment(issue_key, comment)
        author = result.get("author") or {}
        return {
            "issue_key": issue_key,
            "comment_id": result.get("id"),
            "author": author.get("displayName"),
            "status": "created",
        }

    @mcp.tool()
    async def jira_edit_comment(issue_key: str, comment_id: str, comment: str) -> dict[str, Any]:
        """Edit an existing comment on a Jira issue."""
        result = await _get_client().edit_comment(issue_key=issue_key, comment_id=comment_id, comment=comment)
        author = result.get("author") or {}
        return {
            "issue_key": issue_key,
            "comment_id": result.get("id") or comment_id,
            "author": author.get("displayName"),
            "status": "updated",
        }

    @mcp.tool()
    async def jira_get_worklog(issue_key: str) -> dict[str, Any]:
        """Get worklog entries for a Jira issue."""
        worklogs = await _get_client().get_worklog(issue_key)
        return {"issue_key": issue_key, "count": len(worklogs), "worklogs": worklogs}

    @mcp.tool()
    async def jira_add_worklog(
        issue_key: str,
        time_spent: str,
        comment: str | None = None,
        started: str | None = None,
    ) -> dict[str, Any]:
        """Add a worklog entry to a Jira issue."""
        result = await _get_client().add_worklog(
            issue_key=issue_key,
            time_spent=time_spent,
            comment=comment,
            started=started,
        )
        return {
            "issue_key": issue_key,
            "worklog_id": result.get("id"),
            "status": "created",
        }

    @mcp.tool()
    async def jira_get_project_versions(project_key: str) -> list[dict[str, Any]]:
        """Get fix versions for a Jira project."""
        return await _get_client().get_project_versions(project_key)

    @mcp.tool()
    async def jira_get_project_components(project_key: str) -> list[dict[str, Any]]:
        """Get components for a Jira project."""
        return await _get_client().get_project_components(project_key)

    @mcp.tool()
    async def jira_get_link_types() -> list[dict[str, Any]]:
        """List available Jira issue link types."""
        return await _get_client().get_link_types()

    @mcp.tool()
    async def jira_create_issue_link(
        link_type: str,
        inward_issue_key: str,
        outward_issue_key: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Create a link between two Jira issues."""
        return await _get_client().create_issue_link(
            link_type=link_type,
            inward_issue_key=inward_issue_key,
            outward_issue_key=outward_issue_key,
            comment=comment,
        )

    @mcp.tool()
    async def jira_remove_issue_link(link_id: str) -> dict[str, Any]:
        """Remove a Jira issue link by id."""
        return await _get_client().remove_issue_link(link_id)

    @mcp.tool()
    async def jira_get_agile_boards(
        limit: int = 25,
        start_at: int = 0,
        board_type: str | None = None,
        project_key_or_id: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """List Jira Agile boards."""
        return await _get_client().get_agile_boards(
            limit=limit,
            start_at=start_at,
            board_type=board_type,
            project_key_or_id=project_key_or_id,
            name=name,
        )

    @mcp.tool()
    async def jira_get_board_issues(
        board_id: str,
        jql: str | None = None,
        limit: int = 25,
        start_at: int = 0,
    ) -> dict[str, Any]:
        """Get issues on an Agile board."""
        return await _get_client().get_board_issues(
            board_id=board_id,
            jql=jql,
            limit=limit,
            start_at=start_at,
        )

    @mcp.tool()
    async def jira_get_sprints_from_board(
        board_id: str,
        state: str | None = None,
        limit: int = 25,
        start_at: int = 0,
    ) -> dict[str, Any]:
        """List sprints for an Agile board."""
        return await _get_client().get_sprints_from_board(
            board_id=board_id,
            state=state,
            limit=limit,
            start_at=start_at,
        )

    @mcp.tool()
    async def jira_get_sprint_issues(
        sprint_id: str,
        jql: str | None = None,
        limit: int = 25,
        start_at: int = 0,
    ) -> dict[str, Any]:
        """Get issues in a sprint."""
        return await _get_client().get_sprint_issues(
            sprint_id=sprint_id,
            jql=jql,
            limit=limit,
            start_at=start_at,
        )

    @mcp.tool()
    async def jira_create_sprint(
        name: str,
        board_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        goal: str | None = None,
    ) -> dict[str, Any]:
        """Create a sprint on an Agile board."""
        return await _get_client().create_sprint(
            name=name,
            board_id=board_id,
            start_date=start_date,
            end_date=end_date,
            goal=goal,
        )

    @mcp.tool()
    async def jira_update_sprint(
        sprint_id: str,
        name: str | None = None,
        state: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        goal: str | None = None,
    ) -> dict[str, Any]:
        """Update sprint metadata/state."""
        return await _get_client().update_sprint(
            sprint_id=sprint_id,
            name=name,
            state=state,
            start_date=start_date,
            end_date=end_date,
            goal=goal,
        )

    @mcp.tool()
    async def jira_add_issues_to_sprint(sprint_id: str, issue_keys: list[str]) -> dict[str, Any]:
        """Add multiple issues to a sprint."""
        if not issue_keys:
            raise ValueError("issue_keys must contain at least one issue key")
        return await _get_client().add_issues_to_sprint(sprint_id=sprint_id, issue_keys=issue_keys)

    @mcp.tool()
    async def jira_get_service_desk_for_project(project_key: str) -> dict[str, Any]:
        """Get service desk information for a project key."""
        desk = await _get_client().get_service_desk_for_project(project_key)
        if desk is None:
            return {"project_key": project_key, "found": False}
        return {"project_key": project_key, "found": True, "service_desk": desk}

    @mcp.tool()
    async def jira_get_service_desk_queues(service_desk_id: str, limit: int = 50, start_at: int = 0) -> dict[str, Any]:
        """List queues for a Jira Service Desk."""
        return await _get_client().get_service_desk_queues(
            service_desk_id=service_desk_id,
            limit=limit,
            start_at=start_at,
        )

    @mcp.tool()
    async def jira_get_queue_issues(
        service_desk_id: str,
        queue_id: str,
        limit: int = 25,
        start_at: int = 0,
    ) -> dict[str, Any]:
        """Get issues in a Jira Service Desk queue."""
        return await _get_client().get_queue_issues(
            service_desk_id=service_desk_id,
            queue_id=queue_id,
            limit=limit,
            start_at=start_at,
        )

    @mcp.tool()
    async def jira_get_issue_dates(issue_key: str) -> dict[str, Any]:
        """Get common date fields for a Jira issue."""
        return await _get_client().get_issue_dates(issue_key)

    @mcp.tool()
    async def jira_get_issue_sla(issue_key: str) -> dict[str, Any]:
        """Get Jira Service Management SLA info for an issue."""
        return await _get_client().get_issue_sla(issue_key)

    @mcp.tool()
    async def jira_get_user_profile(user_identifier: str) -> dict[str, Any]:
        """Get Jira user profile by accountId (Cloud) or username (Server/DC)."""
        return await _get_client().get_user_profile(user_identifier)

    @mcp.tool()
    async def jira_get_issue_watchers(issue_key: str) -> dict[str, Any]:
        """Get watchers for a Jira issue."""
        return await _get_client().get_issue_watchers(issue_key)

    @mcp.tool()
    async def jira_add_watcher(issue_key: str, user_identifier: str) -> dict[str, Any]:
        """Add a watcher to a Jira issue."""
        return await _get_client().add_watcher(issue_key=issue_key, user_identifier=user_identifier)

    @mcp.tool()
    async def jira_remove_watcher(
        issue_key: str,
        username: str | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        """Remove a watcher from a Jira issue.

        Cloud: provide account_id.
        Server/DC: provide username.
        """
        return await _get_client().remove_watcher(
            issue_key=issue_key,
            username=username,
            account_id=account_id,
        )

    @mcp.tool()
    async def jira_get_issue_proforma_forms(issue_key: str) -> dict[str, Any]:
        """Get Jira Forms (ProForma) attached to an issue."""
        forms = await _get_client().get_issue_proforma_forms(issue_key)
        return {"issue_key": issue_key, "count": len(forms), "forms": forms}

    @mcp.tool()
    async def jira_get_proforma_form_details(issue_key: str, form_id: str) -> dict[str, Any]:
        """Get details for a specific Jira ProForma form."""
        details = await _get_client().get_proforma_form_details(issue_key=issue_key, form_id=form_id)
        return {"issue_key": issue_key, "form_id": form_id, "details": details}

    @mcp.tool()
    async def jira_update_proforma_form_answers(
        issue_key: str,
        form_id: str,
        answers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Update answers for a Jira ProForma form."""
        result = await _get_client().update_proforma_form_answers(
            issue_key=issue_key,
            form_id=form_id,
            answers=answers,
        )
        return {"issue_key": issue_key, "form_id": form_id, "status": "updated", "result": result}

    @mcp.tool()
    async def jira_get_issue_development_info(
        issue_key: str,
        application_type: str | None = None,
        data_type: str | None = None,
    ) -> dict[str, Any]:
        """Get development metadata for a Jira issue."""
        return await _get_client().get_issue_development_info(
            issue_key=issue_key,
            application_type=application_type,
            data_type=data_type,
        )

    @mcp.tool()
    async def jira_get_issues_development_info(
        issue_keys: list[str],
        application_type: str | None = None,
        data_type: str | None = None,
    ) -> dict[str, Any]:
        """Get aggregate development metadata for multiple Jira issues."""
        return await _get_client().get_issues_development_info(
            issue_keys=issue_keys,
            application_type=application_type,
            data_type=data_type,
        )

    @mcp.tool()
    async def jira_transition_issue(
        issue_key: str,
        transition_name: str | None = None,
        transition_id: str | None = None,
    ) -> dict[str, str]:
        """Transition a Jira issue by transition name or transition id."""
        if not transition_name and not transition_id:
            raise ValueError("Provide either transition_name or transition_id")
        return await _get_client().transition_issue(
            issue_key,
            transition_name=transition_name,
            transition_id=transition_id,
        )

    @mcp.tool()
    async def jira_download_attachments(
        issue_key: str,
        include_content: bool = False,
        max_inline_bytes: int = 2_000_000,
    ) -> dict[str, Any]:
        """Get Jira issue attachments with optional inline base64 content."""
        attachments = await _get_client().get_issue_attachments(issue_key)
        results: list[dict[str, Any]] = []
        for item in attachments:
            content_url = item.get("content")
            size = int(item.get("size") or 0)
            entry: dict[str, Any] = {
                "id": item.get("id"),
                "filename": item.get("filename"),
                "mime_type": item.get("mimeType"),
                "size": size,
                "content_url": content_url,
                "thumbnail_url": item.get("thumbnail"),
            }
            if include_content and isinstance(content_url, str) and content_url and size <= max_inline_bytes:
                content = await _get_client().download_jira_attachment(content_url)
                entry["content_base64"] = base64.b64encode(content).decode("ascii")
                entry["content_inline"] = True
            elif include_content:
                entry["content_inline"] = False
                entry["inline_reason"] = "too_large_or_missing_url"
            results.append(entry)

        return {
            "issue_key": issue_key,
            "count": len(results),
            "attachments": results,
        }

    @mcp.tool()
    async def jira_get_issue_images(
        issue_key: str,
        include_content: bool = False,
        max_inline_bytes: int = 2_000_000,
    ) -> dict[str, Any]:
        """Get image attachments for a Jira issue with optional inline base64 content."""
        payload = await jira_download_attachments(
            issue_key=issue_key,
            include_content=include_content,
            max_inline_bytes=max_inline_bytes,
        )
        image_items = [
            item
            for item in payload["attachments"]
            if str(item.get("mime_type", "")).lower().startswith("image/")
        ]
        return {
            "issue_key": issue_key,
            "count": len(image_items),
            "images": image_items,
        }
