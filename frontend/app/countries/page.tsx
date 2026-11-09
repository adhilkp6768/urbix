"use client";

import Link from "next/link";
import { useApi } from "@/lib/useApi";

export default function CountriesPage() {
  const state = useApi<{ results: { slug: string; name: string; country_code?: string }[] }>("/api/v1/geography/countries");
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading countries</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  return (
    <div className="p-4">
      <h1 className="mb-3 text-lg font-semibold">Countries</h1>
      <div className="grid gap-2 md:grid-cols-3">
        {state.data?.results.map((country) => (
          <Link key={country.slug} href={`/countries/${country.country_code}`} className="border border-line bg-panel p-3">{country.name}</Link>
        ))}
      </div>
    </div>
  );
}
