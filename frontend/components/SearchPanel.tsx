"use client";

import { useState } from "react";

type Result = Record<string, any>;
const TYPES = [
  { id: "pains", label: "Pains / voice" },
  { id: "calls", label: "Call chunks" },
  { id: "case_studies", label: "Case studies" },
  { id: "copies", label: "Copies" },
  { id: "components", label: "Copy components" },
];

export default function SearchPanel() {
  const [type, setType] = useState("pains");
  const [query, setQuery] = useState("");
  const [niche, setNiche] = useState("");
  const [smart, setSmart] = useState(true);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Result[] | null>(null);
  const [routed, setRouted] = useState<{ niche: string; score: number }[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true); setError(null); setResults(null); setRouted([]);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, query, niche: niche || undefined, route: smart && !niche, limit: 12 }),
      });
      const data = await res.json();
      if (!res.ok) setError(data.error || "search failed");
      else { setResults(data.results || []); setRouted(data.routed || []); }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="card">
        <div className="mb-3 flex flex-wrap gap-2">
          {TYPES.map((t) => (
            <button key={t.id} onClick={() => setType(t.id)} className={type === t.id ? "btn" : "btn-ghost"}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            className="input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && query.trim() && run()}
            placeholder="Search by meaning — e.g. 'founders skeptical of agencies'"
          />
          <input className="input sm:max-w-[200px]" value={niche} onChange={(e) => setNiche(e.target.value)} placeholder="niche (optional)" />
          <button className="btn" disabled={loading || !query.trim()} onClick={run}>
            {loading ? "Searching…" : "Search"}
          </button>
        </div>
        <label className="mt-3 flex items-center gap-2 text-xs text-muted">
          <input type="checkbox" checked={smart} disabled={!!niche} onChange={(e) => setSmart(e.target.checked)} />
          Smart routing — first match the query to the most relevant niche, then search inside it
          {niche && <span className="text-amber-300">(off: a niche is set manually)</span>}
        </label>
      </div>

      {routed.length > 0 && (
        <div className="card mt-4 border-accent/40 py-3 text-sm">
          <span className="text-muted">Routed to niche:</span>{" "}
          {routed.map((r, i) => (
            <span key={i} className="badge badge-blue mr-1">{r.niche} · {(r.score * 100).toFixed(0)}%</span>
          ))}
        </div>
      )}

      {error && <div className="card mt-4 border-red-500/40 text-sm text-red-300">{error}</div>}

      {results && (
        <div className="mt-4 space-y-2">
          <p className="text-xs text-muted">{results.length} results</p>
          {results.map((r, i) => (
            <div key={i} className="card py-3">
              <div className="mb-1 flex items-center gap-2 text-xs text-muted">
                <span className="chip">score {r.score}</span>
                {r.kind && <span className="chip">{r.kind}</span>}
                {r.tier && <span className="chip">tier {r.tier}</span>}
                {r.status && <span className="chip">{r.status}</span>}
                {r.client_slug && <span>{r.client_slug}</span>}
                {r.positive_rate != null && <span className="chip">PR {(r.positive_rate * 100).toFixed(1)}%</span>}
              </div>
              <p className="text-sm text-slate-200">{snippet(r)}</p>
            </div>
          ))}
          {results.length === 0 && <div className="card text-sm text-muted">No matches.</div>}
        </div>
      )}
    </div>
  );
}

function snippet(r: Result): string {
  return (
    r.item_text ||
    r.chunk_text ||
    r.after_state ||
    [r.t1, r.t2].filter(Boolean).join("  /  ") ||
    JSON.stringify(r)
  );
}
