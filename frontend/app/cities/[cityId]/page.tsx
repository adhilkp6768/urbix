"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { formatValue } from "@/lib/format";
import { domainAccent, statusTone } from "@/lib/tone";
import { useApi } from "@/lib/useApi";

type Overview = { city: { name: string; integration_status: string; area_km2?: number }; domains: Record<string, { availability: string; kpis: { label: string; value: number | null; unit?: string; availability: string }[]; limitations: string[] }> };

export default function CityPage() {
  const params = useParams<{ cityId: string }>();
  const state = useApi<Overview>(`/api/v1/cities/${params.cityId}/overview`);
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading city</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  const data = state.data!;
  const loaded = data.city.integration_status === "partial" || data.city.integration_status === "integrated";
  const domains = Object.entries(data.domains).filter(([, payload]) => payload.kpis.some((item) => item.value !== null && item.value !== undefined));
  const domainHref: Record<string, string> = {
    traffic: "/traffic",
    environment: "/environment",
    crime: "/crime",
    population: "/population",
    waste: "/waste",
    transport: "/transport",
    infrastructure: "/infrastructure",
  };
  return (
    <div className="space-y-3 p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-cyan">City intelligence</p>
          <h1 className="text-2xl font-semibold">{data.city.name}</h1>
          <p className="text-sm text-mist">{loaded ? "Stored extracts are shown below. A missing field stays blank." : "This city is registered. No extract has been loaded, so there are no indicators to show."} {data.city.area_km2 ? `Area ${data.city.area_km2} km² from the stored boundary.` : ""}</p>
        </div>
        {loaded && <Link href={`/cities/${params.cityId}/map`} className="bg-cyan px-3 py-1.5 text-sm font-medium text-ink">Open map</Link>}
      </div>
      {!loaded && (
        <section className="border border-line bg-panel p-4 text-sm">
          <p>Weather and air readings appear after an Open-Meteo extract. Traffic, waste, transit, and safety extracts are loaded for New York.</p>
          <Link href="/cities" className="mt-3 inline-block bg-cyan px-3 py-1.5 font-medium text-ink">See loaded cities</Link>
        </section>
      )}
      {loaded && domains.map(([domain, payload]) => (
        <section key={domain} className="border border-line border-l-4 bg-panel p-3" style={{ borderLeftColor: domainAccent(domain) }}>
          <div className="mb-3 flex items-center justify-between gap-3">
            {domainHref[domain] ? (
              <Link href={`${domainHref[domain]}?city=${params.cityId}`} className="text-sm uppercase tracking-[0.12em] hover:underline" style={{ color: domainAccent(domain) }}>{domain}</Link>
            ) : (
              <h2 className="text-sm uppercase tracking-[0.12em]" style={{ color: domainAccent(domain) }}>{domain}</h2>
            )}
            <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] ${statusTone(payload.availability)}`}>{payload.availability}</span>
          </div>
          <div className="grid gap-2 md:grid-cols-3">
            {payload.kpis.filter((item) => item.value !== null && item.value !== undefined).slice(0, 3).map((item) => (
              <div key={item.label} className="bg-raised px-3 py-2">
                <div className="text-[11px] text-mist">{item.label}</div>
                <div className="mt-1 font-mono text-lg text-paper">{formatValue(item.value, item.unit)}</div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
