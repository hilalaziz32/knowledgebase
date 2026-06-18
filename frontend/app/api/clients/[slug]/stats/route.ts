import { NextResponse } from "next/server";
import { one } from "@/lib/db";
import { getRecord, listRecords } from "@/lib/airtable";

export const dynamic = "force-dynamic";

const num = (v: any) => (typeof v === "number" ? v : Number(v) || 0);

function periodBlock(f: Record<string, any>, suffix: string) {
  const smsSent = num(f[`SMS Sent ${suffix}`]);
  const emailSent = num(f[`Emails Sent ${suffix}`]);
  return {
    sent: { sms: smsSent, email: emailSent, total: smsSent + emailSent },
    positives: {
      sms: num(f[`SMS Positive Replies ${suffix}`]),
      email: num(f[`Email Positive Replies ${suffix}`]),
      total: num(f[`Total Positive Replies ${suffix}`]),
    },
    booked: {
      sms: num(f[`SMS Meetings Booked ${suffix}`]),
      email: num(f[`Email Meetings Booked ${suffix}`]),
      total: num(f[`Total Meetings Booked ${suffix}`]),
    },
    conversion: f[`Total Conversion Rate ${suffix}`] || "—",
  };
}

export async function GET(_req: Request, { params }: { params: { slug: string } }) {
  try {
    const client = await one<any>(
      `select airtable_client_id, client from client_roster where slug=$1`,
      [params.slug]
    );
    if (!client?.airtable_client_id)
      return NextResponse.json({ error: "no airtable id on client" }, { status: 404 });

    const f = await getRecord("📂 Clients", client.airtable_client_id);

    const stats = {
      retainer: num(f["Retainer"]),
      accountManager: (f["Account Manager"] || []).join?.(", ") || f["Account Manager"] || "—",
      status: f["Client Status"] || "—",
      onboardingDate: f["Client Onboarding Date"] || null,
      domain: f["Domain"] || null,
      activeCampaigns: { sms: num(f["Active Campaigns (SMS)"]), email: num(f["Active Campaigns (Email)"]) },
      leadsRemaining: { sms: num(f["Leads Remaining (SMS)"]), email: num(f["Leads Remaining (Email)"]) },
      periods: {
        "This Week": periodBlock(f, "This Week"),
        "This Month": periodBlock(f, "This Calendar Month"),
        "All Time": periodBlock(f, "All Time"),
      },
      kpi: {
        weeklyBooked: num(f["KPI - Weekly Meetings Booked"]),
        monthlyBooked: num(f["KPI - Monthly Meetings Booked"]),
        weeklyPositives: num(f["KPI - Weekly Positive Replies"] ?? f["KPI - Total Weekly Positive Replies"]),
      },
    };

    // per-campaign stats (one filtered list call, not 60 gets)
    const name = client.client?.replace(/'/g, "\\'");
    let campaigns: any[] = [];
    try {
      const recs = await listRecords("📢 Campaigns", {
        formula: `FIND('${name}', ARRAYJOIN({📂 Clients}))`,
        fields: [
          "Name", "Campaign Type", "Campaign Status", "Total Leads", "Completed Leads",
          "Completion Rate", "Emails Sent", "Email Replies", "Leads Remaining",
        ],
        maxRecords: 200,
      });
      campaigns = recs.map((r) => ({
        id: r.id,
        name: r.fields["Name"],
        type: r.fields["Campaign Type"],
        status: r.fields["Campaign Status"] || "—",
        totalLeads: num(r.fields["Total Leads"]),
        completed: num(r.fields["Completed Leads"]),
        completion: r.fields["Completion Rate"] != null ? Math.round(num(r.fields["Completion Rate"]) * 100) : null,
        emailsSent: num(r.fields["Emails Sent"]),
        emailReplies: num(r.fields["Email Replies"]),
        leadsRemaining: num(r.fields["Leads Remaining"]),
      }));
      campaigns.sort((a, b) => b.completed - a.completed);
    } catch {
      // leave campaigns empty if the formula/field lookup fails
    }

    return NextResponse.json({ stats, campaigns });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
