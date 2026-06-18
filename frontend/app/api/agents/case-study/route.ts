import { NextResponse } from "next/server";
import { runAgent, writeUpload } from "@/lib/agents";

export const maxDuration = 300;

export async function POST(req: Request) {
  try {
    const { client, text, sourceLabel } = await req.json();
    if (!client || !text?.trim())
      return NextResponse.json({ error: "client and case-study text are required" }, { status: 400 });

    const file = await writeUpload(`casestudies-${client}`, text);
    const args = ["case_study_agent.py", "--client", client, "--file", file];
    if (sourceLabel) args.push("--source-label", sourceLabel);

    const r = await runAgent(args[0], args.slice(1));
    return NextResponse.json(r, { status: r.ok ? 200 : 500 });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
