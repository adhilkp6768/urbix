"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { useMobile } from "@/components/mobile/AppFrame";

type Answer = { prose?: string; claims?: { statement?: string }[] };

export default function AskPage() {
  const mobile = useMobile();
  const [question, setQuestion] = useState("What is known about traffic and air quality?");
  const [messages, setMessages] = useState<{ role: "you" | "urbix"; text: string }[]>([]);
  const [busy, setBusy] = useState(false);

  async function ask() {
    const text = question.trim();
    if (!text || busy) return;
    setBusy(true);
    setMessages((current) => [...current, { role: "you", text }]);
    setQuestion("");
    try {
      const data = await apiPost<Answer>("/api/v1/ai/query", { question: text, city: mobile.city });
      const claims = (data.claims || []).map((claim) => claim.statement).filter(Boolean).slice(0, 3).join(" ");
      setMessages((current) => [...current, { role: "urbix", text: data.prose || claims || "No evidenced answer was returned." }]);
    } catch (error) {
      setMessages((current) => [...current, { role: "urbix", text: error instanceof Error ? error.message : "The question could not be answered." }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col" style={{ paddingTop: "max(1rem, env(safe-area-inset-top))" }}>
      <div className="px-4">
        <p className="text-[11px] uppercase tracking-[0.22em] text-cyan">Ask</p>
        <h1 className="mt-1 text-2xl font-semibold">Evidence only</h1>
      </div>
      <div className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto px-4 pb-3">
        {messages.length === 0 && <p className="text-sm text-mist">Ask about a stored city extract. The answer stays inside the datasets that are actually loaded.</p>}
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-6 ${message.role === "you" ? "ml-auto bg-cyan/15 text-cyan" : "border border-line bg-panel"}`}>
            {message.text}
          </div>
        ))}
      </div>
      <form
        className="flex gap-2 border-t border-line px-3 py-3"
        onSubmit={(event) => {
          event.preventDefault();
          void ask();
        }}
      >
        <input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about this city" className="min-w-0 flex-1 rounded-full border border-line bg-shell px-4 py-2 text-sm outline-none" />
        <button type="submit" disabled={busy} className="ui-btn-primary disabled:opacity-50">
          {busy ? "…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
