import pytest

from agent.remediation.mode import ExecutionMode, parse_code_mode, parse_infra_mode


def test_code_mode_labels():
    assert parse_code_mode("preview") == ExecutionMode.PREVIEW
    assert parse_code_mode("fix") == ExecutionMode.EXECUTE


def test_infra_mode_labels():
    assert parse_infra_mode("preview") == ExecutionMode.PREVIEW
    assert parse_infra_mode("apply") == ExecutionMode.EXECUTE


def test_code_mode_rejects_apply():
    """'apply' is the infra/config verb, not code's -- must not silently accept it."""
    with pytest.raises(ValueError):
        parse_code_mode("apply")


def test_infra_mode_rejects_fix():
    with pytest.raises(ValueError):
        parse_infra_mode("fix")
