"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Console, postAgent, idle, RunState } from "./Console";

export default function NewClientForm() {
  const router = useRouter();
  const [client, setClient] = useState("");
  const [slug, setSlug] = useState("");
  const [airtableId, setAirtableId] = useState("");
  const [niche, setNiche] = useState("");
  const [subNiche, setSubNiche] = useState("");
  const [form, setForm] = useState("");
  const [state, setState] = useState<RunState>(idle);

  function autoSlug(name: string) {
    setClient(name);
    if (!slug || slug === slugify(client)) setSlug(slugify(name));
  }

  async function submit() {
    setState({ ...idle, loading: true });
    const res = await postAgent("/api/agents/onboarding", {
      client, slug, airtableId, niche, subNiche, form,
    });
    setState(res);
    if (res.ok) {
      setTimeout(() => router.push(`/clients/${slug}`), 800);
      router.refresh();
    }
  }

  return (
    <div className="card max-w-2xl">
      <h2 className="mb-1 text-lg font-medium">Onboard a client</h2>
      <p className="mb-4 text-sm text-muted">
        Paste the onboarding form (and optionally the Account/Persona tabs). The agent extracts the
        client profile + pains and writes them to Evergreen.
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="label">Client name</label>
          <input className="input" value={client} onChange={(e) => autoSlug(e.target.value)} placeholder="Chamber Media" />
        </div>
        <div>
          <label className="label">Slug</label>
          <input className="input" value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="chamber_media" />
        </div>
        <div>
          <label className="label">Airtable client id</label>
          <input className="input" value={airtableId} onChange={(e) => setAirtableId(e.target.value)} placeholder="recL0ZcxKPJidtffg" />
        </div>
        <div>
          <label className="label">Niche</label>
          <input className="input" value={niche} onChange={(e) => setNiche(e.target.value)} placeholder="DTC ecom" />
        </div>
        <div>
          <label className="label">Sub-niche (optional)</label>
          <input className="input" value={subNiche} onChange={(e) => setSubNiche(e.target.value)} placeholder="supplements" />
        </div>
      </div>

      <div className="mt-3">
        <label className="label">Onboarding form / account & persona text</label>
        <textarea className="textarea" value={form} onChange={(e) => setForm(e.target.value)} placeholder="Paste the messy onboarding answers here…" />
      </div>

      <button className="btn mt-4" disabled={state.loading || !client || !slug || !form.trim()} onClick={submit}>
        {state.loading ? "Onboarding…" : "Create client + extract pains"}
      </button>
      <Console state={state} />
    </div>
  );
}

function slugify(s: string) {
  return s.toLowerCase().trim().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}
