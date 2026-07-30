# =============================================================================
# Humaniti AI Runtime Layer — Automated Test Suite
# Intended path in the full project layout: backend/tests/test_runtime.py
#
# Run:
#   pip install -r requirements.txt  (run from backend/)
#   pytest tests/test_runtime.py -v  (run from backend/)
#
# These tests do NOT call the real Anthropic API (no key required, no network,
# no flakiness in CI). ClaudeClient.call is monkeypatched with a stub that
# returns scripted model outputs, so what's actually under test is the
# runtime's own logic: retrieval, judgment reconciliation, verification,
# governance gating, and security — the parts Humaniti is responsible for,
# independent of what any specific LLM says on a given day.
#
# A separate live-integration test (test_live_claude_smoke, skipped unless
# ANTHROPIC_API_KEY is set) exercises the real API for a sanity check before
# a demo.
# =============================================================================

import json
import os

import pytest

from app.db import seed_data as seed
from app.core.runtime_engine import (
    HumanitiRuntime, UserContext, Role, RiskLevel, RAGPipeline, chunk_text,
    VerificationEngine, JudgmentEngine, NO_EVIDENCE_FALLBACK,
)


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def runtime():
    return HumanitiRuntime(api_key="test-key-not-real")


@pytest.fixture
def cfo():
    return UserContext(user_id="u1", display_name="Farah", role=Role.CFO)


@pytest.fixture
def employee():
    return UserContext(user_id="u2", display_name="Junior Employee", role=Role.EMPLOYEE)


def stub_claude(monkeypatch, runtime, response_dict):
    """Replaces the network call with a scripted JSON response."""
    monkeypatch.setattr(runtime.claude, "call", lambda system, user: json.dumps(response_dict))


def stub_claude_raises(monkeypatch, runtime, exc):
    def _raise(system, user):
        raise exc
    monkeypatch.setattr(runtime.claude, "call", _raise)


# -----------------------------------------------------------------------------
# TEST 1 — Hallucination prevention
# "Approve this payment" with no supporting evidence must never be
# auto-approved, and a HIGH risk classification must always route to a human.
# -----------------------------------------------------------------------------

def test_hallucination_prevention_high_risk_never_auto_approved(monkeypatch, runtime, cfo):
    # Model (mis)behaves and claims it can approve — the rule-based Judgment
    # Engine must override it because the amount exceeds the threshold.
    stub_claude(monkeypatch, runtime, {
        "risk_level": "LOW", "decision": "informational", "confidence": 95,
        "conflict_detected": False, "summary": "Approved.",
        "reasoning": "Looks fine.", "root_causes": [], "recommendation": "",
        "sources": ["POL-PROC-5.2"],
    })
    result = runtime.handle_request(
        user=cfo, domain="finance",
        query="Can we approve this $500,000 vendor payment to ABC Technology Consulting?",
        rule_risk=RiskLevel.HIGH,
    )
    assert result["risk_level"] == "HIGH"
    assert result["decision"] == "requires_human_review", (
        "A HIGH-risk finance decision must never be auto-approved, even if the "
        "model itself reports LOW risk. This is the core governance guarantee."
    )


def test_hallucination_prevention_no_fabricated_sources_survive_verification(monkeypatch, runtime, cfo):
    # Model cites a document id that was never retrieved — Verification
    # Engine must strip it and downgrade confidence.
    stub_claude(monkeypatch, runtime, {
        "risk_level": "MEDIUM", "decision": "recommended", "confidence": 90,
        "conflict_detected": False, "summary": "Some answer.",
        "reasoning": "Because reasons.", "root_causes": [], "recommendation": "",
        "sources": ["DOC-DOES-NOT-EXIST"],
    })
    result = runtime.handle_request(user=cfo, domain="finance", query="What is the payment threshold?")
    assert "DOC-DOES-NOT-EXIST" not in result["sources"]
    assert result["confidence"] <= 30
    assert result["conflict_detected"] is True


# -----------------------------------------------------------------------------
# TEST 2 — Missing information
# A question with zero retrievable evidence must trigger the "I don't know"
# fallback rather than a fabricated answer, and must never call the model.
# -----------------------------------------------------------------------------

def test_missing_information_triggers_fallback_without_calling_model(monkeypatch, runtime, cfo):
    called = {"count": 0}

    def _spy(system, user):
        called["count"] += 1
        return "{}"

    monkeypatch.setattr(runtime.claude, "call", _spy)
    # Deliberately shares zero vocabulary with the seed corpus (contrast with a query
    # like "...policy on Antarctica contracts", which would trivially retrieve a
    # policy document via the word "policy" alone — a known limitation of the
    # keyword-overlap retrieval used in this reference build; see RAGPipeline docstring).
    result = runtime.handle_request(
        user=cfo, domain="knowledge",
        query="What are the office rules for bringing pets to the Denver headquarters?",
    )
    assert called["count"] == 0, "No matching evidence should short-circuit before any model call."
    assert result["confidence"] == 0
    assert "do not have enough verified information" in result["summary"].lower()


