/**
 * How long to wait after a `429 rate_limited`. The API puts the wait in
 * `error.details.retry_after_seconds` (and in the `Retry-After` header); these helpers turn it
 * into words. Rounding is always up, so the text never promises a shorter wait than the API's.
 */

/** The wait the API asked for, in seconds, or null when the error carries none. */
export function retryAfterSeconds(details: unknown): number | null {
  if (!details || typeof details !== "object") return null;
  const value = (details as { retry_after_seconds?: unknown }).retry_after_seconds;
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : null;
}

const plural = (count: number, unit: string) => `${count} ${unit}${count === 1 ? "" : "s"}`;

/** "30 seconds", "15 minutes", "2 hours". */
export function waitText(seconds: number): string {
  const whole = Math.max(1, Math.ceil(seconds));
  if (whole < 60) return plural(whole, "second");
  if (whole < 3600) return plural(Math.ceil(whole / 60), "minute");
  return plural(Math.ceil(whole / 3600), "hour");
}

/** "Try again in 15 minutes." from the API's details, or `fallback` when it gave no time. */
export function tryAgainText(details: unknown, fallback = "Try again later."): string {
  const seconds = retryAfterSeconds(details);
  return seconds === null ? fallback : `Try again in ${waitText(seconds)}.`;
}
