"""Proves the mode gate can't be bypassed: preview must NEVER call a
mutating gh/git command, for any category. subprocess is patched
throughout -- this is a unit test of the gating logic, the real
mechanism is exercised live (see the README's Verified section)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent.remediation import code_fix
from agent.remediation.mode import ExecutionMode
from agent.triage.classify import TriageResult


def _fake_completed(stdout: str = "") -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    return m


@pytest.mark.parametrize(
    "triage",
    [
        TriageResult("flaky_test", 0.95, "r", "e", "fast"),
        TriageResult("missing_dependency", 0.95, "r", "No module named 'x'", "fast"),
        TriageResult("bad_config", 0.9, "r", "e", "fast"),
        TriageResult("unknown", 0.0, "r", "", "no-provider"),
    ],
)
def test_preview_mode_never_calls_subprocess(monkeypatch, tmp_path, triage):
    calls = []
    monkeypatch.setattr(code_fix.subprocess, "run", lambda *a, **kw: calls.append(a) or _fake_completed())

    result = code_fix.dispatch(
        str(tmp_path / "state"), "owner/repo", "123", "https://example/run/123", triage, ExecutionMode.PREVIEW
    )

    assert result.applied is False
    assert calls == [], f"preview mode made real calls: {calls}"


def test_fix_mode_flaky_test_only_calls_rerun(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(code_fix.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _fake_completed())

    triage = TriageResult("flaky_test", 0.95, "r", "e", "fast")
    result = code_fix.dispatch(str(tmp_path / "state"), "owner/repo", "123", "url", triage, ExecutionMode.EXECUTE)

    assert result.applied is True
    assert len(calls) == 1
    assert calls[0][:3] == ["gh", "run", "rerun"]


def test_fix_mode_bad_config_only_opens_issue(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        code_fix.subprocess, "run",
        lambda cmd, **kw: calls.append(cmd) or _fake_completed(stdout="https://example/issues/1\n"),
    )

    triage = TriageResult("bad_config", 0.9, "r", "e", "fast")
    result = code_fix.dispatch(str(tmp_path / "state"), "owner/repo", "123", "url", triage, ExecutionMode.EXECUTE)

    assert result.applied is True
    assert len(calls) == 1
    assert calls[0][:3] == ["gh", "issue", "create"]
