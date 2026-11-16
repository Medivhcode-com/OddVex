import { describe, expect, it } from "vitest";
import { APP_NAV, flagsForPath } from "./site";

describe("flagsForPath", () => {
  it("needs no flag for ordinary pages", () => {
    expect(flagsForPath("/app")).toEqual([]);
    expect(flagsForPath("/app/games/evt_1")).toEqual([]);
    expect(flagsForPath("/app/admin/users")).toEqual([]);
    expect(flagsForPath("/app/communityx")).toEqual([]);
  });
  it("matches exact paths, with or without a trailing slash", () => {
    expect(flagsForPath("/app/value")).toEqual(["value_screen"]);
    expect(flagsForPath("/app/value/")).toEqual(["value_screen"]);
    expect(flagsForPath("/app/value/more")).toEqual([]);
  });
  it("puts every community URL behind the community flag", () => {
    for (const path of ["/app/community", "/app/community/", "/app/community/picks/abc", "/app/community/profiles/someone", "/app/community/settings", "/app/community/anything/else"]) {
      expect(flagsForPath(path), path).toEqual(["community"]);
    }
    expect(flagsForPath("/app/admin/community")).toEqual(["community"]);
  });
  it("needs both flags for the leaderboard", () => {
    expect(flagsForPath("/app/community/leaderboard")).toEqual(["community", "community_leaderboard"]);
    expect(flagsForPath("/app/community/leaderboard/")).toEqual(["community", "community_leaderboard"]);
  });
  it("lists the community entry behind its flag", () => {
    expect(APP_NAV.find((item) => item.href === "/app/community")?.flag).toBe("community");
  });
});
