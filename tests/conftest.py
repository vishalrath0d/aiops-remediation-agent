from __future__ import annotations

import os

import pytest


@pytest.fixture
def fixture_log(request):
    def _load(name: str) -> str:
        path = os.path.join(os.path.dirname(__file__), "fixtures", f"{name}.log")
        with open(path, encoding="utf-8") as f:
            return f.read()
    return _load


@pytest.fixture(autouse=True)
def no_real_credentials(monkeypatch):
    """Every test runs with zero external credentials set -- LLM
    providers AND comms backends -- so the suite is free, offline,
    deterministic, and never accidentally fires a real Slack/Jira/
    PagerDuty call."""
    for key in (
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
        "SLACK_BOT_TOKEN", "SLACK_CHANNEL_ID",
        "JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN",
        "PAGERDUTY_ROUTING_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
