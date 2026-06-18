"use client";

export type RunState = {
  loading: boolean;
  output: string | null;
  ok: boolean | null;
};

export const idle: RunState = { loading: false, output: null, ok: null };

export function Console({ state }: { state: RunState }) {
  if (!state.loading && state.output === null) return null;
  return (
    <pre
      className={`mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border p-3 text-xs ${
        state.ok === false ? "border-red-500/40 text-red-300" : "border-edge text-slate-300"
      }`}
    >
      {state.loading ? "running agent…" : state.output}
    </pre>
  );
}

export async function postAgent(url: string, body: unknown): Promise<RunState> {
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) return { loading: false, ok: false, output: data.error || data.output || "failed" };
    return { loading: false, ok: data.ok ?? true, output: data.output || "done." };
  } catch (e: any) {
    return { loading: false, ok: false, output: e.message };
  }
}
