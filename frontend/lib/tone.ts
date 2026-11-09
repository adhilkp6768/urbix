export function domainAccent(name: string) {
  const key = name.toLowerCase();
  if (key.includes("traffic")) return "#6ad7ef";
  if (key.includes("environment") || key.includes("air")) return "#7dcea0";
  if (key.includes("crime") || key.includes("safety")) return "#f0997f";
  if (key.includes("population")) return "#c4b5fd";
  if (key.includes("waste")) return "#e4c56a";
  if (key.includes("transport")) return "#7eb6ff";
  if (key.includes("infrastructure")) return "#8fd0c4";
  return "#6ad7ef";
}

export function statusTone(status: string) {
  if (status === "available" || status === "integrated" || status === "succeeded" || status === "ok") {
    return "border-good/40 bg-good/10 text-good";
  }
  if (status === "partial" || status === "running") {
    return "border-warn/40 bg-warn/10 text-warn";
  }
  if (status === "failed" || status === "error") {
    return "border-bad/40 bg-bad/10 text-bad";
  }
  return "border-line bg-white/5 text-mist";
}