# -----------------------------------------------------------------------------
# TEST 3 — Large document retrieval
# A long synthetic document must be chunked and the correct chunk retrieved
# for a query targeting content buried deep in the document.
# -----------------------------------------------------------------------------

def test_large_document_chunking_and_retrieval():
    filler = "General onboarding background information. " * 400  # ~18,000 chars of noise
    needle = "The emergency vendor suspension code is OMEGA-7-STRIKE."
    long_doc_text = filler[:9000] + " " + needle + " " + filler[9000:]

    docs = [{"id": "DOC-BIG", "title": "1000-page ERP Manual (simulated)", "last_updated": "2026-01-01", "text": long_doc_text}]
    rag = RAGPipeline(documents=docs)

    chunks = chunk_text(long_doc_text)
    assert len(chunks) > 1, "A large document must be split into multiple chunks."

    hits = rag.retrieve("What is the emergency vendor suspension code?", top_n=3)
    assert any("OMEGA-7-STRIKE" in h["chunk"] for h in hits), (
        "Retrieval must surface the chunk containing the answer even though it is "
        "buried in the middle of a large document, without exceeding a single chunk's size."
    )


# -----------------------------------------------------------------------------
# TEST 4 — Conflicting information
# Two documents that disagree must be flagged, not silently resolved.
# -----------------------------------------------------------------------------

def test_conflicting_information_detected(monkeypatch, runtime, cfo):
    stub_claude(monkeypatch, runtime, {
        "risk_level": "MEDIUM", "decision": "recommended", "confidence": 55,
        "conflict_detected": True, "summary": "Sources disagree on the approval threshold.",
        "reasoning": "POL-PROC-5.2 states $250,000 while a legacy note suggests $500,000; flagging for human review.",
        "root_causes": ["Policy version conflict"], "recommendation": "Confirm current policy version with Procurement.",
        "sources": ["POL-PROC-5.2"],
    })
    result = runtime.handle_request(user=cfo, domain="finance", query="What is the approval threshold?")
    assert result["conflict_detected"] is True


# -----------------------------------------------------------------------------
# TEST 5 — Security / unauthorized access
# An Employee-role user must be denied access to the Finance domain before
# any model call is made.
# -----------------------------------------------------------------------------

def test_unauthorized_role_denied_finance_access(monkeypatch, runtime, employee):
    called = {"count": 0}
    monkeypatch.setattr(runtime.claude, "call", lambda s, u: (called.__setitem__("count", called["count"] + 1), "{}")[1])

    with pytest.raises(PermissionError):
        runtime.handle_request(user=employee, domain="finance", query="Approve this payment.")
    assert called["count"] == 0, "Authorization must be checked before any model call, not after."


def test_cfo_has_finance_access(cfo):
    assert cfo.can_access("finance") is True


def test_employee_has_no_finance_access(employee):
    assert employee.can_access("finance") is False


# -----------------------------------------------------------------------------
# TEST 6 — Judgment Engine reconciliation is conservative
# -----------------------------------------------------------------------------

def test_judgment_reconciliation_takes_higher_risk():
    j = JudgmentEngine()
    assert j.reconcile(RiskLevel.HIGH, "LOW") == RiskLevel.HIGH
    assert j.reconcile(RiskLevel.LOW, "HIGH") == RiskLevel.HIGH
    assert j.reconcile(RiskLevel.MEDIUM, "LOW") == RiskLevel.MEDIUM


# -----------------------------------------------------------------------------
# TEST 7 — Self-healing on malformed model output
# -----------------------------------------------------------------------------

def test_malformed_model_output_falls_back_safely(monkeypatch, runtime, cfo):
    monkeypatch.setattr(runtime.claude, "call", lambda s, u: "not valid json at all")
    result = runtime.handle_request(user=cfo, domain="knowledge", query="What is our vendor onboarding process?")
    assert result["confidence"] == 0
    assert "could not be parsed" in result["summary"].lower()


# -----------------------------------------------------------------------------
# TEST 8 — Health monitor records provider failures with a suggested fix
# -----------------------------------------------------------------------------

def test_health_monitor_logs_claude_failures(monkeypatch, runtime, cfo):
    from app.core.runtime_engine import RuntimeError_
    stub_claude_raises(monkeypatch, runtime, RuntimeError_("simulated network failure"))
    runtime.handle_request(user=cfo, domain="knowledge", query="What is our vendor onboarding process?")
    status = runtime.health.status()
    assert status["recent_errors"], "A provider failure must be captured by the health monitor."
    assert "suggested_fix" in status["recent_errors"][-1]


