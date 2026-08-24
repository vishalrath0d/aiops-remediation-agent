import pytest

from agent.comms.incident import Incident, Phase


def _new():
    return Incident(incident_id="abc123", domain="code", target="owner/repo", summary="test")


def test_starts_detected_with_history():
    inc = _new()
    assert inc.phase == Phase.DETECTED
    assert len(inc.history) == 1


def test_valid_transition_chain():
    inc = _new()
    inc.transition(Phase.DIAGNOSING, "x")
    inc.transition(Phase.FIX_PROPOSED, "x")
    inc.transition(Phase.APPLIED, "x")
    inc.transition(Phase.VERIFIED, "x")
    inc.transition(Phase.RESOLVED, "x")
    assert inc.phase == Phase.RESOLVED
    assert len(inc.history) == 6


def test_can_escalate_from_any_non_terminal_phase():
    for start in (Phase.DETECTED, Phase.DIAGNOSING, Phase.FIX_PROPOSED, Phase.APPLIED, Phase.VERIFIED):
        inc = _new()
        inc.phase = start
        inc.transition(Phase.ESCALATED, "x")
        assert inc.phase == Phase.ESCALATED


def test_illegal_transition_raises():
    inc = _new()
    with pytest.raises(ValueError):
        inc.transition(Phase.RESOLVED, "skipping everything")


def test_terminal_phases_accept_no_further_transitions():
    inc = _new()
    inc.transition(Phase.ESCALATED, "x")
    with pytest.raises(ValueError):
        inc.transition(Phase.DIAGNOSING, "x")
