"use client";

import { useEffect, useState } from "react";

type Triple = { sms: number; email: number; total: number };
type Period = { sent: Triple; positives: Triple; booked: Triple; conversion: string };
type Stats = {
  retainer: number;
  accountManager: string;
  status: string;
  domain: string | null;
  activeCampaigns: { sms: number; email: number };
  leadsRemaining: { sms: number; email: number };
  periods: Record<string, Period>;
};
type Campaign = {
  id: string; name: string; type: string; status: string;
  totalLeads: number; completed: number; completion: number | null;
  emailsSent: number; emailReplies: number; leadsRemaining: number;
};

const fmt = (n: number) => n.toLocaleString();

export default function ClientStats({ slug }: { slug: string }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [period, setPeriod] = useState("This Month");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/clients/${slug}/stats`, { cache: "no-store" });
        const data = await res.json();
        if (!res.ok) setError(data.error || "failed to load stats");
        else { setStats(data.stats); setCampaigns(data.campaigns || []); }
      } catch (e: any) { setError(e.message); }
      finally { setLoading(false); }
    })();
  }, [slug]);

  if (loading) return <div className="card text-sm text-muted">Loading live stats from Airtable…</div>;
  if (error) return <div className="card border-amber-500/40 text-sm text-amber-300">Stats unavailable: {error}</div>;
  if (!stats) return null;

  const p = stats.periods[period];

  return (
    <div className="space-y-4">
      {/* meta row */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <StatusBadge status={stats.status} />
        <span className="chip">AM: {stats.accountManager}</span>
        <span className="chip">retainer ${fmt(stats.retainer)}/mo</span>
        <span className="chip">{stats.activeCampaigns.sms} SMS · {stats.activeCampaigns.email} email active</span>
        <span className="chip">{fmt(stats.leadsRemaining.sms + stats.leadsRemaining.email)} leads left</span>
        <span className="ml-auto inline-flex overflow-hidden rounded-lg border border-edge">
          {Object.keys(stats.periods).map((k) => (
            <button key={k} onClick={() => setPeriod(k)}
              className={`px-3 py-1 text-xs ${period === k ? "bg-accent text-white" : "text-muted hover:text-slate-200"}`}>
              {k}
            </button>
          ))}
        </span>
      </div>

      {/* KPI tiles */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile value={fmt(p.sent.total)} label="Messages sent" sub={`${fmt(p.sent.sms)} sms · ${fmt(p.sent.email)} email`} />
        <Tile value={fmt(p.positives.total)} label="Positive replies" sub={`${fmt(p.positives.sms)} sms · ${fmt(p.positives.email)} email`} accent="green" />
        <Tile value={fmt(p.booked.total)} label="Meetings booked" sub={`${fmt(p.booked.sms)} sms · ${fmt(p.booked.email)} email`} accent="blue" />
        <Tile value={String(p.conversion)} label="Conversion rate" sub={`reply → meeting`} accent="amber" />
      </div>

      {/* campaign performance table */}
      <div className="card p-0">
        <div className="flex items-center justify-between px-4 py-3">
          <h3 className="font-medium">Campaign performance <span className="text-muted">· {campaigns.length} live from Airtable</span></h3>
        </div>
        <div className="max-h-[420px] overflow-auto">
          <table className="tbl">
            <thead className="sticky top-0 bg-panel">
              <tr>
                <th>Campaign</th><th>Type</th><th>Status</th>
                <th className="text-right">Leads</th><th className="text-right">Done</th>
                <th className="w-40">Progress</th><th className="text-right">Replies</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c) => (
                <tr key={c.id}>
                  <td className="max-w-[280px] truncate" title={c.name}>{shortName(c.name)}</td>
                  <td><span className="chip">{c.type}</span></td>
                  <td><StatusBadge status={c.status} /></td>
                  <td className="text-right tabular-nums">{fmt(c.totalLeads)}</td>
                  <td className="text-right tabular-nums">{fmt(c.completed)}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="bar flex-1"><span style={{ width: `${pct(c)}%` }} /></div>
                      <span className="w-9 text-right text-[11px] text-muted">{pct(c)}%</span>
                    </div>
                  </td>
                  <td className="text-right tabular-nums">{c.emailReplies ? fmt(c.emailReplies) : "—"}</td>
                </tr>
              ))}
              {campaigns.length === 0 && (
                <tr><td colSpan={7} className="py-6 text-center text-muted">No campaigns found in Airtable.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function pct(c: Campaign) {
  if (c.completion != null) return Math.min(100, Math.max(0, c.completion));
  if (!c.totalLeads) return 0;
  return Math.min(100, Math.round((c.completed / c.totalLeads) * 100));
}

function Tile({ value, label, sub, accent }: { value: string; label: string; sub?: string; accent?: string }) {
  const color =
    accent === "green" ? "text-emerald-300" :
    accent === "blue" ? "text-sky-300" :
    accent === "amber" ? "text-amber-300" : "text-slate-100";
  return (
    <div className="tile">
      <div className={`tile-value ${color}`}>{value}</div>
      <div className="tile-label">{label}</div>
      {sub && <div className="tile-sub">{sub}</div>}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const s = (status || "").toUpperCase();
  const cls =
    /ACTIVE|PROCESSING|RESUMED/.test(s) ? "badge-green" :
    /SCHEDULED|DRAFT/.test(s) ? "badge-blue" :
    /PAUSED|REFILL|AWAIT/.test(s) ? "badge-amber" :
    /CANCEL|STOP|UNHEALTHY|FAIL/.test(s) ? "badge-red" :
    /COMPLETE/.test(s) ? "badge-gray" : "badge-gray";
  return <span className={`badge ${cls}`}>{status || "—"}</span>;
}

function shortName(name: string) {
  if (!name) return "—";
  const m = name.split("-").slice(1).join("-").trim();
  return m || name;
}
