/**
 * Request metadata the web server passes on to the API: the visitor's address and a request id.
 * Pure helpers, shared by the proxy, the server-side `api()` and the `/api/ov` bridge.
 */

/** Same shape the API accepts (`services/api` middleware); anything else is replaced, never echoed. */
const REQUEST_ID_RE = /^[A-Za-z0-9._-]{8,64}$/;
/** IPv4 or IPv6 literal characters only, so a forged header cannot smuggle anything else upstream. */
const IP_RE = /^[0-9A-Fa-f:.]{2,45}$/;

type HeaderReader = { get(name: string): string | null };

export function isRequestId(value: string | null | undefined): value is string {
  return typeof value === "string" && REQUEST_ID_RE.test(value);
}

/** Reuses a well-formed incoming id so one id follows a request across web and API logs. */
export function requestIdFrom(headers: HeaderReader): string {
  const incoming = headers.get("x-request-id");
  return isRequestId(incoming) ? incoming : crypto.randomUUID();
}

/**
 * The visitor's address as the hosting platform reports it: the first `X-Forwarded-For` hop,
 * else `X-Real-IP`. This is only as trustworthy as the platform in front of the web server:
 * it must overwrite (not append to) a client-supplied `X-Forwarded-For`. Without such a
 * platform (local runs) there is no header and nothing is forwarded.
 */
export function clientIpFrom(headers: HeaderReader): string | undefined {
  const first = headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  if (first && IP_RE.test(first)) return first;
  const real = headers.get("x-real-ip")?.trim();
  if (real && IP_RE.test(real)) return real;
  return undefined;
}

/**
 * Headers for an upstream API call. Exactly one address is sent as `X-Forwarded-For`.
 *
 * The API ignores `X-Forwarded-For` unless it runs with `ODDVEX_TRUST_PROXY=true`, and that
 * must only be set when the API is reachable solely through this web server or another
 * trusted proxy. If the API is also reachable directly, any caller could forge the header
 * and pick its own rate-limit bucket and audit-log address.
 */
export function upstreamMetaHeaders(headers: HeaderReader): { requestId: string; headers: Record<string, string> } {
  const requestId = requestIdFrom(headers);
  const out: Record<string, string> = { "x-request-id": requestId };
  const ip = clientIpFrom(headers);
  if (ip) out["x-forwarded-for"] = ip;
  return { requestId, headers: out };
}
