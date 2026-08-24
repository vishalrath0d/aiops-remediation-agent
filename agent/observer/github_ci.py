"""CI observer -- generalized from self-healing-cicd's observer.py.

The one real change from that project: every function here takes the
target repo as an explicit argument instead of reading it off Settings
once at startup, because this project's whole point is operating on
repos it doesn't own -- there's no single "the repo" the way
self-healing-cicd had.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class FailedRun:
    repo: str
    run_id: str
    conclusion: str
    head_branch: str
    url: str
    created_at: str


def list_failed_runs(repo: str, workflow_file: str | None = None, limit: int = 20) -> list[FailedRun]:
    cmd = [
        "gh", "run", "list",
        "--repo", repo,
        "--status", "failure",
        "--limit", str(limit),
        "--json", "databaseId,conclusion,headBranch,url,createdAt",
    ]
    if workflow_file:
        cmd[3:3] = ["--workflow", workflow_file]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    rows = json.loads(result.stdout)
    return [
        FailedRun(
            repo=repo,
            run_id=str(row["databaseId"]),
            conclusion=row["conclusion"],
            head_branch=row["headBranch"],
            url=row["url"],
            created_at=row["createdAt"],
        )
        for row in rows
    ]


def fetch_failed_log(repo: str, run_id: str) -> str:
    result = subprocess.run(
        ["gh", "run", "view", run_id, "--repo", repo, "--log-failed"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def run_status(repo: str, run_id: str) -> tuple[str, str]:
    result = subprocess.run(
        ["gh", "run", "view", run_id, "--repo", repo, "--json", "status,conclusion"],
        capture_output=True, text=True, check=True,
    )
    row = json.loads(result.stdout)
    return row["status"], row.get("conclusion") or ""
