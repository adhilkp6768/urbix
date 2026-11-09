"use client";
import { useApi } from "@/lib/useApi";

export default function Page() {
  const state = useApi<{ results: { id: string; name: string; status: string; horizon: string; algorithm: string; limitations: string; metrics: { name: string; value: number | null; baseline_value?: number | null }[] }[] }>("/api/v1/models");
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading the model registry</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  return (
    <div className="space-y-2 p-4">
      <h1 className="text-lg font-semibold">Model registry</h1>
      {(state.data?.results || []).map((model) => (
        <article key={model.id} className="border border-line bg-panel p-3 text-sm">
          <div className="font-medium">{model.name}</div>
          <div className="text-xs text-mist">{model.status} · {model.algorithm} · {model.horizon}</div>
          <p className="mt-1 text-mist">{model.limitations}</p>
          {model.metrics.map((metric) => <p key={metric.name}>{metric.name}: {metric.value ?? "not computed"} (baseline {metric.baseline_value ?? "n/a"})</p>)}
        </article>
      ))}
      {!state.data?.results.length && <p className="text-sm text-mist">The registry is empty. Use Predictions to train against the loaded extract.</p>}
    </div>
  );
}
