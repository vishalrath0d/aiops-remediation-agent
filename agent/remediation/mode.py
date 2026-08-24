"""Execution mode: the one gate every remediation action in this project
passes through before it's allowed to change anything real.

Two states internally -- PREVIEW and EXECUTE -- but the label shown to a
human/CLI differs by domain, because "fix" and "apply" mean different
things and neither reads naturally for the other domain:

  - code fixes:            preview / fix
  - Terraform (infra):     preview / apply
  - Ansible (config):      preview / apply

PREVIEW is always the default. Nothing in this project ever mutates
anything without an explicit, per-run EXECUTE.
"""
from __future__ import annotations

from enum import Enum


class ExecutionMode(Enum):
    PREVIEW = "preview"
    EXECUTE = "execute"


CODE_LABELS = {ExecutionMode.PREVIEW: "preview", ExecutionMode.EXECUTE: "fix"}
INFRA_LABELS = {ExecutionMode.PREVIEW: "preview", ExecutionMode.EXECUTE: "apply"}


def parse_code_mode(value: str) -> ExecutionMode:
    return _parse(value, CODE_LABELS)


def parse_infra_mode(value: str) -> ExecutionMode:
    return _parse(value, INFRA_LABELS)


def _parse(value: str, labels: dict[ExecutionMode, str]) -> ExecutionMode:
    by_label = {label: mode for mode, label in labels.items()}
    if value not in by_label:
        raise ValueError(f"{value!r} is not one of {sorted(by_label)}")
    return by_label[value]
