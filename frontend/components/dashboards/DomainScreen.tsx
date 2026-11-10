"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { SeriesChart } from "@/components/charts/SeriesChart";
import { formatValue } from "@/lib/format";
import { domainAccent, statusTone } from "@/lib/tone";
import { useApi } from "@/lib/useApi";

type Kpi = { label: string; value: number | string | null; unit?: string; methodology?: string; availability: string; dataset_code?: string; period?: string };
type Payload = {
  availability?: string;
  kpis?: Kpi[];
  rankings?: { name: string; value: number | null; unit?: string }[];
  series?: { name: string; value: number | null }[];
  series_label?: string;
  limitations?: string[];
  sources?: { code: string; name: string; limitations?: string }[];
  note?: string;
  reason?: string;
};

export function DomainScreen({ title, path, detail }: { title: string; path: string; detail?: string }) {
  const city = useSearchParams().get("city") || "nyc";
  const request = path.includes("city=") ? path : `${path}${path.includes("?") ? "&" : "?"}city=${encodeURIComponent(city)}`;
  const accent = domainAccent(title);
  const state = useApi<Payload>(request);
  const [tab, setTab] = useState<"chart" | "ranking" | "sources">("chart");
  const [selectedKpi, setSelectedKpi] = useState<string | null>(null);

  const data = state.data || {};
  const kpis = data.kpis || [];
  const series = useMemo(() => (data.series || []).filter((point) => point.value !== null), [data.series]);
  const chartPoints = series.length ? series : (data.rankings || []).filter((row) => row.value !== null).map((row) => ({ name: row.name, value: row.value }));
  const chartLabel = data.series_label || (series.length ? "Series" : "Ranking");
  const active = kpis.find((item) => item.label === selectedKpi) || kpis[0];
  const ranked = (data.rankings || []).filter((row) => typeof row.value === "number") as { name: string; value: number; unit?: string }[];
  const top = ranked.length ? Math.max(...ranked.map((row) => row.value)) : 0;

  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading {title}</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">Could not load {title}. {state.error}</p>;

  return (
    <div className="space-y-4 p-4 md:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-3xl">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-2xl font-bold md:text-3xl" style={{ color: accent }}>{title}</h1>
            <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] ${statusTone(data.availability || "unavailable")}`}>{data.availability || "unavailable"}</span>
          </div>
          <p className="mt-2 text-sm leading-6 text-mist">{detail || "Indicators appear only when a verified extract is stored. Missing measurements stay unavailable."}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href={`/cities/${city}`} className="ui-btn-ghost text-xs">City overview</Link>
          <Link href={`/cities/${city}/map`} className="ui-btn-primary text-xs">Open map</Link>
        </div>
      </div>

      {!kpis.length && (
        <div className="ui-card p-5 text-sm text-mist">
          {data.reason || data.limitations?.[0] || "No indicators are loaded for this domain yet."}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((item) => {
          const selected = (active?.label || "") === item.label;
          return (
            <button
              key={item.label}
              type="button"
              onClick={() => setSelectedKpi(item.label)}
              className={`ui-card border-l-4 p-4 text-left transition hover:-translate-y-0.5 ${selected ? "shadow-glow" : ""}`}
              style={{ borderLeftColor: accent }}
            >
              <div className="text-[10px] uppercase tracking-[0.14em] text-mist">{item.label}</div>
              <div className={`mt-2 font-mono text-2xl ${item.availability === "available" ? "text-paper" : "text-mist"}`}>{formatValue(item.value, item.unit)}</div>
              <p className="mt-2 line-clamp-2 text-[11px] leading-4 text-mist">{item.methodology}</p>
              <p className="mt-2 font-mono text-[10px] text-cyan/80">{item.dataset_code}{item.period ? ` · ${item.period}` : ""}</p>
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-2">
        {[
          ["chart", chartLabel],
          ["ranking", "Ranking"],
          ["sources", "Sources & limits"],
        ].map(([id, label]) => (
          <button key={id} type="button" onClick={() => setTab(id as typeof tab)} className={`ui-chip ${tab === id ? "ui-chip-active" : ""}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === "chart" && (
        <section className="ui-card p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-[11px] uppercase tracking-[0.14em] text-mist">{chartLabel}</h2>
            {active && <span className="text-xs text-mist">Focus: {active.label}</span>}
          </div>
          <SeriesChart points={chartPoints as { name: string; value: number | null }[]} color={accent} />
        </section>
      )}

      {tab === "ranking" && (
        <section className="ui-card p-4">
          <h2 className="mb-3 text-[11px] uppercase tracking-[0.14em] text-mist">Ranking</h2>
          <div className="space-y-3">
            {ranked.slice(0, 12).map((row) => (
              <div key={row.name}>
                <div className="mb-1 flex justify-between gap-3 text-sm">
                  <span className="truncate">{row.name}</span>
                  <span className="font-mono text-cyan">{formatValue(row.value, row.unit)}</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-raised">
                  <div className="h-full rounded-full" style={{ width: `${top ? Math.max(6, (100 * row.value) / top) : 0}%`, background: accent }} />
                </div>
              </div>
            ))}
            {!ranked.length && <p className="text-sm text-mist">No ranking is available.</p>}
          </div>
        </section>
      )}

      {tab === "sources" && (
        <section className="ui-card space-y-3 p-4 text-sm text-mist">
          {(data.limitations || []).map((item) => <p key={item} className="leading-6">{item}</p>)}
          {(data.sources || []).map((source) => (
            <p key={source.code} className="leading-6">
              <span className="text-cyan">{source.code}</span> — {source.name}. {source.limitations}
            </p>
          ))}
          {!data.limitations?.length && !data.sources?.length && <p>No source notes are attached to this view.</p>}
        </section>
      )}
    </div>
  );
}
