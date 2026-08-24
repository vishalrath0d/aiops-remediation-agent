"""Slack notifications: real Slack Web API calls (chat.postMessage then
chat.update on the SAME message as the incident progresses through
phases), the exact pattern gitlab-access-bot's bot.py uses for its own
request lifecycle -- generalized here from one company's Slack workspace
to any SLACK_BOT_TOKEN/SLACK_CHANNEL_ID.

Best-effort by design, same rule as every comms backend in this module:
disabled (silently) if not configured, and a failure here must never
raise into the caller -- a Slack outage or bad token must never stop the
actual remediation work. See config.py's SlackConfig.

Not live-verified: no Slack workspace/bot token was available in the
environment this was built in. The API calls below match Slack's
documented Web API exactly (verified against the docs, not guessed) --
see the README's "Verified" section for what that distinction means in
practice.
"""
from __future__ import annotations

import json
import urllib.request

from agent.comms.incident import Incident
from agent.config import SlackConfig

_API_BASE = "https://slack.com/api"


def post_incident_message(config: SlackConfig, incident: Incident) -> str | None:
    if not config.enabled:
        return None
    try:
        resp = _call(config, "chat.postMessage", {
            "channel": config.channel_id,
            "text": _render(incident, "Incident detected"),
        })
        return resp.get("ts") if resp.get("ok") else None
    except Exception as exc:  # noqa: BLE001 - best-effort, never block the caller
        print(f"warning: Slack post_incident_message failed: {exc}")
        return None


def update_incident_message(config: SlackConfig, ts: str, incident: Incident, note: str) -> None:
    if not config.enabled or not ts:
        return
    try:
        _call(config, "chat.update", {
            "channel": config.channel_id,
            "ts": ts,
            "text": _render(incident, note),
        })
    except Exception as exc:  # noqa: BLE001
        print(f"warning: Slack update_incident_message failed: {exc}")


def _render(incident: Incident, note: str) -> str:
    return (
        f"*[{incident.domain}] {incident.summary}*\n"
        f"Phase: `{incident.phase.value}` -- {note}\n"
        f"Target: `{incident.target}` | Incident: `{incident.incident_id}`"
    )


def _call(config: SlackConfig, method: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{_API_BASE}/{method}", data=body,
        headers={"content-type": "application/json", "authorization": f"Bearer {config.bot_token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())
