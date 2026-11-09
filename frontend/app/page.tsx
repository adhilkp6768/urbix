"use client";

import Link from "next/link";
import { useApi } from "@/lib/useApi";

type World = { availability: string; countries: number; cities_referenced: number; cities_with_data: number; note: string; cities: { slug: string; name: string; integration_status: string; country_code?: string }[] };

export default function GlobalPage() {
  const state = useApi<World>("/api/v1/geography/world");
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading the geographical registry</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  const data = state.data!;
  const loaded = data.cities.filter((city) => city.integration_status === "partial" || city.integration_status === "integrated");
  const waiting = data.cities.filter((city) => !loaded.includes(city));
  return (
    <div className="space-y-4 p-4">
      <div>
        <p className="text-[11px] uppercase tracking-[0.18em] text-cyan">Global intelligence</p>
        <h1 className="text-2xl font-semibold">Cities with evidence, not a global average</h1>
        <p className="mt-2 max-w-3xl text-sm text-mist">{data.note} Open a city with ingested data to see indicators. A referenced city has a name and a coordinate, and no measurements yet.</p>
      </div>
      <div className="grid gap-2 md:grid-cols-3">
        <Stat label="Countries in the registry" value={data.countries} />
        <Stat label="Cities referenced" value={data.cities_referenced} />
        <Stat label="Cities with ingested data" value={data.cities_with_data} />
      </div>
      <section>
        <h2 className="mb-2 text-[11px] uppercase tracking-[0.16em] text-cyan">Loaded</h2>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {loaded.map((city) => (
            <Link key={city.slug} href={`/cities/${city.slug}`} className="border border-cyan/40 bg-panel p-3 hover:border-cyan">
              <div className="text-sm font-medium">{city.name}</div>
              <div className="mt-1 text-[11px] text-good">Indicators loaded · {city.country_code}</div>
            </Link>
          ))}
        </div>
      </section>
      <section>
        <h2 className="mb-2 text-[11px] uppercase tracking-[0.16em] text-mist">Registered, no extract yet</h2>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {waiting.map((city) => (
            <Link key={city.slug} href={`/cities/${city.slug}`} className="border border-line bg-panel p-3 hover:border-cyan/50">
              <div className="text-sm font-medium">{city.name}</div>
              <div className="mt-1 text-[11px] text-mist">No dataset loaded · {city.country_code}</div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-line bg-panel p-3">
      <div className="text-[10px] uppercase tracking-[0.14em] text-mist">{label}</div>
      <div className="mt-1 font-mono text-2xl text-paper">{value}</div>
    </div>
  );
}
