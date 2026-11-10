"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { depthLabel, statusTone } from "@/lib/tone";

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
        ["Assistant", `/ai${query}`],
        ["Investigations", "/investigations"],
        ["Predictions", "/predictions"],
        ["Anomalies", "/anomalies"],
        ["Cross-domain", `/analysis${query}`],
      ],
    },
    {
      label: "Operations",
      items: [
        ["Reports", `/reports${query}`],
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

type CityOption = { slug: string; name: string; depth?: string; domain_count?: number };

function ShellInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const params = useSearchParams();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<{ slug: string; name: string; level: string; country_code?: string }[]>([]);
  const pathCity = pathname.match(/^\/cities\/([^/]+)/)?.[1];
  const city = pathCity || params.get("city") || "nyc";
  const cityLabel = city === "nyc" ? "New York" : city.replace(/-/g, " ");
  const groups = useMemo(() => navigation(city), [city]);
  const [menuOpen, setMenuOpen] = useState(false);
  const [loadedCities, setLoadedCities] = useState<CityOption[]>([]);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({ Global: true, City: true, Domains: true, Intelligence: false, Operations: false });

  useEffect(() => {
    apiGet<{ cities: CityOption[] }>("/api/v1/geography/world")
      .then((data) => {
        const loaded = (data.cities || [])
          .filter((item) => (item as { integration_status?: string }).integration_status === "partial" || (item as { integration_status?: string }).integration_status === "integrated" || (item.domain_count || 0) > 0 || item.depth === "weather")
          .sort((a, b) => (b.domain_count || 0) - (a.domain_count || 0) || a.name.localeCompare(b.name));
        setLoadedCities(loaded.map((city) => ({ slug: city.slug, name: city.name, depth: city.depth, domain_count: city.domain_count })));
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

  const selected = loadedCities.find((item) => item.slug === city);

  return (
    <div className="min-h-screen bg-ink text-paper">
      <header className="sticky top-0 z-30 border-b border-line bg-shell/95 backdrop-blur-md">
        <div className="flex items-center gap-3 px-3 py-2.5 md:px-4">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-cyan text-sm font-bold text-white shadow-soft">U</span>
            <span className="hidden sm:block">
              <span className="font-display block text-sm font-bold tracking-wide">URBIX</span>
              <span className="block text-[10px] uppercase tracking-[0.18em] text-mist">Urban evidence</span>
            </span>
          </Link>
          <button type="button" className="ui-btn-ghost px-3 py-1.5 text-xs md:hidden" onClick={() => setMenuOpen((open) => !open)}>
            {menuOpen ? "Close" : "Menu"}
          </button>
          <form
            className="relative ml-1 hidden min-w-[220px] flex-1 md:block"
            onSubmit={(event) => {
              event.preventDefault();
              if (hits[0]) router.push(geographyHref(hits[0]));
            }}
          >
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search cities, countries…"
              className="ui-input"
            />
            {hits.length > 0 && (
              <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-line bg-panel shadow-soft">
                {hits.map((hit) => (
                  <Link key={hit.slug} href={geographyHref(hit)} className="block px-3 py-2 text-sm hover:bg-white/5" onClick={() => setHits([])}>
                    {hit.name} <span className="text-mist">{hit.level}</span>
                  </Link>
                ))}
              </div>
            )}
          </form>
          <div className="ml-auto flex items-center gap-2 text-xs">
            {loadedCities.length > 0 ? (
              <label className="flex items-center gap-2">
                <span className="hidden text-mist lg:inline">City</span>
                <select
                  aria-label="City"
                  value={loadedCities.some((item) => item.slug === city) ? city : ""}
                  onChange={(event) => {
                    if (event.target.value) router.push(`/cities/${event.target.value}`);
                  }}
                  className="max-w-[140px] rounded-full border border-line bg-raised px-3 py-1.5 text-paper sm:max-w-[180px]"
                >
                  {!loadedCities.some((item) => item.slug === city) && <option value="">{cityLabel}</option>}
                  {loadedCities.map((item) => (
                    <option key={item.slug} value={item.slug}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <Link href={`/cities/${city}`} className="ui-btn-ghost capitalize">{cityLabel}</Link>
            )}
            {selected?.depth && <span className={`hidden rounded-full border px-2 py-1 text-[10px] uppercase tracking-[0.12em] md:inline ${statusTone(selected.depth)}`}>{depthLabel(selected.depth)}</span>}
            <Link href="/m" className="ui-btn-primary px-3 py-1.5 text-xs">Phone</Link>
            <Link href={`/ai?city=${encodeURIComponent(city)}`} className="ui-btn-ghost hidden px-3 py-1.5 text-xs sm:inline-flex">Ask AI</Link>
          </div>
        </div>
      </header>
      <div className="grid min-h-[calc(100vh-57px)] grid-cols-1 md:grid-cols-[240px_1fr]">
        <aside className={`${menuOpen ? "block" : "hidden"} border-r border-line/80 bg-shell/80 px-2 py-3 backdrop-blur-sm md:block`}>
          <div className="mb-3 rounded-2xl border border-line/70 bg-panel/70 p-3 md:hidden">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search geography"
              className="ui-input"
            />
            {hits.length > 0 && (
              <div className="mt-2 space-y-1">
                {hits.map((hit) => (
                  <Link key={hit.slug} href={geographyHref(hit)} className="block rounded-lg px-2 py-1.5 text-sm hover:bg-white/5" onClick={() => setHits([])}>
                    {hit.name}
                  </Link>
                ))}
              </div>
            )}
          </div>
          {groups.map((group) => {
            const open = openGroups[group.label] ?? true;
            return (
              <div key={group.label} className="mb-2">
                <button
                  type="button"
                  className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-[10px] uppercase tracking-[0.16em] text-mist hover:bg-white/5"
                  onClick={() => setOpenGroups((current) => ({ ...current, [group.label]: !open }))}
                >
                  <span>{group.label}</span>
                  <span className="text-cyan">{open ? "–" : "+"}</span>
                </button>
                {open &&
                  group.items.map(([label, href]) => {
                    const active = pathname === href.split("?")[0];
                    return (
                      <Link
                        key={href}
                        href={href}
                        className={`mt-0.5 block rounded-lg border-l-2 px-2.5 py-1.5 text-sm transition ${
                          active ? "border-cyan bg-cyan/10 text-cyan" : "border-transparent text-paper/85 hover:bg-white/5"
                        }`}
                      >
                        {label}
                      </Link>
                    );
                  })}
              </div>
            );
          })}
        </aside>
        <main className="min-w-0 animate-fade-up">{children}</main>
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
