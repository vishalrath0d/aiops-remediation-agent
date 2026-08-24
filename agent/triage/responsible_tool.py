"""The tool-routing decision: given what's actually broken, which tool
is responsible for fixing it?

This is deliberately NOT a text classifier guessing from a description --
each observer (agent/observer/*.py) already reports which layer it found
a problem in (a CI run failing is unambiguously a code concern; a
Terraform-plan/Ansible-check finding already says which layer). What
this module owns is the one real decision that isn't already implicit:
priority, when a target has both infra and config drift at once.
"""
from __future__ import annotations

from agent.observer.infra_drift import DriftFinding

ResponsibleTool = str  # "code" | "terraform" | "ansible"


def route_infra_incident(
    terraform_finding: DriftFinding | None,
    ansible_finding: DriftFinding | None,
) -> ResponsibleTool | None:
    """Terraform wins if both are present -- a resource that doesn't
    exist (or is the wrong shape) makes any config-drift finding on top
    of it meaningless: you can't correctly configure something that
    isn't there yet. See observer/infra_drift.py's module docstring for
    why Terraform is checked first in practice, not just prioritized
    here after the fact."""
    if terraform_finding is not None:
        return "terraform"
    if ansible_finding is not None:
        return "ansible"
    return None
