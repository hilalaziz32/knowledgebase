import { Pool } from "pg";

// One shared pool across hot-reloads in dev.
declare global {
  // eslint-disable-next-line no-var
  var _evergreenPool: Pool | undefined;
}

function makePool() {
  const url = process.env.SUPABASE_DB_URL;
  if (!url) throw new Error("SUPABASE_DB_URL is not set in frontend/.env.local");
  return new Pool({
    connectionString: url,
    ssl: { rejectUnauthorized: false }, // Supabase pooler requires SSL
    max: 5,
  });
}

export function pool(): Pool {
  if (!global._evergreenPool) global._evergreenPool = makePool();
  return global._evergreenPool;
}

export async function q<T = any>(text: string, params: any[] = []): Promise<T[]> {
  const res = await pool().query(text, params);
  return res.rows as T[];
}

export async function one<T = any>(text: string, params: any[] = []): Promise<T | null> {
  const rows = await q<T>(text, params);
  return rows[0] ?? null;
}
