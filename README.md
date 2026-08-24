# aiops-remediation-agent

Generalizes [`self-healing-cicd`](https://github.com/vishalrath0d/self-healing-cicd)'s
real Observe → Triage → Remediate → Verify loop two ways: it operates on *any*
consumer repo it's pointed at (not just itself), and it routes a problem to
whichever tool is actually responsible for fixing it — code, Terraform, or
Ansible — instead of only ever knowing how to touch CI/CD.

_(README in progress — full architecture, design rationale, and the real
verified end-to-end run are being written up now. See `docs/next/next.md`.)_
