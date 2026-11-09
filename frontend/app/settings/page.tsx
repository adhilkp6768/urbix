"use client";
import { useApi } from "@/lib/useApi";
export default function Page() {
  const state = useApi<{ status: string; dialect: string; geo_units: number; llm_configured: boolean; openaq_configured: boolean }>("/api/v1/health");
  if (state.status === "loading") return <p className="p-6 text-sm text-mist">Loading settings</p>;
  if (state.status === "error") return <p className="p-6 text-sm text-bad">{state.error}</p>;
  const data = state.data!;
  return (
    <div className="space-y-2 p-4 text-sm">
      <h1 className="text-lg font-semibold">Settings</h1>
      <p>API {data.status}</p>
      <p>Database dialect {data.dialect}</p>
      <p>Geographies {data.geo_units}</p>
      <p>Language model {data.llm_configured ? "configured" : "not configured — the rule planner is active"}</p>
      <p>OpenAQ {data.openaq_configured ? "configured" : "not configured — station data stays unavailable"}</p>
      <p className="max-w-2xl text-mist">Secrets are read from the server environment. This page does not display keys. PostgreSQL with PostGIS is the deployment database. SQLite is the portable development database and does not provide GIST indexes.</p>
    </div>
  );
}
