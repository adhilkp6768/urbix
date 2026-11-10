"use client";

import { useEffect, useRef } from "react";

export function SeriesChart({ points, color = "#1f6f8b" }: { points: { name: string; value: number | null }[]; color?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    let chart: { dispose: () => void; resize: () => void } | null = null;
    let disposed = false;
    const onResize = () => chart?.resize();
    import("echarts").then((echarts) => {
      if (disposed || !ref.current) return;
      const instance = echarts.init(ref.current, undefined, { renderer: "canvas" });
      chart = instance;
      instance.setOption({
        backgroundColor: "transparent",
        grid: { left: 44, right: 12, top: 20, bottom: 32 },
        tooltip: {
          trigger: "axis",
          backgroundColor: "rgba(255, 255, 255, 0.96)",
          borderColor: "#c5d0da",
          textStyle: { color: "#14202b", fontSize: 12 },
        },
        xAxis: {
          type: "category",
          data: points.map((point) => point.name),
          axisLabel: { color: "#5c6e7d", fontSize: 10 },
          axisLine: { lineStyle: { color: "#c5d0da" } },
          axisTick: { show: false },
        },
        yAxis: {
          type: "value",
          axisLabel: { color: "#5c6e7d", fontSize: 10 },
          splitLine: { lineStyle: { color: "rgba(197, 208, 218, 0.9)", type: "dashed" } },
        },
        series: [
          {
            type: "line",
            data: points.map((point) => point.value),
            showSymbol: points.length < 24,
            symbolSize: 6,
            smooth: 0.2,
            lineStyle: { color, width: 2.5 },
            itemStyle: { color },
            areaStyle: {
              color: {
                type: "linear",
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: `${color}33` },
                  { offset: 1, color: `${color}05` },
                ],
              },
            },
          },
        ],
      });
    });
    window.addEventListener("resize", onResize);
    return () => {
      disposed = true;
      window.removeEventListener("resize", onResize);
      chart?.dispose();
    };
  }, [points, color]);
  if (!points.length) return <p className="text-sm text-mist">No time series is available for this selection.</p>;
  return <div ref={ref} className="h-56 w-full" />;
}
