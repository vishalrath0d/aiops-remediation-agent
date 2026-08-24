from agent.config import Settings
from agent.triage.classify import FAST_CONFIDENCE_THRESHOLD, classify, fast_classify


def test_fast_classify_missing_dependency(fixture_log):
    result = fast_classify(fixture_log("missing_dependency"))
    assert result.category == "missing_dependency"
    assert result.confidence >= FAST_CONFIDENCE_THRESHOLD


def test_fast_classify_bad_config(fixture_log):
    result = fast_classify(fixture_log("bad_config"))
    assert result.category == "bad_config"


def test_fast_classify_flaky_strong(fixture_log):
    result = fast_classify(fixture_log("flaky_test_strong"))
    assert result.category == "flaky_test"
    assert result.confidence >= FAST_CONFIDENCE_THRESHOLD


def test_ambiguous_assertion_is_low_confidence(fixture_log):
    result = fast_classify(fixture_log("ambiguous_assertion"))
    assert result.confidence < FAST_CONFIDENCE_THRESHOLD


def test_truly_unknown_no_match(fixture_log):
    assert fast_classify(fixture_log("truly_unknown")) is None


def test_classify_escalates_ambiguous_with_no_provider(fixture_log):
    settings = Settings()
    result = classify(fixture_log("ambiguous_assertion"), settings)
    assert result.category == "unknown"
    assert result.method == "no-provider"