# -----------------------------------------------------------------------------
# TEST 9 — AI Provider Abstraction & fallback mode
# The runtime must never crash when Claude is unavailable: it detects the
# failure, logs it, and continues the same governed pipeline on the
# Enterprise Scenario Engine instead.
# -----------------------------------------------------------------------------

def test_api_unavailable_triggers_fallback(monkeypatch, runtime, cfo):
    """API unavailable (network failure, timeout, etc.) -> fallback activated,
    the request still completes, and the failure is logged."""
    from app.core.runtime_engine import RuntimeError_
    stub_claude_raises(monkeypatch, runtime, RuntimeError_("simulated network outage"))
    result = runtime.handle_request(
        user=cfo, domain="delivery",
        query="Assess delivery risk for the SAP program.",
        rule_risk=RiskLevel.HIGH,
    )
    assert result["ai_mode"] == "demo-fallback"
    assert "Enterprise Scenario Engine" in result["reasoning_source"]
    assert result["decision"] == "requires_human_review", "Fallback must not bypass governance gating."
    assert result["confidence"] > 0, "Fallback must return a real, usable answer, not a blank one."
    assert runtime.health.status()["recent_errors"], "The outage must be logged, not swallowed silently."


def test_invalid_or_missing_api_key_graceful_failure(cfo):
    """Invalid/missing API key -> graceful failure, not a crash, not an
    unhandled exception bubbling up to the caller."""
    runtime = HumanitiRuntime(api_key=None, ai_mode="production")  # force an attempt despite no key
    result = runtime.handle_request(user=cfo, domain="knowledge", query="What is our vendor onboarding process?")
    assert result["ai_mode"] == "demo-fallback"
    assert result["confidence"] > 0
    errors = runtime.health.status()["recent_errors"]
    assert errors and "ANTHROPIC_API_KEY" in errors[-1]["error"]


def test_demo_mode_never_calls_external_provider(monkeypatch, cfo):
    """AI_MODE=demo must never attempt a network call, even with a valid key
    configured — useful for demos with zero API credits / no connectivity."""
    runtime = HumanitiRuntime(api_key="test-key-not-real", ai_mode="demo")
    called = {"count": 0}
    monkeypatch.setattr(runtime.claude, "call", lambda s, u: (called.__setitem__("count", called["count"] + 1), "{}")[1])
    result = runtime.handle_request(user=cfo, domain="delivery", query="Assess delivery risk.")
    assert called["count"] == 0
    assert result["ai_mode"] == "demo"
    assert result["reasoning_source"] == "Enterprise Scenario Engine"


def test_low_confidence_response_triggers_human_escalation(monkeypatch, runtime, cfo):
    """Low confidence -> human escalation, even when the model itself
    classified the request as a plain informational lookup."""
    stub_claude(monkeypatch, runtime, {
        "risk_level": "LOW", "decision": "informational", "confidence": 25,
        "conflict_detected": False, "summary": "Uncertain answer.",
        "reasoning": "Evidence is thin and doesn't fully answer the question.",
        "root_causes": [], "recommendation": "", "sources": ["POL-PROC-5.2"],
    })
    result = runtime.handle_request(user=cfo, domain="finance", query="What is the payment threshold?")
    assert result["decision"] == "requires_human_review"
    assert result.get("low_confidence_escalation") is True
    assert result["human_action_required"] is True


def test_no_enterprise_data_requests_additional_context(monkeypatch, runtime, cfo):
    """No enterprise data available -> the system asks for more context
    instead of guessing, and this holds even in demo mode."""
    runtime.provider_manager.mode = "demo"
    result = runtime.handle_request(
        user=cfo, domain="finance",
        query="Should we approve this payment?",  # no amount, no vendor — nothing to reason over
    )
    assert result["confidence"] < 40
    assert "amount" in result["reasoning"].lower() or "resubmit" in result["recommendation"].lower()


# -----------------------------------------------------------------------------
# LIVE SMOKE TEST — only runs if you export ANTHROPIC_API_KEY, for a final
# sanity check right before a stakeholder demo. Skipped in normal CI.
# -----------------------------------------------------------------------------

@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
def test_live_claude_smoke(cfo):
    runtime = HumanitiRuntime(api_key=os.environ["ANTHROPIC_API_KEY"])
    result = runtime.handle_request(
        user=cfo, domain="finance",
        query="Can we approve this $500,000 vendor payment to ABC Technology Consulting?",
        rule_risk=RiskLevel.HIGH,
    )
    assert result["decision"] == "requires_human_review"
    assert result["confidence"] >= 0
