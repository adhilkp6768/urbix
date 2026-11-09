"use client";
import { useApi } from "@/lib/useApi";
export default function Page() {
  const state = useApi<{ sources: { code: string; name: string; provider: string; access_mode: string }[]; datasets: { code: string; name: string; availability: string; limitations: string; endpoint_url?: string }[] }>("/api/v1/data-sources");
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading the catalog</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  return (
    <div className="space-y-3 p-4">
      <h1 className="text-lg font-semibold">Data sources</h1>
      <div className="grid gap-2 md:grid-cols-2">
        {(state.data?.datasets || []).map((dataset) => (
          <article key={dataset.code} className="border border-line bg-panel p-3 text-sm">
            <div className="font-medium">{dataset.name}</div>
            <div className="font-mono text-[11px] text-cyan">{dataset.code} · {dataset.availability}</div>
            <p className="mt-1 text-mist">{dataset.limitations}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
