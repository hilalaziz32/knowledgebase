const API = "https://api.airtable.com/v0";

function token() {
  const t = process.env.AIRTABLE_API_KEY || process.env.AIRTABLE;
  if (!t) throw new Error("AIRTABLE_API_KEY not set");
  return t;
}
function baseId() {
  return process.env.AIRTABLE_BASE_ID || "appP3VJXaEqNopR1l";
}

export async function getRecord(table: string, id: string): Promise<Record<string, any>> {
  const res = await fetch(`${API}/${baseId()}/${encodeURIComponent(table)}/${id}`, {
    headers: { Authorization: `Bearer ${token()}` },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`airtable ${table}/${id}: ${res.status}`);
  const data = await res.json();
  return data.fields || {};
}

export async function listRecords(
  table: string,
  opts: { formula?: string; fields?: string[]; maxRecords?: number } = {}
): Promise<{ id: string; fields: Record<string, any> }[]> {
  const out: { id: string; fields: Record<string, any> }[] = [];
  let offset: string | undefined;
  do {
    const u = new URL(`${API}/${baseId()}/${encodeURIComponent(table)}`);
    if (opts.formula) u.searchParams.set("filterByFormula", opts.formula);
    if (opts.maxRecords) u.searchParams.set("maxRecords", String(opts.maxRecords));
    (opts.fields || []).forEach((f) => u.searchParams.append("fields[]", f));
    if (offset) u.searchParams.set("offset", offset);
    const res = await fetch(u, { headers: { Authorization: `Bearer ${token()}` }, cache: "no-store" });
    if (!res.ok) throw new Error(`airtable list ${table}: ${res.status}`);
    const data = await res.json();
    for (const r of data.records || []) out.push({ id: r.id, fields: r.fields || {} });
    offset = data.offset;
  } while (offset);
  return out;
}
