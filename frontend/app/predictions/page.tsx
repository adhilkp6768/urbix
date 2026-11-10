"use client";

import { useState } from "react";
import Link from "next/link";
import { apiPost } from "@/lib/api";
import { statusTone } from "@/lib/tone";
import { useApi } from "@/lib/useApi";

function describe(result: { status?: string; reason?: string; algorithm?: string }) {
  if (result.status === "withheld") return result.reason || "Training was withheld because the extract is too short.";
  if (result.status === "trained") return `Trained with ${result.algorithm || "the selected model"}.`;
  if (result.status === "completed") return "The environment runs finished. A withheld run stays listed with its reason.";
  return result.reason || result.status || "The run finished.";
}

const DOMAINS = [
  { id: "traffic", label: "Traffic", blurb: "Volume and crash-count series where connected." },
  { id: "environment", label: "Environment", blurb: "Air and weather extracts with enough history." },
  { id: "waste", label: "Waste", blurb: "Municipal tonnage where a feed exists." },
];

export default function Page() {
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState("");
  const state = useApi<{ results: { name: string; horizon: string; status: string; algorithm: string; limitations: string; metrics: { name: string; value: number | null; baseline_name?: string; baseline_value?: number | null }[] }[] }>(`/api/v1/models?refresh=${revision}`);
  const [message, setMessage] = useState("");

  async function train(domain: string) {
    if (busy) return;
    setBusy(domain);
    setMessage(`Training ${domain}…`);
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
    <div className="space-y-5 p-4 md:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-cyan">Predictions</p>
          <h1 className="font-display text-3xl font-bold">Train against loaded extracts</h1>
          <p className="mt-2 max-w-2xl text-sm text-mist">Training stays withheld when a series is too short. Successful runs appear in the model registry.</p>
        </div>
        <Link href="/models" className="ui-btn-ghost">Open registry</Link>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {DOMAINS.map((domain) => (
          <button
            key={domain.id}
            type="button"
            onClick={() => train(domain.id)}
            disabled={Boolean(busy)}
            className="ui-card p-4 text-left transition hover:-translate-y-0.5 hover:border-cyan/50 disabled:opacity-50"
          >
            <div className="font-display text-lg font-semibold">{domain.label}</div>
            <p className="mt-2 text-sm text-mist">{domain.blurb}</p>
            <div className="mt-4 text-sm font-semibold text-cyan">{busy === domain.id ? "Training…" : "Train now"}</div>
          </button>
        ))}
      </div>

      {message && <div className="ui-card border-cyan/30 p-4 text-sm text-paper">{message}</div>}
      {state.status === "loading" && <p className="text-sm text-mist">Loading models</p>}
      {state.status === "error" && <p className="text-sm text-bad">{state.error}</p>}

      <div className="grid gap-3 lg:grid-cols-2">
        {(state.data?.results || []).map((model) => (
          <article key={model.name + model.horizon} className="ui-card p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="font-display text-lg font-semibold">{model.name}</h2>
                <p className="mt-1 text-xs text-mist">{model.algorithm} · {model.horizon}</p>
              </div>
              <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] ${statusTone(model.status)}`}>{model.status}</span>
            </div>
            <p className="mt-3 text-sm leading-6 text-mist">{model.limitations}</p>
            <ul className="mt-3 space-y-1 text-sm">
              {model.metrics.map((metric) => (
                <li key={metric.name} className="flex justify-between gap-3 rounded-xl bg-raised/70 px-3 py-2">
                  <span className="text-mist">{metric.name}</span>
                  <span className="font-mono text-paper">{metric.value ?? "not computed"}</span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>

      {state.status === "ready" && !state.data?.results.length && (
        <div className="ui-card p-5 text-sm text-mist">No model has been trained yet. Pick a domain above to start.</div>
      )}
    </div>
  );
}
