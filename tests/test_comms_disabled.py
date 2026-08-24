"""Proves the best-effort contract: with no credentials configured
(the autouse no_real_credentials fixture in conftest.py), every comms
backend is a true no-op -- specifically, none of them ever reach the
network layer. urllib.request.urlopen is patched to raise if called at
all, so a bug that skipped an `enabled` check would fail this test
immediately rather than silently trying (and failing) a real HTTP call."""
from __future__ import annotations

import pytest

from agent.comms import jira, pagerduty, slack
from agent.comms.incident import Incident
from agent.config import JiraConfig, PagerDutyConfig, SlackConfig


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("a disabled comms backend tried to make a real network call")

    monkeypatch.setattr("urllib.request.urlopen", _boom)


def _incident():
    return Incident(incident_id="x", domain="code", target="owner/repo", summary="s")


def test_slack_disabled_is_noop():
    config = SlackConfig(bot_token=None, channel_id=None)
    assert config.enabled is False
    assert slack.post_incident_message(config, _incident()) is None
    slack.update_incident_message(config, "ts", _incident(), "note")  # must not raise


def test_jira_disabled_is_noop():
    config = JiraConfig(url=None, email=None, api_token=None)
    assert config.enabled is False
    assert jira.create_ticket(config, _incident()) is None
    jira.add_comment(config, None, "note")
    jira.try_transition(config, None, jira.DONE_NAMES)


def test_pagerduty_disabled_is_noop():
    config = PagerDutyConfig(routing_key=None)
    assert config.enabled is False
    assert pagerduty.trigger(config, _incident()) is None
    pagerduty.resolve(config, _incident())
