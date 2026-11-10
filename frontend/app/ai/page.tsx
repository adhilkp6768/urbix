"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { apiPost } from "@/lib/api";
import { useApi } from "@/lib/useApi";

type Answer = { prose: string; planner?: string; tools?: string[]; investigation_id?: string; claims?: { claim_type: string; statement: string; dataset_code?: string }[] };

export default function AssistantPage() {
  const city = useSearchParams().get("city") || "nyc";
  const [question, setQuestion] = useState("What traffic and air-quality evidence is loaded for this city?");
  const [state, setState] = useState<"idle" | "loading" | "error" | "ready">("idle");
  const [error, setError] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [revision, setRevision] = useState(0);
  const history = useApi<{ results: { id: string; question: string }[] }>(`/api/v1/ai/investigations?refresh=${revision}`);

  async function submit() {
    setState("loading");
    try {
      const result = await apiPost<Answer>("/api/v1/ai/query", { question, city });
      setAnswer(result);
      setRevision((value) => value + 1);
      setState("ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
      setState("error");
    }
  }

  return (
    <div className="grid gap-3 p-4 lg:grid-cols-[1fr_280px]">
      <section className="border border-line bg-panel p-3">
        <h1 className="text-lg font-semibold">Urban intelligence assistant</h1>
        <p className="mt-1 text-sm text-mist">The assistant can only call approved tools. If no model key is configured, a rule planner selects those tools. Numbers in the answer have to appear in the tool evidence.</p>
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} className="ui-input mt-3 h-28" />
        <button onClick={submit} className="ui-btn-primary mt-2" disabled={state === "loading"}>{state === "loading" ? "Investigating" : "Ask"}</button>
        {state === "error" && <p className="mt-3 text-sm text-bad">{error}</p>}
        {answer && (
          <div className="mt-4 space-y-2">
            <p className="text-xs text-mist">Planner {answer.planner} · tools {(answer.tools || []).join(", ")}</p>
            <p className="text-sm leading-6">{answer.prose}</p>
            {(answer.claims || []).map((claim, index) => (
              <div key={index} className="border border-line px-2 py-1.5 text-xs">
                <span className="mr-2 uppercase tracking-wider text-cyan">{claim.claim_type}</span>
                {claim.statement}
                {claim.dataset_code && <span className="ml-2 font-mono text-mist">{claim.dataset_code}</span>}
              </div>
            ))}
          </div>
        )}
      </section>
      <aside className="border border-line bg-panel p-3 text-sm">
        <h2 className="text-[11px] uppercase tracking-[0.14em] text-mist">Investigations</h2>
        <ul className="mt-2 space-y-2">
          {(history.data?.results || []).map((item) => (
            <li key={item.id}><Link href={`/investigations/${item.id}`} className="hover:text-cyan">{item.question}</Link></li>
          ))}
          {history.status === "ready" && !history.data?.results.length && <li className="text-mist">None yet.</li>}
        </ul>
      </aside>
    </div>
  );
}
