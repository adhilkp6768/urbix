"use client";

import maplibregl, { GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

type Feature = { geometry?: { type?: string; coordinates?: unknown }; properties?: Record<string, unknown> };
type Collection = { type: "FeatureCollection"; features: Feature[]; center?: [number, number] | null };

function numericValues(data: Collection) {
  return data.features
    .map((feature) => feature.properties?.value)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
}

function applyLayer(map: maplibregl.Map, data: Collection, pitch: number) {
  const source = map.getSource("urbix") as GeoJSONSource | undefined;
  if (!source) return;
  source.setData(data as GeoJSON.FeatureCollection);
  const values = numericValues(data);
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const mid = min + (max - min) / 2;
  const fill = values.length
    ? ["interpolate", ["linear"], ["coalesce", ["get", "value"], min], min, "#7eb6c9", mid, "#1f6f8b", max, "#c45c4a"]
    : "#1f6f8b";
  map.setPaintProperty("urbix-fill", "fill-color", fill as maplibregl.ExpressionSpecification);
  map.setPaintProperty("urbix-fill", "fill-opacity", values.length ? 0.58 : 0.34);
  const scaled = (fallback: string) =>
    (values.length
      ? ["case", ["==", ["typeof", ["get", "value"]], "number"], ["interpolate", ["linear"], ["get", "value"], min, "#7eb6c9", mid, "#1f6f8b", max, "#c45c4a"], fallback]
      : fallback) as maplibregl.ExpressionSpecification;
  map.setPaintProperty("urbix-line", "line-color", scaled("#1f6f8b"));
  map.setPaintProperty("urbix-point", "circle-color", scaled("#9a7b4f"));
  map.setPaintProperty("urbix-point", "circle-radius", data.features.length > 1500 ? 3 : values.length ? 6 : 4.5);
  if (data.features.length) {
    const bounds = new maplibregl.LngLatBounds();
    const extend = (coordinates: unknown) => {
      if (!Array.isArray(coordinates)) return;
      if (typeof coordinates[0] === "number" && typeof coordinates[1] === "number") {
        bounds.extend(coordinates as [number, number]);
        return;
      }
      coordinates.forEach(extend);
    };
    data.features.forEach((feature) => extend(feature.geometry?.coordinates));
    if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 36, maxZoom: 12, duration: 400, pitch });
  } else if (data.center && data.center[0] != null && data.center[1] != null) {
    map.easeTo({ center: data.center, zoom: 10, duration: 400, pitch });
  } else {
    map.easeTo({ pitch });
  }
}

export function UrbanMap({ data, pitch }: { data: Collection; pitch: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const dataRef = useRef(data);
  const pitchRef = useRef(pitch);
  dataRef.current = data;
  pitchRef.current = pitch;

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const initial = dataRef.current;
    const map = new maplibregl.Map({
      container: ref.current,
      style: "https://tiles.openfreemap.org/styles/liberty",
      center: initial.center || [-73.98, 40.73],
      zoom: 10,
      pitch: pitchRef.current,
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.on("load", () => {
      map.addSource("urbix", { type: "geojson", data: dataRef.current as GeoJSON.FeatureCollection });
      map.addLayer({
        id: "urbix-fill",
        type: "fill",
        source: "urbix",
        filter: ["match", ["geometry-type"], ["Polygon", "MultiPolygon"], true, false],
        paint: { "fill-color": "#1f6f8b", "fill-opacity": 0.34 },
      });
      map.addLayer({
        id: "urbix-outline",
        type: "line",
        source: "urbix",
        filter: ["match", ["geometry-type"], ["Polygon", "MultiPolygon"], true, false],
        paint: { "line-color": "#14202b", "line-width": 1 },
      });
      map.addLayer({
        id: "urbix-line",
        type: "line",
        source: "urbix",
        filter: ["match", ["geometry-type"], ["LineString", "MultiLineString"], true, false],
        paint: { "line-color": "#1f6f8b", "line-width": 2.4 },
      });
      map.addLayer({
        id: "urbix-point",
        type: "circle",
        source: "urbix",
        filter: ["==", ["geometry-type"], "Point"],
        paint: { "circle-radius": 4.5, "circle-color": "#9a7b4f", "circle-stroke-width": 1, "circle-stroke-color": "#ffffff" },
      });
      const layers = ["urbix-point", "urbix-line", "urbix-fill"];
      map.on("click", (event) => {
        const feature = map.queryRenderedFeatures(event.point, { layers })[0];
        if (!feature) return;
        const properties = feature.properties || {};
        const missing = properties.value == null || properties.value === "null";
        const value = missing ? "" : `<br/>${Number(properties.value).toLocaleString()} ${properties.unit || ""}`;
        const when = properties.period || properties.observed_at;
        const holder = document.createElement("div");
        holder.innerHTML = `<strong></strong>${value}${missing && properties.unit ? "<br/>Unavailable" : ""}${when ? `<br/><small>${String(when).slice(0, 16).replace("T", " ")}</small>` : ""}`;
        (holder.querySelector("strong") as HTMLElement).textContent = String(properties.name || "Area");
        new maplibregl.Popup({ closeButton: false }).setLngLat(event.lngLat).setDOMContent(holder).addTo(map);
      });
      for (const id of layers) {
        map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
      }
      applyLayer(map, dataRef.current, pitchRef.current);
      map.resize();
    });
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(ref.current);
    mapRef.current = map;
    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded() || !map.getSource("urbix")) return;
    applyLayer(map, data, pitch);
  }, [data, pitch]);

  return <div ref={ref} style={{ position: "absolute", inset: 0 }} />;
}
