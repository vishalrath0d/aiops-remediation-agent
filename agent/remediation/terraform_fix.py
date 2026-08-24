"""Terraform remediation: preview is always `terraform plan` (real,
harmless, read-only); apply is a real `terraform apply -auto-approve`
against whatever `terraform_dir` points at. Nothing here knows or cares
that the demo target is local Docker instead of a real cloud account --
point terraform_dir at a real backend/provider config later and this
module needs zero changes."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass

from agent.remediation.mode import ExecutionMode


@dataclass(frozen=True)
class TerraformResult:
    mode: ExecutionMode
    applied: bool
    """True only when a real `terraform apply` actually ran."""
    output: str


def preview(terraform_dir: str) -> TerraformResult:
    result = subprocess.run(
        ["terraform", "plan", "-no-color", "-input=false"],
        cwd=terraform_dir, capture_output=True, text=True,
    )
    return TerraformResult(mode=ExecutionMode.PREVIEW, applied=False, output=result.stdout + result.stderr)


def apply(terraform_dir: str) -> TerraformResult:
    result = subprocess.run(
        ["terraform", "apply", "-auto-approve", "-no-color", "-input=false"],
        cwd=terraform_dir, capture_output=True, text=True, check=True,
    )
    return TerraformResult(mode=ExecutionMode.EXECUTE, applied=True, output=result.stdout + result.stderr)


def remediate(terraform_dir: str, mode: ExecutionMode) -> TerraformResult:
    if mode == ExecutionMode.PREVIEW:
        return preview(terraform_dir)
    return apply(terraform_dir)
