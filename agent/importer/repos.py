"""Repo import: real, live, via the GitHub API -- catalog every repo an
owner (user or org) has, as the starting inventory of what this agent
could potentially watch. Doesn't itself add anything to a watch list --
that's a real follow-up (this project scopes "discover what exists," not
"auto-enroll everything discovered")."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class RepoSummary:
    name: str
    full_name: str
    is_private: bool
    is_archived: bool
    pushed_at: str
    default_branch: str


def import_repos(owner: str, limit: int = 200) -> list[RepoSummary]:
    result = subprocess.run(
        [
            "gh", "repo", "list", owner, "--limit", str(limit),
            "--json", "name,nameWithOwner,isPrivate,isArchived,pushedAt,defaultBranchRef",
        ],
        capture_output=True, text=True, check=True,
    )
    rows = json.loads(result.stdout)
    return [
        RepoSummary(
            name=row["name"],
            full_name=row["nameWithOwner"],
            is_private=row["isPrivate"],
            is_archived=row["isArchived"],
            pushed_at=row["pushedAt"],
            default_branch=(row.get("defaultBranchRef") or {}).get("name", "main"),
        )
        for row in rows
    ]
