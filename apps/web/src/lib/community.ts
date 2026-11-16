import "server-only";
import { cache } from "react";
import type { Schemas } from "@oddvex/types";
import { api, apiOrNull } from "@/lib/api";
import type { MyProfile } from "@/lib/community-copy";
import { flagOn, requireFlag, type Flags } from "@/lib/flags";
import { currentUser } from "@/lib/session";
import type { User } from "@/lib/types";

export const COMMUNITY_HOME = "/app/community";
export const PAGE_SIZE = 20;

export const profileHref = (handle: string) => `${COMMUNITY_HOME}/profiles/${encodeURIComponent(handle)}`;
export const pickHref = (id: string) => `${COMMUNITY_HOME}/picks/${encodeURIComponent(id)}`;

/** The caller's own community profile, or null until they create one. One request per render. */
export const getMyProfile = cache(async (): Promise<MyProfile | null> => apiOrNull<MyProfile>("/v1/community/profile", { auth: true }));

export const getGuidelines = cache(async () => api<Schemas["CommunityGuidelinesOut"]>("/v1/community/guidelines"));

export type CommunityContext = { flags: Flags; leaderboard: boolean; user: User | null; me: MyProfile | null };

/**
 * Every community page calls this first. While the `community` flag (or any extra flag the
 * page names) is off the page is the standard not-found page; the proxy already answered the
 * request with a real 404. Signed-out visitors get `user: null` and the page asks them to log in.
 */
export async function communityContext(...extraFlags: string[]): Promise<CommunityContext> {
  const flags = await requireFlag("community", ...extraFlags);
  const user = await currentUser();
  const me = user ? await getMyProfile() : null;
  return { flags, leaderboard: flagOn(flags, "community_leaderboard"), user, me };
}
