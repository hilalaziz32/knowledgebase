import { NextResponse } from "next/server";
import { q } from "@/lib/db";

export const dynamic = "force-dynamic";

type Node = { id: string; type: string; label: string; value?: number; niche?: string };
type Edge = { source: string; target: string; kind: string };

export async function GET() {
  try {
    const clients = await q<any>(`
      select cr.slug, cr.client, cr.niche,
        (select count(*) from campaigns ca where ca.client_slug=cr.slug)::int          campaigns,
        (select count(*) from master_sheet_pains p where p.client_slug=cr.slug)::int    pains,
        (select count(*) from case_studies cs where cs.owner_client_slug=cr.slug)::int  cases,
        (select count(*) from client_calls c where c.client_slug=cr.slug)::int          calls,
        (select count(*) from copies cp where cp.client_slug=cr.slug)::int              copies
      from client_roster cr order by cr.client`);

    const kbNiches = new Set(
      (await q<any>(`select niche from niche_knowledge`)).map((r) => r.niche)
    );

    const nodes: Node[] = [];
    const edges: Edge[] = [];
    const seen = new Set<string>();
    const add = (n: Node) => { if (!seen.has(n.id)) { seen.add(n.id); nodes.push(n); } };

    for (const c of clients) {
      const niche = c.niche || "unassigned";
      const nicheId = `niche:${niche}`;
      add({ id: nicheId, type: "niche", label: niche, niche });

      // niche-knowledge hub (the cross-client brain)
      if (kbNiches.has(c.niche)) {
        const kbId = `kb:${niche}`;
        add({ id: kbId, type: "kb", label: "Niche knowledge", niche });
        edges.push({ source: nicheId, target: kbId, kind: "synthesizes" });
      }

      const cId = `client:${c.slug}`;
      add({ id: cId, type: "client", label: c.client, niche });
      edges.push({ source: cId, target: nicheId, kind: "in-niche" });

      const metrics: [string, number][] = [
        ["campaigns", c.campaigns], ["pains", c.pains], ["case studies", c.cases],
        ["calls", c.calls], ["copies", c.copies],
      ];
      for (const [label, value] of metrics) {
        if (!value) continue;
        const mId = `m:${c.slug}:${label}`;
        add({ id: mId, type: "metric", label, value, niche });
        edges.push({ source: cId, target: mId, kind: "has" });
      }
    }

    const niches = nodes.filter((n) => n.type === "niche").length;
    const sharedNiches = nodes
      .filter((n) => n.type === "niche")
      .map((n) => ({
        niche: n.label,
        clients: clients.filter((c) => (c.niche || "unassigned") === n.label).map((c) => c.client),
      }))
      .filter((x) => x.clients.length > 1);

    return NextResponse.json({ nodes, edges, summary: { clients: clients.length, niches, sharedNiches } });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
