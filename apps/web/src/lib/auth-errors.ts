import { ApiError, ApiUnavailableError } from "@/lib/api";
import { tryAgainText } from "@/lib/retry";

/** One sentence for an error from the sign-in, sign-up, reset and account calls in `lib/auth-actions.ts`. */
export function describeAuthError(error: unknown, fallback: string): string {
  if (error instanceof ApiUnavailableError) return "OddVex can't reach its data service right now. Try again in a moment.";
  if (error instanceof ApiError) {
    // The sign-in lock can last 15 minutes (failed attempts are counted per email and network, and
    // per email across all networks), so the wait comes from the API's
    // `details.retry_after_seconds`; without it the wording names no time at all.
    if (error.status === 429) return `Too many attempts. ${tryAgainText(error.details)}`;
    return error.message || fallback;
  }
  return fallback;
}
