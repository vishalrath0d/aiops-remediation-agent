"""Local, per-machine state -- same pattern as self-healing-cicd's
state.py: which (repo, run_id) pairs have already been processed, plus
an append-only audit log of every incident's full lifecycle. Gitignored,
not shared between machines."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


def _processed_path(state_dir: str) -> str:
    return os.path.join(state_dir, "processed_runs.json")


def _audit_path(state_dir: str) -> str:
    return os.path.join(state_dir, "audit_log.jsonl")


def load_processed(state_dir: str) -> set[str]:
    path = _processed_path(state_dir)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return set(json.load(f))


def mark_processed(state_dir: str, key: str) -> None:
    os.makedirs(state_dir, exist_ok=True)
    processed = load_processed(state_dir)
    processed.add(key)
    with open(_processed_path(state_dir), "w", encoding="utf-8") as f:
        json.dump(sorted(processed), f, indent=2)


@dataclass(frozen=True)
class AuditEntry:
    timestamp: str
    incident_id: str
    domain: str
    target: str
    summary: str
    final_phase: str
    detail: str


def append_audit_entry(state_dir: str, entry: AuditEntry) -> None:
    os.makedirs(state_dir, exist_ok=True)
    with open(_audit_path(state_dir), "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry)) + "\n")


def new_audit_entry(**kwargs) -> AuditEntry:
    return AuditEntry(timestamp=datetime.now(timezone.utc).isoformat(), **kwargs)
