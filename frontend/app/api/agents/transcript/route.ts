import { NextResponse } from "next/server";
import { runAgent, writeUpload } from "@/lib/agents";

export const maxDuration = 600;

export async function POST(req: Request) {
  try {
    const { client, sourceCallId, title, provider, mine, text } = await req.json();
    if (!client || !sourceCallId || !text?.trim())
      return NextResponse.json(
        { error: "client, sourceCallId and transcript text are required" },
        { status: 400 }
      );

    const file = await writeUpload(`transcript-${sourceCallId}`, text);
    const args = [
      "transcript_agent.py",
      "--client", client,
      "--source-call-id", sourceCallId,
      "--file", file,
      "--provider", provider || "manual",
    ];
    if (title) args.push("--title", title);
    if (mine === false) args.push("--no-mine");

    const r = await runAgent(args[0], args.slice(1));
    return NextResponse.json(r, { status: r.ok ? 200 : 500 });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
