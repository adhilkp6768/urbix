"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { formatValue } from "@/lib/format";
import { useApi } from "@/lib/useApi";

type Metric = { label: string; left?: { value: number | null; unit?: string | null } | null; right?: { value: number | null; unit?: string | null } | null };
type Compare = { availability: string; left?: { name: string; area_km2?: number }; right?: { name: string; area_km2?: number }; metrics?: Metric[]; note?: string; reason?: string };
type World = { cities: { slug: string; name: string; integration_status?: string }[] };

function CompareInner() {
  const params = useSearchParams();
  const world = useApi<World>("/api/v1/geography/world");
  const cities = (world.data?.cities || []).filter((city) => city.integration_status === "partial" || city.integration_status === "integrated");
  const [left, setLeft] = useState(params.get("left") || "nyc");
  const [right, setRight] = useState(params.get("right") || "london");
  const [pair, setPair] = useState({ left: params.get("left") || "nyc", right: params.get("right") || "london" });
  const state = useApi<Compare>(`/api/v1/compare?left=${encodeURIComponent(pair.left)}&right=${encodeURIComponent(pair.right)}`);
  return (
    <div className="space-y-3 p-4">
      <h1 className="text-lg font-semibold">Compare geographies</h1>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          setPair({ left, right });
        }}
      >
        <label className="text-sm text-mist">
          Left
          <select value={left} onChange={(event) => setLeft(event.target.value)} className="mt-1 block border border-line bg-ink px-2 py-1 text-paper">
            {cities.map((city) => <option key={city.slug} value={city.slug}>{city.name}</option>)}
            {!cities.some((city) => city.slug === left) && <option value={left}>{left}</option>}
          </select>
        </label>
        <label className="text-sm text-mist">
          Right
          <select value={right} onChange={(event) => setRight(event.target.value)} className="mt-1 block border border-line bg-ink px-2 py-1 text-paper">
            {cities.map((city) => <option key={city.slug} value={city.slug}>{city.name}</option>)}
            {!cities.some((city) => city.slug === right) && <option value={right}>{right}</option>}
          </select>
        </label>
        <button type="submit" className="bg-cyan px-3 py-1.5 text-sm font-medium text-ink">Compare</button>
      </form>
      {state.status === "loading" && <p className="text-sm text-mist">Comparing</p>}
      {state.status === "error" && <p className="text-sm text-bad">{state.error}</p>}
      {state.data && (
        <div className="grid gap-2 md:grid-cols-2">
          <Card name={state.data.left?.name} area={state.data.left?.area_km2} />
          <Card name={state.data.right?.name} area={state.data.right?.area_km2} />
          {(state.data.metrics || []).map((metric) => (
            <div key={metric.label} className="border border-line bg-panel p-3 md:col-span-2">
              <div className="text-[11px] uppercase tracking-[0.12em] text-mist">{metric.label}</div>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <p className="font-mono text-lg">{formatValue(metric.left?.value, metric.left?.unit)}</p>
                <p className="font-mono text-lg">{formatValue(metric.right?.value, metric.right?.unit)}</p>
              </div>
            </div>
          ))}
          <p className="text-sm text-mist md:col-span-2">{state.data.note || state.data.reason}</p>
        </div>
      )}
    </div>
  );
}

function Card({ name, area }: { name?: string; area?: number }) {
  return <div className="border border-line bg-panel p-3"><div>{name || "Unknown"}</div><div className="text-sm text-mist">{area ? `${area} km²` : "Area unavailable"}</div></div>;
}

export default function ComparePage() {
  return <Suspense fallback={<p className="p-6 text-sm text-mist">Loading comparison</p>}><CompareInner /></Suspense>;
}
