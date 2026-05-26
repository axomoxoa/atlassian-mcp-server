import pytest

from atlassian_mcp_server.tools.jira import _validate_no_unresolved_template_placeholders


def test_validate_no_unresolved_template_placeholders_accepts_plain_text() -> None:
    _validate_no_unresolved_template_placeholders(
        summary="Implement integration for billing",
        description="No placeholders here.",
    )


def test_validate_no_unresolved_template_placeholders_rejects_summary_placeholder() -> None:
    with pytest.raises(ValueError, match="jira_create_ticket_from_template"):
        _validate_no_unresolved_template_placeholders(
            summary="Implement integration {integration}",
            description="Normal description.",
        )


def test_validate_no_unresolved_template_placeholders_rejects_description_placeholder() -> None:
    with pytest.raises(ValueError, match=r"\{owner\}"):
        _validate_no_unresolved_template_placeholders(
            summary="Implement integration",
            description="Owner is {owner}.",
        )
