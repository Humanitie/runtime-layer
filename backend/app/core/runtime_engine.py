# =============================================================================
# Humaniti AI Runtime Layer — Core Engine
# Intended path in the full project layout: backend/app/core/*.py
# (Context Engine, RAG Pipeline, Judgment Engine, Governance/Audit, Claude
#  client are combined into one module here for a readable single-file
#  reference build; splitting them into separate files under app/core/ is a
#  mechanical refactor, not a design change.)
#
# This is the part of the system that answers Part 8 of the build brief:
# "identify and fix existing AI software limitations." Each class below has
# a docstring stating which limitation it addresses and how.
# =============================================================================

from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.db import seed_data as seed

logger = logging.getLogger("humaniti.runtime")
logging.basicConfig(level=logging.INFO)


# -----------------------------------------------------------------------------
# 1. CONTEXT MANAGEMENT ENGINE
#    Limitation addressed: "AI answers without understanding company context /
#    limited memory." We attach organization + role + conversation context to
#    every request instead of relying on the model's implicit memory.
# -----------------------------------------------------------------------------

class Role(str, Enum):
    CFO = "CFO"
    FINANCE_MANAGER = "Finance Manager"
    PROJECT_MANAGER = "Project Manager"
    DELIVERY_LEAD = "Delivery Lead"
    EMPLOYEE = "Employee"
    ADMIN = "Admin"


ROLE_PERMISSIONS = {
    Role.CFO: {"finance": True, "delivery": True, "knowledge": True, "hr": True},
    Role.FINANCE_MANAGER: {"finance": True, "delivery": False, "knowledge": True, "hr": False},
    Role.PROJECT_MANAGER: {"finance": False, "delivery": True, "knowledge": True, "hr": False},
    Role.DELIVERY_LEAD: {"finance": False, "delivery": True, "knowledge": True, "hr": True},
    Role.EMPLOYEE: {"finance": False, "delivery": False, "knowledge": True, "hr": False},
    Role.ADMIN: {"finance": True, "delivery": True, "knowledge": True, "hr": True},
}


@dataclass
class UserContext:
    user_id: str
    display_name: str
    role: Role
    org_name: str = "Meridian Industrial Group (simulated tenant)"

    def can_access(self, domain: str) -> bool:
        return ROLE_PERMISSIONS.get(self.role, {}).get(domain, False)


class ContextEngine:
    """Builds the context block sent with every model call: who is asking,
    what they're allowed to see, and what conversation history is relevant.
    Prevents the classic failure mode where a Project Manager and a CFO get
    identically-scoped answers to the same question."""

    def __init__(self):
        self._conversation_memory: dict[str, list[dict]] = {}

    def remember(self, user_id: str, role: str, content: str):
        self._conversation_memory.setdefault(user_id, []).append(
            {"role": role, "content": content, "ts": datetime.now(timezone.utc).isoformat()}
        )
        # keep only last 20 turns per user — bounded memory, not unbounded context growth
        self._conversation_memory[user_id] = self._conversation_memory[user_id][-20:]

    def history(self, user_id: str) -> list[dict]:
        return self._conversation_memory.get(user_id, [])

    def authorize(self, user: UserContext, domain: str) -> None:
        if not user.can_access(domain):
            raise PermissionError(
                f"User {user.display_name} ({user.role.value}) is not authorized for the "
                f"'{domain}' domain. Access denied by Context Engine before any model call was made."
            )


# -----------------------------------------------------------------------------
# 2. LARGE DOCUMENT / RAG PIPELINE
#    Limitation addressed: "context window limits, can't process large docs."
#    Real deployment: Upload -> Extract -> Chunk -> Embed (pgvector/Chroma) ->
#    Retrieve -> Generate. This reference implementation chunks + retrieves
#    with TF-IDF-style scoring so it runs with zero external dependencies;
#    swap `embed()`/`similarity()` for a real embedding model without
#    touching any calling code — that seam is the point.
# -----------------------------------------------------------------------------

