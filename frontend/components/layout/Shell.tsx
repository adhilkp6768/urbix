"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

function navigation(city: string) {
  const query = `?city=${encodeURIComponent(city)}`;
  return [
  {
    label: "Global",
    items: [
      ["Overview", "/"],
      ["Countries", "/countries"],
      ["Cities", "/cities"],
      ["Compare", "/compare"],
    ],
  },
  {
    label: "City",
    items: [
      ["Command centre", `/cities/${city}`],
      ["Map", `/cities/${city}/map`],
      ["Districts", `/cities/${city}/districts`],
    ],
  },
  {
    label: "Domains",
    items: [
      ["Traffic", `/traffic${query}`],
      ["Environment", `/environment${query}`],
      ["Public safety", `/crime${query}`],
      ["Population", `/population${query}`],
      ["Transportation", `/transport${query}`],
      ["Waste", `/waste${query}`],
      ["Infrastructure", `/infrastructure${query}`],
    ],
  },
  {
    label: "Intelligence",
    items: [
      ["Assistant", "/ai"],
      ["Investigations", "/investigations"],
      ["Predictions", "/predictions"],
      ["Anomalies", "/anomalies"],
      ["Cross-domain", "/analysis"],
    ],
  },
  {
    label: "Operations",
    items: [
      ["Reports", "/reports"],
      ["Alerts", "/alerts"],
      ["Data sources", "/data-sources"],
      ["Data quality", "/data-quality"],
      ["Models", "/models"],
      ["Connectors", "/connectors"],
      ["Settings", "/settings"],
    ],
  },
  ];
}

function ShellInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const params = useSearchParams();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<{ slug: string; name: string; level: string; country_code?: string }[]>([]);
  const pathCity = pathname.match(/^\/cities\/([^/]+)/)?.[1];
  const city = pathCity || params.get("city") || "nyc";
  const cityLabel = city === "nyc" ? "New York" : city.replace(/-/g, " ");
  const groups = navigation(city);
  const [menuOpen, setMenuOpen] = useState(false);
  const [loadedCities, setLoadedCities] = useState<{ slug: string; name: string }[]>([]);

  useEffect(() => {
    apiGet<{ cities: { slug: string; name: string; integration_status?: string }[] }>("/api/v1/geography/world")
      .then((data) => {
        setLoadedCities((data.cities || []).filter((city) => city.integration_status === "partial" || city.integration_status === "integrated").map((city) => ({ slug: city.slug, name: city.name })));
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (query.trim().length < 2) {
      setHits([]);
      return;
    }
    const handle = setTimeout(() => {
      apiGet<{ results: { slug: string; name: string; level: string; country_code?: string }[] }>(`/api/v1/geography/search?q=${encodeURIComponent(query)}`)
        .then((data) => setHits(data.results))
        .catch(() => setHits([]));
    }, 250);
    return () => clearTimeout(handle);
  }, [query]);

  if (pathname === "/m" || pathname.startsWith("/m/")) return <>{children}</>;

  return (
    <div className="min-h-screen bg-ink text-paper">
      <header className="flex items-center gap-4 border-b border-line bg-shell px-4 py-2">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-sm bg-cyan text-xs font-semibold text-ink">U</span>
          <span>
            <span className="block text-sm font-semibold tracking-wide">URBIX</span>
            <span className="block text-[10px] uppercase tracking-[0.16em] text-mist">Understand cities</span>
          </span>
        </Link>
        <button type="button" className="border border-line px-2 py-1 text-xs md:hidden" onClick={() => setMenuOpen((open) => !open)}>
          {menuOpen ? "Close" : "Menu"}
        </button>
        <form
          className="relative ml-4 hidden min-w-[240px] flex-1 md:block"
          onSubmit={(event) => {
            event.preventDefault();
            if (hits[0]) router.push(geographyHref(hits[0]));
          }}
        >
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search geography"
            className="w-full border border-line bg-ink px-3 py-1.5 text-sm text-paper outline-none placeholder:text-mist/70 focus:border-cyan"
          />
          {hits.length > 0 && (
            <div className="absolute z-20 mt-1 w-full border border-line bg-panel">
              {hits.map((hit) => (
                <Link key={hit.slug} href={geographyHref(hit)} className="block px-3 py-1.5 text-sm hover:bg-white/5" onClick={() => setHits([])}>
                  {hit.name} <span className="text-mist">{hit.level}</span>
                </Link>
              ))}
            </div>
          )}
        </form>
        <div className="ml-auto flex items-center gap-2 text-xs text-mist">
          {loadedCities.length > 0 ? (
            <select
              aria-label="City"
              value={loadedCities.some((item) => item.slug === city) ? city : ""}
              onChange={(event) => {
                if (event.target.value) router.push(`/cities/${event.target.value}`);
              }}
              className="border border-line bg-raised px-2 py-1 text-paper"
            >
              {!loadedCities.some((item) => item.slug === city) && <option value="">{cityLabel}</option>}
              {loadedCities.map((item) => <option key={item.slug} value={item.slug}>{item.name}</option>)}
            </select>
          ) : (
            <Link href={`/cities/${city}`} className="border border-line bg-raised px-2 py-1 capitalize text-paper">{cityLabel}</Link>
          )}
          <Link href="/m" className="bg-cyan px-2 py-1 font-medium text-ink">Phone</Link>
          <Link href="/ai" className="border border-line px-2 py-1">AI analysis</Link>
          <Link href="/alerts" className="border border-line px-2 py-1">Alerts</Link>
        </div>
      </header>
      <div className="grid min-h-[calc(100vh-49px)] grid-cols-1 md:grid-cols-[220px_1fr]">
        <aside className={`${menuOpen ? "block" : "hidden"} border-r border-line bg-shell px-2 py-3 md:block`}>
          {groups.map((group) => (
            <div key={group.label} className="mb-4">
              <div className="px-2 text-[10px] uppercase tracking-[0.16em] text-mist">{group.label}</div>
              {group.items.map(([label, href]) => {
                const active = pathname === href.split("?")[0];
                return (
                  <Link key={href} href={href} className={`mt-0.5 block border-l-2 px-2 py-1.5 text-sm ${active ? "border-cyan bg-cyan/10 text-cyan" : "border-transparent text-paper/85 hover:bg-white/5"}`}>
                    {label}
                  </Link>
                );
              })}
            </div>
          ))}
        </aside>
        <main className="min-w-0">{children}</main>
      </div>
    </div>
  );
}

function geographyHref(hit: { slug: string; level: string; country_code?: string }) {
  if (hit.level === "city") return `/cities/${hit.slug}`;
  if (hit.level === "country" && hit.country_code) return `/countries/${hit.country_code.toLowerCase()}`;
  return `/compare?left=${encodeURIComponent(hit.slug)}&right=borough-manhattan`;
}

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-mist">Loading workspace</div>}>
      <ShellInner>{children}</ShellInner>
    </Suspense>
  );
}
