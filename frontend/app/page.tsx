import Link from "next/link";
import { q } from "@/lib/db";

export const dynamic = "force-dynamic";

type Row = {
  slug: string; client: string; niche: string | null; sub_niche: string | null; status: string | null;
  calls: string; pains: string; case_studies: string; campaigns: string; copies: string;
};

export default async function Home() {
  let rows: Row[] = [];
  let error: string | null = null;
  try {
    rows = await q<Row>(`
      select cr.slug, cr.client, cr.niche, cr.sub_niche, cr.status,
        (select count(*) from client_calls c where c.client_slug = cr.slug)         as calls,
        (select count(*) from master_sheet_pains p where p.client_slug = cr.slug)   as pains,
        (select count(*) from case_studies cs where cs.owner_client_slug = cr.slug) as case_studies,
        (select count(*) from campaigns ca where ca.client_slug = cr.slug)          as campaigns,
        (select count(*) from copies cp where cp.client_slug = cr.slug)             as copies
      from client_roster cr order by cr.client`);
  } catch (e: any) { error = e.message; }

  const totals = rows.reduce((a, r) => ({
    calls: a.calls + +r.calls, pains: a.pains + +r.pains,
    cases: a.cases + +r.case_studies, campaigns: a.campaigns + +r.campaigns,
  }), { calls: 0, pains: 0, cases: 0, campaigns: 0 });

  return (
    <main className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Evergreen</h1>
        <p className="text-sm text-muted">First-party memory across every client. Click a client for live campaign stats.</p>
      </div>

      {error && <div className="card border-rose-500/40 text-sm text-rose-300">DB error: {error}</div>}

      {!error && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Tile value={rows.length} label="Clients" />
          <Tile value={totals.campaigns} label="Campaigns" />
          <Tile value={totals.calls} label="Calls / docs" />
          <Tile value={totals.pains} label="Pains mined" />
          <Tile value={totals.cases} label="Case studies" />
        </div>
      )}

      {!error && rows.length === 0 && (
        <div className="card text-sm text-muted">
          No clients yet. <Link href="/clients/new" className="text-accent">Add your first client →</Link>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((r) => (
          <Link key={r.slug} href={`/clients/${r.slug}`} className="card group transition hover:border-accent">
            <div className="mb-1 flex items-center justify-between">
              <h2 className="text-lg font-medium group-hover:text-accent">{r.client}</h2>
              {r.status && <span className="chip">{r.status}</span>}
            </div>
            <p className="mb-4 text-xs text-muted">{r.niche || "—"}{r.sub_niche ? ` · ${r.sub_niche}` : ""}</p>
            <div className="grid grid-cols-5 gap-1.5 text-center">
              <Mini label="camp" value={r.campaigns} />
              <Mini label="calls" value={r.calls} />
              <Mini label="pains" value={r.pains} />
              <Mini label="cases" value={r.case_studies} />
              <Mini label="copy" value={r.copies} />
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}

function Tile({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="tile text-center">
      <div className="tile-value">{value}</div>
      <div className="tile-label">{label}</div>
    </div>
  );
}
function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-edge bg-ink py-2">
      <div className="text-base font-semibold tabular-nums">{value}</div>
      <div className="text-[9px] uppercase tracking-wide text-muted">{label}</div>
    </div>
  );
}
