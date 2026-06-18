import { NextResponse } from "next/server";
import { runAgent, writeUpload } from "@/lib/agents";

export const maxDuration = 120;

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { campaignId, ...copy } = body;
    if (!copy.client_slug || !(copy.t1 || copy.t2))
      return NextResponse.json({ error: "client_slug and at least t1 or t2 are required" }, { status: 400 });

    const file = await writeUpload(`copy-${copy.client_slug}`, JSON.stringify(copy));
    const args = ["copy_agent.py", "--file", file];
    if (campaignId) args.push("--campaign-id", String(campaignId));

    const r = await runAgent(args[0], args.slice(1));
    return NextResponse.json(r, { status: r.ok ? 200 : 500 });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
