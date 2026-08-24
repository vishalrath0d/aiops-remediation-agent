"""Ansible remediation: preview is `ansible-playbook --check --diff`
(real, executes nothing, shows exactly what would change); apply is a
real, unrestricted playbook run. Same "swap the target, not the code"
property as terraform_fix.py -- point ansible_inventory at real hosts
later and nothing here changes."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass

from agent.remediation.mode import ExecutionMode


@dataclass(frozen=True)
class AnsibleResult:
    mode: ExecutionMode
    applied: bool
    output: str


def preview(inventory: str, playbook: str) -> AnsibleResult:
    result = subprocess.run(
        ["ansible-playbook", "-i", inventory, playbook, "--check", "--diff"],
        capture_output=True, text=True,
    )
    return AnsibleResult(mode=ExecutionMode.PREVIEW, applied=False, output=result.stdout + result.stderr)


def apply(inventory: str, playbook: str) -> AnsibleResult:
    result = subprocess.run(
        ["ansible-playbook", "-i", inventory, playbook],
        capture_output=True, text=True, check=True,
    )
    return AnsibleResult(mode=ExecutionMode.EXECUTE, applied=True, output=result.stdout + result.stderr)


def remediate(inventory: str, playbook: str, mode: ExecutionMode) -> AnsibleResult:
    if mode == ExecutionMode.PREVIEW:
        return preview(inventory, playbook)
    return apply(inventory, playbook)
