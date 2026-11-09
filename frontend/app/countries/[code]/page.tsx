"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useApi } from "@/lib/useApi";

export default function CountryPage() {
  const params = useParams<{ code: string }>();
  const state = useApi<{ results: { slug: string; name: string; integration_status: string }[] }>(`/api/v1/geography/countries/${params.code}/cities`);
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading cities</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  return (
    <div className="p-4">
      <h1 className="mb-3 text-lg font-semibold">{params.code} cities</h1>
      <div className="grid gap-2 md:grid-cols-2">
        {(state.data?.results || []).map((city) => (
          <Link key={city.slug} href={`/cities/${city.slug}`} className="border border-line bg-panel p-3">
            <div>{city.name}</div>
            <div className="text-xs text-mist">{city.integration_status}</div>
          </Link>
        ))}
        {!state.data?.results.length && <p className="text-sm text-mist">No cities are registered for this country.</p>}
      </div>
    </div>
  );
}
