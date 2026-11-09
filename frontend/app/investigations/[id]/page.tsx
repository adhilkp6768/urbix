"use client";
import { useParams } from "next/navigation";
import { useApi } from "@/lib/useApi";
export default function Page() {
  const params = useParams<{ id: string }>();
  const state = useApi<{ question: string; answer: { prose?: string; claims?: { claim_type: string; statement: string }[] } }>(`/api/v1/ai/investigations/${params.id}`);
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading investigation</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  return (
    <div className="space-y-3 p-4">
      <h1 className="text-lg font-semibold">{state.data?.question}</h1>
      <p className="text-sm">{state.data?.answer?.prose}</p>
      {(state.data?.answer?.claims || []).map((claim, index) => <p key={index} className="border border-line bg-panel p-2 text-sm"><span className="mr-2 text-cyan">{claim.claim_type}</span>{claim.statement}</p>)}
    </div>
  );
}
