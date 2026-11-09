"use client";
import { useState } from "react";
import { apiPost } from "@/lib/api";
import { useApi } from "@/lib/useApi";

function describe(result: { status?: string; reason?: string; algorithm?: string }) {
  if (result.status === "withheld") return result.reason || "Training was withheld because the extract is too short.";
  if (result.status === "trained") return `Trained with ${result.algorithm || "the selected model"}.`;
  if (result.status === "completed") return "The environment runs finished. A withheld run stays listed with its reason.";
  return result.reason || result.status || "The run finished.";
}

export default function Page() {
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState("");
  const state = useApi<{ results: { name: string; horizon: string; status: string; algorithm: string; limitations: string; metrics: { name: string; value: number | null; baseline_name?: string; baseline_value?: number | null }[] }[] }>(`/api/v1/models?refresh=${revision}`);
  const [message, setMessage] = useState("");
  async function train(domain: string) {
    if (busy) return;
    setBusy(domain);
    setMessage(`Training ${domain}`);
    try {
      const result = await apiPost<{ status?: string; reason?: string; algorithm?: string; runs?: { status?: string; reason?: string; algorithm?: string }[] }>("/api/v1/predictions/run", { domain });
      const runs = result.runs?.map(describe).join(" ") || describe(result);
      setMessage(runs);
      setRevision((value) => value + 1);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Training failed");
    } finally {
      setBusy("");
    }
  }
  return (
    <div className="space-y-3 p-4">
      <div className="flex flex-wrap gap-2">
        {["traffic", "environment", "waste"].map((domain) => <button type="button" key={domain} onClick={() => train(domain)} disabled={Boolean(busy)} className="border border-line bg-panel px-3 py-1.5 text-sm capitalize disabled:opacity-50">{busy === domain ? "Training" : `Train ${domain}`}</button>)}
      </div>
      {message && <p className="text-sm text-mist">{message}</p>}
      {state.status === "loading" && <p className="text-sm text-mist">Loading models</p>}
      {state.status === "error" && <p className="text-sm text-bad">{state.error}</p>}
      {(state.data?.results || []).map((model) => (
        <article key={model.name + model.horizon} className="border border-line bg-panel p-3">
          <h2 className="font-medium">{model.name}</h2>
          <p className="text-xs text-mist">{model.algorithm} · {model.horizon} · {model.status}</p>
          <p className="mt-1 text-sm text-mist">{model.limitations}</p>
          <ul className="mt-2 text-sm">
            {model.metrics.map((metric) => <li key={metric.name}>{metric.name}: {metric.value ?? "not computed"} · baseline {metric.baseline_name || "none"} {metric.baseline_value ?? ""}</li>)}
          </ul>
        </article>
      ))}
      {state.status === "ready" && !state.data?.results.length && <p className="text-sm text-mist">No model has been trained. Training stays withheld when the extract is too short.</p>}
    </div>
  );
}
