"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet } from "@/lib/api";
import { formatValue } from "@/lib/format";
import { useMobile } from "@/components/mobile/AppFrame";

type Kpi = { label: string; value: number | string | null; unit?: string | null; availability?: string };
type Overview = {
  availability?: string;
  city?: { name?: string };
  reason?: string;
  domains?: Record<string, { availability?: string; kpis?: Kpi[]; limitations?: string[] }>;
};

export default function PulsePage() {
  const mobile = useMobile();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pull, setPull] = useState(0);
  const startY = useRef<number | null>(null);

  useEffect(() => {
    let stop = false;
    setError(null);
    setLoading(true);
    apiGet<Overview>(`/api/v1/cities/${mobile.city}/overview`)
      .then((data) => {
        if (!stop) setOverview(data);
      })
      .catch((reason) => {
        if (!stop) setError(reason instanceof Error ? reason.message : "Overview is unavailable.");
      })
      .finally(() => {
        if (!stop) setLoading(false);
      });
    return () => {
      stop = true;
    };
  }, [mobile.city, mobile.tick]);

  const selected = mobile.cities.find((item) => item.slug === mobile.city);
  const kpis = Object.values(overview?.domains || {}).flatMap((domain) => domain.kpis || []).filter((kpi) => kpi.value !== null && kpi.value !== undefined).slice(0, 6);
  const latest = mobile.freshness?.datasets.find((row) => row.status === "succeeded" && row.finished_at);

  return (
    <div
      className="h-full overflow-y-auto px-4"
      style={{ paddingTop: "max(1rem, env(safe-area-inset-top))" }}
      onTouchStart={(event) => {
        if (event.currentTarget.scrollTop <= 0) startY.current = event.touches[0].clientY;
      }}
      onTouchMove={(event) => {
        if (startY.current == null) return;
        setPull(Math.max(0, Math.min(96, event.touches[0].clientY - startY.current)));
      }}
      onTouchEnd={() => {
        if (pull > 64) mobile.reload();
        startY.current = null;
        setPull(0);
      }}
    >
      <div className="overflow-hidden text-center text-[11px] uppercase tracking-[0.16em] text-cyan" style={{ height: pull }}>
        {pull > 64 ? "Release to reload" : "Pull to reload"}
      </div>
      <p className="text-[11px] uppercase tracking-[0.22em] text-cyan">URBIX</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight">{selected?.name || overview?.city?.name || "City"}</h1>
      <p className="mt-1 text-sm text-mist">Evidence from the last successful extract. Missing values stay unavailable.</p>

      <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
        {mobile.cities.map((item) => (
          <button
            key={item.slug}
            type="button"
            onClick={() => mobile.setCity(item.slug)}
            className={`shrink-0 rounded-full border px-3 py-1.5 text-sm ${item.slug === mobile.city ? "border-cyan bg-cyan/15 text-cyan" : "border-line text-mist"}`}
          >
            {item.name}
          </button>
        ))}
      </div>

      <section className="mt-4 rounded-2xl border border-line bg-panel p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-mist">Source refresh</p>
            <p className="mt-1 text-sm">
              {mobile.refreshing
                ? "A cloud refresh is fetching sources now."
                : latest?.finished_at
                  ? `Last successful extract finished ${new Date(latest.finished_at).toLocaleString()}.`
                  : "No successful extract is recorded yet."}
            </p>
          </div>
          <button
            type="button"
            disabled={mobile.refreshing}
            onClick={() => mobile.refreshSources("current")}
            className="shrink-0 rounded-full bg-cyan px-3 py-2 text-xs font-semibold text-ink disabled:opacity-50"
          >
            {mobile.refreshing ? "Running" : "Refresh"}
          </button>
        </div>
        {mobile.refreshError && <p className="mt-2 text-sm text-bad">{mobile.refreshError}</p>}
        {mobile.refreshing && (
          <ul className="mt-3 space-y-1 text-xs text-mist">
            {mobile.freshness?.refresh.steps.slice(0, 6).map((step) => (
              <li key={step.dataset_code} className="flex justify-between gap-3">
                <span>{step.dataset_code}</span>
                <span className={step.status === "failed" ? "text-bad" : "text-cyan"}>{step.status}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {error && <p className="mt-4 text-sm text-bad">{error}</p>}
      {(overview?.availability === "unavailable" || overview?.availability === "reference") && (
        <p className="mt-4 text-sm text-mist">{overview.reason || "This city has no loaded extracts. Choose a city marked as loaded."}</p>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3 pb-6">
        {loading && <p className="col-span-2 text-sm text-mist">Loading indicators</p>}
        {!loading && kpis.length === 0 && !error && <p className="col-span-2 text-sm text-mist">Indicators will appear when an extract is stored for this city.</p>}
        {kpis.map((kpi) => (
          <article key={kpi.label} className="rounded-2xl border border-line bg-panel p-3">
            <p className="min-h-8 text-[11px] uppercase leading-4 tracking-[0.12em] text-mist">{kpi.label}</p>
            <p className="mt-2 font-mono text-xl text-cyan">{formatValue(kpi.value, kpi.unit)}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
