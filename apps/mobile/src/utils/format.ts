/**
 * Pure display helpers, ported from apps/web/src/lib/format.ts.
 * No odds math lives here: prices arrive from the API already converted.
 */

export type OddsFormat = 'american' | 'decimal';

/** Uses a true minus sign (U+2212) so negatives align with plus signs in a tabular face. */
export function formatAmerican(value: number): string {
  const rounded = Math.round(value);
  return rounded > 0 ? `+${rounded}` : `${rounded}`.replace('-', '−');
}

export function formatDecimal(value: number): string {
  return value.toFixed(2);
}

export function formatPrice(price: { american: number; decimal: number }, format: OddsFormat): string {
  return format === 'american' ? formatAmerican(price.american) : formatDecimal(price.decimal);
}

export function formatLine(line: number | null | undefined, opts: { signed?: boolean } = {}): string {
  if (line === null || line === undefined) return '';
  const abs = Number.isInteger(line) ? `${Math.abs(line)}` : Math.abs(line).toFixed(1);
  if (!opts.signed) return line < 0 ? `−${abs}` : abs;
  if (line === 0) return 'PK';
  return line > 0 ? `+${abs}` : `−${abs}`;
}

export function formatPercent(probability: number | null | undefined, digits = 1): string {
  if (probability === null || probability === undefined || Number.isNaN(probability)) return 'n/a';
  return `${(probability * 100).toFixed(digits)}%`;
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

/** "Sat, Nov 15, 7:30 PM" in the device's time zone and locale conventions for en-US. */
export function formatStart(iso: string, timeZone?: string): string {
  return new Intl.DateTimeFormat('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone,
  }).format(new Date(iso));
}
