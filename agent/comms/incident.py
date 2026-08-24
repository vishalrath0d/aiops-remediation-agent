"""The incident lifecycle every remediation goes through, and the one
object every comms backend (GitHub/Slack/Jira/PagerDuty) renders its own
way. A phase transition happens once, in the orchestrator; every backend
just reacts to it -- no backend decides the incident's state itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Phase(Enum):
    DETECTED = "detected"
    DIAGNOSING = "diagnosing"
    FIX_PROPOSED = "fix_proposed"       # a preview was generated
    APPLIED = "applied"                 # a real fix/apply ran
    VERIFIED = "verified"               # the fix was confirmed to work
    RESOLVED = "resolved"               # terminal, success
    ESCALATED = "escalated"             # terminal, needs a human


# The only transitions the orchestrator is allowed to make -- kept
# explicit so an invalid jump (e.g. DETECTED -> RESOLVED, skipping
# diagnosis entirely) is a caught bug, not a silent state that never
# happened.
_ALLOWED_TRANSITIONS: dict[Phase, set[Phase]] = {
    Phase.DETECTED: {Phase.DIAGNOSING, Phase.ESCALATED},
    Phase.DIAGNOSING: {Phase.FIX_PROPOSED, Phase.ESCALATED},
    Phase.FIX_PROPOSED: {Phase.APPLIED, Phase.ESCALATED},
    Phase.APPLIED: {Phase.VERIFIED, Phase.ESCALATED},
    Phase.VERIFIED: {Phase.RESOLVED, Phase.ESCALATED},
    Phase.RESOLVED: set(),
    Phase.ESCALATED: set(),
}


@dataclass
class Incident:
    incident_id: str
    domain: str
    """'code', 'terraform', or 'ansible'."""
    target: str
    """The repo (code) or the terraform_dir/inventory host (infra/config)."""
    summary: str
    phase: Phase = Phase.DETECTED
    history: list[tuple[str, Phase, str]] = field(default_factory=list)
    """(timestamp, phase, note) for every transition, oldest first."""

    def __post_init__(self) -> None:
        self.history.append((datetime.now(timezone.utc).isoformat(), self.phase, "incident created"))

    def transition(self, to: Phase, note: str) -> None:
        allowed = _ALLOWED_TRANSITIONS[self.phase]
        if to not in allowed:
            raise ValueError(f"illegal transition {self.phase.value} -> {to.value} (allowed: {[p.value for p in allowed]})")
        self.phase = to
        self.history.append((datetime.now(timezone.utc).isoformat(), to, note))
