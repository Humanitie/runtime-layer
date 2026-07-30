// Intended path: frontend/src/App.jsx
// Production React scaffold that mirrors humaniti_ai_runtime_layer_demo.html,
// but calls the real FastAPI backend (humaniti_backend_app.py) instead of
// calling Claude directly from the browser — this is the pattern the
// "Runtime Settings" tab in the standalone demo tells you to graduate to.
//
// Setup (once files are placed per the paths noted in each header comment):
//   npm install
//   npm run dev
// Requires the backend running at http://localhost:8000 (see humaniti_backend_app.py).

import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function callApi(path, body, user) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": user.id,
      "X-User-Role": user.role,
      "X-User-Name": user.name,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

const NAV = [
  { key: "dashboard", label: "Executive Dashboard" },
  { key: "delivery", label: "Delivery Risk Intelligence" },
  { key: "finance", label: "Finance Decision Assistant" },
  { key: "knowledge", label: "Knowledge Assistant" },
  { key: "audit", label: "Audit & Governance Log" },
];

function Badge({ risk }) {
  const cls =
    risk === "HIGH" ? "bg-red-500/10 text-red-400" :
    risk === "MEDIUM" ? "bg-amber-500/10 text-amber-400" :
    "bg-emerald-500/10 text-emerald-400";
  return <span className={`px-2 py-0.5 rounded text-xs font-bold ${cls}`}>{risk} RISK</span>;
}

