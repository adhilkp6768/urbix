"use client";
import { useApi } from "@/lib/useApi";
export default function Page() {
  const state = useApi<{ results: { id: string; method: string; summary: string; score?: number }[] }>("/api/v1/anomalies");
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading anomalies</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  return (
    <div className="space-y-2 p-4">
      <h1 className="text-lg font-semibold">Anomalies</h1>
      <p className="text-sm text-mist">Anomaly rows are created by a trained detector. None are invented when the detector has not run.</p>
      {(state.data?.results || []).map((row) => <article key={row.id} className="border border-line bg-panel p-3 text-sm">{row.method}: {row.summary}</article>)}
      {!state.data?.results.length && <p className="text-sm text-mist">No anomalies have been recorded.</p>}
    </div>
  );
}
