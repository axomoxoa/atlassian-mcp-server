import pytest

from atlassian_mcp_server.tools.jira import _parse_string_mapping


def test_parse_string_mapping_accepts_json_string_and_scalars() -> None:
    value = _parse_string_mapping(
        '{"integration":"mytestintegration","enabled":true,"count":3,"empty":null}',
        argument_name="placeholder_values",
    )

    assert value == {
        "integration": "mytestintegration",
        "enabled": "True",
        "count": "3",
        "empty": "",
    }


def test_parse_string_mapping_rejects_nested_values() -> None:
    with pytest.raises(ValueError, match="placeholder_values values must be string-compatible scalars"):
        _parse_string_mapping(
            '{"integration":{"name":"mytestintegration"}}',
            argument_name="placeholder_values",
        )


def test_parse_string_mapping_decodes_escaped_quotes_and_slashes() -> None:
    value = _parse_string_mapping(
        '{"note":"He said \\\"deploy now\\\"","url":"https:\\/\\/example.com\\/a\\/b"}',
        argument_name="placeholder_values",
    )

    assert value == {
        "note": 'He said "deploy now"',
        "url": "https://example.com/a/b",
    }


def test_parse_string_mapping_reports_json_encoding_hints() -> None:
    with pytest.raises(ValueError, match='Escape embedded double quotes as'):
        _parse_string_mapping(
            '{"integration":"Acme "Blue" Team"}',
            argument_name="placeholder_values",
        )
