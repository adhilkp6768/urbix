"use client";
import { useApi } from "@/lib/useApi";
export default function Page() {
  const state = useApi<{ results: { id: string; severity: string; title: string; detail: string; dataset_code?: string }[] }>("/api/v1/alerts");
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading alerts</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  return (
    <div className="space-y-2 p-4">
      <h1 className="text-lg font-semibold">Alerts</h1>
      {(state.data?.results || []).map((row) => (
        <article key={row.id} className="border border-line bg-panel p-3">
          <div className="text-xs uppercase tracking-wider text-warn">{row.severity}</div>
          <h2 className="text-sm font-medium">{row.title}</h2>
          <p className="text-sm text-mist">{row.detail}</p>
        </article>
      ))}
      {!state.data?.results.length && <p className="text-sm text-mist">No alerts. Low-speed alerts appear only after a traffic-speed snapshot is stored.</p>}
    </div>
  );
}
