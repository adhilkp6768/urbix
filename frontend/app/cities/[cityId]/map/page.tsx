"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { UrbanMap } from "@/components/maps/UrbanMap";
import { useApi } from "@/lib/useApi";

const layers = ["admin", "traffic", "environment", "waste", "transit", "roads", "population", "crime"];

type MapData = { type: "FeatureCollection"; features: []; note: string; count: number; center?: [number, number] | null };

export default function MapPage() {
  const params = useParams<{ cityId: string }>();
  const [layer, setLayer] = useState("admin");
  const [pitch, setPitch] = useState(0);
  const state = useApi<MapData>(`/api/v1/maps/geojson?city=${params.cityId}&layer=${layer}`);
  const [view, setView] = useState<MapData | null>(null);

  useEffect(() => {
    setView(null);
  }, [params.cityId]);

  useEffect(() => {
    if (state.status === "ready" && state.data) setView(state.data);
  }, [state.status, state.data]);

  return (
    <div className="grid h-[calc(100vh-49px)] min-h-[560px] grid-cols-1 md:grid-cols-[200px_minmax(0,1fr)]">
      <aside className="max-h-52 overflow-auto border-b border-line bg-shell p-3 md:max-h-none md:border-b-0 md:border-r">
        <div className="text-[10px] uppercase tracking-[0.16em] text-mist">Layers</div>
        {layers.map((item) => (
          <button type="button" key={item} onClick={() => setLayer(item)} className={`mt-1 block w-full border-l-2 px-2 py-1.5 text-left text-sm capitalize ${layer === item ? "border-cyan bg-cyan/10 text-cyan" : "border-transparent hover:bg-white/5"}`}>{item}</button>
        ))}
        <div className="mt-4 text-[10px] uppercase tracking-[0.16em] text-mist">View</div>
        <button type="button" onClick={() => setPitch(pitch ? 0 : 50)} className="mt-2 border border-cyan/50 bg-cyan/10 px-2 py-1 text-sm text-cyan">{pitch ? "Show 2D" : "Show 3D"}</button>
      </aside>
      <div className="relative min-h-[420px]">
        {view ? <UrbanMap key={params.cityId} data={view} pitch={pitch} /> : <div className="grid h-full place-items-center text-sm text-mist">{state.status === "error" ? state.error : "Loading map"}</div>}
        {view && (
          <div className="pointer-events-none absolute bottom-3 left-3 right-14 border border-line bg-shell/90 p-3 text-sm">
            <p className="text-mist">{view.note}</p>
            <p className="mt-1 font-mono text-xs text-cyan">{view.count} features{state.status === "loading" ? " · loading" : ""}</p>
          </div>
        )}
      </div>
    </div>
  );
}
