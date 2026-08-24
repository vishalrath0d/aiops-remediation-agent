"""Terraform state import: parses the REAL output of `terraform show
-json` (either generated live against terraform_dir, or a JSON file
handed in -- e.g. to import from an environment you don't want this
agent running `terraform show` against directly) into a normalized
resource inventory.

`terraform show -json`'s shape is Terraform's own stable, documented
machine-readable state format -- this isn't scraping human-oriented
output, it's the same interface tools like Terraform Cloud's own UI are
built on.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class ManagedResource:
    address: str
    resource_type: str
    name: str
    attributes: dict


def import_from_live_state(terraform_dir: str) -> list[ManagedResource]:
    result = subprocess.run(
        ["terraform", "show", "-json"],
        cwd=terraform_dir, capture_output=True, text=True, check=True,
    )
    return _parse(json.loads(result.stdout))


def import_from_file(state_json_path: str) -> list[ManagedResource]:
    with open(state_json_path, encoding="utf-8") as f:
        return _parse(json.load(f))


def _parse(show_json: dict) -> list[ManagedResource]:
    root = show_json.get("values", {}).get("root_module", {})
    resources = root.get("resources", [])
    return [
        ManagedResource(
            address=r["address"],
            resource_type=r["type"],
            name=r["name"],
            attributes=r.get("values", {}),
        )
        for r in resources
    ]
