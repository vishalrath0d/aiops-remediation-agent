"""aiops-remediation-agent: generalizes self-healing-cicd's real
Observe -> Triage -> Remediate -> Verify loop to (a) operate on any
consumer repo it's pointed at, not just itself, and (b) route a failure
to whichever tool is actually responsible for it -- code, Terraform, or
Ansible -- rather than only ever knowing how to touch CI/CD.

See the root README for the full architecture, what's live-verified
(a real cross-repo code fix against self-healing-cicd, a real Terraform
apply and a real Ansible run against a local Docker stand-in for cloud
infra) and what's real-but-unverified (Slack/Jira/PagerDuty -- no test
workspace available in the environment this was built in).
"""
