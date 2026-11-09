"use client";

import Link from "next/link";
import { useApi } from "@/lib/useApi";

export default function CitiesPage() {
  const state = useApi<{ results: { slug: string; name: string; integration_status: string; country_code?: string }[] }>("/api/v1/cities");
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading cities</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  const cities = state.data?.results || [];
  const loaded = cities.filter((city) => city.integration_status === "partial" || city.integration_status === "integrated");
  const waiting = cities.filter((city) => !loaded.includes(city));
  return (
    <div className="space-y-4 p-4">
      <CityGroup title="Loaded" cities={loaded} hint="Indicators loaded" />
      <CityGroup title="Registered, no extract yet" cities={waiting} hint="No dataset loaded" />
    </div>
  );
}

function CityGroup({ title, cities, hint }: { title: string; cities: { slug: string; name: string; country_code?: string }[]; hint: string }) {
  if (!cities.length) return null;
  return (
    <section>
      <h1 className="mb-2 text-[11px] uppercase tracking-[0.16em] text-mist">{title}</h1>
      <div className="grid gap-2 md:grid-cols-3">
        {cities.map((city) => (
          <Link key={city.slug} href={`/cities/${city.slug}`} className="border border-line bg-panel p-3">
            <div className="font-medium">{city.name}</div>
            <div className="text-xs text-mist">{hint} · {city.country_code}</div>
          </Link>
        ))}
      </div>
    </section>
  );
}