def chunk_text(text: str, max_chars: int = 800, overlap: int = 120) -> list[str]:
    """Splits large documents into overlapping chunks so no single request
    ever exceeds the model's context window, regardless of source doc size."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


_TOKEN_RE = re.compile(r"[a-z0-9$]+")

# Without this, a query as generic as "What is the approval process?" would trivially
# "match" nearly every document via function words like "is"/"the"/"for" alone,
# regardless of topic — the retrieval would never legitimately come back empty, which
# would quietly defeat the whole no-evidence-no-answer guarantee. This is a cheap but
# real precision fix, not just a naming workaround.
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he", "in",
    "is", "it", "its", "of", "on", "that", "the", "to", "was", "were", "will", "with",
    "what", "which", "who", "whom", "this", "these", "those", "i", "we", "you", "your",
    "our", "their", "do", "does", "did", "can", "could", "should", "would", "if", "or",
    "but", "not", "no", "yes", "how", "when", "where", "why", "about", "above", "after",
    "again", "all", "any", "because", "been", "before", "being", "below", "between",
    "both", "during", "each", "few", "further", "have", "having", "here", "into",
    "itself", "just", "more", "most", "only", "other", "over", "own", "same", "so",
    "some", "such", "than", "then", "there", "through", "too", "under", "until", "up",
    "very", "them",
}


def _tokenize(s: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((s or "").lower()) if t not in _STOPWORDS]


class RAGPipeline:
    """Indexes the document corpus and retrieves the top-N most relevant
    chunks for a query, with a real similarity score attached — so the
    reasoning engine (and the audit log) always know exactly which evidence
    it is grounded on."""

    def __init__(self, documents: list[dict] | None = None):
        self.documents = documents if documents is not None else seed.document_corpus()
        self._index = self._build_index()

    def _build_index(self):
        index = []
        for doc in self.documents:
            for chunk in chunk_text(doc["text"]):
                index.append({**doc, "chunk": chunk})
        return index

    def _score(self, query_tokens: set[str], chunk_tokens: list[str]) -> float:
        if not chunk_tokens:
            return 0.0
        overlap = sum(1 for t in chunk_tokens if t in query_tokens)
        # light length-normalization so short, precise matches aren't buried by long chunks
        return overlap / math.sqrt(len(chunk_tokens))

    def retrieve(self, query: str, top_n: int = 4, min_score: float = 0.01) -> list[dict]:
        q_tokens = set(_tokenize(query))
        scored = []
        for entry in self._index:
            score = self._score(q_tokens, _tokenize(entry["chunk"]))
            if score > min_score:
                scored.append({**entry, "score": round(score, 4)})
        scored.sort(key=lambda d: d["score"], reverse=True)
        return scored[:top_n]

    def as_context_block(self, retrieved: list[dict]) -> str:
        if not retrieved:
            return "(no matching documents retrieved — treat as unverified)"
        return "\n\n".join(
            f"[{d['id']}] {d['title']} (last updated: {d['last_updated']}, relevance: {d['score']})\n{d['chunk']}"
            for d in retrieved
        )


# -----------------------------------------------------------------------------
# 3. JUDGMENT ENGINE
#    Limitation addressed: "AI can't distinguish recommendation vs. execution,
#    no governance." Risk classification is a hard rule evaluated in Python —
#    NOT left to the model's discretion — then cross-checked against the
#    model's own self-reported classification. If they disagree, the system
#    always takes the more conservative (higher-risk) of the two.
# -----------------------------------------------------------------------------

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


_RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}

FINANCE_APPROVAL_THRESHOLD = 250_000


class JudgmentEngine:
    """Deterministic, auditable risk classification. This is intentionally
    NOT delegated entirely to the LLM: a $500,000 payment request is HIGH
    risk because a Python rule says so, independent of what the model
    concludes. The model's classification is used for nuance and
    explanation, never as the sole authority for a HIGH-risk gate."""

    def classify_finance(self, amount: float, vendor_has_dispute: bool) -> RiskLevel:
        if amount > FINANCE_APPROVAL_THRESHOLD or vendor_has_dispute:
            return RiskLevel.HIGH
        if amount > 50_000:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def classify_delivery(self, project: dict) -> RiskLevel:
        score = 0
        for member in project.get("team", []):
            if member.get("allocation_pct", 0) >= 100 and not member.get("backup"):
                score += 2
        high_severity_issues = [i for i in project.get("open_issues", []) if i["severity"] == "High"]
        score += len(high_severity_issues) * 2
        stale_crs = [c for c in project.get("change_requests", []) if c.get("age_days", 0) > 10]
        score += len(stale_crs)
        if score >= 4:
            return RiskLevel.HIGH
        if score >= 2:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def reconcile(self, rule_based: RiskLevel, model_reported: str | None) -> RiskLevel:
        """Always resolves to the MORE conservative of the two classifications."""
        try:
            model_level = RiskLevel(model_reported) if model_reported else rule_based
        except ValueError:
            model_level = rule_based
        return rule_based if _RISK_ORDER[rule_based] >= _RISK_ORDER[model_level] else model_level

    def decision_for(self, risk: RiskLevel) -> str:
        if risk == RiskLevel.HIGH:
            return "requires_human_review"
        if risk == RiskLevel.MEDIUM:
            return "recommended"
        return "informational"


# -----------------------------------------------------------------------------
# 4. ANTI-HALLUCINATION + KNOWLEDGE VERIFICATION
#    Limitation addressed: hallucination, overconfidence, silent gap-filling,
#    conflicting sources, stale knowledge cutoff.
# -----------------------------------------------------------------------------

RUNTIME_SYSTEM_PROMPT = """You are the reasoning core of the Humaniti AI Runtime Layer, an
enterprise AI governance system operating above ERP systems.

