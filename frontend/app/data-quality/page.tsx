"use client";
import { useApi } from "@/lib/useApi";
export default function Page() {
  const state = useApi<{ checks: { dataset_code: string; check: string; status: string; detail: string }[]; jobs: { dataset_code: string; status: string; rows_written: number; message?: string }[] }>("/api/v1/data-quality");
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading quality checks</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  return (
    <div className="grid gap-3 p-4 lg:grid-cols-2">
      <section>
        <h1 className="mb-2 text-lg font-semibold">Jobs</h1>
        {(state.data?.jobs || []).map((job, index) => <p key={index} className="border-b border-line py-2 text-sm"><span className={job.status === "failed" ? "text-bad" : job.status === "succeeded" ? "text-good" : "text-warn"}>{job.status}</span> {job.dataset_code} · {job.rows_written} · {job.message}</p>)}
        {!state.data?.jobs.length && <p className="text-sm text-mist">No ingestion jobs yet.</p>}
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Checks</h2>
        {(state.data?.checks || []).map((check, index) => <p key={index} className="border-b border-line py-2 text-sm"><span className={check.status === "failed" ? "text-bad" : check.status === "passed" || check.status === "ok" ? "text-good" : "text-warn"}>{check.status}</span> {check.dataset_code} {check.check}: {check.detail}</p>)}
      </section>
    </div>
  );
}
