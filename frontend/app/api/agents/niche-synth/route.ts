import { NextResponse } from "next/server";
import { runAgent } from "@/lib/agents";

export const maxDuration = 300;

export async function POST(req: Request) {
  try {
    const { niche } = await req.json();
    if (!niche) return NextResponse.json({ error: "niche is required" }, { status: 400 });

    const r = await runAgent("niche_synth_agent.py", ["--niche", niche]);
    return NextResponse.json(r, { status: r.ok ? 200 : 500 });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
