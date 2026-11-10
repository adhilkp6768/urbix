"use client";

import { useEffect, useState } from "react";
import { SeriesChart } from "@/components/charts/SeriesChart";
import { apiGet } from "@/lib/api";
import { formatValue } from "@/lib/format";
import { domainAccent, statusTone } from "@/lib/tone";
import { useMobile } from "@/components/mobile/AppFrame";

const DOMAINS = [
  ["traffic", "Traffic", "/api/v1/traffic/trends"],
  ["environment", "Environment", "/api/v1/environment/trends"],
  ["transport", "Transit", "/api/v1/transport/analytics"],
  ["waste", "Waste", "/api/v1/waste/analytics"],
  ["crime", "Crime", "/api/v1/crime/analytics"],
  ["population", "Population", "/api/v1/population/analytics"],
  ["infrastructure", "Roads", "/api/v1/infrastructure/analytics"],
] as const;

type DomainPayload = {
  availability?: string;
  series_label?: string;
  series?: { name: string; value: number | null }[];
  kpis?: { label: string; value: number | string | null; unit?: string | null; period?: string | null }[];
  rankings?: { name: string; value: number | null; unit?: string }[];
  sources?: { code: string; name: string; license_name?: string | null }[];
  limitations?: string[];
  reason?: string;
};

export default function ExplorePage() {
  const mobile = useMobile();
  const [open, setOpen] = useState<string>("environment");
  const [payload, setPayload] = useState<DomainPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [panel, setPanel] = useState<"series" | "rank" | "notes">("series");

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

  const accent = domainAccent(open);
  const points = (payload?.series || []).filter((point) => point.value !== null) as { name: string; value: number }[];
  const ranked = (payload?.rankings || []).filter((row) => typeof row.value === "number").slice(0, 8) as { name: string; value: number; unit?: string }[];
  const top = ranked.length ? Math.max(...ranked.map((row) => row.value)) : 0;
  const period = (value?: string | null) => (value ? String(value).slice(0, 16).replace("T", " ") : "");

  return (
    <div className="h-full overflow-y-auto px-4" style={{ paddingTop: "0.75rem" }}>
      <p className="text-[11px] uppercase tracking-[0.2em] text-cyan">Explore</p>
      <h1 className="font-display mt-1 text-2xl font-bold">Domains</h1>
      <p className="mt-1 text-sm text-mist">Switch domains and inspect series, rankings, and source notes.</p>

      <div className="mt-4 flex gap-2 overflow-x-auto pb-2">
        {DOMAINS.map(([code, label]) => (
          <button
            key={code}
            type="button"
            onClick={() => setOpen(code)}
            className={`shrink-0 rounded-full border px-3 py-1.5 text-sm transition ${open === code ? "border-cyan bg-cyan/15 text-cyan" : "border-line text-mist"}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-2 flex items-center justify-between gap-3">
        <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] ${statusTone(payload?.availability || "unavailable")}`}>
          {payload?.availability || "loading"}
        </span>
        <div className="flex gap-1">
          {[
            ["series", "Series"],
            ["rank", "Rank"],
            ["notes", "Notes"],
          ].map(([id, label]) => (
            <button key={id} type="button" onClick={() => setPanel(id as typeof panel)} className={`rounded-full px-2.5 py-1 text-[11px] ${panel === id ? "bg-cyan/15 text-cyan" : "text-mist"}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-bad">{error}</p>}
      {payload?.availability === "unavailable" && (
        <section className="mt-3 rounded-[24px] border border-line bg-panel p-4">
          <p className="text-sm font-medium text-paper">Unavailable for this city</p>
          <p className="mt-1 text-sm leading-6 text-mist">{payload.reason || payload.limitations?.[0] || "No verified source is connected."}</p>
        </section>
      )}

      {payload?.availability !== "unavailable" && (
        <>
          {panel === "series" && (
            <section className="mt-3 rounded-[24px] border border-line bg-panel p-3">
              <p className="text-sm text-mist">{payload?.series_label || "Series"}</p>
              {points.length > 0 ? <SeriesChart points={points} color={accent} /> : <p className="py-8 text-sm text-mist">No time series is available for this selection.</p>}
            </section>
          )}
          <div className="mt-3 grid grid-cols-2 gap-2">
            {(payload?.kpis || []).map((kpi) => (
              <div key={kpi.label} className="rounded-[22px] border border-line border-l-4 bg-panel px-3 py-3" style={{ borderLeftColor: accent }}>
                <p className="text-[11px] leading-4 text-mist">{kpi.label}</p>
                <p className="mt-1 font-mono text-base" style={{ color: accent }}>{formatValue(kpi.value, kpi.unit)}</p>
                {kpi.period && <p className="mt-0.5 text-[10px] text-mist">{period(kpi.period)}</p>}
              </div>
            ))}
          </div>
          {panel === "rank" && ranked.length > 0 && (
            <section className="mt-3 rounded-[24px] border border-line bg-panel p-3">
              <p className="text-sm text-mist">Top {ranked.length}{ranked[0].unit ? ` · ${ranked[0].unit}` : ""}</p>
              <div className="mt-2 space-y-2">
                {ranked.map((row) => (
                  <div key={row.name}>
                    <div className="flex justify-between gap-2 text-xs">
                      <span className="truncate text-paper">{row.name}</span>
                      <span className="font-mono text-cyan">{row.value.toLocaleString(undefined, { maximumFractionDigits: 1 })}</span>
                    </div>
                    <div className="mt-1 h-1.5 rounded-full bg-white/5">
                      <div className="h-1.5 rounded-full" style={{ width: `${top ? Math.max(4, (100 * row.value) / top) : 0}%`, background: accent }} />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
          {panel === "notes" && (
            <div className="mt-3 space-y-2 pb-2">
              {(payload?.limitations || []).slice(0, 4).map((item) => (
                <p key={item} className="rounded-[18px] border border-line bg-panel px-3 py-2 text-xs leading-5 text-mist">{item}</p>
              ))}
              {(payload?.sources || []).length > 0 && (
                <p className="text-[11px] leading-5 text-mist">
                  Sources: {(payload?.sources || []).map((source) => `${source.name}${source.license_name ? ` (${source.license_name})` : ""}`).join(" · ")}
                </p>
              )}
            </div>
          )}
        </>
      )}
      <div className="h-8" />
    </div>
  );
}
