"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Console, postAgent, idle, RunState } from "./Console";

export default function ClientActions({
  slug,
  niche,
  airtableId,
}: {
  slug: string;
  niche: string | null;
  airtableId: string | null;
}) {
  const router = useRouter();
  const [tab, setTab] = useState<"case" | "transcript" | "campaigns" | "niche">("case");

  const tabs = [
    { id: "case", label: "Add case studies" },
    { id: "transcript", label: "Add transcript" },
    { id: "campaigns", label: "Sync campaigns" },
    { id: "niche", label: "Synthesize niche" },
  ] as const;

  return (
    <div className="card">
      <div className="mb-4 flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={tab === t.id ? "btn" : "btn-ghost"}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "case" && <CaseStudyForm slug={slug} onDone={() => router.refresh()} />}
      {tab === "transcript" && <TranscriptForm slug={slug} onDone={() => router.refresh()} />}
      {tab === "campaigns" && <CampaignSync slug={slug} airtableId={airtableId} onDone={() => router.refresh()} />}
      {tab === "niche" && <NicheSynth niche={niche} onDone={() => router.refresh()} />}
    </div>
  );
}

function CaseStudyForm({ slug, onDone }: { slug: string; onDone: () => void }) {
  const [text, setText] = useState("");
  const [sourceLabel, setSourceLabel] = useState("");
  const [state, setState] = useState<RunState>(idle);
  async function run() {
    setState({ ...idle, loading: true });
    const r = await postAgent("/api/agents/case-study", { client: slug, text, sourceLabel });
    setState(r);
    if (r.ok) onDone();
  }
  return (
    <div>
      <p className="mb-3 text-sm text-muted">Paste case studies. The agent splits, tiers (S–D), dedups and embeds them.</p>
      <label className="label">Source label (for dedup)</label>
      <input className="input mb-3" value={sourceLabel} onChange={(e) => setSourceLabel(e.target.value)} placeholder="Chamber Media Master Sheet · Tab 4" />
      <label className="label">Case studies</label>
      <textarea className="textarea" value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste one or many case studies…" />
      <button className="btn mt-3" disabled={state.loading || !text.trim()} onClick={run}>
        {state.loading ? "Processing…" : "Extract + tier + save"}
      </button>
      <Console state={state} />
    </div>
  );
}

function TranscriptForm({ slug, onDone }: { slug: string; onDone: () => void }) {
  const [text, setText] = useState("");
  const [sourceCallId, setSourceCallId] = useState("");
  const [title, setTitle] = useState("");
  const [mine, setMine] = useState(true);
  const [state, setState] = useState<RunState>(idle);
  async function run() {
    setState({ ...idle, loading: true });
    const r = await postAgent("/api/agents/transcript", {
      client: slug, sourceCallId, title, provider: "manual", mine, text,
    });
    setState(r);
    if (r.ok) onDone();
  }
  return (
    <div>
      <p className="mb-3 text-sm text-muted">Paste a call transcript. It's chunked, embedded, and pains are mined.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="label">Source call id (unique)</label>
          <input className="input" value={sourceCallId} onChange={(e) => setSourceCallId(e.target.value)} placeholder="chamber_media_call7" />
        </div>
        <div>
          <label className="label">Title</label>
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Discovery call" />
        </div>
      </div>
      <label className="label mt-3">Transcript</label>
      <textarea className="textarea" value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the transcript…" />
      <label className="mt-2 flex items-center gap-2 text-xs text-muted">
        <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} />
        mine pains/lingo with the LLM
      </label>
      <button className="btn mt-3" disabled={state.loading || !text.trim() || !sourceCallId} onClick={run}>
        {state.loading ? "Ingesting…" : "Ingest transcript"}
      </button>
      <Console state={state} />
    </div>
  );
}

function CampaignSync({ slug, airtableId, onDone }: { slug: string; airtableId: string | null; onDone: () => void }) {
  const [state, setState] = useState<RunState>(idle);
  async function run(dryRun: boolean) {
    setState({ ...idle, loading: true });
    const r = await postAgent("/api/agents/campaign-sync", { client: slug, dryRun });
    setState(r);
    if (r.ok && !dryRun) onDone();
  }
  return (
    <div>
      <p className="mb-3 text-sm text-muted">
        Pulls this client's campaigns from Airtable {airtableId ? `(${airtableId})` : "(needs an Airtable id on the client)"} and upserts them.
      </p>
      <div className="flex gap-2">
        <button className="btn-ghost" disabled={state.loading} onClick={() => run(true)}>Dry run</button>
        <button className="btn" disabled={state.loading} onClick={() => run(false)}>Sync to DB</button>
      </div>
      <Console state={state} />
    </div>
  );
}

function NicheSynth({ niche, onDone }: { niche: string | null; onDone: () => void }) {
  const [val, setVal] = useState(niche || "");
  const [state, setState] = useState<RunState>(idle);
  async function run() {
    setState({ ...idle, loading: true });
    const r = await postAgent("/api/agents/niche-synth", { niche: val });
    setState(r);
    if (r.ok) onDone();
  }
  return (
    <div>
      <p className="mb-3 text-sm text-muted">Clusters all pains/calls/winners in this niche and writes the cross-client summary.</p>
      <label className="label">Niche</label>
      <input className="input mb-3" value={val} onChange={(e) => setVal(e.target.value)} placeholder="DTC ecom" />
      <button className="btn" disabled={state.loading || !val} onClick={run}>
        {state.loading ? "Synthesizing…" : "Run niche synthesis"}
      </button>
      <Console state={state} />
    </div>
  );
}
