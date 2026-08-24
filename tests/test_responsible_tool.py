from agent.observer.infra_drift import DriftFinding
from agent.triage.responsible_tool import route_infra_incident

_TF = DriftFinding(layer="terraform", summary="1 to add", detail="...")
_ANS = DriftFinding(layer="ansible", summary="1 task would change", detail="...")


def test_no_findings_routes_nowhere():
    assert route_infra_incident(None, None) is None


def test_terraform_only():
    assert route_infra_incident(_TF, None) == "terraform"


def test_ansible_only():
    assert route_infra_incident(None, _ANS) == "ansible"


def test_terraform_wins_when_both_present():
    """A missing/wrong-shaped resource makes any config-drift finding on
    top of it meaningless -- Terraform must be fixed first."""
    assert route_infra_incident(_TF, _ANS) == "terraform"
