"""GitHub-native incident tracking: one real issue per incident, opened
on DETECTED and updated with a real comment on every subsequent phase
transition, closed on RESOLVED. This is the one comms backend that's
always on (no env-gating, no "enabled" check) -- it needs nothing beyond
the `gh` auth already required for everything else in this project, and
every incident should be visible somewhere even if Slack/Jira/PagerDuty
are all unconfigured.

Same "comment per lifecycle event" shape as gitlab-access-bot's Jira
mirror (jira_client.py) -- proven pattern, applied to the tracker every
incident here always has, GitHub itself, instead of a downstream mirror.
"""
from __future__ import annotations

import subprocess

from agent.comms.incident import Incident, Phase


def open_tracking_issue(tracker_repo: str, incident: Incident) -> str:
    """Returns the created issue's URL."""
    title = f"[aiops] {incident.domain}: {incident.summary}"
    body = (
        f"**Incident** `{incident.incident_id}`\n"
        f"- Domain: `{incident.domain}`\n"
        f"- Target: `{incident.target}`\n"
        f"- Phase: `{incident.phase.value}`\n\n"
        "This issue is updated automatically as the incident progresses."
    )
    result = subprocess.run(
        ["gh", "issue", "create", "--repo", tracker_repo, "--title", title, "--body", body],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def post_phase_update(tracker_repo: str, issue_url: str, incident: Incident, note: str) -> None:
    issue_number = issue_url.rstrip("/").rsplit("/", 1)[-1]
    body = f"**Phase -> `{incident.phase.value}`**\n\n{note}"
    subprocess.run(
        ["gh", "issue", "comment", issue_number, "--repo", tracker_repo, "--body", body],
        check=True, capture_output=True,
    )
    if incident.phase == Phase.RESOLVED:
        # ESCALATED deliberately does NOT close the issue -- escalating
        # means "a human needs to look at this" (a preview awaiting an
        # apply decision, or a fix that didn't work). Closing it right
        # then would defeat the entire point of escalating. Found live:
        # the first real run closed issue #1 on a preview-only outcome,
        # which is exactly backwards.
        subprocess.run(
            ["gh", "issue", "close", issue_number, "--repo", tracker_repo],
            check=True, capture_output=True,
        )
