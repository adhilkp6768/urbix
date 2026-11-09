"use client";

import { useEffect, useState } from "react";
import { SeriesChart } from "@/components/charts/SeriesChart";
import { apiGet } from "@/lib/api";
import { formatValue } from "@/lib/format";
import { useMobile } from "@/components/mobile/AppFrame";

const DOMAINS = [
  ["traffic", "Traffic", "/api/v1/traffic/trends"],
  ["environment", "Environment", "/api/v1/environment/trends"],
  ["transport", "Transit", "/api/v1/transport/analytics"],
  ["waste", "Waste", "/api/v1/waste/analytics"],
  ["crime", "Crime", "/api/v1/crime/analytics"],
  ["population", "Population", "/api/v1/population/analytics"],
] as const;

type DomainPayload = {
  availability?: string;
  series_label?: string;
  series?: { name: string; value: number | null }[];
  kpis?: { label: string; value: number | string | null; unit?: string | null }[];
  limitations?: string[];
};

export default function ExplorePage() {
  const mobile = useMobile();
  const [open, setOpen] = useState<string>("traffic");
  const [payload, setPayload] = useState<DomainPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const domain = DOMAINS.find((item) => item[0] === open);
    if (!domain) return;
    let stop = false;
    setError(null);
    apiGet<DomainPayload>(`${domain[2]}?city=${mobile.city}`)
      .then((data) => {
        if (!stop) setPayload(data);
      })
      .catch((reason) => {
        if (!stop) setError(reason instanceof Error ? reason.message : "This domain is unavailable.");
      });
    return () => {
      stop = true;
    };
  }, [open, mobile.city, mobile.tick]);

  const points = (payload?.series || []).filter((point) => point.value !== null) as { name: string; value: number }[];

  return (
    <div className="h-full overflow-y-auto px-4" style={{ paddingTop: "max(1rem, env(safe-area-inset-top))" }}>
      <p className="text-[11px] uppercase tracking-[0.22em] text-cyan">Explore</p>
      <h1 className="mt-1 text-2xl font-semibold">Domains</h1>
      <div className="mt-4 flex gap-2 overflow-x-auto pb-2">
        {DOMAINS.map(([code, label]) => (
          <button key={code} type="button" onClick={() => setOpen(code)} className={`shrink-0 rounded-full border px-3 py-1.5 text-sm ${open === code ? "border-cyan bg-cyan/15 text-cyan" : "border-line text-mist"}`}>
            {label}
          </button>
        ))}
      </div>
      {error && <p className="mt-3 text-sm text-bad">{error}</p>}
      <section className="mt-3 rounded-2xl border border-line bg-panel p-3">
        <p className="text-sm text-mist">{payload?.series_label || "Series"}</p>
        {points.length > 0 ? <SeriesChart points={points} /> : <p className="py-8 text-sm text-mist">No time series is available for this selection.</p>}
      </section>
      <div className="mt-3 space-y-2 pb-8">
        {(payload?.kpis || []).slice(0, 4).map((kpi) => (
          <div key={kpi.label} className="flex items-center justify-between gap-3 rounded-2xl border border-line bg-panel px-3 py-3">
            <span className="text-sm text-mist">{kpi.label}</span>
            <span className="font-mono text-sm text-cyan">{formatValue(kpi.value, kpi.unit)}</span>
          </div>
        ))}
        {(payload?.limitations || []).slice(0, 2).map((item) => (
          <p key={item} className="text-xs leading-5 text-mist">{item}</p>
        ))}
      </div>
    </div>
  );
}
