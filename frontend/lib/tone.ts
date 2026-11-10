export function domainAccent(name: string) {
  const key = name.toLowerCase();
  if (key.includes("traffic")) return "#1f6f8b";
  if (key.includes("environment") || key.includes("air")) return "#2f8f6b";
  if (key.includes("crime") || key.includes("safety")) return "#c45c4a";
  if (key.includes("population")) return "#9a7b4f";
  if (key.includes("waste")) return "#b8862a";
  if (key.includes("transport")) return "#3a7ca5";
  if (key.includes("infrastructure")) return "#4d7c8a";
  return "#1f6f8b";
}

export function statusTone(status: string) {
  if (status === "available" || status === "integrated" || status === "succeeded" || status === "ok" || status === "deep" || status === "trained") {
    return "border-good/35 bg-good/10 text-good";
  }
  if (status === "partial" || status === "running" || status === "broad" || status === "weather" || status === "thin") {
    return "border-warn/35 bg-warn/10 text-warn";
  }
  if (status === "failed" || status === "error" || status === "unavailable") {
    return "border-bad/35 bg-bad/10 text-bad";
  }
  return "border-line bg-raised text-mist";
}

export function depthLabel(depth?: string) {
  if (depth === "deep") return "Deep extract";
  if (depth === "broad") return "Multi-domain";
  if (depth === "thin") return "Limited extract";
  if (depth === "weather") return "Weather only";
  return "Reference";
}
