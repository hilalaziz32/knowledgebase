import { NextResponse } from "next/server";
import { runAgent } from "@/lib/agents";

export const maxDuration = 120;

export async function POST(req: Request) {
  try {
    const { type, query, niche, status, limit } = await req.json();
    if (!type || !query?.trim())
      return NextResponse.json({ error: "type and query are required" }, { status: 400 });

    const args = ["search_agent.py", "--type", type, "--query", query, "--limit", String(limit || 10)];
    if (niche) args.push("--niche", niche);
    if (status) args.push("--status", status);

    const r = await runAgent(args[0], args.slice(1), 120000);
    if (!r.ok) return NextResponse.json({ error: r.output }, { status: 500 });

    // the agent prints a single JSON object (warnings already stripped)
    const line = r.output.split("\n").reverse().find((l) => l.trim().startsWith("{"));
    if (!line) return NextResponse.json({ results: [], raw: r.output });
    return NextResponse.json(JSON.parse(line));
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
