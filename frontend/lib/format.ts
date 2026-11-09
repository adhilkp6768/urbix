export function formatValue(value: unknown, unit?: string | null) {
  if (value === null || value === undefined || value === "") return "Unavailable";
  const number = typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 1 }) : String(value);
  return unit ? `${number} ${unit}` : number;
}
