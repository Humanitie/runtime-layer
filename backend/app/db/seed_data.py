# =============================================================================
# Humaniti AI Runtime Layer — Simulated ERP Environment (SAP S/4HANA style)
# Intended path in the full project layout: backend/app/db/seed_data.py
#
# This module is the single source of truth for the simulated enterprise
# data used across Finance, Procurement, Project Delivery, HR and Enterprise
# Knowledge. It is imported by:
#   - humaniti_backend_models_db.py   (loads it into SQLite/Postgres)
#   - humaniti_backend_app.py         (serves it via the API)
#   - humaniti_backend_tests.py       (drives the automated test suite)
#   - humaniti_ai_runtime_layer_demo.html (mirrors this data client-side)
#
# Keep the data consistent across all four so the investor demo and the
# backend tell the same story.
# =============================================================================

PROJECTS = [
    {
        "id": "PRJ-1001",
        "name": "SAP S/4HANA Finance Transformation",
        "client": "Meridian Industrial Group",
        "budget": 4_000_000,
        "spent": 2_350_000,
        "timeline_months": 18,
        "pct_complete": 58,
        "phase": "Testing",
        "team": [
            {"role": "Solution Architect", "name": "D. Whitfield", "allocation_pct": 100,
             "note": "Sole owner of core architecture decisions; no documented backup."},
            {"role": "Functional Consultants", "count": 4, "allocation_pct": 95},
            {"role": "Developers", "count": 6, "allocation_pct": 90},
            {"role": "Testing Team", "count": 5, "allocation_pct": 94,
             "note": "Limited slack remaining before test cycle deadline."},
        ],
        "dependencies": [
            "Client sign-off on chart-of-accounts redesign (pending 19 days)",
            "Legacy data migration validation (in progress)",
        ],
        "open_issues": [
            {"id": "ISS-114", "desc": "Architecture decisions undocumented outside solution architect's working notes", "severity": "High"},
            {"id": "ISS-119", "desc": "UAT test cases behind schedule by 9 business days", "severity": "Medium"},
            {"id": "ISS-122", "desc": "Client approval on 3 change requests outstanding >14 days", "severity": "Medium"},
        ],
        "change_requests": [
            {"id": "CR-08", "status": "Awaiting client approval", "age_days": 16},
            {"id": "CR-09", "status": "Awaiting client approval", "age_days": 11},
        ],
    },
    {
        "id": "PRJ-1002",
        "name": "Dynamics 365 Procurement Rollout — Phase 1",
        "client": "Northfield Logistics",
        "budget": 1_200_000,
        "spent": 410_000,
        "timeline_months": 8,
        "pct_complete": 34,
        "phase": "Build",
        "team": [
            {"role": "Solution Architect", "name": "R. Ibarra", "allocation_pct": 60},
            {"role": "Functional Consultants", "count": 2, "allocation_pct": 80},
            {"role": "Developers", "count": 3, "allocation_pct": 75},
        ],
        "dependencies": ["Vendor master data cleanup (client-owned, on track)"],
        "open_issues": [
            {"id": "ISS-201", "desc": "Minor scope clarification on approval matrix", "severity": "Low"},
        ],
        "change_requests": [],
    },
]

INVOICES = [
    {
        "id": "INV-2291",
        "vendor": "ABC Technology Consulting",
        "amount": 500_000,
        "status": "Pending Approval",
        "contract_ref": "CTR-4471",
        "due_date": "2026-08-05",
        "description": "Milestone 3 — Integration testing services",
    },
    {
        "id": "INV-2288",
        "vendor": "Northline Data Services",
        "amount": 42_500,
        "status": "Approved",
        "contract_ref": "CTR-3310",
        "due_date": "2026-07-30",
        "description": "Monthly managed hosting — July",
    },
]

VENDORS = [
    {
        "id": "VEN-201", "name": "ABC Technology Consulting",
        "category": "Systems Integration Services", "risk_rating": "Medium",
        "active_since": "2023-02-01",
        "prior_issues": "1 late delivery (2024), resolved without dispute.",
    },
    {
        "id": "VEN-118", "name": "Northline Data Services",
        "category": "Managed Hosting", "risk_rating": "Low",
        "active_since": "2021-06-15", "prior_issues": "None on record.",
    },
]

CONTRACTS = [
    {
        "id": "CTR-4471", "vendor": "ABC Technology Consulting", "total_value": 1_800_000,
        "milestones_paid": 2, "milestones_total": 5,
        "terms": "Payments require Finance Director sign-off above $250,000 per Procurement Policy v5.2, Section 4.1.",
    },
    {
        "id": "CTR-3310", "vendor": "Northline Data Services", "total_value": 510_000,
        "milestones_paid": 7, "milestones_total": 12,
        "terms": "Standard monthly billing, cost-center approver only, no elevated threshold.",
    },
]

