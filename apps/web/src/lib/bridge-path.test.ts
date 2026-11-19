import { describe, expect, it } from "vitest";
import { bridgePath } from "./bridge-path";

/** Segments as the route handler receives them: already percent-decoded once by Next.js. */
describe("bridgePath", () => {
  it("returns the API path for a listed area", () => {
    expect(bridgePath(["v1", "me"])).toBe("/v1/me");
    expect(bridgePath(["v1", "events", "evt_nba_20261119_2", "odds"])).toBe("/v1/events/evt_nba_20261119_2/odds");
    expect(bridgePath(["v1", "bets", "3f2b7c1e-8a41-4d59-9c0e-5a1b2c3d4e5f", "settle"])).toBe("/v1/bets/3f2b7c1e-8a41-4d59-9c0e-5a1b2c3d4e5f/settle");
    expect(bridgePath(["v1", "community", "profiles", "demo_bettor"])).toBe("/v1/community/profiles/demo_bettor");
    expect(bridgePath(["v1", "me", "export.csv"])).toBe("/v1/me/export.csv");
  });

  it("covers every area the browser uses and nothing else", () => {
    for (const area of ["quant", "bets", "sync", "assistant", "events", "players", "props", "me", "watchlist", "alerts", "notifications", "value", "flags", "community"]) {
      expect(bridgePath(["v1", area]), area).toBe(`/v1/${area}`);
      expect(bridgePath(["v1", area, "x"]), area).toBe(`/v1/${area}/x`);
    }
    for (const area of ["admin", "auth", "dev", "meta", "health", "sports", "mexico", "Me", "ME", "", "me "]) {
      expect(bridgePath(["v1", area]), area).toBeNull();
      expect(bridgePath(["v1", area, "x"]), area).toBeNull();
    }
    expect(bridgePath(["health"])).toBeNull();
    expect(bridgePath(["v1"])).toBeNull();
    expect(bridgePath(["v2", "me"])).toBeNull();
    expect(bridgePath(["V1", "me"])).toBeNull();
  });

  it("refuses a segment that holds a separator, a dot segment or another layer of encoding", () => {
    for (const segment of [
      "me/../admin", // %2F decoded
      "..\\admin", // %5C decoded
      "..",
      ".",
      "...",
      "%2e%2e", // %252e%252e decoded
      "%2E%2E",
      ".%2e",
      "%2f",
      "%5c",
      "%252e",
      "x?y=1",
      "x#y",
      "..;",
      "x;y=1",
      "",
      " ",
      "x y",
      "\t",
      "x\n",
      "x\u0000",
      "‥", // two-dot leader
      "．．", // fullwidth full stops
      "／", // fullwidth solidus
      "x​", // zero-width space
    ]) {
      expect(bridgePath(["v1", "me", segment, "admin", "users"]), JSON.stringify(segment)).toBeNull();
      expect(bridgePath(["v1", "me", segment]), JSON.stringify(segment)).toBeNull();
      expect(bridgePath([segment, "v1", "me"]), JSON.stringify(segment)).toBeNull();
    }
    expect(bridgePath(["v1", "me/../admin/users"])).toBeNull();
    expect(bridgePath(["v1/admin/users"])).toBeNull();
    expect(bridgePath(["v1", "flags/../../health"])).toBeNull();
  });

  it("refuses anything that is not a list of strings", () => {
    for (const value of [undefined, null, "v1/me", [], [["v1", "me"]], ["v1", 7], ["v1", null], { 0: "v1", 1: "me", length: 2 }]) {
      expect(bridgePath(value)).toBeNull();
    }
  });
});
