"""Infra + config drift observers -- real drift detection using each
tool's OWN mechanism for it, not a text classifier guessing from a log:

  - Terraform: `terraform plan -detailed-exitcode`. Exit code 2 means
    real, computed drift (a resource missing, changed, or extra);
    0 means genuinely nothing to do; 1 is a real error. This is
    Terraform's own documented mechanism for "is there drift," not
    something this project invented.
  - Ansible: `ansible-playbook --check --diff`. Check mode runs every
    task without changing anything and reports what WOULD have changed
    -- if any task reports changed=true, that's real config drift on an
    already-provisioned target.

Terraform is checked first, deliberately: if the resource Ansible would
configure doesn't exist yet, Ansible has nothing meaningful to report
(the connection itself fails) -- fixing the missing resource is a
precondition for a config-drift check to mean anything at all. See
agent/triage/responsible_tool.py for where this ordering becomes the
actual routing decision.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class DriftFinding:
    layer: str
    """'terraform' or 'ansible'."""

    summary: str
    detail: str


def check_terraform_drift(terraform_dir: str) -> DriftFinding | None:
    result = subprocess.run(
        ["terraform", "plan", "-detailed-exitcode", "-no-color", "-input=false"],
        cwd=terraform_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return None
    if result.returncode == 1:
        raise RuntimeError(f"terraform plan failed (not drift, a real error):\n{result.stderr}")
    # returncode == 2: real, computed drift
    summary = _summarize_plan(result.stdout)
    return DriftFinding(layer="terraform", summary=summary, detail=result.stdout)


def _summarize_plan(plan_output: str) -> str:
    for line in plan_output.splitlines():
        line = line.strip()
        if line.startswith("Plan:"):
            return line
    return "terraform plan reports changes (see detail)"


def check_ansible_drift(inventory: str, playbook: str) -> DriftFinding | None:
    result = subprocess.run(
        [
            "ansible-playbook", "-i", inventory, playbook,
            "--check", "--diff",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and "changed=" not in result.stdout:
        # A real connection/execution failure (e.g. the target doesn't
        # exist), not config drift -- caller should have already routed
        # to Terraform first in that case, but don't silently swallow it
        # if this got called out of order.
        raise RuntimeError(f"ansible-playbook --check failed to run:\n{result.stdout}\n{result.stderr}")

    changed = _parse_changed_count(result.stdout)
    if changed == 0:
        return None
    return DriftFinding(
        layer="ansible",
        summary=f"{changed} task(s) would change on the next real run",
        detail=result.stdout,
    )


def _parse_changed_count(playbook_output: str) -> int:
    for line in playbook_output.splitlines():
        if "changed=" in line:
            for token in line.split():
                if token.startswith("changed="):
                    return int(token.split("=", 1)[1])
    return 0
