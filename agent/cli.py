"""Command-line entry point.

    python -m agent.cli code run-once --repo OWNER/NAME --tracker-repo OWNER/TRACKER --code-mode preview
    python -m agent.cli infra run-once --tracker-repo OWNER/TRACKER --infra-mode preview
    python -m agent.cli import repos --owner OWNER
    python -m agent.cli import terraform-state [--file PATH]
    python -m agent.cli import ansible-inventory --file PATH
    python -m agent.cli trigger-infra-drift    # destroys the demo container for real
    python -m agent.cli trigger-config-drift   # corrupts the demo container's config for real
"""
from __future__ import annotations

import argparse
import subprocess
import sys

from agent.config import require_gh_cli, load_settings
from agent.remediation.mode import parse_code_mode, parse_infra_mode


def _cmd_code_run_once(args) -> int:
    from agent.orchestrator import run_code_once

    settings = load_settings(code_repo=args.repo)
    mode = parse_code_mode(args.code_mode)
    outcomes = run_code_once(settings, args.tracker_repo, mode)
    if not outcomes:
        print("no new failed runs to process")
        return 0
    for outcome in outcomes:
        print(f"incident {outcome.incident.incident_id}: phase={outcome.incident.phase.value} -- {outcome.detail}")
    return 0


def _cmd_infra_run_once(args) -> int:
    from agent.orchestrator import run_infra_once

    settings = load_settings(terraform_dir=args.terraform_dir, ansible_inventory=args.ansible_inventory, ansible_playbook=args.ansible_playbook)
    mode = parse_infra_mode(args.infra_mode)
    outcome = run_infra_once(settings, args.tracker_repo, mode)
    if outcome is None:
        print("no infra/config drift detected")
        return 0
    print(f"incident {outcome.incident.incident_id}: domain={outcome.incident.domain} phase={outcome.incident.phase.value}")
    print(outcome.detail)
    return 0


def _cmd_import_repos(args) -> int:
    from agent.importer.repos import import_repos

    for repo in import_repos(args.owner):
        print(f"{repo.full_name}\tprivate={repo.is_private}\tarchived={repo.is_archived}\tpushed={repo.pushed_at}")
    return 0


def _cmd_import_terraform_state(args) -> int:
    from agent.importer.terraform_state import import_from_file, import_from_live_state

    resources = import_from_file(args.file) if args.file else import_from_live_state(args.dir)
    for r in resources:
        print(f"{r.address}\t{r.resource_type}\t{r.name}")
    return 0


def _cmd_import_ansible_inventory(args) -> int:
    from agent.importer.ansible_inventory import import_inventory

    for host in import_inventory(args.file):
        print(f"{host.name}\t{host.variables}")
    return 0


def _cmd_trigger_infra_drift(args) -> int:
    subprocess.run(["terraform", "destroy", "-auto-approve", "-no-color"], cwd=args.terraform_dir, check=True)
    print(f"destroyed the demo instance -- {args.terraform_dir} now has real, live Terraform drift")
    return 0


def _cmd_trigger_config_drift(args) -> int:
    subprocess.run(
        ["docker", "exec", args.instance_name, "sh", "-c", "rm -f /etc/aiops-demo/app.conf; deluser appuser 2>/dev/null || true"],
        check=True,
    )
    print(f"removed the config file and user from {args.instance_name} -- now has real, live Ansible drift")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent")
    sub = parser.add_subparsers(dest="command", required=True)

    code = sub.add_parser("code").add_subparsers(dest="code_command", required=True)
    code_run = code.add_parser("run-once")
    code_run.add_argument("--repo", required=True)
    code_run.add_argument("--tracker-repo", required=True)
    code_run.add_argument("--code-mode", default="preview", choices=["preview", "fix"])
    code_run.set_defaults(func=_cmd_code_run_once)

    infra = sub.add_parser("infra").add_subparsers(dest="infra_command", required=True)
    infra_run = infra.add_parser("run-once")
    infra_run.add_argument("--tracker-repo", required=True)
    infra_run.add_argument("--infra-mode", default="preview", choices=["preview", "apply"])
    infra_run.add_argument("--terraform-dir", default="demo_infra/terraform")
    infra_run.add_argument("--ansible-inventory", default="demo_infra/ansible/inventory.yml")
    infra_run.add_argument("--ansible-playbook", default="demo_infra/ansible/configure.yml")
    infra_run.set_defaults(func=_cmd_infra_run_once)

    imp = sub.add_parser("import").add_subparsers(dest="import_command", required=True)
    imp_repos = imp.add_parser("repos")
    imp_repos.add_argument("--owner", required=True)
    imp_repos.set_defaults(func=_cmd_import_repos)

    imp_tf = imp.add_parser("terraform-state")
    imp_tf.add_argument("--dir", default="demo_infra/terraform")
    imp_tf.add_argument("--file", default=None)
    imp_tf.set_defaults(func=_cmd_import_terraform_state)

    imp_ans = imp.add_parser("ansible-inventory")
    imp_ans.add_argument("--file", required=True)
    imp_ans.set_defaults(func=_cmd_import_ansible_inventory)

    trigger_infra = sub.add_parser("trigger-infra-drift")
    trigger_infra.add_argument("--terraform-dir", default="demo_infra/terraform")
    trigger_infra.set_defaults(func=_cmd_trigger_infra_drift)

    trigger_config = sub.add_parser("trigger-config-drift")
    trigger_config.add_argument("--instance-name", default="aiops-demo-instance")
    trigger_config.set_defaults(func=_cmd_trigger_config_drift)

    args = parser.parse_args(argv)
    if args.command == "code":
        require_gh_cli()
    if args.command == "import" and args.import_command == "repos":
        require_gh_cli()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
