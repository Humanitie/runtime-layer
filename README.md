# Humaniti AI Runtime Layer™

**Enterprise AI orchestration, governance, and decision intelligence layer.**

An AI runtime that sits above ERP systems (SAP, Oracle, Dynamics, Workday) and safely
orchestrates AI reasoning: it enforces context, validates outputs against retrieved
evidence, classifies risk, and routes anything consequential to a human — with a full
audit trail. It does not replace the ERP. It makes the ERP's data AI-ready.

This repository contains the working backend + frontend codebase scaffold for the
Runtime Layer — the engineering proof behind the pitch, ready to hand to an engineer or
deploy yourself.

> **Note:** a separate stakeholder-ready single-file interactive demo
> (`humaniti_ai_runtime_layer_demo.html`, no install/server required, live Claude API
> calls with automatic fallback to a built-in Demo Simulation engine) was previously
> built alongside this codebase but is not included in this particular archive — it
> needs to be regenerated. See `DEMO_SCRIPT.md` for how it's meant to be used once
> it exists again.

Both implement the same **AI Provider Abstraction**: the runtime layer (context,
retrieval, risk classification, governance, audit) never talks to Claude directly — it
talks to a provider manager that can route to Claude ("Production"), a deterministic
rule-based "Demo Simulation" engine, or (later) another model vendor. See
`ARCHITECTURE.md` for the full design and why it matters for a credible pitch.

---

## 1. Run the standalone demo (2 minutes, once regenerated)

1. Open `humaniti_ai_runtime_layer_demo.html` in Chrome/Edge/Firefox.
2. Go to **Runtime Settings**. Pick an **AI Mode**:
   - **Auto** (recommended) — uses Claude if you add a key below, Demo Simulation otherwise.
   - **Demo Simulation** — no key needed at all; every scenario runs on the built-in
     rule-based engine. Use this if you don't want to risk a live API call in the room.
   - **Production** — always tries Claude; still auto-falls-back to simulation if the
     call fails.
   Paste an Anthropic API key (`sk-ant-...`) if you want live Claude reasoning, pick a
   model, click **Save & Connect**.
3. Go to **Delivery Risk Intelligence** and click **Run Risk Analysis** — this is the
   one scenario to lead with (see `DEMO_SCRIPT.md`). Then try **Finance Decision
   Assistant** and **Knowledge Assistant**.
4. Open **Audit & Governance Log** to show every interaction was recorded, and export
   it as JSON.

Your API key is stored only in that browser's local storage and is sent only to
`api.anthropic.com`. This direct-from-browser pattern is fine for a live demo; it is
explicitly **not** the production pattern — see the warning banner in the demo's
Settings tab and the architecture note below.

## 2. Project layout

```
humaniti-ai-runtime-layer/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, routes
│   │   ├── core/
│   │   │   └── runtime_engine.py   # context engine, RAG pipeline, judgment
│   │   │                            # engine, verification engine, AI
│   │   │                            # provider abstraction, audit log
│   │   └── db/
│   │       └── seed_data.py     # simulated ERP data
│   ├── tests/
│   │   └── test_runtime.py
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       └── index.css
├── docker-compose.yml
├── ARCHITECTURE.md
├── API_DOCS.md
└── DEMO_SCRIPT.md
```

## 3. Run the backend locally

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # then edit .env — set AI_MODE and, optionally, ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

`AI_MODE` controls the reasoning provider (see `ARCHITECTURE.md`): `production` always
tries Claude, `demo` never calls an external API, `auto` (default) uses Claude if a key
is present and falls back to the Enterprise Scenario Engine otherwise — and falls back
automatically on any Claude failure regardless of mode, so the API is never a single
point of failure for a demo.

Run the test suite from `backend/` (no API key required for the core suite — the model
call is mocked so the tests verify Humaniti's own logic, not Anthropic's uptime):

```bash
pytest tests/test_runtime.py -v
```

To also run the one live-integration smoke test right before a demo:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pytest tests/test_runtime.py -v -k live_claude_smoke
```

> **Verification status:** this suite has been run — 16 tests passed, 1 skipped (the
> live-Claude smoke test, which only runs with a real `ANTHROPIC_API_KEY` set), plus a
> manual FastAPI `TestClient` smoke pass across every endpoint including the governance
> approve/reject workflow. Re-run it yourself after cloning to confirm it still holds in
> your environment before relying on it for a live demo.

## 4. Run the frontend locally

```bash
npm install
npm run dev
# then open http://localhost:5173 (requires the backend running on :8000)
```

## 5. Deploy

```bash
export ANTHROPIC_API_KEY=sk-ant-...
docker compose up --build
```

This brings up Postgres with `pgvector` and the backend together. Swap the
keyword-overlap retrieval in `RAGPipeline` (in `backend/app/core/runtime_engine.py`)
for real embeddings against `pgvector` when you move past the prototype stage — the
`retrieve()` method is the one seam designed to be swapped without touching any
calling code.

## 6. How to talk about this with investors

See `DEMO_SCRIPT.md`. Two rules, up front:

- Don't say "Claude built my app." Say: *"I built a functional prototype to validate
  the Runtime Layer workflow — context management, retrieval-grounded reasoning,
  risk classification, and governed escalation — using Claude as a development
  accelerator, not as the product."*
- Show **one** workflow breaking and being caught, not twenty features. The delivery
  risk scenario is the strongest story: a $4M SAP project with a named single point of
  failure, live-reasoned in front of the room.
