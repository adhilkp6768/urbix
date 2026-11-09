"use client";

import { useEffect, useRef } from "react";

export function SeriesChart({ points }: { points: { name: string; value: number | null }[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    let chart: { dispose: () => void; resize: () => void } | null = null;
    let disposed = false;
    const onResize = () => chart?.resize();
    import("echarts").then((echarts) => {
      if (disposed || !ref.current) return;
      const instance = echarts.init(ref.current);
      chart = instance;
      instance.setOption({
        backgroundColor: "transparent",
        grid: { left: 48, right: 12, top: 16, bottom: 28 },
        tooltip: { trigger: "axis" },
        xAxis: { type: "category", data: points.map((point) => point.name), axisLabel: { color: "#b7c9d8", fontSize: 10 }, axisLine: { lineStyle: { color: "#38536c" } } },
        yAxis: { type: "value", axisLabel: { color: "#b7c9d8", fontSize: 10 }, splitLine: { lineStyle: { color: "#38536c" } } },
        series: [{ type: "line", data: points.map((point) => point.value), showSymbol: false, lineStyle: { color: "#6ad7ef", width: 2 }, areaStyle: { color: "rgba(106,215,239,0.16)" } }],
      });
    });
    window.addEventListener("resize", onResize);
    return () => {
      disposed = true;
      window.removeEventListener("resize", onResize);
      chart?.dispose();
    };
  }, [points]);
  if (!points.length) return <p className="text-sm text-mist">No time series is available for this selection.</p>;
  return <div ref={ref} className="h-56 w-full" />;
}
