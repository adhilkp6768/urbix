"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { depthLabel } from "@/lib/tone";

export type CityChip = { slug: string; name: string; integration_status?: string; depth?: string; domain_count?: number };

type Freshness = {
  refresh: { running: boolean; scope: string | null; started_at: string | null; finished_at: string | null; steps: { dataset_code: string; status: string; message?: string | null; rows_written?: number | null }[] };
  datasets: { dataset_code: string; status: string; finished_at: string | null; message: string | null; rows_written: number }[];
};

type MobileContextValue = {
  city: string;
  cities: CityChip[];
  setCity: (slug: string) => void;
  tick: number;
  reload: () => void;
  freshness: Freshness | null;
  refreshing: boolean;
  refreshError: string | null;
  refreshSources: (scope?: "current" | "full") => Promise<void>;
};

const MobileContext = createContext<MobileContextValue | null>(null);

export function useMobile() {
  const value = useContext(MobileContext);
  if (!value) throw new Error("Mobile frame is missing.");
  return value;
}

const TABS = [
  { href: "/m", label: "Pulse", icon: "●" },
  { href: "/m/map", label: "Map", icon: "◎" },
  { href: "/m/explore", label: "Explore", icon: "▦" },
  { href: "/m/ask", label: "Ask", icon: "?" },
];

export function AppFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [city, setCityState] = useState("nyc");
  const [cities, setCities] = useState<CityChip[]>([{ slug: "nyc", name: "New York" }]);
  const [tick, setTick] = useState(0);
  const [freshness, setFreshness] = useState<Freshness | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  useEffect(() => {
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  }, []);

  useEffect(() => {
    const saved = window.localStorage.getItem("urbix-city");
    if (saved) setCityState(saved);
  }, []);

  useEffect(() => {
    apiGet<{ cities: CityChip[] }>("/api/v1/geography/world")
      .then((data) => {
        const loaded = (data.cities || [])
          .filter((item) => item.integration_status === "partial" || item.integration_status === "integrated" || (item.domain_count || 0) > 0 || item.depth === "weather")
          .sort((a, b) => (b.domain_count || 0) - (a.domain_count || 0) || a.name.localeCompare(b.name));
        if (loaded.length) {
          setCities(loaded);
          setCityState((current) => (loaded.some((item) => item.slug === current) ? current : loaded[0].slug));
        }
      })
      .catch(() => undefined);
  }, [tick]);

  useEffect(() => {
    let stop = false;
    const load = () => {
      apiGet<Freshness>("/api/v1/system/freshness")
        .then((data) => {
          if (!stop) setFreshness(data);
        })
        .catch(() => undefined);
    };
    load();
    const handle = setInterval(load, freshness?.refresh.running ? 4000 : 30000);
    return () => {
      stop = true;
      clearInterval(handle);
    };
  }, [tick, freshness?.refresh.running]);

  const value = useMemo<MobileContextValue>(() => ({
    city,
    cities,
    setCity: (slug) => {
      setCityState(slug);
      window.localStorage.setItem("urbix-city", slug);
    },
    tick,
    reload: () => setTick((current) => current + 1),
    freshness,
    refreshing: Boolean(freshness?.refresh.running),
    refreshError,
    refreshSources: async (scope = "current") => {
      setRefreshError(null);
      try {
        const result = await apiPost<{ started?: boolean }>("/api/v1/system/refresh", { scope });
        if (result.started === false) setRefreshError("A refresh is already running.");
        setTick((current) => current + 1);
      } catch (error) {
        setRefreshError(error instanceof Error ? error.message : "Refresh could not start.");
      }
    },
  }), [city, cities, tick, freshness, refreshError]);

  const selected = cities.find((item) => item.slug === city);

  return (
    <MobileContext.Provider value={value}>
      <div className="fixed inset-0 flex flex-col bg-ink text-paper">
        <div
          className="flex items-center justify-between gap-3 border-b border-line bg-shell/95 px-4 backdrop-blur"
          style={{ paddingTop: "max(0.65rem, env(safe-area-inset-top))" }}
        >
          <div className="min-w-0 py-2">
            <p className="text-[10px] uppercase tracking-[0.18em] text-cyan">URBIX</p>
            <p className="truncate font-display text-sm font-semibold">{selected?.name || "City"}</p>
          </div>
          <div className="flex items-center gap-2">
            {selected?.depth && <span className="hidden rounded-full border border-line px-2 py-1 text-[10px] uppercase tracking-[0.12em] text-mist xs:inline">{depthLabel(selected.depth)}</span>}
            <Link href="/" className="rounded-full border border-line px-3 py-1.5 text-[11px] text-mist">Desktop</Link>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
        <nav
          className="grid grid-cols-4 border-t border-line bg-shell/95 backdrop-blur"
          style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        >
          {TABS.map((tab) => {
            const active = tab.href === "/m" ? pathname === "/m" : pathname.startsWith(tab.href);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`flex flex-col items-center gap-1 py-2.5 text-center transition ${active ? "text-cyan" : "text-mist"}`}
              >
                <span className={`grid h-7 w-7 place-items-center rounded-full text-xs ${active ? "bg-cyan/15" : "bg-transparent"}`}>{tab.icon}</span>
                <span className="text-[10px] uppercase tracking-[0.14em]">{tab.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </MobileContext.Provider>
  );
}
