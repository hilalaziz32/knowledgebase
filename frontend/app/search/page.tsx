import SearchPanel from "@/components/SearchPanel";

export default function SearchPage() {
  return (
    <main>
      <h1 className="mb-1 text-2xl font-semibold">Search the memory</h1>
      <p className="mb-5 text-sm text-muted">Semantic search across pains, calls, case studies, and copies.</p>
      <SearchPanel />
    </main>
  );
}
