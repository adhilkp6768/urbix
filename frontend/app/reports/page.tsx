"use client";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { apiPost } from "@/lib/api";
import { useApi } from "@/lib/useApi";

export default function Page() {
  const city = useSearchParams().get("city") || "nyc";
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const state = useApi<{ results: { id: string; title: string; body: { observations?: string[]; limitations?: string[]; methodology?: string } }[] }>(`/api/v1/ai/reports?refresh=${revision}`);
  const [message, setMessage] = useState("");
  async function create() {
    if (busy) return;
    setBusy(true);
    setMessage("Writing report from stored indicators");
    try {
      await apiPost("/api/v1/ai/reports", { city });
      setRevision((value) => value + 1);
      setMessage(`Report stored from the ${city} extract.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Report failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-3 p-4">
      <button type="button" onClick={create} disabled={busy} className="ui-btn-primary disabled:opacity-50">{busy ? "Writing" : "Generate evidence report"}</button>
      {message && <p className="text-sm text-mist">{message}</p>}
      {(state.data?.results || []).map((report) => (
        <article key={report.id} className="border border-line bg-panel p-3 text-sm">
          <h2 className="font-medium">{report.title}</h2>
          <p className="mt-1 text-mist">{report.body?.methodology}</p>
          {(report.body?.observations || []).slice(0, 6).map((line) => <p key={line}>{line}</p>)}
        </article>
      ))}
    </div>
  );
}
