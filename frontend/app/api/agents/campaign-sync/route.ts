import { NextResponse } from "next/server";
import { runAgent } from "@/lib/agents";

export const maxDuration = 300;

export async function POST(req: Request) {
  try {
    const { client, airtableId, dryRun } = await req.json();
    if (!client) return NextResponse.json({ error: "client is required" }, { status: 400 });

    const args = ["campaign_sync_agent.py", "--client", client];
    if (airtableId) args.push("--airtable-id", airtableId);
    if (dryRun) args.push("--dry-run");

    const r = await runAgent(args[0], args.slice(1));
    return NextResponse.json(r, { status: r.ok ? 200 : 500 });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
