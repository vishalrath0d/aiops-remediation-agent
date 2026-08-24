"""Jira notifications: real Jira Cloud REST API v3 calls -- create one
issue per incident, add a comment on every phase transition, best-effort
status transition to whatever the target project's workflow calls
"In Progress"/"Done" (tries common names, silently skips if none match
rather than guessing a company-specific workflow's exact transition ID).

Deliberately generic where gitlab-access-bot's jira_client.py (the real
prior art this generalizes) is specific: that file targets one real
company Jira project's exact custom-field screen scheme
(customfield_13063 etc.) discovered by hand against that instance --
correct for that one Jira, meaningless (or actively wrong) against any
other. This module only ever sets Jira's own standard fields (project,
issuetype, summary, description) plus comments -- the honest, portable
subset of that pattern.

Same best-effort contract as slack.py: no-op if JIRA_URL/JIRA_EMAIL/
JIRA_API_TOKEN aren't all set, never raises into the caller. Not
live-verified -- no Jira Cloud instance was available in the environment
this was built in; calls match Jira's documented REST API v3 shape.
"""
from __future__ import annotations

import json
import urllib.request

from agent.comms.incident import Incident
from agent.config import JiraConfig

# Transition names tried, in order, when moving an incident forward --
# generic enough to match a lot of real Jira workflows without assuming
# any one company's exact configuration.
IN_PROGRESS_NAMES = ("In Progress", "In progress", "Start Progress")
DONE_NAMES = ("Done", "Resolved", "Closed")


def create_ticket(config: JiraConfig, incident: Incident) -> str | None:
    if not config.enabled:
        return None
    try:
        resp = _post(config, "issue", {
            "fields": {
                "project": {"key": config.project_key},
                "issuetype": {"name": config.issue_type},
                "summary": f"[aiops] {incident.domain}: {incident.summary}",
                "description": _adf(f"Target: {incident.target}\nIncident: {incident.incident_id}"),
            }
        })
        return resp.get("key")
    except Exception as exc:  # noqa: BLE001
        print(f"warning: Jira create_ticket failed: {exc}")
        return None


def add_comment(config: JiraConfig, issue_key: str | None, note: str) -> None:
    if not config.enabled or not issue_key:
        return
    try:
        _post(config, f"issue/{issue_key}/comment", {"body": _adf(note)})
    except Exception as exc:  # noqa: BLE001
        print(f"warning: Jira add_comment failed: {exc}")


def try_transition(config: JiraConfig, issue_key: str | None, target_names: tuple[str, ...]) -> None:
    """Best-effort only -- if none of target_names match a real available
    transition on this issue, this silently does nothing rather than
    guessing a transition ID."""
    if not config.enabled or not issue_key:
        return
    try:
        available = _get(config, f"issue/{issue_key}/transitions").get("transitions", [])
        for t in available:
            if t.get("name") in target_names:
                _post(config, f"issue/{issue_key}/transitions", {"transition": {"id": t["id"]}})
                return
    except Exception as exc:  # noqa: BLE001
        print(f"warning: Jira try_transition failed: {exc}")


def _adf(text: str) -> dict:
    """Jira Cloud's Atlassian Document Format -- the real required shape
    for description/comment bodies in REST API v3 (plain strings are
    rejected)."""
    return {
        "type": "doc", "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def _post(config: JiraConfig, path: str, payload: dict) -> dict:
    return _request(config, "POST", path, payload)


def _get(config: JiraConfig, path: str) -> dict:
    return _request(config, "GET", path, None)


def _request(config: JiraConfig, method: str, path: str, payload: dict | None) -> dict:
    import base64

    body = json.dumps(payload).encode() if payload is not None else None
    auth = base64.b64encode(f"{config.email}:{config.api_token}".encode()).decode()
    req = urllib.request.Request(
        f"{config.url}/rest/api/3/{path}", data=body, method=method,
        headers={"content-type": "application/json", "authorization": f"Basic {auth}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}
