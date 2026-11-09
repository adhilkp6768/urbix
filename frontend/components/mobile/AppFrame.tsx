"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

export type CityChip = { slug: string; name: string; integration_status?: string };

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
  { href: "/m", label: "Pulse" },
  { href: "/m/map", label: "Map" },
  { href: "/m/explore", label: "Explore" },
  { href: "/m/ask", label: "Ask" },
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
    apiGet<{ cities: CityChip[] }>("/api/v1/geography/world")
      .then((data) => {
        const loaded = (data.cities || []).filter((item) => item.integration_status === "partial" || item.integration_status === "integrated");
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

  return (
    <MobileContext.Provider value={value}>
      <div className="fixed inset-0 flex flex-col bg-ink text-paper">
        <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
        <nav
          className="grid grid-cols-4 border-t border-line bg-shell"
          style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        >
          {TABS.map((tab) => {
            const active = tab.href === "/m" ? pathname === "/m" : pathname.startsWith(tab.href);
            return (
              <Link key={tab.href} href={tab.href} className={`py-3 text-center text-[11px] uppercase tracking-[0.14em] ${active ? "text-cyan" : "text-mist"}`}>
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </MobileContext.Provider>
  );
}
