"use client";

import Link from "next/link";
import { statusTone } from "@/lib/tone";
import { useApi } from "@/lib/useApi";

type Model = {
  id: string;
  name: string;
  status: string;
  horizon: string;
  algorithm: string;
  limitations: string;
  metrics: { name: string; value: number | null; baseline_value?: number | null }[];
};

export default function Page() {
  const state = useApi<{ results: Model[] }>("/api/v1/models");
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading the model registry</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  const models = state.data?.results || [];

  return (
    <div className="space-y-5 p-4 md:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-cyan">Forecasting</p>
          <h1 className="font-display text-3xl font-bold">Model registry</h1>
          <p className="mt-2 max-w-2xl text-sm text-mist">Trained models stay tied to the loaded extract. Metrics appear only after a successful run from Predictions.</p>
        </div>
        <Link href="/predictions" className="ui-btn-primary">Train models</Link>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {models.map((model) => {
          const primary = model.metrics[0];
          return (
            <article key={model.id} className="ui-card p-4 transition hover:border-cyan/40">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-display text-lg font-semibold">{model.name}</h2>
                  <p className="mt-1 text-xs text-mist">{model.algorithm} · {model.horizon}</p>
                </div>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] ${statusTone(model.status)}`}>{model.status}</span>
              </div>
              <p className="mt-3 text-sm leading-6 text-mist">{model.limitations}</p>
              {primary && (
                <div className="mt-4 rounded-2xl bg-raised/80 p-3">
                  <div className="text-[10px] uppercase tracking-[0.14em] text-mist">{primary.name}</div>
                  <div className="mt-1 flex items-end justify-between gap-3">
                    <div className="font-mono text-2xl text-cyan">{primary.value ?? "n/a"}</div>
                    <div className="text-xs text-mist">baseline {primary.baseline_value ?? "n/a"}</div>
                  </div>
                </div>
              )}
              {model.metrics.length > 1 && (
                <ul className="mt-3 space-y-1 text-sm text-mist">
                  {model.metrics.slice(1).map((metric) => (
                    <li key={metric.name} className="flex justify-between gap-3">
                      <span>{metric.name}</span>
                      <span className="font-mono text-paper">{metric.value ?? "not computed"}</span>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          );
        })}
      </div>

      {!models.length && (
        <div className="ui-card p-6 text-sm text-mist">
          The registry is empty. Open <Link href="/predictions" className="text-cyan underline">Predictions</Link> and train against a loaded extract.
        </div>
      )}
    </div>
  );
}
