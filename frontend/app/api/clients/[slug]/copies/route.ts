import { NextResponse } from "next/server";
import { q } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { slug: string } }) {
  const slug = params.slug;
  try {
    const [copies, campaigns] = await Promise.all([
      q(
        `select c.id, c.status, c.lever, c.t1, c.t2, c.char_t1, c.char_t2, c.campaign_id,
                ca.name as campaign_name,
                cp.positive_rate, cp.sent, cp.booked
         from copies c
         left join campaigns ca on ca.id = c.campaign_id
         left join copy_performance cp on cp.copy_id = c.id
         where c.client_slug = $1
         order by c.id desc`,
        [slug]
      ),
      q(`select id, name, channel from campaigns where client_slug = $1 order by name`, [slug]),
    ]);
    return NextResponse.json({ copies, campaigns });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
