import Link from "next/link";
import { notFound } from "next/navigation";
import { one } from "@/lib/db";
import CopyManager from "@/components/CopyManager";

export const dynamic = "force-dynamic";

export default async function CopyPage({ params }: { params: { slug: string } }) {
  const client = await one<any>(`select slug, client from client_roster where slug=$1`, [params.slug]);
  if (!client) notFound();
  return (
    <main>
      <Link href={`/clients/${params.slug}`} className="text-xs text-muted hover:text-accent">← {client.client}</Link>
      <h1 className="mb-1 mt-2 text-2xl font-semibold">Copy — {client.client}</h1>
      <p className="mb-5 text-sm text-muted">Write a copy, save it to Evergreen, and link it to a synced campaign.</p>
      <CopyManager slug={params.slug} />
    </main>
  );
}
