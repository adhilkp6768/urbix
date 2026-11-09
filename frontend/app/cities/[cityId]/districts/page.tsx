"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useApi } from "@/lib/useApi";

export default function DistrictsPage() {
  const params = useParams<{ cityId: string }>();
  const [kind, setKind] = useState("borough");
  const state = useApi<{ results: { slug: string; name: string; area_km2?: number; kind?: string }[] }>(`/api/v1/geography/cities/${params.cityId}/districts?kind=${kind}`);
  return (
    <div className="p-4">
      <div className="mb-3 flex gap-2">
        {[["borough", "Boroughs"], ["community_district", "Community districts"], ["cdta", "CDTAs"], ["nta", "Neighborhoods"]].map(([item, label]) => (
          <button key={item} onClick={() => setKind(item)} className={`border px-2 py-1 text-xs ${kind === item ? "border-cyan bg-cyan/10 text-cyan" : "border-line text-mist"}`}>{label}</button>
        ))}
      </div>
      {state.status === "error" && <p className="text-sm text-bad">{state.error}</p>}
      {state.status === "loading" && <p className="text-sm text-mist">Loading districts</p>}
      <div className="grid gap-2 md:grid-cols-3">
        {state.data?.results.map((row) => (
          <Link key={row.slug} href={`/compare?left=${row.slug}&right=borough-manhattan`} className="border border-line bg-panel p-3">
            <div className="text-sm">{row.name}</div>
            <div className="text-xs text-mist">{row.area_km2 ? `${row.area_km2} km²` : "area unavailable"}</div>
          </Link>
        ))}
        {state.status === "ready" && !state.data?.results.length && <p className="text-sm text-mist">No polygons of this kind are loaded.</p>}
      </div>
    </div>
  );
}
