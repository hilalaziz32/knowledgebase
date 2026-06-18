"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

type Node = { id: string; type: string; label: string; value?: number; niche?: string };
type Edge = { source: string; target: string; kind: string };
type Graph = { nodes: Node[]; edges: Edge[]; summary: any };

const W = 1000, H = 640;

const STYLE: Record<string, { r: number; fill: string; ring: string }> = {
  niche:   { r: 30, fill: "#5b8cff", ring: "#9db8ff" },
  kb:      { r: 22, fill: "#a855f7", ring: "#d8b4fe" },
  client:  { r: 24, fill: "#10b981", ring: "#6ee7b7" },
  metric:  { r: 13, fill: "#1e2a44", ring: "#3b4d74" },
};

export default function GraphView() {
  const [g, setG] = useState<Graph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"network" | "clusters">("network");
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    fetch("/api/graph", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => (d.error ? setError(d.error) : setG(d)))
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="card border-rose-500/40 text-sm text-rose-300">Graph error: {error}</div>;
  if (!g) return <div className="card text-sm text-muted">Building graph…</div>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex overflow-hidden rounded-lg border border-edge">
          <button onClick={() => setView("network")} className={`px-3 py-1 text-xs ${view === "network" ? "bg-accent text-white" : "text-muted"}`}>Network</button>
          <button onClick={() => setView("clusters")} className={`px-3 py-1 text-xs ${view === "clusters" ? "bg-accent text-white" : "text-muted"}`}>Niche clusters</button>
        </span>
        <Legend />
        {view === "network" && (
          <span className="ml-auto inline-flex gap-1">
            <button className="btn-ghost px-2 py-1" onClick={() => setZoom((z) => Math.max(0.4, z - 0.15))}>−</button>
            <button className="btn-ghost px-2 py-1" onClick={() => setZoom(1)}>reset</button>
            <button className="btn-ghost px-2 py-1" onClick={() => setZoom((z) => Math.min(2.5, z + 0.15))}>+</button>
          </span>
        )}
      </div>

      {g.summary?.sharedNiches?.length > 0 && (
        <div className="card border-accent/40 text-sm">
          <b className="text-accent">Cross-client links:</b>{" "}
          {g.summary.sharedNiches.map((s: any, i: number) => (
            <span key={i}>{s.clients.join(" ↔ ")} <span className="text-muted">(via {s.niche})</span>{i < g.summary.sharedNiches.length - 1 ? " · " : ""}</span>
          ))}
        </div>
      )}

      {view === "network" ? <Network g={g} zoom={zoom} /> : <Clusters g={g} />}
    </div>
  );
}

function Network({ g, zoom }: { g: Graph; zoom: number }) {
  const pos = useForceLayout(g);
  const byId = (id: string) => pos[id];

  return (
    <div className="card overflow-hidden p-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-[640px] w-full">
        <g transform={`translate(${W / 2},${H / 2}) scale(${zoom}) translate(${-W / 2},${-H / 2})`}>
          {g.edges.map((e, i) => {
            const a = byId(e.source), b = byId(e.target);
            if (!a || !b) return null;
            return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#243049" strokeWidth={e.kind === "synthesizes" ? 2 : 1} />;
          })}
          {g.nodes.map((n) => {
            const p = byId(n.id); if (!p) return null;
            const s = STYLE[n.type] || STYLE.metric;
            const label = n.type === "metric" ? `${n.label} ${n.value}` : n.label;
            const inner = (
              <g>
                <circle cx={p.x} cy={p.y} r={s.r} fill={s.fill} stroke={s.ring} strokeWidth={1.5} />
                <text x={p.x} y={p.y + s.r + 12} textAnchor="middle" fontSize={n.type === "metric" ? 9 : 12}
                  fill={n.type === "metric" ? "#8aa0c6" : "#e2e8f0"} fontWeight={n.type === "client" || n.type === "niche" ? 600 : 400}>
                  {label.length > 22 ? label.slice(0, 21) + "…" : label}
                </text>
              </g>
            );
            return n.type === "client" ? (
              <Link key={n.id} href={`/clients/${n.id.split(":")[1]}`}>{inner}</Link>
            ) : <g key={n.id}>{inner}</g>;
          })}
        </g>
      </svg>
    </div>
  );
}

