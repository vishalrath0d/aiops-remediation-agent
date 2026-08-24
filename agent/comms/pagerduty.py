"""PagerDuty notifications: real PagerDuty Events API v2 calls (the
same public, documented API any PagerDuty-integrated monitoring tool
uses) -- trigger on DETECTED, resolve on RESOLVED. Escalation-only tool,
deliberately not wired to every phase: PagerDuty's whole job is "wake a
human up," which should happen once when an incident starts and once
when it's genuinely over, not on every intermediate phase change (that's
what the GitHub issue and Slack message are for).

Same best-effort contract as the other comms backends: no-op if
PAGERDUTY_ROUTING_KEY isn't set, never raises into the caller. Not
live-verified -- no PagerDuty account was available in the environment
this was built in; calls match the Events API v2 documented request/
response shape exactly.
"""
from __future__ import annotations

import json
import urllib.request

from agent.comms.incident import Incident
from agent.config import PagerDutyConfig

_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"


def trigger(config: PagerDutyConfig, incident: Incident) -> str | None:
    if not config.enabled:
        return None
    try:
        resp = _send(config, {
            "routing_key": config.routing_key,
            "event_action": "trigger",
            "dedup_key": incident.incident_id,
            "payload": {
                "summary": f"[aiops] {incident.domain}: {incident.summary}",
                "source": incident.target,
                "severity": "warning",
            },
        })
        return resp.get("dedup_key")
    except Exception as exc:  # noqa: BLE001
        print(f"warning: PagerDuty trigger failed: {exc}")
        return None


def resolve(config: PagerDutyConfig, incident: Incident) -> None:
    if not config.enabled:
        return
    try:
        _send(config, {
            "routing_key": config.routing_key,
            "event_action": "resolve",
            "dedup_key": incident.incident_id,
        })
    except Exception as exc:  # noqa: BLE001
        print(f"warning: PagerDuty resolve failed: {exc}")


def _send(config: PagerDutyConfig, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(_EVENTS_URL, data=body, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())
