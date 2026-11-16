import { describe, expect, it } from "vitest";
import { clientIpFrom, isRequestId, requestIdFrom, upstreamMetaHeaders } from "./request-meta";

const h = (values: Record<string, string>) => new Headers(values);

describe("requestIdFrom", () => {
  it("reuses a well-formed incoming id", () => {
    expect(requestIdFrom(h({ "x-request-id": "abc-123_DEF.456" }))).toBe("abc-123_DEF.456");
  });
  it("replaces a missing or malformed id with a fresh one", () => {
    for (const bad of ["", "short", "has space in it", "x".repeat(65), "new\nline-12345"]) {
      const headers = new Headers();
      if (bad) headers.set("x-request-id", bad.replace("\n", " "));
      const id = requestIdFrom(headers);
      expect(isRequestId(id)).toBe(true);
      expect(id).not.toBe(bad);
    }
  });
});

describe("clientIpFrom", () => {
  it("takes the first forwarded hop", () => {
    expect(clientIpFrom(h({ "x-forwarded-for": "203.0.113.7, 10.0.0.1" }))).toBe("203.0.113.7");
  });
  it("falls back to x-real-ip", () => {
    expect(clientIpFrom(h({ "x-real-ip": "2001:db8::1" }))).toBe("2001:db8::1");
  });
  it("ignores values that are not addresses", () => {
    expect(clientIpFrom(h({ "x-forwarded-for": "<script>, 10.0.0.1", "x-real-ip": "not an ip" }))).toBeUndefined();
    expect(clientIpFrom(h({}))).toBeUndefined();
  });
});

describe("upstreamMetaHeaders", () => {
  it("sends one address and the request id", () => {
    const out = upstreamMetaHeaders(h({ "x-forwarded-for": "203.0.113.7, 10.0.0.1", "x-request-id": "req-12345678" }));
    expect(out).toEqual({ requestId: "req-12345678", headers: { "x-request-id": "req-12345678", "x-forwarded-for": "203.0.113.7" } });
  });
  it("omits the address when the platform supplied none", () => {
    expect(upstreamMetaHeaders(h({})).headers["x-forwarded-for"]).toBeUndefined();
  });
});