EMPLOYEES = [
    {"id": "EMP-01", "name": "D. Whitfield", "role": "Solution Architect", "utilization_pct": 100,
     "skills": ["SAP FI/CO", "S/4HANA architecture", "Integration design"], "availability": "Fully allocated"},
    {"id": "EMP-02", "name": "R. Ibarra", "role": "Solution Architect", "utilization_pct": 60,
     "skills": ["Dynamics 365", "Procurement processes"], "availability": "40% available"},
    {"id": "EMP-03", "name": "M. Okafor", "role": "Functional Consultant", "utilization_pct": 95,
     "skills": ["SAP FI/CO", "Testing coordination"], "availability": "Fully allocated"},
]

PURCHASE_REQUESTS = [
    {"id": "PR-551", "requestor": "M. Okafor", "item": "Additional UAT environment license", "amount": 18_000, "status": "Pending Procurement Review"},
]

POLICIES = [
    {
        "id": "POL-PROC-5.2", "title": "Procurement Approval Policy", "version": "5.2",
        "last_updated": "2026-03-11", "module": "Finance",
        "body": (
            "Section 4.1: Any single payment or invoice exceeding $250,000 requires written "
            "approval from the Finance Director in addition to the standard cost-center "
            "approver, regardless of prior milestone approvals. "
            "Section 4.2: Payments to vendors with an open dispute in the prior 12 months "
            "require additional Procurement review before release."
        ),
    },
    {
        "id": "SOP-VEND-002", "title": "Vendor Onboarding SOP", "version": "3.0",
        "last_updated": "2025-11-02", "module": "Procurement",
        "body": (
            "Step 1: Requesting department submits a Vendor Intake Form to Procurement. "
            "Step 2: Procurement runs a compliance and financial-risk check (min. 3 business days). "
            "Step 3: Legal reviews and issues a Master Services Agreement. "
            "Step 4: Finance creates the vendor record in the ERP system with a default payment "
            "approval threshold. "
            "Step 5: Vendor is activated only after all four steps are confirmed complete in the "
            "Vendor Governance Log."
        ),
    },
    {
        "id": "POL-DELIVERY-2.1", "title": "Delivery Risk Escalation Policy", "version": "2.1",
        "last_updated": "2025-08-19", "module": "Project Delivery",
        "body": (
            "Any project where a single named individual is the sole approver or sole "
            "knowledge-holder for a critical work stream must be flagged as a Key Person "
            "Dependency risk. Project leadership must name a documented secondary owner "
            "within 14 calendar days of the flag being raised, or escalate to the Delivery "
            "Steering Committee."
        ),
    },
    {
        "id": "POL-CHANGE-1.4", "title": "Change Management Policy", "version": "1.4",
        "last_updated": "2025-05-30", "module": "Project Delivery",
        "body": (
            "Change requests outstanding for more than 10 business days without client "
            "response must be escalated to the Engagement Sponsor. Unresolved change "
            "requests are a leading indicator of schedule slippage and must be reflected "
            "in the weekly delivery risk report."
        ),
    },
    {
        "id": "POL-HR-004", "title": "Resource Overallocation Policy", "version": "1.2",
        "last_updated": "2025-09-14", "module": "HR",
        "body": (
            "Any employee sustained above 90% utilization for more than 3 consecutive "
            "weeks must be flagged to the Resource Manager for rebalancing or backup "
            "staffing review."
        ),
    },
]

# Flat corpus used by the retrieval layer (see runtime_engine.py -> RAGPipeline)
def document_corpus():
    docs = []
    for p in POLICIES:
        docs.append({"id": p["id"], "title": p["title"], "last_updated": p["last_updated"],
                     "text": f"{p['title']} {p['body']}"})
    for c in CONTRACTS:
        docs.append({"id": c["id"], "title": f"Contract {c['id']} — {c['vendor']}",
                     "last_updated": "n/a", "text": f"{c['terms']} {c['vendor']} {c['total_value']}"})
    for v in VENDORS:
        docs.append({"id": v["id"], "title": f"Vendor Record — {v['name']}",
                     "last_updated": v["active_since"],
                     "text": f"{v['name']} {v['risk_rating']} {v['prior_issues']}"})
    for i in INVOICES:
        docs.append({"id": i["id"], "title": f"Invoice {i['id']} — {i['vendor']}",
                     "last_updated": i["due_date"],
                     "text": f"{i['vendor']} {i['amount']} {i['status']} {i['description']}"})
    for pr in PROJECTS:
        docs.append({"id": pr["id"], "title": f"Project — {pr['name']}",
                     "last_updated": "live", "text": _project_text(pr)})
    return docs


def _project_text(p):
    parts = [p["name"], p["client"], str(p["budget"]), p["phase"]]
    for t in p["team"]:
        parts.append(f"{t['role']} {t.get('name','')} {t.get('note','')}")
    parts += p["dependencies"]
    for i in p["open_issues"]:
        parts.append(f"{i['id']} {i['severity']} {i['desc']}")
    for c in p["change_requests"]:
        parts.append(f"{c['id']} {c['status']}")
    return " ".join(parts)
