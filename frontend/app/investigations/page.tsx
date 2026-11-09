"use client";
import Link from "next/link";
import { useApi } from "@/lib/useApi";
export default function Page() {
  const state = useApi<{ results: { id: string; question: string; created_at?: string }[] }>("/api/v1/ai/investigations");
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading investigations</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  return (
    <div className="space-y-2 p-4">
      <h1 className="text-lg font-semibold">Investigations</h1>
      {(state.data?.results || []).map((item) => <Link key={item.id} href={`/investigations/${item.id}`} className="block border border-line bg-panel p-3">{item.question}</Link>)}
      {!state.data?.results.length && <p className="text-sm text-mist">No investigations have been run.</p>}
    </div>
  );
}
