from __future__ import annotations

import asyncio
import base64
import json
from urllib.parse import urljoin
from typing import Any, Literal

import httpx

from .config import AtlassianConfig, ServiceConfig


MAX_RETRIES = 3
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class AtlassianRequestError(RuntimeError):
    """Raised when an Atlassian API request fails with a non-auth error."""


class AtlassianAuthenticationError(PermissionError):
    """Raised when Atlassian API credentials are invalid or expired."""


class AtlassianClient:
    def __init__(self, config: AtlassianConfig) -> None:
        self._config = config
        self._jira_headers = self._build_headers(config.jira)
        self._confluence_headers = self._build_headers(config.confluence)

    @staticmethod
    def _build_headers(service: ServiceConfig) -> dict[str, str]:
        authorization: str
        if service.auth_mode == "basic":
            token = f"{service.username}:{service.password}".encode("utf-8")
            authorization = f"Basic {base64.b64encode(token).decode('ascii')}"
        else:
            authorization = f"Bearer {service.bearer_token}"

        return {
            "Accept": "application/json",
            "Authorization": authorization,
            "Content-Type": "application/json",
            "User-Agent": "atlassian-mcp-server/0.1.0",
        }

    @property
    def jira_headers(self) -> dict[str, str]:
        return dict(self._jira_headers)

    @property
    def confluence_headers(self) -> dict[str, str]:
        return dict(self._confluence_headers)

    def _jira_path(self, path: str) -> str:
        return f"{self._config.jira.api_base_path}{path}"

    def _confluence_path(self, path: str) -> str:
        return f"{self._config.confluence.api_base_path}{path}"

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError):
            text = response.text.strip()
            return text[:500] if text else response.reason_phrase

        if isinstance(payload, dict):
            error_messages = payload.get("errorMessages")
            if isinstance(error_messages, list) and error_messages:
                first = error_messages[0]
                return str(first)

            message = payload.get("message") or payload.get("error") or payload.get("detail")
            if message:
                return str(message)

            errors = payload.get("errors")
            if isinstance(errors, dict) and errors:
                first_key = next(iter(errors.keys()))
                return f"{first_key}: {errors[first_key]}"

        return response.reason_phrase

    @staticmethod
    def _retry_delay_seconds(response: httpx.Response | None, attempt: int) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                return float(max(1, int(retry_after)))

        # Exponential backoff: 1s, 2s, 4s
        return float(2 ** attempt)

    async def _request(
        self,
        service: Literal["jira", "confluence"],
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if service == "jira":
            base_url = self._config.jira.base_url
            headers = self._jira_headers
        else:
            base_url = self._config.confluence.base_url
            headers = self._confluence_headers

        url = f"{base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        params=params,
                        json=json_body,
                    )
                    response.raise_for_status()
                    if not response.content:
                        return {}
                    return response.json()
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    if status_code in {401, 403}:
                        raise AtlassianAuthenticationError(
                            f"{service} authentication failed ({status_code}): "
                            f"{self._extract_error_message(exc.response)}"
                        ) from exc

                    if status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(self._retry_delay_seconds(exc.response, attempt))
                        continue

                    raise AtlassianRequestError(
                        f"{service} API request failed ({status_code}) for {method} {path}: "
                        f"{self._extract_error_message(exc.response)}"
                    ) from exc
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(self._retry_delay_seconds(None, attempt))
                        continue
                    raise AtlassianRequestError(
                        f"{service} request failed after retries for {method} {path}: {type(exc).__name__}: {exc}"
                    ) from exc

        raise AtlassianRequestError(f"{service} request failed unexpectedly for {method} {path}")

    async def _request_bytes(
        self,
        service: Literal["jira", "confluence"],
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> bytes:
        if service == "jira":
            base_url = self._config.jira.base_url
            headers = self._jira_headers
        else:
            base_url = self._config.confluence.base_url
            headers = self._confluence_headers

        url = f"{base_url}{path}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        params=params,
                    )
                    response.raise_for_status()
                    return response.content
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    if status_code in {401, 403}:
                        raise AtlassianAuthenticationError(
                            f"{service} authentication failed ({status_code}): "
                            f"{self._extract_error_message(exc.response)}"
                        ) from exc

                    if status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(self._retry_delay_seconds(exc.response, attempt))
                        continue

                    raise AtlassianRequestError(
                        f"{service} API request failed ({status_code}) for {method} {path}: "
                        f"{self._extract_error_message(exc.response)}"
                    ) from exc
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(self._retry_delay_seconds(None, attempt))
                        continue
                    raise AtlassianRequestError(
                        f"{service} request failed after retries for {method} {path}: {type(exc).__name__}: {exc}"
                    ) from exc

        raise AtlassianRequestError(f"{service} binary request failed unexpectedly for {method} {path}")

    async def _download_absolute_bytes(self, service: Literal["jira", "confluence"], download_url: str) -> bytes:
        headers = self._jira_headers if service == "jira" else self._confluence_headers
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.get(download_url, headers=headers)
                    response.raise_for_status()
                    return response.content
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    if status_code in {401, 403}:
                        raise AtlassianAuthenticationError(
                            f"{service} authentication failed ({status_code}): "
                            f"{self._extract_error_message(exc.response)}"
                        ) from exc
                    if status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(self._retry_delay_seconds(exc.response, attempt))
                        continue
                    raise AtlassianRequestError(
                        f"{service} download failed ({status_code}) for {download_url}: "
                        f"{self._extract_error_message(exc.response)}"
                    ) from exc
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(self._retry_delay_seconds(None, attempt))
                        continue
                    raise AtlassianRequestError(
                        f"{service} download failed after retries for {download_url}: {type(exc).__name__}: {exc}"
                    ) from exc

        raise AtlassianRequestError(f"{service} absolute download failed unexpectedly for {download_url}")

    async def _request_confluence_multipart(
        self,
        path: str,
        *,
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = self._confluence_headers.copy()
        headers.pop("Content-Type", None)
        headers["X-Atlassian-Token"] = "no-check"
        url = f"{self._config.confluence.base_url}{path}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.post(url, headers=headers, files=files, data=data)
                    response.raise_for_status()
                    if not response.content:
                        return {}
                    return response.json()
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    if status_code in {401, 403}:
                        raise AtlassianAuthenticationError(
                            f"confluence authentication failed ({status_code}): "
                            f"{self._extract_error_message(exc.response)}"
                        ) from exc
                    if status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(self._retry_delay_seconds(exc.response, attempt))
                        continue
                    raise AtlassianRequestError(
                        f"confluence multipart request failed ({status_code}) for POST {path}: "
                        f"{self._extract_error_message(exc.response)}"
                    ) from exc
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(self._retry_delay_seconds(None, attempt))
                        continue
                    raise AtlassianRequestError(
                        f"confluence multipart request failed after retries for POST {path}: "
                        f"{type(exc).__name__}: {exc}"
                    ) from exc

        raise AtlassianRequestError(f"confluence multipart request failed unexpectedly for POST {path}")

    async def _request_jira_multipart(
        self,
        path: str,
        *,
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = self._jira_headers.copy()
        headers.pop("Content-Type", None)
        headers["X-Atlassian-Token"] = "no-check"
        url = f"{self._config.jira.base_url}{path}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.post(url, headers=headers, files=files, data=data)
                    response.raise_for_status()
                    if not response.content:
                        return {}
                    return response.json()
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    if status_code in {401, 403}:
                        raise AtlassianAuthenticationError(
                            f"jira authentication failed ({status_code}): "
                            f"{self._extract_error_message(exc.response)}"
                        ) from exc
                    if status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(self._retry_delay_seconds(exc.response, attempt))
                        continue
                    raise AtlassianRequestError(
                        f"jira multipart request failed ({status_code}) for POST {path}: "
                        f"{self._extract_error_message(exc.response)}"
                    ) from exc
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(self._retry_delay_seconds(None, attempt))
                        continue
                    raise AtlassianRequestError(
                        f"jira multipart request failed after retries for POST {path}: "
                        f"{type(exc).__name__}: {exc}"
                    ) from exc

        raise AtlassianRequestError(f"jira multipart request failed unexpectedly for POST {path}")

    async def get_myself(self) -> dict[str, Any]:
        return await self._request("jira", "GET", self._jira_path("/myself"))

    async def list_projects(self) -> list[dict[str, Any]]:
        if self._config.jira.deployment == "cloud":
            data = await self._request("jira", "GET", self._jira_path("/project/search"), params={"maxResults": 50})
            return data.get("values", [])

        data = await self._request("jira", "GET", self._jira_path("/project"))
        return data if isinstance(data, list) else data.get("values", [])

    async def get_issue_fields(
        self,
        issue_key: str,
        *,
        fields: list[str] | None = None,
        expand: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if fields is not None:
            params["fields"] = ",".join(fields)
        if expand:
            params["expand"] = expand
        return await self._request(
            "jira",
            "GET",
            self._jira_path(f"/issue/{issue_key}"),
            params=params or None,
        )

    async def get_issue(self, issue_key: str) -> dict[str, Any]:
        return await self.get_issue_fields(
            issue_key,
            fields=["summary", "status", "issuetype", "priority", "assignee", "reporter", "description", "comment"],
        )

    async def get_issue_attachments(self, issue_key: str) -> list[dict[str, Any]]:
        issue = await self.get_issue_fields(issue_key, fields=["attachment"])
        fields = issue.get("fields") or {}
        attachments = fields.get("attachment") or []
        return attachments if isinstance(attachments, list) else []

    async def download_jira_attachment(self, content_url: str) -> bytes:
        return await self._download_absolute_bytes("jira", content_url)

    async def upload_jira_attachment(
        self,
        issue_key: str,
        *,
        filename: str,
        content: bytes,
        media_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        result = await self._request_jira_multipart(
            self._jira_path(f"/issue/{issue_key}/attachments"),
            files={"file": (filename, content, media_type)},
        )
        if isinstance(result, list):
            return result[0] if result else {}
        return result

    async def create_issue(
        self,
        project_key: str,
        summary: str,
        issue_type: str,
        *,
        description: str | None = None,
        assignee: str | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if description:
            fields["description"] = description
        if assignee:
            fields["assignee"] = {"name": assignee}
        if additional_fields:
            fields.update(additional_fields)

        return await self._request(
            "jira",
            "POST",
            self._jira_path("/issue"),
            json_body={"fields": fields},
        )

    async def update_issue(
        self,
        issue_key: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        await self._request(
            "jira",
            "PUT",
            self._jira_path(f"/issue/{issue_key}"),
            json_body={"fields": fields},
        )
        return {"issue_key": issue_key, "status": "updated"}

    async def clear_issue_assignee(self, issue_key: str) -> dict[str, Any]:
        await self._request(
            "jira",
            "PUT",
            self._jira_path(f"/issue/{issue_key}"),
            json_body={"fields": {"assignee": None}},
        )
        return {"issue_key": issue_key, "status": "unassigned"}

    async def delete_issue(self, issue_key: str) -> dict[str, Any]:
        await self._request(
            "jira",
            "DELETE",
            self._jira_path(f"/issue/{issue_key}"),
        )
        return {"issue_key": issue_key, "status": "deleted"}

    async def search_issues(
        self,
        jql: str,
        limit: int = 10,
        fields: list[str] | None = None,
        *,
        start_at: int = 0,
        validate_query: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "jql": jql,
            "maxResults": max(1, min(limit, 50)),
            "startAt": max(0, start_at),
            "validateQuery": validate_query,
            "fields": fields
            or [
                "summary",
                "status",
                "issuetype",
                "priority",
                "assignee",
                "updated",
            ],
        }
        search_path = "/search/jql" if self._config.jira.deployment == "cloud" else "/search"
        return await self._request("jira", "POST", self._jira_path(search_path), json_body=payload)

    async def list_fields(self) -> list[dict[str, Any]]:
        data = await self._request("jira", "GET", self._jira_path("/field"))
        return data if isinstance(data, list) else data.get("values", [])

    async def search_fields(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        if self._config.jira.deployment == "cloud":
            data = await self._request(
                "jira",
                "GET",
                self._jira_path("/field/search"),
                params={"query": query, "maxResults": max(1, min(limit, 50))},
            )
            return data.get("values", [])

        # Jira Server/DC does not consistently expose /field/search.
        all_fields = await self.list_fields()
        lowered = query.strip().lower()
        if not lowered:
            return all_fields[: max(1, min(limit, 50))]
        matches = [
            field
            for field in all_fields
            if lowered in str(field.get("name", "")).lower() or lowered in str(field.get("id", "")).lower()
        ]
        return matches[: max(1, min(limit, 50))]

    async def list_statuses(self) -> list[dict[str, Any]]:
        data = await self._request("jira", "GET", self._jira_path("/status"))
        return data if isinstance(data, list) else data.get("values", [])

    async def list_issue_types(self) -> list[dict[str, Any]]:
        data = await self._request("jira", "GET", self._jira_path("/issuetype"))
        return data if isinstance(data, list) else data.get("values", [])

    async def add_comment(self, issue_key: str, comment: str) -> dict[str, Any]:
        if self._config.jira.deployment == "cloud":
            body = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": comment}],
                        }
                    ],
                }
            }
        else:
            body = {"body": comment}

        return await self._request(
            "jira",
            "POST",
            self._jira_path(f"/issue/{issue_key}/comment"),
            json_body=body,
        )

    async def edit_comment(self, issue_key: str, comment_id: str, comment: str) -> dict[str, Any]:
        if self._config.jira.deployment == "cloud":
            body = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": comment}],
                        }
                    ],
                }
            }
        else:
            body = {"body": comment}

        return await self._request(
            "jira",
            "PUT",
            self._jira_path(f"/issue/{issue_key}/comment/{comment_id}"),
            json_body=body,
        )

    async def get_worklog(self, issue_key: str) -> list[dict[str, Any]]:
        data = await self._request("jira", "GET", self._jira_path(f"/issue/{issue_key}/worklog"))
        return data.get("worklogs", [])

    async def add_worklog(
        self,
        issue_key: str,
        time_spent: str,
        *,
        comment: str | None = None,
        started: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"timeSpent": time_spent}
        if started:
            body["started"] = started
        if comment:
            if self._config.jira.deployment == "cloud":
                body["comment"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": comment}],
                        }
                    ],
                }
            else:
                body["comment"] = comment

        return await self._request(
            "jira",
            "POST",
            self._jira_path(f"/issue/{issue_key}/worklog"),
            json_body=body,
        )

    async def get_project_versions(self, project_key: str) -> list[dict[str, Any]]:
        data = await self._request("jira", "GET", self._jira_path(f"/project/{project_key}/versions"))
        return data if isinstance(data, list) else data.get("values", [])

    async def get_project_components(self, project_key: str) -> list[dict[str, Any]]:
        data = await self._request("jira", "GET", self._jira_path(f"/project/{project_key}/components"))
        return data if isinstance(data, list) else data.get("values", [])

    async def get_link_types(self) -> list[dict[str, Any]]:
        data = await self._request("jira", "GET", self._jira_path("/issueLinkType"))
        return data.get("issueLinkTypes", [])

    async def create_issue_link(
        self,
        *,
        link_type: str,
        inward_issue_key: str,
        outward_issue_key: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_issue_key},
            "outwardIssue": {"key": outward_issue_key},
        }
        if comment:
            if self._config.jira.deployment == "cloud":
                body["comment"] = {
                    "body": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": comment}],
                            }
                        ],
                    }
                }
            else:
                body["comment"] = {"body": comment}

        return await self._request(
            "jira",
            "POST",
            self._jira_path("/issueLink"),
            json_body=body,
        )

    async def remove_issue_link(self, link_id: str) -> dict[str, Any]:
        await self._request("jira", "DELETE", self._jira_path(f"/issueLink/{link_id}"))
        return {"link_id": link_id, "status": "deleted"}

    async def get_agile_boards(
        self,
        *,
        limit: int = 25,
        start_at: int = 0,
        board_type: str | None = None,
        project_key_or_id: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "maxResults": max(1, min(limit, 50)),
            "startAt": max(0, start_at),
        }
        if board_type:
            params["type"] = board_type
        if project_key_or_id:
            params["projectKeyOrId"] = project_key_or_id
        if name:
            params["name"] = name
        return await self._request("jira", "GET", "/rest/agile/1.0/board", params=params)

    async def get_board_issues(
        self,
        board_id: str,
        *,
        jql: str | None = None,
        limit: int = 25,
        start_at: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "maxResults": max(1, min(limit, 50)),
            "startAt": max(0, start_at),
        }
        if jql:
            params["jql"] = jql
        return await self._request("jira", "GET", f"/rest/agile/1.0/board/{board_id}/issue", params=params)

    async def get_sprints_from_board(
        self,
        board_id: str,
        *,
        state: str | None = None,
        limit: int = 25,
        start_at: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "maxResults": max(1, min(limit, 50)),
            "startAt": max(0, start_at),
        }
        if state:
            params["state"] = state
        return await self._request("jira", "GET", f"/rest/agile/1.0/board/{board_id}/sprint", params=params)

    async def get_sprint_issues(
        self,
        sprint_id: str,
        *,
        jql: str | None = None,
        limit: int = 25,
        start_at: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "maxResults": max(1, min(limit, 50)),
            "startAt": max(0, start_at),
        }
        if jql:
            params["jql"] = jql
        return await self._request("jira", "GET", f"/rest/agile/1.0/sprint/{sprint_id}/issue", params=params)

    async def create_sprint(
        self,
        *,
        name: str,
        board_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        goal: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "originBoardId": int(board_id),
        }
        if start_date:
            body["startDate"] = start_date
        if end_date:
            body["endDate"] = end_date
        if goal:
            body["goal"] = goal
        return await self._request("jira", "POST", "/rest/agile/1.0/sprint", json_body=body)

    async def update_sprint(
        self,
        sprint_id: str,
        *,
        name: str | None = None,
        state: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        goal: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if state is not None:
            body["state"] = state
        if start_date is not None:
            body["startDate"] = start_date
        if end_date is not None:
            body["endDate"] = end_date
        if goal is not None:
            body["goal"] = goal
        return await self._request("jira", "PUT", f"/rest/agile/1.0/sprint/{sprint_id}", json_body=body)

    async def add_issues_to_sprint(self, sprint_id: str, issue_keys: list[str]) -> dict[str, Any]:
        await self._request(
            "jira",
            "POST",
            f"/rest/agile/1.0/sprint/{sprint_id}/issue",
            json_body={"issues": issue_keys},
        )
        return {"sprint_id": sprint_id, "count": len(issue_keys), "status": "updated"}

    async def get_service_desks(self, limit: int = 50, start_at: int = 0) -> dict[str, Any]:
        return await self._request(
            "jira",
            "GET",
            "/rest/servicedeskapi/servicedesk",
            params={"limit": max(1, min(limit, 100)), "start": max(0, start_at)},
        )

    async def get_service_desk_for_project(self, project_key: str) -> dict[str, Any] | None:
        desks = await self.get_service_desks(limit=100)
        values = desks.get("values", []) if isinstance(desks, dict) else []
        lowered = project_key.strip().lower()
        for desk in values:
            project = desk.get("projectKey") or desk.get("project", {}).get("key")
            if isinstance(project, str) and project.lower() == lowered:
                return desk
        return None

    async def get_service_desk_queues(self, service_desk_id: str, limit: int = 50, start_at: int = 0) -> dict[str, Any]:
        return await self._request(
            "jira",
            "GET",
            f"/rest/servicedeskapi/servicedesk/{service_desk_id}/queue",
            params={"limit": max(1, min(limit, 100)), "start": max(0, start_at)},
        )

    async def get_queue_issues(self, service_desk_id: str, queue_id: str, limit: int = 25, start_at: int = 0) -> dict[str, Any]:
        return await self._request(
            "jira",
            "GET",
            f"/rest/servicedeskapi/servicedesk/{service_desk_id}/queue/{queue_id}/issue",
            params={"limit": max(1, min(limit, 50)), "start": max(0, start_at)},
        )

    async def get_issue_dates(self, issue_key: str) -> dict[str, Any]:
        issue = await self._request(
            "jira",
            "GET",
            self._jira_path(f"/issue/{issue_key}"),
            params={"fields": "created,updated,resolutiondate,duedate,statuscategorychangedate"},
        )
        fields = issue.get("fields") or {}
        return {
            "issue_key": issue.get("key") or issue_key,
            "created": fields.get("created"),
            "updated": fields.get("updated"),
            "resolution_date": fields.get("resolutiondate"),
            "due_date": fields.get("duedate"),
            "status_category_changed_date": fields.get("statuscategorychangedate"),
        }

    async def get_issue_sla(self, issue_key: str) -> dict[str, Any]:
        return await self._request(
            "jira",
            "GET",
            f"/rest/servicedeskapi/request/{issue_key}/sla",
        )

    async def get_user_profile(self, user_identifier: str) -> dict[str, Any]:
        params: dict[str, Any]
        if self._config.jira.deployment == "cloud":
            params = {"accountId": user_identifier}
        else:
            params = {"username": user_identifier}
        return await self._request("jira", "GET", self._jira_path("/user"), params=params)

    async def get_issue_watchers(self, issue_key: str) -> dict[str, Any]:
        return await self._request("jira", "GET", self._jira_path(f"/issue/{issue_key}/watchers"))

    async def add_watcher(self, issue_key: str, user_identifier: str) -> dict[str, Any]:
        if self._config.jira.deployment == "cloud":
            body: Any = user_identifier
        else:
            body = user_identifier
        await self._request(
            "jira",
            "POST",
            self._jira_path(f"/issue/{issue_key}/watchers"),
            json_body=body,
        )
        return {"issue_key": issue_key, "user_identifier": user_identifier, "status": "added"}

    async def remove_watcher(
        self,
        issue_key: str,
        *,
        username: str | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        if self._config.jira.deployment == "cloud":
            if not account_id:
                raise ValueError("account_id is required for Jira Cloud")
            params = {"accountId": account_id}
            removed = account_id
        else:
            if not username:
                raise ValueError("username is required for Jira Server/Data Center")
            params = {"username": username}
            removed = username

        await self._request(
            "jira",
            "DELETE",
            self._jira_path(f"/issue/{issue_key}/watchers"),
            params=params,
        )
        return {"issue_key": issue_key, "user_identifier": removed, "status": "removed"}

    async def get_issue_proforma_forms(self, issue_key: str) -> list[dict[str, Any]]:
        data = await self._request(
            "jira",
            "GET",
            f"/rest/api/3/issue/{issue_key}/forms",
        )
        forms = data.get("forms") if isinstance(data, dict) else None
        if isinstance(forms, list):
            return forms
        return data if isinstance(data, list) else []

    async def get_proforma_form_details(self, issue_key: str, form_id: str) -> dict[str, Any]:
        return await self._request(
            "jira",
            "GET",
            f"/rest/api/3/issue/{issue_key}/forms/{form_id}",
        )

    async def update_proforma_form_answers(self, issue_key: str, form_id: str, answers: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._request(
            "jira",
            "PUT",
            f"/rest/api/3/issue/{issue_key}/forms/{form_id}",
            json_body={"answers": answers},
        )

    async def get_issue_development_info(
        self,
        issue_key: str,
        *,
        application_type: str | None = None,
        data_type: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if application_type:
            params["applicationType"] = application_type
        if data_type:
            params["dataType"] = data_type
        return await self._request(
            "jira",
            "GET",
            f"/rest/dev-status/latest/issue/detail?issueIdOrKey={issue_key}",
            params=params,
        )

    async def get_issues_development_info(
        self,
        issue_keys: list[str],
        *,
        application_type: str | None = None,
        data_type: str | None = None,
    ) -> dict[str, Any]:
        if not issue_keys:
            raise ValueError("issue_keys must contain at least one key")
        params: dict[str, Any] = {
            "issueIdOrKeys": ",".join(issue_keys),
        }
        if application_type:
            params["applicationType"] = application_type
        if data_type:
            params["dataType"] = data_type
        return await self._request(
            "jira",
            "GET",
            "/rest/dev-status/latest/issue/summary",
            params=params,
        )

    async def list_transitions(self, issue_key: str) -> list[dict[str, Any]]:
        data = await self._request("jira", "GET", self._jira_path(f"/issue/{issue_key}/transitions"))
        return data.get("transitions", [])

    async def get_field_options(
        self,
        field_id: str,
        *,
        context_id: str | None = None,
        project_key: str | None = None,
        issue_type: str | None = None,
    ) -> dict[str, Any]:
        if self._config.jira.deployment == "cloud":
            resolved_context_id = context_id
            if not resolved_context_id:
                context_params: dict[str, Any] = {"maxResults": 50}
                if project_key:
                    context_params["projectKey"] = project_key
                if issue_type:
                    context_params["issueTypeId"] = issue_type
                contexts = await self._request(
                    "jira",
                    "GET",
                    self._jira_path(f"/field/{field_id}/context"),
                    params=context_params,
                )
                context_values = contexts.get("values", [])
                if not context_values:
                    return {"field_id": field_id, "context_id": None, "options": []}
                resolved_context_id = str(context_values[0].get("id"))

            options = await self._request(
                "jira",
                "GET",
                self._jira_path(f"/field/{field_id}/context/{resolved_context_id}/option"),
                params={"maxResults": 200},
            )
            return {
                "field_id": field_id,
                "context_id": resolved_context_id,
                "options": options.get("values", []),
            }

        if not project_key or not issue_type:
            raise ValueError("project_key and issue_type are required on Jira Server/Data Center")

        data = await self._request(
            "jira",
            "GET",
            self._jira_path("/issue/createmeta"),
            params={
                "projectKeys": project_key,
                "issuetypeNames": issue_type,
                "expand": "projects.issuetypes.fields",
            },
        )
        projects = data.get("projects", [])
        if not projects:
            return {"field_id": field_id, "context_id": None, "options": []}

        issue_types = projects[0].get("issuetypes", [])
        if not issue_types:
            return {"field_id": field_id, "context_id": None, "options": []}

        field_meta = issue_types[0].get("fields", {}).get(field_id, {})
        options = field_meta.get("allowedValues", []) if isinstance(field_meta, dict) else []
        return {
            "field_id": field_id,
            "context_id": None,
            "options": options,
        }

    async def transition_issue(
        self,
        issue_key: str,
        *,
        transition_name: str | None = None,
        transition_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_transition_id = transition_id
        if resolved_transition_id is None:
            transitions = await self.list_transitions(issue_key)
            lowered_name = (transition_name or "").strip().lower()
            match = next((item for item in transitions if item.get("name", "").lower() == lowered_name), None)
            if match is None:
                available = ", ".join(item.get("name", "") for item in transitions)
                raise ValueError(f"Transition not found. Available transitions: {available}")
            resolved_transition_id = str(match["id"])

        await self._request(
            "jira",
            "POST",
            self._jira_path(f"/issue/{issue_key}/transitions"),
            json_body={"transition": {"id": resolved_transition_id}},
        )
        return {
            "issue_key": issue_key,
            "transition_id": resolved_transition_id,
            "status": "ok",
        }

    async def search_confluence(self, query: str | None = None, cql: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        effective_cql = (cql or "").strip()
        if not effective_cql:
            if not query or not query.strip():
                raise ValueError("Provide either query or cql")
            escaped_query = query.replace('"', '\\"')
            effective_cql = f'type = page AND text ~ "{escaped_query}"'

        data = await self._request(
            "confluence",
            "GET",
            self._confluence_path("/search"),
            params={
                "cql": effective_cql,
                "limit": max(1, min(limit, 25)),
                "expand": "content.version,content.space",
            },
        )
        return data.get("results", [])

    async def get_confluence_page(self, page_id: str, expand: str = "body.storage,version,space") -> dict[str, Any]:
        return await self._request(
            "confluence",
            "GET",
            self._confluence_path(f"/content/{page_id}"),
            params={"expand": expand},
        )

    async def create_confluence_page(
        self,
        *,
        space_key: str,
        title: str,
        content: str,
        parent_page_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": content,
                    "representation": "storage",
                }
            },
        }
        if parent_page_id:
            body["ancestors"] = [{"id": parent_page_id}]

        return await self._request(
            "confluence",
            "POST",
            self._confluence_path("/content"),
            json_body=body,
        )

    async def update_confluence_page(
        self,
        *,
        page_id: str,
        title: str | None = None,
        content: str | None = None,
    ) -> dict[str, Any]:
        current = await self.get_confluence_page(page_id=page_id, expand="version,space,body.storage")
        current_version = (current.get("version") or {}).get("number")
        if not isinstance(current_version, int):
            raise AtlassianRequestError(f"Unable to resolve current version for Confluence page {page_id}")
        body_storage = ((current.get("body") or {}).get("storage") or {}).get("value")

        body: dict[str, Any] = {
            "id": page_id,
            "type": "page",
            "title": title or current.get("title"),
            "version": {"number": current_version + 1},
            "body": {
                "storage": {
                    "value": content if content is not None else (body_storage or ""),
                    "representation": "storage",
                }
            },
        }
        space = current.get("space")
        if isinstance(space, dict) and space.get("key"):
            body["space"] = {"key": space.get("key")}

        return await self._request(
            "confluence",
            "PUT",
            self._confluence_path(f"/content/{page_id}"),
            json_body=body,
        )

    async def delete_confluence_page(self, page_id: str) -> dict[str, Any]:
        await self._request(
            "confluence",
            "DELETE",
            self._confluence_path(f"/content/{page_id}"),
        )
        return {"page_id": page_id, "status": "deleted"}

    async def get_confluence_page_children(self, page_id: str, limit: int = 25) -> list[dict[str, Any]]:
        data = await self._request(
            "confluence",
            "GET",
            self._confluence_path(f"/content/{page_id}/child/page"),
            params={"limit": max(1, min(limit, 100))},
        )
        return data.get("results", [])

    async def get_confluence_attachments(
        self,
        content_id: str,
        *,
        start: int = 0,
        limit: int = 50,
        filename: str | None = None,
        media_type: str | None = None,
    ) -> dict[str, Any]:
        data = await self._request(
            "confluence",
            "GET",
            self._confluence_path(f"/content/{content_id}/child/attachment"),
            params={
                "start": max(0, start),
                "limit": max(1, min(limit, 100)),
                "expand": "version,metadata,extensions",
            },
        )
        results = data.get("results", [])
        if filename:
            needle = filename.lower()
            results = [item for item in results if needle in str(item.get("title", "")).lower()]
        if media_type:
            wanted = media_type.lower()
            results = [
                item
                for item in results
                if str((item.get("extensions") or {}).get("mediaType", "")).lower() == wanted
            ]
        return {
            "start": data.get("start", start),
            "limit": data.get("limit", limit),
            "size": data.get("size", len(results)),
            "results": results,
        }

    async def get_confluence_attachment(self, attachment_id: str) -> dict[str, Any]:
        return await self._request(
            "confluence",
            "GET",
            self._confluence_path(f"/content/{attachment_id}"),
            params={"expand": "version,metadata,extensions"},
        )

    async def download_confluence_attachment(self, attachment_id: str) -> bytes:
        attachment = await self.get_confluence_attachment(attachment_id)
        links = attachment.get("_links") or {}
        download_path = links.get("download")
        if not isinstance(download_path, str) or not download_path:
            raise AtlassianRequestError(f"Attachment {attachment_id} has no downloadable URL")
        download_url = download_path if download_path.startswith("http") else urljoin(self._config.confluence.base_url, download_path)
        return await self._download_absolute_bytes("confluence", download_url)

    async def delete_confluence_attachment(self, attachment_id: str) -> dict[str, Any]:
        await self._request(
            "confluence",
            "DELETE",
            self._confluence_path(f"/content/{attachment_id}"),
        )
        return {"attachment_id": attachment_id, "status": "deleted"}

    async def upload_confluence_attachment(
        self,
        content_id: str,
        *,
        file_name: str,
        content_bytes: bytes,
        media_type: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, str] | None = None
        if comment:
            data = {"comment": comment}
        payload = await self._request_confluence_multipart(
            self._confluence_path(f"/content/{content_id}/child/attachment"),
            files={"file": (file_name, content_bytes, media_type)},
            data=data,
        )
        return payload

    async def get_confluence_comments(self, page_id: str, limit: int = 25) -> list[dict[str, Any]]:
        data = await self._request(
            "confluence",
            "GET",
            self._confluence_path(f"/content/{page_id}/child/comment"),
            params={"limit": max(1, min(limit, 100)), "expand": "body.storage,version"},
        )
        return data.get("results", [])

    async def add_confluence_comment(self, page_id: str, body: str) -> dict[str, Any]:
        payload = {
            "type": "comment",
            "container": {"type": "page", "id": page_id},
            "body": {
                "storage": {
                    "value": body,
                    "representation": "storage",
                }
            },
        }
        return await self._request(
            "confluence",
            "POST",
            self._confluence_path("/content"),
            json_body=payload,
        )

    async def get_confluence_labels(self, page_id: str) -> list[dict[str, Any]]:
        data = await self._request(
            "confluence",
            "GET",
            self._confluence_path(f"/content/{page_id}/label"),
            params={"limit": 200},
        )
        return data.get("results", [])

    async def add_confluence_label(self, page_id: str, name: str) -> list[dict[str, Any]]:
        data = await self._request(
            "confluence",
            "POST",
            self._confluence_path(f"/content/{page_id}/label"),
            json_body=[{"prefix": "global", "name": name}],
        )
        if isinstance(data, list):
            return data
        return data.get("results", [])

    async def search_confluence_user(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        escaped_query = query.replace('"', '\\"')
        cql = f'user.fullname ~ "{escaped_query}"'
        data = await self._request(
            "confluence",
            "GET",
            self._confluence_path("/search/user"),
            params={"cql": cql, "limit": max(1, min(limit, 50))},
        )
        if isinstance(data, list):
            return data
        return data.get("results", [])


def compact_issue(issue: dict[str, Any]) -> dict[str, Any]:
    fields = issue.get("fields", {})
    assignee = fields.get("assignee") or {}
    status = fields.get("status") or {}
    issue_type = fields.get("issuetype") or {}
    priority = fields.get("priority") or {}
    return {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "status": status.get("name"),
        "issue_type": issue_type.get("name"),
        "priority": priority.get("name"),
        "assignee": assignee.get("displayName"),
        "updated": fields.get("updated"),
    }


def compact_jira_field(field: dict[str, Any]) -> dict[str, Any]:
    schema = field.get("schema") or {}
    return {
        "id": field.get("id"),
        "name": field.get("name"),
        "custom": field.get("custom"),
        "schema_type": schema.get("type"),
        "schema_custom": schema.get("custom"),
    }


def compact_jira_status(status: dict[str, Any]) -> dict[str, Any]:
    category = status.get("statusCategory") or {}
    return {
        "id": status.get("id"),
        "name": status.get("name"),
        "description": status.get("description"),
        "category": category.get("name"),
    }


def compact_jira_issue_type(issue_type: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": issue_type.get("id"),
        "name": issue_type.get("name"),
        "description": issue_type.get("description"),
        "subtask": issue_type.get("subtask"),
    }


def compact_project(project: dict[str, Any]) -> dict[str, Any]:
    lead = project.get("lead") or {}
    return {
        "id": project.get("id"),
        "key": project.get("key"),
        "name": project.get("name"),
        "project_type": project.get("projectTypeKey"),
        "lead": lead.get("displayName"),
    }


def compact_confluence_result(result: dict[str, Any]) -> dict[str, Any]:
    content = result.get("content") or {}
    space = content.get("space") or {}
    return {
        "title": content.get("title"),
        "type": content.get("type"),
        "page_id": content.get("id"),
        "space": space.get("name"),
        "url": result.get("url"),
        "excerpt": result.get("excerpt"),
    }
