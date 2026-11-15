/** Pure display helpers. No odds math lives here: prices arrive from the API already converted. */

export type OddsFormat = "american" | "decimal";

export function formatAmerican(value: number): string {
  const rounded = Math.round(value);
  return rounded > 0 ? `+${rounded}` : `${rounded}`.replace("-", "−");
}

export function formatDecimal(value: number): string {
  return value.toFixed(2);
}

export function formatPrice(price: { american: number; decimal: number }, format: OddsFormat): string {
  return format === "american" ? formatAmerican(price.american) : formatDecimal(price.decimal);
}

export function formatLine(line: number | null | undefined, opts: { signed?: boolean } = {}): string {
  if (line === null || line === undefined) return "";
  const abs = Number.isInteger(line) ? `${Math.abs(line)}` : Math.abs(line).toFixed(1);
  if (!opts.signed) return line < 0 ? `−${abs}` : abs;
  if (line === 0) return "PK";
  return line > 0 ? `+${abs}` : `−${abs}`;
}

export function formatPercent(probability: number | null | undefined, digits = 1): string {
  if (probability === null || probability === undefined || Number.isNaN(probability)) return "n/a";
  return `${(probability * 100).toFixed(digits)}%`;
}

export function formatMoney(amount: number, opts: { signed?: boolean } = {}): string {
  const abs = Math.abs(amount).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (opts.signed) return amount > 0 ? `+$${abs}` : amount < 0 ? `−$${abs}` : `$${abs}`;
  return amount < 0 ? `−$${abs}` : `$${abs}`;
}

/** "42s ago", "6 min ago", "3h ago". `now` is injectable so the output is testable. */
export function formatAge(iso: string, now: Date = new Date()): string {
  const seconds = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function formatStart(iso: string, timeZone = "America/New_York"): string {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone,
    timeZoneName: "short",
  }).format(new Date(iso));
}

export function formatDay(iso: string, timeZone = "America/New_York"): string {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone }).format(new Date(iso));
}

export function titleCase(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
