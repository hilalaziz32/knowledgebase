import { NextResponse } from "next/server";
import { q } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const rows = await q(`
      select cr.slug, cr.client, cr.niche, cr.sub_niche, cr.offer,
             cr.airtable_client_id, cr.status,
        (select count(*) from client_calls c where c.client_slug = cr.slug)        as calls,
        (select count(*) from master_sheet_pains p where p.client_slug = cr.slug)  as pains,
        (select count(*) from case_studies cs where cs.owner_client_slug = cr.slug) as case_studies,
        (select count(*) from campaigns ca where ca.client_slug = cr.slug)         as campaigns
      from client_roster cr
      order by cr.client`);
    return NextResponse.json(rows);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
