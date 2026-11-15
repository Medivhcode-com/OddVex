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
  const text = Math.abs(probability * 100).toFixed(digits);
  // A true minus sign, and never a "-0.0%".
  return `${probability < 0 && Number(text) !== 0 ? '−' : ''}${text}%`;
}

/** A fraction as a signed percentage: 0.125 is "+12.5%", -0.02 is "−2.0%", zero is unsigned. */
export function formatSignedPercent(fraction: number | null | undefined, digits = 1): string {
  if (fraction === null || fraction === undefined || Number.isNaN(fraction)) return 'n/a';
  const text = Math.abs(fraction * 100).toFixed(digits);
  if (Number(text) === 0) return `${text}%`;
  return `${fraction > 0 ? '+' : '−'}${text}%`;
}

/** "$1,250.00", "−$25.00"; with `signed`, gains carry a plus: "+$22.73". Grouping is done by hand so it does not depend on the engine's Intl data. */
export function formatMoney(amount: number, opts: { signed?: boolean } = {}): string {
  const [whole, cents] = Math.abs(amount).toFixed(2).split('.');
  const abs = `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${cents}`;
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

/** "Nov 15" in the device's time zone. */
export function formatDay(iso: string, timeZone?: string): string {
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone }).format(new Date(iso));
}

/** "player_prop" becomes "Player Prop". Used for API keys such as markets and results. */
export function titleCase(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/** What a person typed as odds, ready for the API: trimmed, typographic minus signs made plain. The API parses it. */
export function cleanOdds(raw: string): string {
  return raw.trim().replace(/[−–]/g, '-');
}

/** Typed American odds shown back with a sign: "150" is "+150", "-110" is "−110". Display only. */
export function showTypedAmerican(odds: string): string {
  return odds.startsWith('-') || odds.startsWith('+') ? odds.replace('-', '−') : `+${odds}`;
}
