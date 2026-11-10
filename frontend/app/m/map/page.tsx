"use client";

import { useEffect, useState } from "react";
import { UrbanMap } from "@/components/maps/UrbanMap";
import { apiGet } from "@/lib/api";
import { useMobile } from "@/components/mobile/AppFrame";

const LAYERS = [
  ["admin", "Districts"],
  ["traffic", "Traffic"],
  ["environment", "Air"],
  ["population", "People"],
  ["crime", "Safety"],
  ["transit", "Transit"],
  ["roads", "Roads"],
  ["waste", "Waste"],
] as const;

type LayerData = { type: "FeatureCollection"; features: { geometry?: { type?: string; coordinates?: unknown }; properties?: Record<string, unknown> }[]; center?: [number, number] | null; note?: string; count?: number };

export default function MobileMapPage() {
  const mobile = useMobile();
  const [layer, setLayer] = useState<(typeof LAYERS)[number][0]>("admin");
  const [data, setData] = useState<LayerData>({ type: "FeatureCollection", features: [] });

  useEffect(() => {
    let stop = false;
    apiGet<LayerData>(`/api/v1/maps/geojson?city=${mobile.city}&layer=${layer}`)
      .then((next) => {
        if (!stop) setData(next);
      })
      .catch(() => {
        if (!stop) setData({ type: "FeatureCollection", features: [], note: "This layer could not be loaded." });
      });
    return () => {
      stop = true;
    };
  }, [mobile.city, layer, mobile.tick]);

  const values = data.features.map((feature) => feature.properties?.value).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const unit = String(data.features.find((feature) => typeof feature.properties?.value === "number")?.properties?.unit || "");
  const format = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: value < 100 ? 1 : 0 });

  return (
    <div className="relative h-full">
      <UrbanMap data={data} pitch={40} />
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 px-3" style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top))" }}>
        <div className="pointer-events-auto flex gap-2 overflow-x-auto pb-2">
          {LAYERS.map(([code, label]) => (
            <button
              key={code}
              type="button"
              onClick={() => setLayer(code)}
              className={`shrink-0 rounded-full border px-3 py-1.5 text-xs shadow-soft backdrop-blur ${code === layer ? "border-cyan bg-panel text-cyan" : "border-line bg-panel/90 text-mist"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="pointer-events-none absolute inset-x-3 bottom-3 z-10 rounded-2xl border border-line bg-panel/95 p-3 text-xs text-mist shadow-soft backdrop-blur">
        {values.length > 1 && (
          <div className="mb-2">
            <div className="h-1.5 rounded-full" style={{ background: "linear-gradient(90deg, #7eb6c9, #1f6f8b, #c45c4a)" }} />
            <div className="mt-1 flex justify-between font-mono text-[10px] text-paper">
              <span>{format(Math.min(...values))}</span>
              <span className="text-mist">{unit}</span>
              <span>{format(Math.max(...values))}</span>
            </div>
          </div>
        )}
        <p>{data.note || "Layer note is unavailable."}</p>
        <p className="mt-1 font-mono text-cyan">{data.features?.length ?? data.count ?? 0} features</p>
      </div>
    </div>
  );
}
