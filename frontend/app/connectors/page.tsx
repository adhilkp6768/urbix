"use client";
import { useState } from "react";
import { apiPost } from "@/lib/api";
import { useApi } from "@/lib/useApi";

export default function Page() {
  const state = useApi<{ results: string[] }>("/api/v1/connectors");
  const [message, setMessage] = useState("");
  const [running, setRunning] = useState<string | null>(null);
  async function run(code: string) {
    if (running) return;
    setRunning(code);
    setMessage(`Running ${code}`);
    try {
      const payload = code === "open-meteo-weather" || code === "open-meteo-air-quality" ? { days: 7 } : {};
      const result = await apiPost<{ status: string; message: string }>(`/api/v1/connectors/${code}/run`, payload);
      setMessage(`${result.status}: ${result.message}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Connector failed");
    } finally {
      setRunning(null);
    }
  }
  return (
    <div className="space-y-2 p-4">
      <h1 className="text-lg font-semibold">Connectors</h1>
      <p className="max-w-3xl text-sm text-mist">Weather and air connectors request every registered city. The other connectors stay on their published source, which is New York unless the source itself is global.</p>
      <p className="text-sm text-mist">{message}</p>
      {(state.data?.results || []).map((code) => (
        <div key={code} className="flex items-center justify-between border border-line bg-panel px-3 py-2 text-sm">
          <span className="font-mono text-xs">{code}</span>
          <button type="button" onClick={() => run(code)} disabled={running !== null} className="bg-cyan px-3 py-1 text-xs font-medium text-ink disabled:opacity-50">{running === code ? "Running" : "Run"}</button>
        </div>
      ))}
    </div>
  );
}
