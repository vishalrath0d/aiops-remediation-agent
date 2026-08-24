"""Runtime configuration. Same philosophy as self-healing-cicd's
config.py (env vars + sane defaults, no framework) plus the integration
gates: every one of Slack/Jira/PagerDuty is OFF unless its own env vars
are fully present, and a missing/misconfigured one must never block the
core remediation flow -- the exact "never let a downstream integration
outage break the actual work" rule gitlab-access-bot's jira_client.py
was built around, generalized here to three integrations instead of one.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field

from agent.remediation.mode import ExecutionMode


class ToolNotAvailable(RuntimeError):
    pass


def require_cli(name: str, install_hint: str) -> None:
    if shutil.which(name) is None:
        raise ToolNotAvailable(f"`{name}` is not installed or not on PATH -- {install_hint}")


def require_gh_cli() -> None:
    require_cli("gh", "install from https://cli.github.com/")
    result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ToolNotAvailable(f"`gh auth status` failed -- run `gh auth login` first.\n{result.stderr.strip()}")


@dataclass(frozen=True)
class SlackConfig:
    bot_token: str | None = field(default_factory=lambda: os.environ.get("SLACK_BOT_TOKEN"))
    channel_id: str | None = field(default_factory=lambda: os.environ.get("SLACK_CHANNEL_ID"))

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.channel_id)


@dataclass(frozen=True)
class JiraConfig:
    url: str | None = field(default_factory=lambda: os.environ.get("JIRA_URL", "").rstrip("/") or None)
    email: str | None = field(default_factory=lambda: os.environ.get("JIRA_EMAIL"))
    api_token: str | None = field(default_factory=lambda: os.environ.get("JIRA_API_TOKEN"))
    project_key: str = field(default_factory=lambda: os.environ.get("JIRA_PROJECT_KEY", "OPS"))
    issue_type: str = field(default_factory=lambda: os.environ.get("JIRA_ISSUE_TYPE", "Task"))

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.email and self.api_token)


@dataclass(frozen=True)
class PagerDutyConfig:
    routing_key: str | None = field(default_factory=lambda: os.environ.get("PAGERDUTY_ROUTING_KEY"))

    @property
    def enabled(self) -> bool:
        return bool(self.routing_key)


@dataclass(frozen=True)
class Settings:
    code_repo: str | None = None
    """owner/name of the consumer repo the code-fix path operates on --
    NOT this project's own repo. See observer/github_ci.py."""

    terraform_dir: str = "demo_infra/terraform"
    ansible_inventory: str = "demo_infra/ansible/inventory.yml"
    ansible_playbook: str = "demo_infra/ansible/configure.yml"

    default_code_mode: ExecutionMode = ExecutionMode.PREVIEW
    default_infra_mode: ExecutionMode = ExecutionMode.PREVIEW

    state_dir: str = "state"
    poll_interval_seconds: int = 10
    verify_timeout_seconds: int = 300

    llm_providers: tuple[str, ...] = field(default_factory=lambda: _configured_llm_providers())

    slack: SlackConfig = field(default_factory=SlackConfig)
    jira: JiraConfig = field(default_factory=JiraConfig)
    pagerduty: PagerDutyConfig = field(default_factory=PagerDutyConfig)


def _configured_llm_providers() -> tuple[str, ...]:
    order = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        order.append("anthropic")
    if os.environ.get("OPENAI_API_KEY"):
        order.append("openai")
    if os.environ.get("GEMINI_API_KEY"):
        order.append("gemini")
    return tuple(order)


def load_settings(**overrides) -> Settings:
    return Settings(**overrides)
