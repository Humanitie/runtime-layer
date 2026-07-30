# Investor / Stakeholder Demo Script — Humaniti AI Runtime Layer™

**Target length: 3 minutes of narrative + 5 minutes of live demo + Q&A.**
**Rule: show one workflow breaking and being caught. Not twenty features.**

---

## How to introduce this (do / don't)

**Don't say:** "Claude built my app."
**Do say:** "I built a functional prototype to validate the Runtime Layer workflow —
context management, evidence-grounded reasoning, risk classification, and governed
escalation — using Claude as a development accelerator. Claude is not the product;
the diagnostic framework, the governance rules, and the audit model are."

---

## The 3-minute story

**Problem (30 seconds)**

"System integration firms lose margin and scalability because delivery bottlenecks
are invisible until projects are already delayed. And now, as every enterprise tries
to adopt AI, they're hitting a second problem: they can't trust it. AI hallucinates,
it doesn't know their internal policies, and there's no governance trail when it's
wrong."

**Solution (30 seconds)**

"Humaniti is an AI Runtime Layer — not another ERP AI assistant. It sits above SAP,
Oracle, Dynamics, whatever the enterprise already runs, and it governs how AI reasons
over that operational data: grounding every answer in retrieved evidence, classifying
risk, and routing anything consequential to a human, with a full audit trail."

**Outcome (30 seconds)**

"The result is predictable delivery, protected margin, and — critically — an AI
deployment enterprises can actually trust in front of their own governance and
compliance teams."

**Live demo (remaining time)** — walk through the single scenario below.

---

## The one scenario to lead with: Delivery Risk Intelligence

1. Open the demo, go to **Executive Dashboard**. Point at the KPI row for two
   seconds — "here's the operational picture across a live SAP program" — then move on.
   Don't linger on the dashboard; it's supporting evidence, not the story.
2. Open **Delivery Risk Intelligence**. Say: *"This is a real $4M SAP S/4HANA program.
   Existing tools — Jira, Power BI, ServiceNow — would show you the same status field
   they've shown you the whole project: 58% complete, testing phase."*
3. Click **Run Risk Analysis**. Narrate the pipeline strip as it lights up: intake,
   classification, context, retrieval, reasoning, judgment, governance, audit —
   *"every step here is a control point, not a black box."*
4. When the result renders, read the **root causes** out loud, not the risk badge:
   architect single point of failure, undocumented decisions, stale change requests.
   *"This is the diagnosis existing tools can't give you — not that it's late, but why,
   with the evidence attached."*
5. Point at **Sources** — *"every claim is tied to a document. If it can't cite one, it
   says so instead of guessing."*
6. If the recommendation triggers a human-review gate, click through **Approve /
   Modify / Reject** — *"and this decision, whichever way it goes, is permanently
   attached to this record."*
7. Close on **Audit & Governance Log** — *"this is what a compliance officer or a
   board asks for six months from now, and it already exists."*

**If time allows,** show the Finance Decision Assistant only to make one point: ask
it to approve the $500,000 payment, and show that it refuses and routes to a human —
*"the system is structurally incapable of auto-approving a high-risk financial
decision, regardless of what the model itself concludes."*

---

## Anticipated objections

**"How is this different from Jira, Power BI, Monday, or ServiceNow?"**
"Those tools show activity. Delivery Intelligence interprets operational signals to
identify why delivery is at risk and what decision a leader needs to make — with
evidence, not just a red status dot."

**"How do you get the data?"**
"The MVP uses structured inputs and integrations against a simulated ERP environment
built to mirror SAP S/4HANA's data model. The long-term vision connects project
management, ERP, resource planning, and delivery systems directly."

**"Is this just ChatGPT / Claude with a UI?"**
"No. The model is one component. The differentiated value is the diagnostic
framework, the operational data model, the deterministic risk-classification rules
that don't depend on any one model's judgment, and the governance and audit layer
around it — all of which exist independent of which LLM is doing the reasoning
underneath."

**"What stops it from hallucinating?"**
"Three things, stacked: it refuses to answer at all when no evidence is retrieved; it
strips any source the model cites that wasn't actually retrieved; and every answer
ships with a confidence score and a reasoning trace tied to specific document IDs. You
just watched all three happen live."

**"Is this production-ready?"**
"This is a validated prototype, not production infrastructure — and that's an honest,
appropriate stage for where the business is. The backend, database schema, test
suite, and Docker deployment in the accompanying codebase are the engineering path
from here to a pilot deployment."

**"What happens if Claude is down or you run out of API credits mid-pitch?"**
"Watch — I can force it." Switch **Runtime Settings → AI Mode** to Demo Simulation and
re-run the scenario. *"The runtime layer doesn't depend on any one model vendor. It has
an AI Provider Manager underneath — Claude is one interchangeable reasoning engine
behind it, not the product. If the API fails for any reason, it automatically falls
back to a rule-based simulation engine and tells you it did so, instead of crashing or
guessing."* This is a strength to demonstrate on purpose, not just a fallback to hope
you never need.

---

## Before you present: pre-flight checklist

- [ ] Decide your AI Mode going in: **Auto** with a tested key (live reasoning, safest
      default), or **Demo Simulation** if you'd rather not risk a live API call in front
      of investors at all — both tell a credible story, see the objection above
- [ ] If using Auto/Production: Anthropic API key entered in Runtime Settings, tested
      once beforehand, and confirm the "Claude API" status pill shows Connected
- [ ] Stable internet connection if relying on live Claude reasoning (the demo calls
      `api.anthropic.com` directly) — though note the automatic fallback means a dropped
      connection no longer stalls the demo, it just switches reasoning source
- [ ] Run the Delivery Risk scenario once before the meeting so you know roughly what
      it will say — live reasoning will vary slightly each run; Demo Simulation is
      deterministic and will say the same thing every time if you want zero surprises
- [ ] Have a screenshot/export of the audit log as a backup visual regardless of mode
- [ ] `pytest humaniti_backend_tests.py -v` run locally at least once, so you can say
      "the anti-hallucination, fallback, and security behavior is unit-tested" and mean it
