"use client";

import { useApi } from "@/lib/useApi";

type Correlation = {
  availability: string;
  relationship?: string;
  interpretation?: string;
  result?: { coefficient: number; n: number; p_value: number | null; method: string } | null;
};

export default function Page() {
  const state = useApi<Correlation>("/api/v1/analysis/correlations?city=nyc");
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Computing the paired series</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  const data = state.data!;
  return (
    <div className="space-y-3 p-4">
      <h1 className="text-lg font-semibold">Cross-domain analysis</h1>
      <p className="max-w-3xl text-sm text-mist">{data.interpretation || "No aligned series are available."}</p>
      {data.result ? (
        <div className="border border-line bg-panel p-3 text-sm">
          <div>{data.relationship}</div>
          <div className="mt-2 font-mono text-cyan">{data.result.method} {data.result.coefficient.toFixed(3)} · n={data.result.n} · p={data.result.p_value ?? "not computed"}</div>
        </div>
      ) : (
        <p className="text-sm text-mist">The association is unavailable until both hourly series share at least 12 timestamps.</p>
      )}
    </div>
  );
}
