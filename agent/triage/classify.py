"""CI-failure triage -- the same two-stage design proven in
self-healing-cicd (regex fast-pass, LLM escalation only for genuinely
ambiguous cases, "unknown" is a valid and expected answer), reused as-is
here since it's the same underlying problem (classify a CI log) just
called from a project that also handles two other domains.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from agent.config import Settings

ALLOWED_CATEGORIES = ("flaky_test", "missing_dependency", "bad_config", "unknown")
FAST_CONFIDENCE_THRESHOLD = 0.8


@dataclass(frozen=True)
class TriageResult:
    category: str
    confidence: float
    reasoning: str
    evidence: str
    method: str

    def __post_init__(self) -> None:
        if self.category not in ALLOWED_CATEGORIES:
            raise ValueError(f"category {self.category!r} not in {ALLOWED_CATEGORIES}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence {self.confidence!r} out of [0, 1]")


_MISSING_DEP_RE = re.compile(r"ModuleNotFoundError: No module named '([\w.]+)'")
_BAD_CONFIG_RE = re.compile(
    r"RuntimeError:.*\b(not set|is not set|missing required|required.*(?:env|config|secret))\b",
    re.IGNORECASE,
)
_FLAKY_STRONG_RE = re.compile(r"intermittent -- passes most runs", re.IGNORECASE)
_ASSERTION_RE = re.compile(r"AssertionError")


def fast_classify(log_text: str) -> TriageResult | None:
    m = _MISSING_DEP_RE.search(log_text)
    if m:
        return TriageResult(
            category="missing_dependency", confidence=0.95,
            reasoning=f"log contains a real ModuleNotFoundError for '{m.group(1)}'",
            evidence=m.group(0), method="fast",
        )
    m = _BAD_CONFIG_RE.search(log_text)
    if m:
        return TriageResult(
            category="bad_config", confidence=0.9,
            reasoning="log contains a RuntimeError describing missing/blank required configuration",
            evidence=m.group(0), method="fast",
        )
    strong = _FLAKY_STRONG_RE.search(log_text)
    if strong:
        return TriageResult(
            category="flaky_test", confidence=0.95,
            reasoning="assertion failure carries its own 'intermittent' evidence string",
            evidence=strong.group(0), method="fast",
        )
    m = _ASSERTION_RE.search(log_text)
    if m:
        return TriageResult(
            category="flaky_test", confidence=0.4,
            reasoning="bare AssertionError with no flaky-specific evidence -- ambiguous",
            evidence=m.group(0), method="fast",
        )
    return None


_TRIAGE_PROMPT = """You are triaging a CI/CD pipeline failure log for a self-healing \
automation agent. Read the log excerpt below and classify it into EXACTLY ONE of \
these categories: flaky_test, missing_dependency, bad_config, unknown.

Respond with ONLY a JSON object: {{"category": "...", "confidence": 0.0-1.0, \
"reasoning": "...", "evidence": "the exact log line(s) that justify this"}}

"unknown" is correct and expected when the log doesn't clearly fit -- do not force a \
fit. A low-confidence guess is worse than an honest "unknown", because this triage \
feeds an automation system that takes real actions based on your answer.

Log excerpt:
---
{log_excerpt}
---
"""
_MAX_LOG_CHARS_FOR_LLM = 4000


def llm_classify(log_text: str, settings: Settings) -> TriageResult:
    if not settings.llm_providers:
        return TriageResult(
            category="unknown", confidence=0.0,
            reasoning="no LLM provider configured -- escalating rather than guessing",
            evidence="", method="no-provider",
        )
    excerpt = log_text[-_MAX_LOG_CHARS_FOR_LLM:]
    prompt = _TRIAGE_PROMPT.format(log_excerpt=excerpt)

    last_error: Exception | None = None
    for provider in settings.llm_providers:
        try:
            raw = _call_provider(provider, prompt)
            parsed = _parse_llm_json(raw)
            return TriageResult(
                category=parsed["category"], confidence=float(parsed["confidence"]),
                reasoning=parsed["reasoning"], evidence=parsed.get("evidence", ""), method="llm",
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    return TriageResult(
        category="unknown", confidence=0.0,
        reasoning=f"all configured LLM providers failed ({last_error}) -- escalating",
        evidence="", method="no-provider",
    )


def _parse_llm_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[len("json"):]
    parsed = json.loads(text.strip())
    if parsed.get("category") not in ALLOWED_CATEGORIES:
        raise ValueError(f"model returned an out-of-allow-list category: {parsed!r}")
    return parsed


def _call_provider(provider: str, prompt: str) -> str:
    if provider == "anthropic":
        return _call_anthropic(prompt)
    if provider == "openai":
        return _call_openai(prompt)
    if provider == "gemini":
        return _call_gemini(prompt)
    raise ValueError(f"unknown provider {provider!r}")


def _call_anthropic(prompt: str) -> str:
    body = json.dumps({
        "model": "claude-3-5-haiku-latest", "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"]


def _call_openai(prompt: str) -> str:
    body = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body,
        headers={"content-type": "application/json", "authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def _call_gemini(prompt: str) -> str:
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    api_key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"]


def classify(log_text: str, settings: Settings) -> TriageResult:
    fast = fast_classify(log_text)
    if fast is not None and fast.confidence >= FAST_CONFIDENCE_THRESHOLD:
        return fast
    try:
        return llm_classify(log_text, settings)
    except urllib.error.URLError as exc:
        return TriageResult(
            category="unknown", confidence=0.0,
            reasoning=f"LLM call failed at the network layer ({exc}) -- escalating",
            evidence="", method="no-provider",
        )