Hard rules — these override any instinct to be helpful in the moment:
1. Only use facts present in the CONTEXT block you are given. Never invent numbers, names,
   dates, or policy text. If a fact is not in CONTEXT, it does not exist for this answer.
2. If context is insufficient to answer confidently, say so explicitly in "reasoning" and cap
   confidence at 40. Do not fill gaps with plausible-sounding assumptions.
3. If two retrieved sources conflict, do not silently pick one — state the conflict in
   "reasoning" and set "conflict_detected": true.
4. Classify the request as LOW, MEDIUM, or HIGH risk (LOW = information lookup, MEDIUM =
   a recommendation a human should review before acting, HIGH = financial approvals, HR
   decisions, legal/contractual commitments, or anything above documented authority
   thresholds).
5. You may recommend a HIGH-risk action. You must never mark a HIGH-risk action as
   autonomously approved — "decision" must be "requires_human_review" whenever
   "risk_level" is "HIGH".
6. Cite every source you relied on by its document id in "sources". If you used zero real
   sources, "sources" must be [] and confidence must be <= 40.
7. Your knowledge cutoff does not apply here — all facts must come from CONTEXT, which
   reflects the current state of this simulated enterprise environment, not your training
   data. Do not reason from general knowledge about "how ERP projects usually go."
