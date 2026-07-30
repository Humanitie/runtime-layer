# =============================================================================
# Humaniti AI Runtime Layer — FastAPI Application
# Intended path in the full project layout: backend/app/main.py
# (routes below would normally be split into app/api/routes_*.py; kept in one
#  file here so the reference build is easy to read top-to-bottom)
#
# Run locally:
#   pip install -r requirements.txt  (run from backend/)
#   cp .env.example .env   # then edit .env (AI_MODE, ANTHROPIC_API_KEY)
#   uvicorn app.main:app --reload --port 8000   (run from backend/)
#
# Docs then at http://localhost:8000/docs (FastAPI auto-generated OpenAPI UI)
# =============================================================================

from __future__ import annotations

from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()  # reads AI_MODE / ANTHROPIC_API_KEY / DATABASE_URL from .env if present

from app.db import seed_data as seed
from app.core.runtime_engine import (
    HumanitiRuntime, UserContext, Role, RiskLevel, FINANCE_APPROVAL_THRESHOLD,
)

app = FastAPI(
    title="Humaniti AI Runtime Layer",
    description="Enterprise AI orchestration, governance, and decision intelligence layer.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only — restrict to known origins in production
    allow_methods=["*"],
    allow_headers=["*"],
)

runtime = HumanitiRuntime()  # single shared runtime instance for this demo process


# -----------------------------------------------------------------------------
# Auth simulation — a real deployment resolves this from SSO/JWT. For the
# demo, the caller sends X-User-Id / X-User-Role headers so the security
# test suite (see tests/test_runtime.py) can exercise the Context
# Engine's authorization gate deterministically.
# -----------------------------------------------------------------------------

def get_current_user(
    x_user_id: str = Header(default="demo-user"),
    x_user_role: str = Header(default="Employee"),
    x_user_name: str = Header(default="Demo User"),
) -> UserContext:
    try:
        role = Role(x_user_role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown role '{x_user_role}'.")
    return UserContext(user_id=x_user_id, display_name=x_user_name, role=role)


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------

class DeliveryRiskRequest(BaseModel):
    project_id: str = Field(default="PRJ-1001")
    question: str = Field(default="Assess overall delivery risk and recommend mitigations.")


class FinanceDecisionRequest(BaseModel):
    question: str


class KnowledgeRequest(BaseModel):
    question: str


class HumanDecisionRequest(BaseModel):
    audit_id: str
    decision: Literal["Approved", "Rejected", "Modified"]
    by: str
    reason: str = ""


# -----------------------------------------------------------------------------
# Use Case 1 — Delivery Risk Intelligence
# -----------------------------------------------------------------------------

@app.post("/api/delivery/analyze")
def analyze_delivery(req: DeliveryRiskRequest, user: UserContext = Depends(get_current_user)):
    project = next((p for p in seed.PROJECTS if p["id"] == req.project_id), None)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Unknown project_id {req.project_id}")

    rule_risk = runtime.judgment.classify_delivery(project)
    extra_facts = (
        f"PROJECT {project['id']} — {project['name']}\n"
        f"Client: {project['client']} | Budget: ${project['budget']:,} | Spent: ${project['spent']:,} | "
        f"{project['pct_complete']}% complete | Phase: {project['phase']}\n"
        f"Team: {project['team']}\n"
        f"Dependencies: {project['dependencies']}\n"
        f"Open Issues: {project['open_issues']}\n"
        f"Change Requests: {project['change_requests']}"
    )
    try:
        result = runtime.handle_request(
            user=user, domain="delivery", query=req.question,
            extra_facts=extra_facts, rule_risk=rule_risk,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return result


# -----------------------------------------------------------------------------
# Use Case 2 — Finance Decision Assistant
# -----------------------------------------------------------------------------

@app.post("/api/finance/decide")
def finance_decide(req: FinanceDecisionRequest, user: UserContext = Depends(get_current_user)):
    amount = _extract_amount(req.question)
    vendor_name = _extract_vendor(req.question)
    vendor = next((v for v in seed.VENDORS if v["name"].lower() in req.question.lower()), None)
    vendor_has_dispute = bool(vendor and "dispute" in vendor.get("prior_issues", "").lower() and "resolved" not in vendor.get("prior_issues", "").lower())

    rule_risk = runtime.judgment.classify_finance(amount or 0, vendor_has_dispute)
    try:
        result = runtime.handle_request(
            user=user, domain="finance", query=req.question, rule_risk=rule_risk,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    result["_rule_engine_threshold"] = FINANCE_APPROVAL_THRESHOLD
    result["_rule_engine_amount_detected"] = amount
    return result


def _extract_amount(text: str) -> float | None:
    import re
    m = re.search(r"\$?([\d,]+(?:\.\d+)?)(?:\s*k)?", text.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _extract_vendor(text: str) -> str | None:
    for v in seed.VENDORS:
        if v["name"].lower() in text.lower():
            return v["name"]
    return None


# -----------------------------------------------------------------------------
# Use Case 3 — Enterprise Knowledge Assistant
# -----------------------------------------------------------------------------

@app.post("/api/knowledge/ask")
def knowledge_ask(req: KnowledgeRequest, user: UserContext = Depends(get_current_user)):
    try:
        result = runtime.handle_request(user=user, domain="knowledge", query=req.question)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return result


# -----------------------------------------------------------------------------
# Governance — human-in-the-loop decisions
# -----------------------------------------------------------------------------

@app.post("/api/governance/decide")
def governance_decide(req: HumanDecisionRequest):
    try:
        rec = runtime.audit.apply_human_decision(req.audit_id, req.decision, req.by, req.reason)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return rec


@app.get("/api/governance/pending")
def governance_pending():
    return runtime.audit.pending()


# -----------------------------------------------------------------------------
# Audit
# -----------------------------------------------------------------------------

@app.get("/api/audit")
def audit_log():
    return runtime.audit.all()


# -----------------------------------------------------------------------------
# Executive Dashboard
# -----------------------------------------------------------------------------

@app.get("/api/dashboard")
def dashboard():
    records = runtime.audit.all()
    return {
        "health": runtime.health.status(),
        "ai_mode": runtime.provider_manager.mode,
        "pending_decisions": len(runtime.audit.pending()),
        "escalations": len([r for r in records if r.risk_level == "HIGH"]),
        "total_interactions": len(records),
        "projects_at_risk": [
            {"id": p["id"], "name": p["name"], "risk": runtime.judgment.classify_delivery(p).value}
            for p in seed.PROJECTS
        ],
        "bottleneck_categories": [
            "Executive / Architect Dependency",
            "Approval Threshold Exposure",
            "Resource Utilization",
        ],
    }


@app.get("/api/health")
def health():
    status = runtime.health.status()
    status["ai_mode_configured"] = runtime.provider_manager.mode
    status["ai_mode_effective"] = "production" if runtime.provider_manager._wants_production() else "demo"
    return status


@app.get("/")
def root():
    return {
        "product": "Humaniti AI Runtime Layer",
        "tagline": "Enterprise AI orchestration, governance, and decision intelligence layer.",
        "docs": "/docs",
    }