function Clusters({ g }: { g: Graph }) {
  const niches = g.nodes.filter((n) => n.type === "niche");
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {niches.map((nz) => {
        const clients = g.nodes.filter((n) => n.type === "client" && n.niche === nz.label);
        const hasKb = g.nodes.some((n) => n.type === "kb" && n.niche === nz.label);
        return (
          <div key={nz.id} className="card">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-medium text-accent">{nz.label}</h3>
              {hasKb ? <span className="badge badge-blue">niche brain ✓</span> : <span className="chip">no summary</span>}
            </div>
            <div className="space-y-2">
              {clients.map((c) => {
                const metrics = g.nodes.filter((m) => m.type === "metric" && m.id.startsWith(`m:${c.id.split(":")[1]}:`));
                return (
                  <Link key={c.id} href={`/clients/${c.id.split(":")[1]}`} className="block rounded-lg border border-edge p-2 hover:border-accent">
                    <div className="text-sm font-medium">{c.label}</div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {metrics.map((m) => <span key={m.id} className="chip">{m.label} {m.value}</span>)}
                    </div>
                  </Link>
                );
              })}
            </div>
            {clients.length > 1 && <p className="mt-3 text-xs text-accent">↔ {clients.length} clients share this niche &amp; its knowledge</p>}
          </div>
        );
      })}
    </div>
  );
}

function Legend() {
  const items = [["niche", "Niche"], ["kb", "Niche knowledge"], ["client", "Client"], ["metric", "Data"]];
  return (
    <span className="flex flex-wrap gap-3 text-xs text-muted">
      {items.map(([t, l]) => (
        <span key={t} className="flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded-full" style={{ background: STYLE[t].fill }} />{l}
        </span>
      ))}
    </span>
  );
}

// --- tiny dependency-free force layout ---
function useForceLayout(g: Graph) {
  return useMemo(() => {
    const nodes = g.nodes.map((n, i) => ({
      id: n.id, type: n.type,
      x: W / 2 + Math.cos(i) * 120 + (i % 7) * 18,
      y: H / 2 + Math.sin(i) * 120 + (i % 5) * 18,
      vx: 0, vy: 0,
      pin: n.type === "niche",
    }));
    const idx: Record<string, number> = {};
    nodes.forEach((n, i) => (idx[n.id] = i));
    const links = g.edges.map((e) => ({ s: idx[e.source], t: idx[e.target] })).filter((l) => l.s != null && l.t != null);

    // pin niches in a vertical spine
    const niches = nodes.filter((n) => n.pin);
    niches.forEach((n, i) => {
      n.x = W * 0.32;
      n.y = (H / (niches.length + 1)) * (i + 1);
    });

    for (let iter = 0; iter < 320; iter++) {
      // repulsion
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          let dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y;
          let d2 = dx * dx + dy * dy || 0.01;
          const f = 2600 / d2;
          const d = Math.sqrt(d2);
          const ux = dx / d, uy = dy / d;
          nodes[i].vx += ux * f; nodes[i].vy += uy * f;
          nodes[j].vx -= ux * f; nodes[j].vy -= uy * f;
        }
      }
      // springs
      for (const l of links) {
        const a = nodes[l.s], b = nodes[l.t];
        let dx = b.x - a.x, dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
        const target = 90;
        const f = (d - target) * 0.02;
        const ux = dx / d, uy = dy / d;
        a.vx += ux * f; a.vy += uy * f;
        b.vx -= ux * f; b.vy -= uy * f;
      }
      // integrate
      for (const n of nodes) {
        if (n.pin) { n.vx = 0; n.vy = 0; continue; }
        n.x += n.vx * 0.85; n.y += n.vy * 0.85;
        n.vx *= 0.82; n.vy *= 0.82;
        n.x = Math.max(40, Math.min(W - 40, n.x));
        n.y = Math.max(30, Math.min(H - 30, n.y));
      }
    }
    const out: Record<string, { x: number; y: number }> = {};
    nodes.forEach((n) => (out[n.id] = { x: n.x, y: n.y }));
    return out;
  }, [g]);
}
