import { NextResponse } from "next/server";
import { q } from "@/lib/db";

// Both copy and campaign live in Supabase, so linking is a single column write.
// The copy inherits the campaign's niche/persona where it doesn't already have them.
export async function POST(req: Request) {
  try {
    const { copyId, campaignId } = await req.json();
    if (!copyId) return NextResponse.json({ error: "copyId required" }, { status: 400 });

    if (campaignId === null) {
      await q(`update copies set campaign_id = null, updated_at = now() where id = $1`, [copyId]);
      return NextResponse.json({ ok: true, unlinked: true });
    }

    const camp = await q(`select niche, persona from campaigns where id = $1`, [campaignId]);
    if (camp.length === 0) return NextResponse.json({ error: "campaign not found" }, { status: 404 });

    await q(
      `update copies set campaign_id = $1,
         niche = coalesce(niche, $2), persona = coalesce(persona, $3), updated_at = now()
       where id = $4`,
      [campaignId, camp[0].niche, camp[0].persona, copyId]
    );
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
