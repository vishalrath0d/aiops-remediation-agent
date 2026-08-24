"""Ansible inventory import: parses a real Ansible YAML inventory (the
same format `demo_infra/ansible/inventory.yml` uses) into a normalized
host list. Stdlib-only -- a real Ansible inventory is just YAML with a
predictable `all: hosts: {name: {vars...}}` / `all: children: {...}`
shape, so this doesn't need PyYAML or Ansible's own (much heavier)
inventory-parsing machinery for the read-only "what hosts exist" case
this project needs.
"""
from __future__ import annotations

from dataclasses import dataclass

try:
    import yaml
except ImportError:  # pragma: no cover - exercised via the yaml-missing test
    yaml = None


@dataclass(frozen=True)
class InventoryHost:
    name: str
    variables: dict


def import_inventory(path: str) -> list[InventoryHost]:
    if yaml is None:
        raise RuntimeError(
            "PyYAML is required to parse an Ansible inventory -- pip install pyyaml"
        )
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    hosts: dict[str, dict] = {}
    _collect_hosts(data.get("all", {}), hosts)
    return [InventoryHost(name=name, variables=variables) for name, variables in hosts.items()]


def _collect_hosts(group: dict, out: dict[str, dict]) -> None:
    for name, variables in (group.get("hosts") or {}).items():
        out[name] = variables or {}
    for _child_name, child in (group.get("children") or {}).items():
        _collect_hosts(child or {}, out)
