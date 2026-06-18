import Link from "next/link";
import { notFound } from "next/navigation";
import { q, one } from "@/lib/db";
import ClientActions from "@/components/ClientActions";
import ClientStats from "@/components/ClientStats";

export const dynamic = "force-dynamic";

export default async function ClientPage({ params }: { params: { slug: string } }) {
  const slug = params.slug;
  const client = await one<any>(
    `select slug, client, niche, sub_niche, offer, airtable_client_id, status
     from client_roster where slug=$1`,
    [slug]
  );
  if (!client) notFound();

  const [pains, painKinds, caseStudies, calls, niche, counts] = await Promise.all([
    q<any>(`select kind, persona, item_text, confidence from master_sheet_pains where client_slug=$1 order by confidence desc, kind limit 40`, [slug]),
    q<any>(`select kind, count(*)::int n from master_sheet_pains where client_slug=$1 group by kind order by n desc`, [slug]),
    q<any>(`select subject_brand, tier, after_state, unique_mechanism from case_studies where owner_client_slug=$1 order by tier, subject_brand`, [slug]),
    q<any>(`select c.title, c.source, c.source_call_id, (select count(*) from call_chunks ch where ch.call_id=c.id) chunks from client_calls c where c.client_slug=$1 order by c.id`, [slug]),
    one<any>(`select commonalities_summary, shared_lingo, dream_outcomes, refreshed_at from niche_knowledge where niche=$1`, [client.niche]),
    one<any>(`select
        (select count(*) from client_calls where client_slug=$1) calls,
        (select count(*) from master_sheet_pains where client_slug=$1) pains,
        (select count(*) from case_studies where owner_client_slug=$1) cases,
        (select count(*) from campaigns where client_slug=$1) campaigns,
        (select count(*) from copies where client_slug=$1) copies`, [slug]),
  ]);

  return (
    <main className="space-y-6">
      <div>
        <Link href="/" className="text-xs text-muted hover:text-accent">← all clients</Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{client.client}</h1>
          <span className="chip">{client.niche || "no niche"}{client.sub_niche ? ` · ${client.sub_niche}` : ""}</span>
          <div className="ml-auto flex gap-2">
            <Link href={`/clients/${slug}/copy`} className="btn-ghost">✍️ Copy</Link>
            <Link href="/search" className="btn-ghost">🔎 Search</Link>
          </div>
        </div>
        {client.offer && <p className="mt-2 max-w-3xl text-sm text-slate-300">{client.offer}</p>}
      </div>

      {/* LIVE performance */}
      <ClientStats slug={slug} />

      {/* knowledge corpus counts */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <MiniStat label="Calls / docs" value={counts.calls} />
        <MiniStat label="Pains" value={counts.pains} />
        <MiniStat label="Case studies" value={counts.cases} />
        <MiniStat label="Campaigns" value={counts.campaigns} />
        <MiniStat label="Copies" value={counts.copies} />
      </div>

      {/* feed actions */}
      <ClientActions slug={slug} niche={client.niche} airtableId={client.airtable_client_id} />

      {/* knowledge */}
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card">
          <SectionHead title="Pains & voice" extra={painKinds.map((k: any) => `${k.kind}:${k.n}`).join("  ")} />
          <ul className="space-y-2">
            {pains.map((p: any, i: number) => (
              <li key={i} className="text-sm">
                <span className="chip mr-2">{p.kind}</span>
                <span className={p.confidence === "confirmed" ? "text-slate-100" : "text-slate-400"}>{p.item_text}</span>
              </li>
            ))}
            {pains.length === 0 && <Empty />}
          </ul>
        </section>

        <section className="card">
          <SectionHead title="Case studies" extra={`${caseStudies.length}`} />
          <ul className="space-y-2">
            {caseStudies.map((c: any, i: number) => (
              <li key={i} className="text-sm">
                <span className="chip mr-2">{c.tier}</span>
                <b>{c.subject_brand}</b> — {c.after_state}
                {c.unique_mechanism && <span className="text-muted"> · {c.unique_mechanism}</span>}
              </li>
            ))}
            {caseStudies.length === 0 && <Empty />}
          </ul>
        </section>

        <section className="card">
          <SectionHead title="Calls / docs" extra={`${calls.length}`} />
          <ul className="space-y-1 text-sm">
            {calls.map((c: any, i: number) => (
              <li key={i} className="flex justify-between">
                <span>{c.title || c.source_call_id} <span className="text-muted">({c.source})</span></span>
                <span className="text-muted">{c.chunks} chunks</span>
              </li>
            ))}
            {calls.length === 0 && <Empty />}
          </ul>
        </section>

        <section className="card">
          <SectionHead title="Niche knowledge" extra={niche?.refreshed_at ? `refreshed ${new Date(niche.refreshed_at).toLocaleDateString()}` : "not built"} />
          {niche ? (
            <div className="space-y-3 text-sm">
              <p className="text-slate-200">{niche.commonalities_summary}</p>
              <div className="flex flex-wrap gap-2">
                {asArray(niche.shared_lingo).slice(0, 12).map((x: string, i: number) => <span key={i} className="chip">{x}</span>)}
              </div>
            </div>
          ) : <p className="text-sm text-muted">Run “Synthesize niche” above to build it.</p>}
        </section>
      </div>
    </main>
  );
}

function MiniStat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="tile py-3 text-center">
      <div className="tile-value">{value}</div>
      <div className="tile-label">{label}</div>
    </div>
  );
}
function SectionHead({ title, extra }: { title: string; extra?: string }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="font-medium">{title}</h2>
      {extra && <span className="text-xs text-muted">{extra}</span>}
    </div>
  );
}
function Empty() { return <li className="text-sm text-muted">Nothing yet.</li>; }
function asArray(v: any): string[] {
  if (Array.isArray(v)) return v;
  if (typeof v === "string") { try { return JSON.parse(v); } catch { return []; } }
  return [];
}