function ResultCard({ result }) {
  if (!result) return null;
  return (
    <div className="border border-zinc-800 bg-zinc-900 rounded-xl p-5 mt-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <Badge risk={result.risk_level} />
          <span className="text-sm text-zinc-400">{(result.decision || "").replace("_", " ")}</span>
        </div>
        <span className="text-xs text-zinc-500">Confidence {result.confidence}%</span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded overflow-hidden mb-3">
        <div className="h-full bg-lime-400" style={{ width: `${result.confidence}%` }} />
      </div>
      <p className="text-sm font-medium mb-3">{result.summary}</p>
      <p className="text-xs uppercase tracking-wide text-zinc-500 mb-1">Reasoning</p>
      <p className="text-sm text-zinc-300 whitespace-pre-wrap mb-3">{result.reasoning}</p>
      {result.root_causes?.length > 0 && (
        <>
          <p className="text-xs uppercase tracking-wide text-zinc-500 mb-1">Root Causes</p>
          <ul className="list-disc list-inside text-sm text-zinc-300 mb-3">
            {result.root_causes.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </>
      )}
      {result.recommendation && (
        <>
          <p className="text-xs uppercase tracking-wide text-zinc-500 mb-1">Recommendation</p>
          <p className="text-sm text-zinc-300 mb-3">{result.recommendation}</p>
        </>
      )}
      <p className="text-xs uppercase tracking-wide text-zinc-500 mb-1">Sources</p>
      <div className="flex flex-wrap gap-1">
        {(result.sources || []).length > 0
          ? result.sources.map((s) => (
              <span key={s} className="font-mono text-xs bg-zinc-950 border border-zinc-800 rounded px-2 py-0.5 text-zinc-400">{s}</span>
            ))
          : <span className="text-xs text-zinc-500">No verified sources — treat as low-confidence.</span>}
      </div>
      {result.audit_id && <p className="text-[11px] text-zinc-600 mt-3">Logged as {result.audit_id}</p>}
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("dashboard");
  const [user] = useState({ id: "demo-user", role: "CFO", name: "Farah" });
  const [deliveryResult, setDeliveryResult] = useState(null);
  const [financeQuestion, setFinanceQuestion] = useState(
    "Can we approve this $500,000 vendor payment to ABC Technology Consulting?"
  );
  const [financeResult, setFinanceResult] = useState(null);
  const [knowledgeQuestion, setKnowledgeQuestion] = useState("What is the process for onboarding a new vendor?");
  const [knowledgeResult, setKnowledgeResult] = useState(null);
  const [audit, setAudit] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(null);

  async function runDelivery() {
    setLoading("delivery"); setError(null);
    try {
      const r = await callApi("/api/delivery/analyze", { project_id: "PRJ-1001" }, user);
      setDeliveryResult(r);
    } catch (e) { setError(e.message); } finally { setLoading(null); }
  }

  async function runFinance() {
    setLoading("finance"); setError(null);
    try {
      const r = await callApi("/api/finance/decide", { question: financeQuestion }, user);
      setFinanceResult(r);
    } catch (e) { setError(e.message); } finally { setLoading(null); }
  }

  async function runKnowledge() {
    setLoading("knowledge"); setError(null);
    try {
      const r = await callApi("/api/knowledge/ask", { question: knowledgeQuestion }, user);
      setKnowledgeResult(r);
    } catch (e) { setError(e.message); } finally { setLoading(null); }
  }

  async function loadAudit() {
    setLoading("audit"); setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/audit`);
      setAudit(await res.json());
    } catch (e) { setError(e.message); } finally { setLoading(null); }
  }

  function goTo(key) {
    setView(key);
    if (key === "audit") loadAudit();
  }

  return (
    <div className="min-h-screen bg-black text-zinc-100 flex font-sans">
      <aside className="w-60 border-r border-zinc-900 p-5 shrink-0">
        <div className="mb-8">
          <div className="text-2xl font-black tracking-wide text-lime-400">HUMANITI</div>
          <div className="text-[11px] text-zinc-500 mt-1">AI Runtime Layer™</div>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map((n) => (
            <button
              key={n.key}
              onClick={() => goTo(n.key)}
              className={`text-left text-sm px-3 py-2 rounded-lg ${
                view === n.key ? "bg-lime-400/10 text-lime-400 border border-lime-400/30" : "text-zinc-400 hover:bg-zinc-900"
              }`}
            >
              {n.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="flex-1 p-8 max-w-4xl">
        {error && (
          <div className="mb-4 border border-red-900/50 bg-red-950/30 text-red-400 text-sm rounded-lg p-3">
            Runtime error: {error}. Confirm the backend is running at {API_BASE} and ANTHROPIC_API_KEY is set server-side.
          </div>
        )}

        {view === "dashboard" && (
          <div>
            <h1 className="text-3xl font-black mb-1">Executive Dashboard</h1>
            <p className="text-zinc-500 text-sm mb-6">Operational intelligence above your ERP transactions.</p>
            <div className="grid grid-cols-3 gap-3">
              {["delivery", "finance", "knowledge"].map((k) => (
                <button key={k} onClick={() => goTo(k)} className="border border-zinc-800 bg-zinc-900 rounded-xl p-4 text-left hover:border-lime-400/40">
                  <div className="text-sm font-semibold capitalize">{k} scenario</div>
                  <div className="text-xs text-zinc-500 mt-1">Open →</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {view === "delivery" && (
          <div>
            <h1 className="text-3xl font-black mb-1">Delivery Risk Intelligence</h1>
            <p className="text-zinc-500 text-sm mb-6">SAP S/4HANA Finance Transformation — PRJ-1001</p>
            <button onClick={runDelivery} disabled={loading === "delivery"} className="bg-lime-400 text-black font-bold text-sm px-4 py-2.5 rounded-lg disabled:opacity-50">
              {loading === "delivery" ? "Running…" : "Run Risk Analysis"}
            </button>
            <ResultCard result={deliveryResult} />
          </div>
        )}

        {view === "finance" && (
          <div>
            <h1 className="text-3xl font-black mb-1">Finance Decision Assistant</h1>
            <p className="text-zinc-500 text-sm mb-6">Never auto-approves. Retrieves evidence, classifies risk, routes to a human when required.</p>
            <textarea
              value={financeQuestion}
              onChange={(e) => setFinanceQuestion(e.target.value)}
              rows={2}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-sm mb-3"
            />
            <button onClick={runFinance} disabled={loading === "finance"} className="bg-lime-400 text-black font-bold text-sm px-4 py-2.5 rounded-lg disabled:opacity-50">
              {loading === "finance" ? "Analyzing…" : "Analyze Decision"}
            </button>
            <ResultCard result={financeResult} />
          </div>
        )}

        {view === "knowledge" && (
          <div>
            <h1 className="text-3xl font-black mb-1">Enterprise Knowledge Assistant</h1>
            <p className="text-zinc-500 text-sm mb-6">Grounded only in retrieved source documents.</p>
            <textarea
              value={knowledgeQuestion}
              onChange={(e) => setKnowledgeQuestion(e.target.value)}
              rows={2}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-sm mb-3"
            />
            <button onClick={runKnowledge} disabled={loading === "knowledge"} className="bg-lime-400 text-black font-bold text-sm px-4 py-2.5 rounded-lg disabled:opacity-50">
              {loading === "knowledge" ? "Asking…" : "Ask"}
            </button>
            <ResultCard result={knowledgeResult} />
          </div>
        )}

        {view === "audit" && (
          <div>
            <h1 className="text-3xl font-black mb-1">Audit & Governance Log</h1>
            <p className="text-zinc-500 text-sm mb-6">Every runtime interaction, server-recorded.</p>
            <div className="space-y-3">
              {audit.length === 0 && <p className="text-sm text-zinc-500">No interactions logged yet.</p>}
              {audit.map((a) => (
                <div key={a.id} className="border-l-2 border-zinc-800 pl-3">
                  <div className="text-[11px] text-zinc-500 font-mono">{a.timestamp} · {a.module}</div>
                  <div className="text-sm">{a.query}</div>
                  <div className="text-[11px] text-zinc-500">
                    Risk: {a.risk_level} · Confidence: {a.confidence}% · Sources: {(a.sources_used || []).join(", ") || "none"}
                    {a.human_decision ? ` · Human: ${a.human_decision} by ${a.human_by}` : ""}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
