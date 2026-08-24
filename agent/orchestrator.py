"""Ties every piece together into the two real loops this project runs:

  run_code_once()  -- the self-healing-cicd loop, generalized to any repo.
  run_infra_once() -- observe (Terraform drift, then Ansible drift) ->
                       route to the responsible tool -> remediate
                       (mode-gated) -> verify, with the same incident
                       lifecycle tracked across GitHub (always) and
                       Slack/Jira/PagerDuty (best-effort, if configured).

Comms notifications never abort the loop -- a Slack/Jira/PagerDuty
failure is caught inside those modules themselves (see comms/*.py), so a
notification outage can never stop real remediation work, the same
"never block the core flow" rule gitlab-access-bot's jira_client.py was
built around.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from agent import state
from agent.comms import github_tracker, jira, pagerduty, slack
from agent.comms.incident import Incident, Phase
from agent.config import Settings
from agent.observer import github_ci, infra_drift
from agent.remediation import code_fix, terraform_fix, ansible_fix
from agent.remediation.mode import ExecutionMode
from agent.triage import classify
from agent.triage.responsible_tool import route_infra_incident


@dataclass(frozen=True)
class RunOutcome:
    incident: Incident
    detail: str


class _Notifier:
    """Wraps the 4 comms backends behind one call per phase transition,
    so orchestrator functions don't have to know which backends are
    configured."""

    def __init__(self, settings: Settings, tracker_repo: str):
        self.settings = settings
        self.tracker_repo = tracker_repo
        self.issue_url: str | None = None
        self.slack_ts: str | None = None
        self.jira_key: str | None = None

    def detected(self, incident: Incident) -> None:
        self.issue_url = github_tracker.open_tracking_issue(self.tracker_repo, incident)
        self.slack_ts = slack.post_incident_message(self.settings.slack, incident)
        self.jira_key = jira.create_ticket(self.settings.jira, incident)
        pagerduty.trigger(self.settings.pagerduty, incident)

    def phase_changed(self, incident: Incident, note: str) -> None:
        if self.issue_url:
            github_tracker.post_phase_update(self.tracker_repo, self.issue_url, incident, note)
        if self.slack_ts:
            slack.update_incident_message(self.settings.slack, self.slack_ts, incident, note)
        if self.jira_key:
            jira.add_comment(self.settings.jira, self.jira_key, note)
            if incident.phase == Phase.DIAGNOSING:
                jira.try_transition(self.settings.jira, self.jira_key, jira.IN_PROGRESS_NAMES)
            elif incident.phase in (Phase.RESOLVED, Phase.ESCALATED):
                jira.try_transition(self.settings.jira, self.jira_key, jira.DONE_NAMES)
        if incident.phase == Phase.RESOLVED:
            pagerduty.resolve(self.settings.pagerduty, incident)


def run_code_once(settings: Settings, tracker_repo: str, mode: ExecutionMode) -> list[RunOutcome]:
    if not settings.code_repo:
        raise ValueError("settings.code_repo must be set for run_code_once")

    processed = state.load_processed(settings.state_dir)
    outcomes: list[RunOutcome] = []

    for run in github_ci.list_failed_runs(settings.code_repo):
        key = f"code:{settings.code_repo}:{run.run_id}"
        if key in processed:
            continue

        incident = Incident(
            incident_id=str(uuid.uuid4())[:8], domain="code", target=settings.code_repo,
            summary=f"CI run {run.run_id} failed",
        )
        notifier = _Notifier(settings, tracker_repo)
        notifier.detected(incident)

        incident.transition(Phase.DIAGNOSING, f"fetching and triaging log for run {run.run_id}")
        notifier.phase_changed(incident, f"triaging {run.url}")
        log_text = github_ci.fetch_failed_log(settings.code_repo, run.run_id)
        triage_result = classify.classify(log_text, settings)

        incident.transition(Phase.FIX_PROPOSED, f"triaged as {triage_result.category}")
        notifier.phase_changed(incident, f"category={triage_result.category} confidence={triage_result.confidence:.2f}")
        fix_result = code_fix.dispatch(settings.state_dir, settings.code_repo, run.run_id, run.url, triage_result, mode)

        if mode == ExecutionMode.PREVIEW:
            incident.transition(Phase.ESCALATED, f"preview only, no changes made: {fix_result.detail}")
            notifier.phase_changed(incident, fix_result.detail)
        else:
            incident.transition(Phase.APPLIED, fix_result.detail)
            notifier.phase_changed(incident, fix_result.detail)
            if fix_result.action == "retry_workflow":
                verify_outcome = _verify_retry(settings, run.run_id)
                if verify_outcome == "success":
                    incident.transition(Phase.VERIFIED, "retry succeeded")
                    notifier.phase_changed(incident, "retry succeeded")
                    incident.transition(Phase.RESOLVED, "resolved")
                    notifier.phase_changed(incident, "resolved")
                else:
                    incident.transition(Phase.ESCALATED, f"retry did not fix it (outcome={verify_outcome})")
                    notifier.phase_changed(incident, f"retry outcome={verify_outcome}, needs a human")
            else:
                incident.transition(Phase.ESCALATED, "PR/issue opened, awaiting human review")
                notifier.phase_changed(incident, "awaiting human review")

        state.mark_processed(settings.state_dir, key)
        state.append_audit_entry(
            settings.state_dir,
            state.new_audit_entry(
                incident_id=incident.incident_id, domain=incident.domain, target=incident.target,
                summary=incident.summary, final_phase=incident.phase.value, detail=fix_result.detail,
            ),
        )
        outcomes.append(RunOutcome(incident=incident, detail=fix_result.detail))

    return outcomes


def _verify_retry(settings: Settings, run_id: str) -> str:
    import time

    start = time.monotonic()
    while True:
        status, conclusion = github_ci.run_status(settings.code_repo, run_id)
        if status == "completed":
            return "success" if conclusion == "success" else "failure"
        if time.monotonic() - start >= settings.verify_timeout_seconds:
            return "timed_out"
        time.sleep(settings.poll_interval_seconds)


def run_infra_once(settings: Settings, tracker_repo: str, mode: ExecutionMode) -> RunOutcome | None:
    terraform_finding = infra_drift.check_terraform_drift(settings.terraform_dir)
    ansible_finding = (
        None if terraform_finding is not None
        else infra_drift.check_ansible_drift(settings.ansible_inventory, settings.ansible_playbook)
    )

    responsible = route_infra_incident(terraform_finding, ansible_finding)
    if responsible is None:
        return None  # nothing to do -- no drift found

    finding = terraform_finding if responsible == "terraform" else ansible_finding
    incident = Incident(
        incident_id=str(uuid.uuid4())[:8], domain=responsible,
        target=settings.terraform_dir if responsible == "terraform" else settings.ansible_inventory,
        summary=finding.summary,
    )
    notifier = _Notifier(settings, tracker_repo)
    notifier.detected(incident)

    incident.transition(Phase.DIAGNOSING, f"{responsible} drift detected")
    notifier.phase_changed(incident, finding.summary)

    incident.transition(Phase.FIX_PROPOSED, f"remediation mode: {mode.value}")
    notifier.phase_changed(incident, f"routed to {responsible}, mode={mode.value}")

    if responsible == "terraform":
        result = terraform_fix.remediate(settings.terraform_dir, mode)
    else:
        result = ansible_fix.remediate(settings.ansible_inventory, settings.ansible_playbook, mode)

    if not result.applied:
        incident.transition(Phase.ESCALATED, "preview only, no changes made -- see the preview output")
        notifier.phase_changed(incident, "preview generated, awaiting a human to apply")
    else:
        incident.transition(Phase.APPLIED, f"real {responsible} apply ran")
        notifier.phase_changed(incident, "applied")
        incident.transition(Phase.VERIFIED, "re-checked for remaining drift")
        notifier.phase_changed(incident, "verifying")
        still_drifted = (
            infra_drift.check_terraform_drift(settings.terraform_dir) is not None
            if responsible == "terraform"
            else infra_drift.check_ansible_drift(settings.ansible_inventory, settings.ansible_playbook) is not None
        )
        if still_drifted:
            incident.transition(Phase.ESCALATED, "still drifted after apply -- needs a human")
            notifier.phase_changed(incident, "apply ran but drift persists")
        else:
            incident.transition(Phase.RESOLVED, "no drift remaining")
            notifier.phase_changed(incident, "resolved")

    state.append_audit_entry(
        settings.state_dir,
        state.new_audit_entry(
            incident_id=incident.incident_id, domain=incident.domain, target=incident.target,
            summary=incident.summary, final_phase=incident.phase.value, detail=result.output[-2000:],
        ),
    )
    return RunOutcome(incident=incident, detail=result.output)
