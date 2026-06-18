import { NextResponse } from "next/server";
import { runAgent, writeUpload } from "@/lib/agents";

export const maxDuration = 300;

export async function POST(req: Request) {
  try {
    const { client, slug, airtableId, niche, subNiche, form } = await req.json();
    if (!client || !slug || !form?.trim())
      return NextResponse.json({ error: "client, slug and form text are required" }, { status: 400 });

    const file = await writeUpload(`onboarding-${slug}`, form);
    const args = ["onboarding_agent.py", "--client", client, "--slug", slug, "--form", file];
    if (airtableId) args.push("--airtable-id", airtableId);
    if (niche) args.push("--niche", niche);
    if (subNiche) args.push("--sub-niche", subNiche);

    const r = await runAgent(args[0], args.slice(1));
    return NextResponse.json(r, { status: r.ok ? 200 : 500 });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
