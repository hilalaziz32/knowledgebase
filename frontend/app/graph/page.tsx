import GraphView from "@/components/GraphView";

export default function GraphPage() {
  return (
    <main className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Knowledge graph</h1>
        <p className="text-sm text-muted">
          How every client connects through its niche. Clients in the same niche share one
          niche-knowledge brain — new clients auto-attach to it.
        </p>
      </div>
      <GraphView />
    </main>
  );
}
