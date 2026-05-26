from __future__ import annotations

import base64
import mimetypes

from mcp.server.fastmcp import FastMCP

from ..client import AtlassianClient, compact_confluence_result
from ..config import AtlassianConfig


def _get_client() -> AtlassianClient:
    return AtlassianClient(AtlassianConfig.from_env())


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def confluence_search(query: str | None = None, cql: str | None = None, limit: int = 10) -> list[dict[str, str | None]]:
        """Search Confluence using free text or a raw CQL expression."""
        results = await _get_client().search_confluence(query=query, cql=cql, limit=limit)
        return [compact_confluence_result(result) for result in results]

    @mcp.tool()
    async def confluence_get_page(page_id: str, expand: str = "body.storage,version,space") -> dict[str, object]:
        """Fetch a Confluence page by page id."""
        return await _get_client().get_confluence_page(page_id=page_id, expand=expand)

    @mcp.tool()
    async def confluence_create_page(
        space_key: str,
        title: str,
        content: str,
        parent_page_id: str | None = None,
    ) -> dict[str, object]:
        """Create a Confluence page using storage-format content."""
        created = await _get_client().create_confluence_page(
            space_key=space_key,
            title=title,
            content=content,
            parent_page_id=parent_page_id,
        )
        return {
            "status": "created",
            "page": {
                "id": created.get("id"),
                "title": created.get("title"),
                "type": created.get("type"),
            },
        }

    @mcp.tool()
    async def confluence_update_page(
        page_id: str,
        content: str,
        title: str | None = None,
    ) -> dict[str, object]:
        """Update a Confluence page and increment version."""
        updated = await _get_client().update_confluence_page(
            page_id=page_id,
            title=title,
            content=content,
        )
        return {
            "status": "updated",
            "page": {
                "id": updated.get("id") or page_id,
                "title": updated.get("title") or title,
                "version": (updated.get("version") or {}).get("number"),
            },
        }

    @mcp.tool()
    async def confluence_delete_page(page_id: str) -> dict[str, object]:
        """Delete a Confluence page by page id."""
        return await _get_client().delete_confluence_page(page_id)

    @mcp.tool()
    async def confluence_get_page_children(page_id: str, limit: int = 25) -> list[dict[str, str | None]]:
        """List direct child pages for a Confluence page."""
        children = await _get_client().get_confluence_page_children(page_id=page_id, limit=limit)
        return [
            {
                "id": child.get("id"),
                "title": child.get("title"),
                "type": child.get("type"),
                "status": child.get("status"),
            }
            for child in children
        ]

    @mcp.tool()
    async def confluence_get_comments(page_id: str, limit: int = 25) -> dict[str, object]:
        """Get comments for a Confluence page."""
        comments = await _get_client().get_confluence_comments(page_id=page_id, limit=limit)
        return {"page_id": page_id, "count": len(comments), "comments": comments}

    @mcp.tool()
    async def confluence_add_comment(page_id: str, body: str) -> dict[str, object]:
        """Add a comment to a Confluence page using storage-format content."""
        result = await _get_client().add_confluence_comment(page_id=page_id, body=body)
        return {
            "status": "created",
            "comment": {
                "id": result.get("id"),
                "type": result.get("type"),
            },
        }

    @mcp.tool()
    async def confluence_get_labels(page_id: str) -> dict[str, object]:
        """Get labels attached to a Confluence page."""
        labels = await _get_client().get_confluence_labels(page_id=page_id)
        return {"page_id": page_id, "count": len(labels), "labels": labels}

    @mcp.tool()
    async def confluence_add_label(page_id: str, name: str) -> dict[str, object]:
        """Add a label to a Confluence page."""
        labels = await _get_client().add_confluence_label(page_id=page_id, name=name)
        return {"status": "created", "page_id": page_id, "labels": labels}

    @mcp.tool()
    async def confluence_search_user(query: str, limit: int = 10) -> dict[str, object]:
        """Search Confluence users by full name."""
        users = await _get_client().search_confluence_user(query=query, limit=limit)
        return {"query": query, "count": len(users), "users": users}

    @mcp.tool()
    async def confluence_get_attachments(
        content_id: str,
        start: int = 0,
        limit: int = 50,
        filename: str | None = None,
        media_type: str | None = None,
    ) -> dict[str, object]:
        """List attachments for a Confluence page/blog with optional filtering."""
        data = await _get_client().get_confluence_attachments(
            content_id=content_id,
            start=start,
            limit=limit,
            filename=filename,
            media_type=media_type,
        )
        results = data.get("results", [])
        compact = [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "media_type": (item.get("extensions") or {}).get("mediaType"),
                "file_size": (item.get("extensions") or {}).get("fileSize"),
                "download": (item.get("_links") or {}).get("download"),
            }
            for item in results
        ]
        return {
            "content_id": content_id,
            "start": data.get("start", start),
            "limit": data.get("limit", limit),
            "count": len(compact),
            "attachments": compact,
        }

    @mcp.tool()
    async def confluence_download_attachment(
        attachment_id: str,
        include_content: bool = False,
        max_inline_bytes: int = 2_000_000,
    ) -> dict[str, object]:
        """Get Confluence attachment metadata and optionally inline base64 content."""
        meta = await _get_client().get_confluence_attachment(attachment_id)
        extensions = meta.get("extensions") or {}
        file_size = int(extensions.get("fileSize") or 0)
        result: dict[str, object] = {
            "id": meta.get("id"),
            "title": meta.get("title"),
            "media_type": extensions.get("mediaType"),
            "file_size": file_size,
            "download": (meta.get("_links") or {}).get("download"),
        }
        if include_content and file_size <= max_inline_bytes:
            raw = await _get_client().download_confluence_attachment(attachment_id)
            result["content_base64"] = base64.b64encode(raw).decode("ascii")
            result["content_inline"] = True
        elif include_content:
            result["content_inline"] = False
            result["inline_reason"] = "too_large"
        return result

    @mcp.tool()
    async def confluence_download_content_attachments(
        content_id: str,
        include_content: bool = False,
        max_files: int = 20,
        max_inline_bytes: int = 2_000_000,
    ) -> dict[str, object]:
        """Download attachment metadata for a page/blog and optionally inline file content."""
        listing = await confluence_get_attachments(content_id=content_id, start=0, limit=max_files)
        attachments = listing.get("attachments", [])
        results: list[dict[str, object]] = []
        for item in attachments:
            attachment_id = item.get("id")
            if not isinstance(attachment_id, str):
                continue
            results.append(
                await confluence_download_attachment(
                    attachment_id=attachment_id,
                    include_content=include_content,
                    max_inline_bytes=max_inline_bytes,
                )
            )
        return {
            "content_id": content_id,
            "count": len(results),
            "attachments": results,
        }

    @mcp.tool()
    async def confluence_delete_attachment(attachment_id: str) -> dict[str, object]:
        """Delete a Confluence attachment by id."""
        return await _get_client().delete_confluence_attachment(attachment_id)

    @mcp.tool()
    async def confluence_get_page_images(
        content_id: str,
        include_content: bool = False,
        max_inline_bytes: int = 2_000_000,
    ) -> dict[str, object]:
        """List image attachments for a Confluence page/blog with optional inline content."""
        payload = await confluence_download_content_attachments(
            content_id=content_id,
            include_content=include_content,
            max_inline_bytes=max_inline_bytes,
        )
        images = [
            item
            for item in payload["attachments"]
            if str(item.get("media_type", "")).lower().startswith("image/")
        ]
        return {
            "content_id": content_id,
            "count": len(images),
            "images": images,
        }

    @mcp.tool()
    async def confluence_upload_attachment(
        content_id: str,
        file_name: str,
        content_base64: str,
        media_type: str | None = None,
        comment: str | None = None,
    ) -> dict[str, object]:
        """Upload a single attachment to a Confluence page/blog from base64 content."""
        try:
            file_bytes = base64.b64decode(content_base64, validate=True)
        except Exception as exc:
            raise ValueError(f"content_base64 must be valid base64: {exc}") from exc

        resolved_media_type = media_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        uploaded = await _get_client().upload_confluence_attachment(
            content_id=content_id,
            file_name=file_name,
            content_bytes=file_bytes,
            media_type=resolved_media_type,
            comment=comment,
        )
        results = uploaded.get("results", []) if isinstance(uploaded, dict) else []
        return {
            "content_id": content_id,
            "count": len(results),
            "attachments": [
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "media_type": (item.get("extensions") or {}).get("mediaType"),
                    "file_size": (item.get("extensions") or {}).get("fileSize"),
                }
                for item in results
            ],
        }

    @mcp.tool()
    async def confluence_upload_attachments(
        content_id: str,
        files: list[dict[str, str]],
    ) -> dict[str, object]:
        """Upload multiple attachments from base64 payloads.

        files entries should contain:
        - file_name (required)
        - content_base64 (required)
        - media_type (optional)
        - comment (optional)
        """
        uploaded: list[dict[str, object]] = []
        for entry in files:
            uploaded.append(
                await confluence_upload_attachment(
                    content_id=content_id,
                    file_name=str(entry.get("file_name", "")),
                    content_base64=str(entry.get("content_base64", "")),
                    media_type=entry.get("media_type"),
                    comment=entry.get("comment"),
                )
            )

        flattened: list[dict[str, object]] = []
        for result in uploaded:
            for attachment in result.get("attachments", []):
                if isinstance(attachment, dict):
                    flattened.append(attachment)

        return {
            "content_id": content_id,
            "count": len(flattened),
            "attachments": flattened,
        }
