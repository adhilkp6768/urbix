"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { depthLabel, statusTone } from "@/lib/tone";
import { useApi } from "@/lib/useApi";

type City = {
  slug: string;
  name: string;
  integration_status: string;
  country_code?: string;
  depth?: string;
  domain_count?: number;
  domains?: string[];
  has_weather?: boolean;
};

type World = {
  availability: string;
  countries: number;
  cities_referenced: number;
  cities_with_data: number;
  cities_with_broad_extracts?: number;
  note: string;
  cities: City[];
};

const FILTERS = [
  { id: "all", label: "All" },
  { id: "deep", label: "Deep" },
  { id: "broad", label: "Multi-domain" },
  { id: "weather", label: "Weather only" },
  { id: "reference", label: "Reference" },
] as const;

export default function GlobalPage() {
  const state = useApi<World>("/api/v1/geography/world");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["id"]>("all");
  const cities = state.data?.cities || [];
  const filtered = useMemo(() => {
    return cities
      .filter((city) => {
        const depth = city.depth || (city.integration_status === "partial" || city.integration_status === "integrated" ? "thin" : "reference");
        if (filter === "all") return true;
        if (filter === "deep") return depth === "deep";
        if (filter === "broad") return depth === "broad" || depth === "deep";
        if (filter === "weather") return depth === "weather" || depth === "thin";
        return depth === "reference";
      })
      .sort((a, b) => (b.domain_count || 0) - (a.domain_count || 0) || a.name.localeCompare(b.name));
  }, [cities, filter]);

  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading the geographical registry</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  const data = state.data!;

  return (
    <div className="space-y-5 p-4 md:p-6">
      <section className="relative overflow-hidden rounded-[28px] border border-line bg-panel p-5 shadow-soft md:p-8">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(31,111,139,0.12),transparent_42%),radial-gradient(circle_at_bottom_left,rgba(154,123,79,0.08),transparent_40%)]" />
        <div className="relative max-w-3xl">
          <p className="text-[11px] uppercase tracking-[0.2em] text-cyan">Global intelligence</p>
          <h1 className="font-display mt-2 text-3xl font-bold tracking-tight md:text-4xl">Evidence by city, not a blended world score</h1>
          <p className="mt-3 text-sm leading-6 text-mist md:text-base">{data.note}</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link href="/cities/nyc" className="ui-btn-primary">Open New York</Link>
            <Link href="/compare" className="ui-btn-ghost">Compare cities</Link>
            <Link href="/m" className="ui-btn-ghost">Phone view</Link>
          </div>
        </div>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Countries" value={data.countries} />
        <Stat label="Cities referenced" value={data.cities_referenced} />
        <Stat label="Cities with extracts" value={data.cities_with_data} />
        <Stat label="Broad / deep extracts" value={data.cities_with_broad_extracts || 0} />
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((item) => (
          <button key={item.id} type="button" onClick={() => setFilter(item.id)} className={`ui-chip ${filter === item.id ? "ui-chip-active" : ""}`}>
            {item.label}
          </button>
        ))}
      </div>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {filtered.map((city) => {
          const depth = city.depth || "reference";
          const domains = city.domains || [];
          return (
            <Link key={city.slug} href={`/cities/${city.slug}`} className="ui-card group p-4 transition hover:-translate-y-0.5 hover:border-cyan/50 hover:shadow-glow">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-display text-lg font-semibold">{city.name}</div>
                  <div className="mt-1 text-xs text-mist">{city.country_code || "—"} · {city.domain_count || 0} official domains</div>
                </div>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] ${statusTone(depth)}`}>{depthLabel(depth)}</span>
              </div>
              <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-raised">
                <div className="h-full rounded-full bg-cyan transition-all" style={{ width: `${Math.min(100, ((city.domain_count || 0) / 7) * 100)}%` }} />
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {(domains.length ? domains : city.has_weather ? ["weather"] : ["none"]).slice(0, 6).map((domain) => (
                  <span key={domain} className="rounded-full bg-raised px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-mist group-hover:text-paper">
                    {domain}
                  </span>
                ))}
              </div>
            </Link>
          );
        })}
        {!filtered.length && <p className="text-sm text-mist">No cities match this filter.</p>}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="ui-card p-4">
      <div className="text-[10px] uppercase tracking-[0.14em] text-mist">{label}</div>
      <div className="mt-2 font-mono text-3xl text-paper">{value}</div>
    </div>
  );
}