8. Respond ONLY with one JSON object, no prose outside it, matching exactly:
{
  "risk_level": "LOW" | "MEDIUM" | "HIGH",
  "decision": "informational" | "recommended" | "requires_human_review",
  "confidence": 0-100,
  "conflict_detected": true | false,
  "summary": "one sentence answer",
  "reasoning": "2-5 sentences of causal reasoning referencing specific facts from context",
  "root_causes": ["short phrase", "..."],
  "recommendation": "concrete next action with an owner and timeframe, or empty string",
  "sources": ["DOC-ID", "..."]
}"""

NO_EVIDENCE_FALLBACK = {
    "risk_level": "LOW",
    "decision": "informational",
    "confidence": 0,
    "conflict_detected": False,
    "summary": "I do not have enough verified information to answer this.",
    "reasoning": "No relevant documents were retrieved from the enterprise knowledge base for this query.",
    "root_causes": [],
    "recommendation": "Escalate to a subject-matter owner or upload the relevant source document.",
    "sources": [],
}


def extract_json(text: str) -> dict | None:
    match = re.search(r"\{[\s\S]*\}", text or "")
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class VerificationEngine:
    """Runs before AND after the model call. Before: refuses to call the model
    at all if retrieval found nothing (saves a hallucination-prone call
    entirely). After: validates the model's own confidence/sources claims
    against what was actually retrieved, and downgrades confidence if the
    model claims more certainty than the evidence supports."""

    def pre_check(self, retrieved: list[dict]) -> dict | None:
        if not retrieved:
            return dict(NO_EVIDENCE_FALLBACK)
        return None

    def post_check(self, parsed: dict, retrieved_ids: set[str]) -> dict:
        if parsed is None:
            return dict(NO_EVIDENCE_FALLBACK) | {
                "summary": "The model response could not be parsed into the expected schema.",
                "reasoning": "Self-healing note: response failed schema validation and was replaced with a safe fallback rather than shown unverified.",
            }
        cited = set(parsed.get("sources") or [])
        fabricated = cited - retrieved_ids
        if fabricated:
            parsed["conflict_detected"] = True
            parsed["confidence"] = min(parsed.get("confidence", 0), 30)
            parsed["reasoning"] = (
                parsed.get("reasoning", "")
                + f" [Verification Engine flag: cited source(s) {sorted(fabricated)} were not "
                  f"in the retrieved evidence set and have been treated as unverifiable.]"
            )
            parsed["sources"] = sorted(cited & retrieved_ids)
        return parsed


# -----------------------------------------------------------------------------
# 5. CLAUDE CLIENT WRAPPER
#    Limitation addressed: no retry/self-healing, no observability, no
#    timeout handling, silent failures.
# -----------------------------------------------------------------------------

class RuntimeError_(Exception):
    pass


@dataclass
class ClaudeClient:
    api_key: str | None = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY"))
    model: str = "claude-sonnet-5"
    max_retries: int = 2
    timeout_s: float = 30.0

    def call(self, system_prompt: str, user_message: str) -> str:
        if not self.api_key:
            raise RuntimeError_(
                "ANTHROPIC_API_KEY is not configured. Set it as an environment variable or in "
                "your .env file. The runtime refuses to proceed with a stub response — silent "
                "fallback to fake data is exactly the failure mode this system exists to prevent."
            )
        try:
            import anthropic  # type: ignore
        except ImportError as e:
            raise RuntimeError_(
                "The 'anthropic' package is not installed. Run: pip install anthropic"
            ) from e

        client = anthropic.Anthropic(api_key=self.api_key)
        last_error = None
        for attempt in range(1, self.max_retries + 2):
            try:
                resp = client.messages.create(
                    model=self.model,
                    max_tokens=1400,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                    timeout=self.timeout_s,
                )
                return "".join(block.text for block in resp.content if hasattr(block, "text"))
            except Exception as e:  # noqa: BLE001 — deliberately broad: this is the retry boundary
                last_error = e
                logger.warning("Claude call failed (attempt %s/%s): %s", attempt, self.max_retries + 1, e)
                time.sleep(min(2 ** attempt, 8))
        raise RuntimeError_(f"Claude API call failed after {self.max_retries + 1} attempts: {last_error}")


# -----------------------------------------------------------------------------
# 5.5 AI PROVIDER ABSTRACTION
#    Limitation addressed: single-vendor dependency, no graceful degradation
#    when a provider is unreachable/out of credits/misconfigured. The runtime
#    layer (context, retrieval, judgment, governance, audit) is written
#    against this abstraction, not against Claude directly — the model is a
#    pluggable reasoning engine, not the product. Adding OpenAI/Llama/
#    Mistral/a private model later means adding one more Provider class and
#    registering it in AIProviderManager; nothing else in this file changes.
# -----------------------------------------------------------------------------

class ReasoningProvider:
    name = "base-provider"

    def reason(self, *, system_prompt: str, user_message: str) -> str:
        raise NotImplementedError


class ClaudeProvider(ReasoningProvider):
    name = "Claude API"

    def __init__(self, client: ClaudeClient):
        self.client = client

    def reason(self, *, system_prompt: str, user_message: str) -> str:
        return self.client.call(system_prompt, user_message)


class SimulatedProvider(ReasoningProvider):
    """The Demo Mode / fallback reasoning engine. Runs the exact same
    pipeline stages as production (retrieval already happened upstream;
    this class only supplies the reasoning step) using the deterministic
    Judgment Engine plus scripted-but-data-driven scenario logic — it reacts
    to the actual simulated ERP data, it is not a static canned response."""

    name = "Enterprise Scenario Engine"

    def __init__(self, judgment: "JudgmentEngine"):
        self.judgment = judgment

    def reason_structured(self, *, domain: str, query: str, retrieved: list[dict]) -> dict:
        if domain == "delivery":
            return self._delivery()
        if domain == "finance":
            return self._finance(query)
        return self._knowledge(retrieved)

    def _delivery(self) -> dict:
        project = seed.PROJECTS[0]  # PRJ-1001 — the scenario this engine is scripted around
        risk = self.judgment.classify_delivery(project)
        root_causes = []
        architect = next((t for t in project["team"] if t["role"] == "Solution Architect"), None)
        if architect and architect.get("allocation_pct", 0) >= 100 and architect.get("note"):
            root_causes.append(
                f"Solution Architect ({architect['name']}) is a single point of failure — {architect['note'].lower()}"
            )
        for issue in project["open_issues"]:
            if issue["severity"] == "High":
                root_causes.append(f"{issue['id']}: {issue['desc']}")
        stale = [c for c in project["change_requests"] if c.get("age_days", 0) > 10]
        if stale:
            root_causes.append(
                f"{len(stale)} change request(s) outstanding >10 business days ({', '.join(c['id'] for c in stale)})"
            )
        return {
            "risk_level": risk.value,
            "decision": self.judgment.decision_for(risk),
            "confidence": 89,
            "conflict_detected": False,
            "summary": f"Delivery risk for {project['name']} is {risk.value}, driven primarily by an "
                       f"undocumented key-person dependency on the solution architect.",
            "reasoning": "Deterministic scoring across resourcing, open issues, and change-request aging — "
                         "the same Judgment Engine rule the production path uses. The reasoning source changes; "
                         "the governance rule does not.",
            "root_causes": root_causes,
            "recommendation": "Assign a secondary architecture owner within 14 days per POL-DELIVERY-2.1; "
                               "escalate outstanding change requests per POL-CHANGE-1.4.",
            "sources": ["POL-DELIVERY-2.1", "POL-CHANGE-1.4", project["id"]],
        }

    def _finance(self, query: str) -> dict:
        m = re.search(r"\$?([\d,]+(?:\.\d+)?)", query.replace(",", ""))
        amount = float(m.group(1)) if m else None
        vendor = next((v for v in seed.VENDORS if v["name"].lower() in query.lower()), None)
        if amount is None:
            return {
                "risk_level": "LOW", "decision": "informational", "confidence": 20,
                "conflict_detected": False,
                "summary": "I need a payment amount to classify this decision.",
                "reasoning": "No dollar amount could be parsed from the request. Provide an amount "
                             "(e.g. \"$500,000\") so the Judgment Engine can apply the approval-threshold rule.",
                "root_causes": [], "recommendation": "Resubmit with a specific amount and vendor name.",
                "sources": [],
            }
        has_dispute = bool(
            vendor and "dispute" in vendor["prior_issues"].lower() and "resolved" not in vendor["prior_issues"].lower()
        )
        risk = self.judgment.classify_finance(amount, has_dispute)
        contract = next((c for c in seed.CONTRACTS if vendor and c["vendor"] == vendor["name"]), None)
        sources = ["POL-PROC-5.2"] + ([contract["id"]] if contract else []) + ([vendor["id"]] if vendor else [])
        return {
            "risk_level": risk.value,
            "decision": self.judgment.decision_for(risk),
            "confidence": 91,
            "conflict_detected": False,
            "summary": (
                f"This ${amount:,.0f} payment exceeds delegated approval authority and requires Finance "
                f"Director sign-off." if risk.value == "HIGH" else
                f"This ${amount:,.0f} payment is within standard cost-center approval authority."
            ),
            "reasoning": (
                f"Procurement Approval Policy v5.2, Section 4.1 sets a ${FINANCE_APPROVAL_THRESHOLD:,} "
                f"threshold above which Finance Director approval is required regardless of prior milestone "
                f"approvals."
                + (f" Vendor record on file for {vendor['name']}: risk rating {vendor['risk_rating']}, "
                   f"{vendor['prior_issues']}" if vendor else "")
            ),
            "root_causes": ["Payment amount exceeds the delegated authority threshold."] if risk.value == "HIGH" else [],
            "recommendation": "Route to Finance Director for approval before release." if risk.value == "HIGH" else "",
            "sources": sources,
        }

    def _knowledge(self, retrieved: list[dict]) -> dict:
        if not retrieved:
            return dict(NO_EVIDENCE_FALLBACK)
        top = retrieved[0]
        return {
            "risk_level": "LOW", "decision": "informational",
            "confidence": min(95, 60 + int(top.get("score", 0) * 10)),
            "conflict_detected": False,
            "summary": f"{top['title']} (last updated {top['last_updated']}) answers this directly.",
            "reasoning": top["chunk"],
            "root_causes": [], "recommendation": "", "sources": [d["id"] for d in retrieved],
        }


class AIProviderManager:
    """Owns provider selection, automatic fallback, and the low-confidence
    escalation guardrail. Modes:
      - "production": always attempt Claude; falls back to the Enterprise
        Scenario Engine only if the call itself fails.
      - "demo": never calls an external API — always the Scenario Engine.
        Zero API credits, zero network dependency, zero unpredictable model
        behavior. Built for stakeholder demos.
      - "auto" (default): behaves like "production" if an API key is
        configured, otherwise behaves like "demo"."""

    def __init__(self, claude_client: ClaudeClient, judgment: JudgmentEngine,
                 verifier: VerificationEngine, health: HealthMonitor, mode: str | None = None):
        self.claude_provider = ClaudeProvider(claude_client)
        self.simulated_provider = SimulatedProvider(judgment)
        self.verifier = verifier
        self.health = health
        self.mode = (mode or os.environ.get("AI_MODE", "auto")).lower()

    def _wants_production(self) -> bool:
        if self.mode == "demo":
            return False
        if self.mode == "production":
            return True
        return bool(self.claude_provider.client.api_key)  # auto

    def _confidence_gate(self, response: dict) -> dict:
        """Low-confidence answers must not be silently treated as pure
        information lookups — force human review even when the risk
        classification alone wouldn't have triggered one."""
        if response.get("confidence", 100) < 40 and response.get("decision") == "informational":
            response["decision"] = "requires_human_review"
            response["low_confidence_escalation"] = True
        return response

    def reason(self, *, domain: str, query: str, retrieved: list[dict], retrieved_ids: set[str],
               system_prompt: str, user_message: str) -> dict:
        wants_prod = self._wants_production()
        if wants_prod:
            try:
                raw = self.claude_provider.reason(system_prompt=system_prompt, user_message=user_message)
                parsed = extract_json(raw)
                checked = self.verifier.post_check(parsed, retrieved_ids)
                checked["ai_mode"] = "production"
                checked["reasoning_source"] = self.claude_provider.name
                return self._confidence_gate(checked)
            except RuntimeError_ as e:
                self.health.log_error(
                    "ai_provider_manager", e,
                    "Falling back to the Enterprise Scenario Engine. Verify ANTHROPIC_API_KEY and "
                    "network access to api.anthropic.com to resume live reasoning."
                )
            except Exception as e:  # noqa: BLE001 — a provider failure must never crash the runtime
                self.health.log_error(
                    "ai_provider_manager", e,
                    "Unexpected provider error; falling back to the Enterprise Scenario Engine."
                )
        result = self.simulated_provider.reason_structured(domain=domain, query=query, retrieved=retrieved)
        result["ai_mode"] = "demo" if not wants_prod else "demo-fallback"
        result["reasoning_source"] = self.simulated_provider.name + ("" if not wants_prod else " (auto-fallback)")
        return self._confidence_gate(result)


