import { isRequestId } from "@/lib/request-meta";

/**
 * How the `/app` error screen learns what went wrong. Pure; see `app-error.test.ts`.
 *
 * In a production build the browser receives neither the name nor the message of an error
 * thrown while a page renders on the server. React replaces both and passes on one field,
 * `digest`. So the one thing the screen has to tell apart, "the API could not be reached",
 * travels in the digest as a fixed marker followed by the request id. Nothing else is put
 * there: no message, no address, no stack.
 */
const API_UNAVAILABLE = "api_unavailable:";

/** The digest `ApiUnavailableError` carries. The marker is always present; the id only when well formed. */
export function apiUnavailableDigest(requestId?: string): string {
  return `${API_UNAVAILABLE}${isRequestId(requestId) ? requestId : ""}`;
}

/**
 * What the error screen shows for an error as it arrives in the browser.
 *
 * `reference` is the request id of the failed API call when there is one (the same id is in
 * the API's and the web server's log line), otherwise the digest Next.js made for the error.
 */
export function readAppError(error: { digest?: unknown }): { unreachable: boolean; reference: string | null } {
  const digest = typeof error.digest === "string" ? error.digest : "";
  if (digest.startsWith(API_UNAVAILABLE)) {
    const requestId = digest.slice(API_UNAVAILABLE.length);
    return { unreachable: true, reference: isRequestId(requestId) ? requestId : null };
  }
  return { unreachable: false, reference: digest || null };
}
