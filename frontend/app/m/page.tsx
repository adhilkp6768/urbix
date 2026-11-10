"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { apiGet } from "@/lib/api";
import { formatValue } from "@/lib/format";
import { domainAccent, depthLabel, statusTone } from "@/lib/tone";
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
  const [domainFilter, setDomainFilter] = useState<string>("all");
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
  const domainEntries = Object.entries(overview?.domains || {});
  const liveDomains = domainEntries.filter(([, domain]) => domain.availability === "available" || domain.availability === "partial");
  const kpis = domainEntries
    .filter(([name]) => domainFilter === "all" || name === domainFilter)
    .flatMap(([name, domain]) => (domain.kpis || []).map((kpi) => ({ ...kpi, domain: name })))
    .filter((kpi) => kpi.value !== null && kpi.value !== undefined)
    .slice(0, 8);
  const latest = mobile.freshness?.datasets.find((row) => row.status === "succeeded" && row.finished_at);

  return (
    <div
      className="h-full overflow-y-auto px-4"
      style={{ paddingTop: "0.75rem" }}
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

      <div className="rounded-[24px] border border-line bg-panel p-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-cyan">Pulse</p>
            <h1 className="font-display mt-1 text-3xl font-bold tracking-tight">{selected?.name || overview?.city?.name || "City"}</h1>
            <p className="mt-1 text-sm text-mist">Live from the last successful extract.</p>
          </div>
          {selected?.depth && <span className={`rounded-full border px-2 py-1 text-[10px] uppercase tracking-[0.12em] ${statusTone(selected.depth)}`}>{depthLabel(selected.depth)}</span>}
        </div>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-raised">
          <div className="h-full rounded-full bg-cyan" style={{ width: `${Math.min(100, ((selected?.domain_count || liveDomains.length) / 7) * 100)}%` }} />
        </div>
        <p className="mt-2 text-xs text-mist">{selected?.domain_count || liveDomains.length} official domains connected</p>
      </div>

      <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
        {mobile.cities.map((item) => (
          <button
            key={item.slug}
            type="button"
            onClick={() => mobile.setCity(item.slug)}
            className={`shrink-0 rounded-full border px-3 py-1.5 text-sm transition ${item.slug === mobile.city ? "border-cyan bg-cyan/15 text-cyan" : "border-line text-mist"}`}
          >
            {item.name}
          </button>
        ))}
      </div>

      <section className="mt-4 rounded-[24px] border border-line bg-panel p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-mist">Source refresh</p>
            <p className="mt-1 text-sm leading-5">
              {mobile.refreshing
                ? "Fetching sources now."
                : latest?.finished_at
                  ? `Last success ${new Date(latest.finished_at).toLocaleString()}.`
                  : "No successful extract recorded yet."}
            </p>
          </div>
          <button
            type="button"
            disabled={mobile.refreshing}
            onClick={() => mobile.refreshSources("current")}
            className="ui-btn-primary shrink-0 px-3 py-2 text-xs disabled:opacity-50"
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

      <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
        <button type="button" onClick={() => setDomainFilter("all")} className={`ui-chip ${domainFilter === "all" ? "ui-chip-active" : ""}`}>All</button>
        {liveDomains.map(([name]) => (
          <button key={name} type="button" onClick={() => setDomainFilter(name)} className={`ui-chip capitalize ${domainFilter === name ? "ui-chip-active" : ""}`}>
            {name}
          </button>
        ))}
      </div>

      {error && <p className="mt-4 text-sm text-bad">{error}</p>}
      {(overview?.availability === "unavailable" || overview?.availability === "reference") && (
        <p className="mt-4 text-sm text-mist">{overview.reason || "This city has no loaded extracts. Choose a city with coverage."}</p>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3 pb-4">
        {loading && <p className="col-span-2 text-sm text-mist">Loading indicators</p>}
        {!loading && kpis.length === 0 && !error && <p className="col-span-2 text-sm text-mist">Indicators appear when an extract is stored for this city.</p>}
        {kpis.map((kpi) => (
          <article key={`${kpi.domain}-${kpi.label}`} className="rounded-[22px] border border-line border-l-4 bg-panel p-3" style={{ borderLeftColor: domainAccent(kpi.domain) }}>
            <p className="min-h-8 text-[11px] uppercase leading-4 tracking-[0.12em] text-mist">{kpi.label}</p>
            <p className="mt-2 font-mono text-xl" style={{ color: domainAccent(kpi.domain) }}>{formatValue(kpi.value, kpi.unit)}</p>
            <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-mist">{kpi.domain}</p>
          </article>
        ))}
      </div>

      <div className="pb-8">
        <Link href="/m/explore" className="ui-btn-ghost w-full">Explore domains</Link>
      </div>
    </div>
  );
}
