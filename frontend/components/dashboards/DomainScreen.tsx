"use client";

import { useSearchParams } from "next/navigation";
import { SeriesChart } from "@/components/charts/SeriesChart";
import { formatValue } from "@/lib/format";
import { domainAccent } from "@/lib/tone";
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
};

export function DomainScreen({ title, path, detail }: { title: string; path: string; detail?: string }) {
  const city = useSearchParams().get("city") || "nyc";
  const request = path.includes("city=") ? path : `${path}${path.includes("?") ? "&" : "?"}city=${encodeURIComponent(city)}`;
  const accent = domainAccent(title);
  const state = useApi<Payload>(request);
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading {title}</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">Could not load {title}. {state.error}</p>;
  const data = state.data || {};
  const kpis = data.kpis || [];
  const series = (data.series || []).filter((point) => point.value !== null);
  const chartPoints = series.length ? series : (data.rankings || []).filter((row) => row.value !== null).map((row) => ({ name: row.name, value: row.value }));
  const chartLabel = data.series_label || (series.length ? "Series" : "Ranking");
  return (
    <div className="space-y-3 p-4">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: accent }}>{title}</h1>
        <p className="max-w-3xl text-sm text-mist">{detail || "Indicators appear only when a verified extract is stored. Missing measurements stay unavailable."}</p>
      </div>
      {!kpis.length && <p className="border border-line bg-panel p-4 text-sm text-mist">No indicators are loaded for this domain yet.</p>}
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {kpis.map((item) => (
          <article key={item.label} className="border border-line border-l-4 bg-panel p-3" style={{ borderLeftColor: accent }}>
            <div className="text-[10px] uppercase tracking-[0.14em] text-mist">{item.label}</div>
            <div className={`mt-2 font-mono text-xl ${item.availability === "available" ? "text-paper" : "text-mist"}`}>{formatValue(item.value, item.unit)}</div>
            <p className="mt-2 text-[11px] leading-4 text-mist">{item.methodology}</p>
            <p className="mt-1 font-mono text-[10px] text-cyan/80">{item.dataset_code} {item.period ? `· ${item.period}` : ""}</p>
          </article>
        ))}
      </div>
      <div className="grid gap-3 lg:grid-cols-[1.4fr_0.8fr]">
        <section className="border border-line bg-panel p-3">
          <h2 className="mb-2 text-[11px] uppercase tracking-[0.14em] text-mist">{chartLabel}</h2>
          <SeriesChart points={chartPoints as { name: string; value: number | null }[]} />
        </section>
        <section className="border border-line bg-panel p-3">
          <h2 className="mb-2 text-[11px] uppercase tracking-[0.14em] text-mist">Ranking</h2>
          <ul className="space-y-1">
            {(data.rankings || []).slice(0, 10).map((row) => (
              <li key={row.name} className="flex justify-between gap-3 text-sm">
                <span className="truncate">{row.name}</span>
                <span className="font-mono text-cyan">{formatValue(row.value, row.unit)}</span>
              </li>
            ))}
            {!data.rankings?.length && <li className="text-sm text-mist">No ranking is available.</li>}
          </ul>
        </section>
      </div>
      <section className="border border-line bg-panel p-3 text-sm text-mist">
        {(data.limitations || []).map((item) => <p key={item}>{item}</p>)}
        {(data.sources || []).map((source) => <p key={source.code} className="mt-1"><span className="text-cyan">{source.code}</span> — {source.limitations}</p>)}
      </section>
    </div>
  );
}
