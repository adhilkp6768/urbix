"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { formatValue } from "@/lib/format";
import { domainAccent, statusTone } from "@/lib/tone";
import { useApi } from "@/lib/useApi";

type Overview = {
  city: { name: string; integration_status: string; area_km2?: number; country_code?: string };
  availability?: string;
  domains: Record<string, { availability: string; kpis: { label: string; value: number | null; unit?: string; availability: string }[]; limitations: string[] }>;
};

const DOMAIN_HREF: Record<string, string> = {
  traffic: "/traffic",
  environment: "/environment",
  crime: "/crime",
  population: "/population",
  waste: "/waste",
  transport: "/transport",
  infrastructure: "/infrastructure",
};

export default function CityPage() {
  const params = useParams<{ cityId: string }>();
  const state = useApi<Overview>(`/api/v1/cities/${params.cityId}/overview`);
  const [focus, setFocus] = useState<string | null>(null);

  const data = state.data;
  const entries = useMemo(() => Object.entries(data?.domains || {}), [data]);
  const availableCount = entries.filter(([, payload]) => payload.availability === "available" || payload.availability === "partial").length;

  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading city</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  const city = data!;
  const loaded = city.city.integration_status === "partial" || city.city.integration_status === "integrated";
  const domains = entries.filter(([, payload]) => payload.kpis.some((item) => item.value !== null && item.value !== undefined));
  const active = focus && city.domains[focus] ? focus : domains[0]?.[0] || null;

  return (
    <div className="space-y-4 p-4 md:p-6">
      <section className="relative overflow-hidden rounded-[28px] border border-line bg-panel p-5 shadow-soft md:p-7">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(31,111,139,0.1),transparent_40%),radial-gradient(circle_at_bottom_right,rgba(154,123,79,0.08),transparent_36%)]" />
        <div className="relative flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-cyan">City intelligence</p>
            <h1 className="font-display mt-1 text-3xl font-bold md:text-4xl">{city.city.name}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-mist">
              {loaded ? "Stored extracts are shown below. A missing field stays blank." : "This city is registered. No extract has been loaded, so there are no indicators to show."}
              {city.city.area_km2 ? ` Area ${city.city.area_km2} km² from the stored boundary.` : ""}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className={`rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.12em] ${statusTone(city.availability || city.city.integration_status)}`}>
                {city.availability || city.city.integration_status}
              </span>
              <span className="ui-chip">{availableCount} / {entries.length} domains live</span>
              {city.city.country_code && <span className="ui-chip">{city.city.country_code}</span>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {loaded && <Link href={`/cities/${params.cityId}/map`} className="ui-btn-primary">Open map</Link>}
            <Link href={`/compare?left=${params.cityId}&right=nyc`} className="ui-btn-ghost">Compare</Link>
            <Link href={`/ai?city=${params.cityId}`} className="ui-btn-ghost">Ask AI</Link>
          </div>
        </div>
      </section>

      {!loaded && (
        <section className="ui-card p-5 text-sm text-mist">
          Weather and air readings appear after an Open-Meteo extract. Official traffic, safety, population, and transit extracts are loaded for selected cities.
          <div className="mt-4">
            <Link href="/" className="ui-btn-primary">Browse coverage</Link>
          </div>
        </section>
      )}

      {loaded && (
        <>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {entries.map(([domain, payload]) => (
              <button
                key={domain}
                type="button"
                onClick={() => setFocus(domain)}
                className={`shrink-0 rounded-full border px-3 py-1.5 text-sm capitalize transition ${
                  active === domain ? "border-cyan bg-cyan/15 text-cyan" : "border-line text-mist hover:border-cyan/40"
                }`}
              >
                {domain}
                <span className="ml-2 text-[10px] uppercase tracking-[0.12em] opacity-80">{payload.availability}</span>
              </button>
            ))}
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            {domains.map(([domain, payload]) => {
              const accent = domainAccent(domain);
              const emphasized = active === domain;
              return (
                <section
                  key={domain}
                  className={`ui-card border-l-4 p-4 transition ${emphasized ? "shadow-glow" : "opacity-95"}`}
                  style={{ borderLeftColor: accent }}
                  onMouseEnter={() => setFocus(domain)}
                >
                  <div className="mb-3 flex items-center justify-between gap-3">
                    {DOMAIN_HREF[domain] ? (
                      <Link href={`${DOMAIN_HREF[domain]}?city=${params.cityId}`} className="font-display text-base font-semibold capitalize hover:underline" style={{ color: accent }}>
                        {domain}
                      </Link>
                    ) : (
                      <h2 className="font-display text-base font-semibold capitalize" style={{ color: accent }}>{domain}</h2>
                    )}
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] ${statusTone(payload.availability)}`}>{payload.availability}</span>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-3">
                    {payload.kpis.filter((item) => item.value !== null && item.value !== undefined).slice(0, 3).map((item) => (
                      <div key={item.label} className="rounded-2xl bg-raised/80 px-3 py-2">
                        <div className="text-[11px] text-mist">{item.label}</div>
                        <div className="mt-1 font-mono text-lg text-paper">{formatValue(item.value, item.unit)}</div>
                      </div>
                    ))}
                  </div>
                  {payload.limitations?.[0] && <p className="mt-3 line-clamp-2 text-xs leading-5 text-mist">{payload.limitations[0]}</p>}
                </section>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
