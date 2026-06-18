"use client";

import { useEffect, useState, useCallback } from "react";
import { Console, idle, RunState } from "./Console";

type Campaign = { id: number; name: string; channel: string | null };
type Copy = {
  id: number; status: string; lever: string | null; t1: string | null; t2: string | null;
  char_t1: number | null; char_t2: number | null; campaign_id: number | null;
  campaign_name: string | null; positive_rate: number | null; sent: number | null; booked: number | null;
};

const COMPONENTS = ["disarmer", "identity", "case_line", "unique_mechanism", "relevance", "cta"] as const;

export default function CopyManager({ slug }: { slug: string }) {
  const [copies, setCopies] = useState<Copy[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);

  const load = useCallback(async () => {
    const res = await fetch(`/api/clients/${slug}/copies`, { cache: "no-store" });
    const data = await res.json();
    setCopies(data.copies || []);
    setCampaigns(data.campaigns || []);
  }, [slug]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <NewCopy slug={slug} campaigns={campaigns} onSaved={load} />
      <ExistingCopies copies={copies} campaigns={campaigns} onChange={load} />
    </div>
  );
}

function NewCopy({ slug, campaigns, onSaved }: { slug: string; campaigns: Campaign[]; onSaved: () => void }) {
  const [t1, setT1] = useState("");
  const [t2, setT2] = useState("");
  const [lever, setLever] = useState("");
  const [persona, setPersona] = useState("");
  const [status, setStatus] = useState("draft");
  const [campaignId, setCampaignId] = useState<string>("");
  const [comps, setComps] = useState<Record<string, string>>({});
  const [state, setState] = useState<RunState>(idle);

  async function save() {
    setState({ ...idle, loading: true });
    const components = COMPONENTS.filter((c) => comps[c]?.trim()).map((c) => ({
      component_type: c, item_text: comps[c].trim(),
    }));
    const res = await fetch("/api/agents/save-copy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_slug: slug, t1, t2, lever, persona, status, components,
        campaignId: campaignId ? Number(campaignId) : undefined,
      }),
    });
    const data = await res.json();
    setState({ loading: false, ok: data.ok ?? res.ok, output: data.output || data.error || "saved" });
    if (res.ok) {
      setT1(""); setT2(""); setComps({}); setCampaignId("");
      onSaved();
    }
  }

  return (
    <div className="card">
      <h2 className="mb-3 text-lg font-medium">New copy</h2>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="label">Lever</label><input className="input" value={lever} onChange={(e) => setLever(e.target.value)} placeholder="proof" /></div>
        <div><label className="label">Persona</label><input className="input" value={persona} onChange={(e) => setPersona(e.target.value)} placeholder="VP Marketing" /></div>
      </div>
      <label className="label mt-3">T1 (first message)</label>
      <textarea className="textarea min-h-[80px]" value={t1} onChange={(e) => setT1(e.target.value)} />
      <div className="text-right text-[10px] text-muted">{t1.length} chars</div>
      <label className="label">T2 (follow-up)</label>
      <textarea className="textarea min-h-[60px]" value={t2} onChange={(e) => setT2(e.target.value)} />
      <div className="text-right text-[10px] text-muted">{t2.length} chars</div>

      <p className="label mt-3">Components</p>
      <div className="grid gap-2">
        {COMPONENTS.map((c) => (
          <input key={c} className="input" placeholder={c} value={comps[c] || ""}
            onChange={(e) => setComps((p) => ({ ...p, [c]: e.target.value }))} />
        ))}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <label className="label">Status</label>
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="draft">draft</option>
            <option value="winner">winner</option>
            <option value="loser">loser</option>
            <option value="neutral">neutral</option>
          </select>
        </div>
        <div>
          <label className="label">Connect to campaign</label>
          <select className="input" value={campaignId} onChange={(e) => setCampaignId(e.target.value)}>
            <option value="">— none (link later) —</option>
            {campaigns.map((ca) => (
              <option key={ca.id} value={ca.id}>
                {shortCampaign(ca.name)} {ca.channel ? `· ${ca.channel}` : ""}
              </option>
            ))}
          </select>
        </div>
      </div>
      <button className="btn mt-3 w-full" disabled={state.loading || !(t1.trim() || t2.trim())} onClick={save}>
        {state.loading ? "Saving…" : "Save copy + connect + embed"}
      </button>
      <Console state={state} />
    </div>
  );
}

function ExistingCopies({
  copies, campaigns, onChange,
}: { copies: Copy[]; campaigns: Campaign[]; onChange: () => void }) {
  async function link(copyId: number, value: string) {
    await fetch("/api/copy/link", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ copyId, campaignId: value === "" ? null : Number(value) }),
    });
    onChange();
  }

  return (
    <div className="card">
      <h2 className="mb-3 text-lg font-medium">Copies ({copies.length})</h2>
      {copies.length === 0 && <p className="text-sm text-muted">No copies yet.</p>}
      <div className="space-y-3">
        {copies.map((c) => (
          <div key={c.id} className="rounded-lg border border-edge p-3">
            <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted">
              <span className="chip">#{c.id}</span>
              <span className="chip">{c.status}</span>
              {c.lever && <span className="chip">{c.lever}</span>}
              {c.positive_rate != null && <span className="chip">PR {(c.positive_rate * 100).toFixed(1)}%</span>}
              {c.sent != null && <span>{c.sent} sent</span>}
            </div>
            <p className="text-sm text-slate-200">{c.t1}</p>
            {c.t2 && <p className="mt-1 text-sm text-slate-400">{c.t2}</p>}
            <div className="mt-2 flex items-center gap-2">
              <span className="text-xs text-muted">campaign:</span>
              <select
                className="input max-w-[280px] py-1 text-xs"
                value={c.campaign_id ?? ""}
                onChange={(e) => link(c.id, e.target.value)}
              >
                <option value="">— not linked —</option>
                {campaigns.map((ca) => (
                  <option key={ca.id} value={ca.id}>
                    {shortCampaign(ca.name)} {ca.channel ? `(${ca.channel})` : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function shortCampaign(name: string) {
  if (!name) return "(unnamed)";
  const m = name.split("-").slice(1).join("-").trim();
  return (m || name).slice(0, 55);
}
