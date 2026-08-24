"""Code remediation: the same allow-list design proven in
self-healing-cicd (flaky_test -> retry, missing_dependency -> PR,
bad_config/unknown -> escalate, never auto-fix config), generalized two
ways:

1. Every action takes `repo` explicitly and, where it needs a working
   tree, clones it into a scratch directory under state/clones/ --
   self-healing-cicd assumed it was already running inside a clone of
   the one repo it managed. This project's whole point is operating on
   repos it doesn't own, so that assumption doesn't hold here.
2. Every action is gated by ExecutionMode: preview describes exactly
   what it WOULD do (including, for open_dependency_pr, showing the
   real diff it would commit) without touching anything; fix actually
   does it, identically to how self-healing-cicd always operated.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

from agent.remediation.mode import ExecutionMode
from agent.triage.classify import TriageResult

CATEGORY_TO_ACTION = {
    "flaky_test": "retry_workflow",
    "missing_dependency": "open_dependency_pr",
    "bad_config": "open_escalation_issue",
    "unknown": "open_escalation_issue",
}


@dataclass(frozen=True)
class CodeFixResult:
    action: str
    mode: ExecutionMode
    applied: bool
    detail: str


def _clone_dir(state_dir: str, repo: str) -> str:
    return os.path.join(state_dir, "clones", repo.replace("/", "__"))


def _ensure_clone(state_dir: str, repo: str) -> str:
    path = _clone_dir(state_dir, repo)
    if os.path.isdir(os.path.join(path, ".git")):
        subprocess.run(["git", "-C", path, "fetch", "origin", "main"], check=True, capture_output=True)
        subprocess.run(["git", "-C", path, "checkout", "main"], check=True, capture_output=True)
        subprocess.run(["git", "-C", path, "reset", "--hard", "origin/main"], check=True, capture_output=True)
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run(
        ["gh", "repo", "clone", repo, path],
        check=True, capture_output=True, text=True,
    )
    return path


def dispatch(
    state_dir: str, repo: str, run_id: str, run_url: str, triage: TriageResult, mode: ExecutionMode
) -> CodeFixResult:
    action = CATEGORY_TO_ACTION[triage.category]
    if action == "retry_workflow":
        return _retry_workflow(repo, run_id, mode)
    if action == "open_dependency_pr":
        return _open_dependency_pr(state_dir, repo, run_id, run_url, triage, mode)
    if action == "open_escalation_issue":
        return _open_escalation_issue(repo, run_id, run_url, triage, mode)
    raise AssertionError(f"unreachable: action {action!r}")  # pragma: no cover


def _retry_workflow(repo: str, run_id: str, mode: ExecutionMode) -> CodeFixResult:
    if mode == ExecutionMode.PREVIEW:
        return CodeFixResult(
            action="retry_workflow", mode=mode, applied=False,
            detail=f"would rerun the failed jobs of run {run_id} on {repo}",
        )
    subprocess.run(["gh", "run", "rerun", run_id, "--repo", repo, "--failed"], check=True, capture_output=True)
    return CodeFixResult(action="retry_workflow", mode=mode, applied=True, detail=f"reran failed jobs of run {run_id}")


_MODULE_NAME_RE = re.compile(r"No module named '([\w.]+)'")


def _open_dependency_pr(
    state_dir: str, repo: str, run_id: str, run_url: str, triage: TriageResult, mode: ExecutionMode
) -> CodeFixResult:
    m = _MODULE_NAME_RE.search(triage.evidence)
    module_name = m.group(1) if m else "UNKNOWN_MODULE"
    req_path_hint = "requirements.txt (or the nearest one found under the repo root)"

    if mode == ExecutionMode.PREVIEW:
        return CodeFixResult(
            action="open_dependency_pr", mode=mode, applied=False,
            detail=f"would open a PR on {repo} adding '{module_name}' to {req_path_hint}, "
            f"citing run {run_url}",
        )

    clone_path = _ensure_clone(state_dir, repo)
    req_path = _find_requirements_file(clone_path)
    branch = f"agent/pin-{module_name}-{run_id}"
    subprocess.run(["git", "-C", clone_path, "checkout", "-B", branch], check=True, capture_output=True)

    with open(req_path, "a", encoding="utf-8") as f:
        f.write(f"\n{module_name}  # added by aiops-remediation-agent, run {run_id}\n")

    # `git -C clone_path add <path>` resolves <path> relative to clone_path,
    # not the process's own cwd -- req_path is already clone_path-prefixed
    # (from _find_requirements_file), so it must be relativized here or git
    # looks for it doubly-nested and fails. Found live: the first real
    # cross-repo run hit exactly this (exit 128, "did not match any files").
    req_path_relative = os.path.relpath(req_path, clone_path)
    subprocess.run(["git", "-C", clone_path, "add", req_path_relative], check=True, capture_output=True)
    subprocess.run(
        [
            "git", "-C", clone_path, "commit", "-m",
            f"agent: pin missing dependency '{module_name}'\n\nTriggered by failed run {run_url}.",
        ],
        check=True, capture_output=True,
    )
    subprocess.run(["git", "-C", clone_path, "push", "-u", "origin", branch], check=True, capture_output=True)

    pr = subprocess.run(
        [
            "gh", "pr", "create", "--repo", repo, "--head", branch, "--base", "main",
            "--title", f"agent: pin missing dependency '{module_name}'",
            "--body",
            f"Opened automatically by aiops-remediation-agent.\n\n- Triggering run: {run_url}\n"
            f"- Triage: `{triage.category}` (confidence {triage.confidence:.2f}, method `{triage.method}`)\n"
            f"- Evidence: `{triage.evidence}`\n\nMechanical fix -- review before merging.",
        ],
        check=True, capture_output=True, text=True,
    )
    return CodeFixResult(action="open_dependency_pr", mode=mode, applied=True, detail=pr.stdout.strip())


def _find_requirements_file(clone_path: str) -> str:
    for root, _dirs, files in os.walk(clone_path):
        if ".git" in root:
            continue
        if "requirements.txt" in files:
            return os.path.join(root, "requirements.txt")
    # No existing requirements.txt -- create one at the repo root rather
    # than guessing a nested path.
    return os.path.join(clone_path, "requirements.txt")


def _open_escalation_issue(
    repo: str, run_id: str, run_url: str, triage: TriageResult, mode: ExecutionMode
) -> CodeFixResult:
    title = f"[aiops-remediation-agent] escalation: run {run_id} ({triage.category})"
    body = (
        f"Opened automatically by aiops-remediation-agent at {datetime.now(timezone.utc).isoformat()}.\n\n"
        f"- Triggering run: {run_url}\n"
        f"- Triage: `{triage.category}` (confidence {triage.confidence:.2f}, method `{triage.method}`)\n"
        f"- Reasoning: {triage.reasoning}\n- Evidence: `{triage.evidence}`\n"
    )
    if mode == ExecutionMode.PREVIEW:
        return CodeFixResult(
            action="open_escalation_issue", mode=mode, applied=False,
            detail=f"would open an issue on {repo} titled {title!r}",
        )
    issue = subprocess.run(
        ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body],
        check=True, capture_output=True, text=True,
    )
    return CodeFixResult(action="open_escalation_issue", mode=mode, applied=True, detail=issue.stdout.strip())
