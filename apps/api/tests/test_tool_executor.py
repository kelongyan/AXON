import pytest

from app.services.tools import (
    ToolValidationError,
    execute_builtin_tool,
    redact_mapping,
    validate_input_schema,
)


def test_validate_input_schema_rejects_missing_required_field():
    schema = {
        "type": "object",
        "required": ["text"],
        "properties": {"text": {"type": "string"}},
    }

    with pytest.raises(ToolValidationError) as exc_info:
        validate_input_schema(schema, {})

    assert "Missing required field: text" in str(exc_info.value)


def test_validate_input_schema_rejects_wrong_type():
    schema = {
        "type": "object",
        "required": ["limit"],
        "properties": {"limit": {"type": "integer"}},
    }

    with pytest.raises(ToolValidationError) as exc_info:
        validate_input_schema(schema, {"limit": "3"})

    assert "limit must be integer" in str(exc_info.value)


def test_redact_mapping_hides_sensitive_fields_recursively():
    redacted = redact_mapping(
        {
            "query": "status",
            "api_key": "secret-value",
            "headers": {"Authorization": "Bearer abcdefghijkl"},
        }
    )

    assert redacted == {
        "query": "status",
        "api_key": "[REDACTED]",
        "headers": {"Authorization": "[REDACTED]"},
    }


def test_json_transform_selects_requested_keys():
    output = execute_builtin_tool(
        "json_transform",
        {
            "data": {"title": "Report", "secret": "hidden", "count": 2},
            "select_keys": ["title", "count"],
        },
    )

    assert output == {"result": {"title": "Report", "count": 2}}


def test_markdown_report_generate_returns_markdown():
    output = execute_builtin_tool(
        "markdown_report_generate",
        {
            "title": "Phase 2",
            "sections": [
                {"heading": "Summary", "content": "Tool Registry works."},
                {"heading": "Risk", "content": "High-risk tools are blocked."},
            ],
        },
    )

    assert output == {
        "markdown": "# Phase 2\n\n## Summary\n\nTool Registry works.\n\n## Risk\n\nHigh-risk tools are blocked."
    }