# -----------------------------------------------------------------------------
# 6. GOVERNANCE + AUDIT LOG
#    Limitation addressed: "no audit trail, no accountability for who
#    approved what." Every runtime interaction is appended here, and human
#    decisions are recorded against the same record.
# -----------------------------------------------------------------------------

@dataclass
class AuditRecord:
    id: str
    timestamp: str
    user_id: str
    role: str
    module: str
    query: str
    sources_used: list[str]
    risk_level: str
    decision: str
    confidence: int
    ai_response: dict
    human_decision: str | None = None
    human_by: str | None = None
    human_reason: str | None = None
    human_ts: str | None = None


class AuditLog:
    def __init__(self):
        self._records: dict[str, AuditRecord] = {}
        self._seq = 0

    def record(self, *, user: UserContext, module: str, query: str,
               retrieved: list[dict], ai_response: dict) -> AuditRecord:
        self._seq += 1
        rec = AuditRecord(
            id=f"AUD-{self._seq:05d}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user.user_id,
            role=user.role.value,
            module=module,
            query=query,
            sources_used=[d["id"] for d in retrieved],
            risk_level=ai_response.get("risk_level", "LOW"),
            decision=ai_response.get("decision", "informational"),
            confidence=ai_response.get("confidence", 0),
            ai_response=ai_response,
        )
        self._records[rec.id] = rec
        return rec

    def apply_human_decision(self, audit_id: str, decision: str, by: str, reason: str = ""):
        rec = self._records.get(audit_id)
        if not rec:
            raise KeyError(f"No audit record {audit_id}")
        if rec.decision != "requires_human_review":
            raise ValueError(f"Audit record {audit_id} did not require human review.")
        rec.human_decision = decision
        rec.human_by = by
        rec.human_reason = reason
        rec.human_ts = datetime.now(timezone.utc).isoformat()
        return rec

    def all(self) -> list[AuditRecord]:
        return list(self._records.values())

    def pending(self) -> list[AuditRecord]:
        return [r for r in self._records.values() if r.decision == "requires_human_review" and not r.human_decision]


# -----------------------------------------------------------------------------
# 7. SELF-MONITORING / HEALTH
#    Limitation addressed: silent failures, no bug self-resolution signal.
# -----------------------------------------------------------------------------

class HealthMonitor:
    def __init__(self, claude_client: ClaudeClient, rag: RAGPipeline):
        self.claude_client = claude_client
        self.rag = rag
        self.error_log: list[dict] = []

    def log_error(self, source: str, error: Exception, suggested_fix: str):
        self.error_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "error": str(error),
            "suggested_fix": suggested_fix,
        })
        logger.error("[%s] %s -- suggested fix: %s", source, error, suggested_fix)

    def status(self) -> dict:
        return {
            "claude_api_configured": bool(self.claude_client.api_key),
            "document_store_size": len(self.rag.documents),
            "recent_errors": self.error_log[-10:],
            "health_score": max(0, 100 - 5 * len(self.error_log[-20:])),
        }


# -----------------------------------------------------------------------------
# 8. RUNTIME ORCHESTRATOR
#    Wires the pieces above into the pipeline described in the architecture
#    diagram: Intake -> Classification -> Context -> Retrieval -> Reasoning ->
#    Judgment -> Governance -> Audit.
# -----------------------------------------------------------------------------

class HumanitiRuntime:
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-5", ai_mode: str | None = None):
        self.context_engine = ContextEngine()
        self.rag = RAGPipeline()
        self.judgment = JudgmentEngine()
        self.verifier = VerificationEngine()
        self.claude = ClaudeClient(api_key=api_key, model=model)
        self.audit = AuditLog()
        self.health = HealthMonitor(self.claude, self.rag)
        # AI_MODE env var (or the ai_mode kwarg) selects production / demo / auto.
        # See AIProviderManager for what each mode does.
        self.provider_manager = AIProviderManager(self.claude, self.judgment, self.verifier, self.health, mode=ai_mode)

    def handle_request(self, *, user: UserContext, domain: str, query: str,
                        extra_facts: str = "", rule_risk: RiskLevel | None = None) -> dict:
        # 1. Intake + authorization (Context Engine)
        self.context_engine.authorize(user, domain)
        self.context_engine.remember(user.user_id, "user", query)

        # 2. Retrieval (RAG Pipeline)
        retrieved = self.rag.retrieve(query)
        retrieved_ids = {d["id"] for d in retrieved}

        # 3. Pre-check (Verification Engine) — refuse to call any provider with zero evidence
        fallback = self.verifier.pre_check(retrieved)
        if fallback is not None and not extra_facts:
            ai_response = fallback
            ai_response.setdefault("ai_mode", "n/a")
            ai_response.setdefault("reasoning_source", "Verification Engine (no evidence — no provider called)")
        else:
            # 4. Reasoning — delegated to the AI Provider Manager, which owns
            #    provider selection, automatic fallback, and never lets a
            #    provider failure propagate as a crash.
            context_block = self.rag.as_context_block(retrieved)
            if extra_facts:
                context_block = f"{extra_facts}\n\n{context_block}"
            user_message = f"CONTEXT:\n{context_block}\n\nREQUEST:\n{query}"
            ai_response = self.provider_manager.reason(
                domain=domain, query=query, retrieved=retrieved, retrieved_ids=retrieved_ids,
                system_prompt=RUNTIME_SYSTEM_PROMPT, user_message=user_message,
            )

        # 5. Judgment Engine reconciliation (deterministic rule wins ties)
        if rule_risk is not None:
            final_risk = self.judgment.reconcile(rule_risk, ai_response.get("risk_level"))
            ai_response["risk_level"] = final_risk.value
            ai_response["decision"] = self.judgment.decision_for(final_risk)

        # human_action_required is always recomputed last so it reflects the
        # final decision after both the confidence gate and rule-risk
        # reconciliation have had a chance to change it.
        ai_response["human_action_required"] = ai_response.get("decision") == "requires_human_review"

        # 6. Governance + Audit
        record = self.audit.record(user=user, module=domain, query=query,
                                    retrieved=retrieved, ai_response=ai_response)
        ai_response["audit_id"] = record.id
        self.context_engine.remember(user.user_id, "assistant", ai_response.get("summary", ""))
        return ai_response
