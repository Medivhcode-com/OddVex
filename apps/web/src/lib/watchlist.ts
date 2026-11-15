import "server-only";
import type { Schemas } from "@oddvex/types";
import { api } from "@/lib/api";

export type WatchItem = Schemas["WatchlistItemOut"];

/** The signed-in user's watchlist, or an empty list when signed out or unavailable. */
export async function getWatchlist(signedIn: boolean): Promise<WatchItem[]> {
  if (!signedIn) return [];
  try {
    return (await api<Schemas["WatchlistOut"]>("/v1/watchlist", { auth: true })).items;
  } catch {
    return [];
  }
}

export function watchId(items: WatchItem[], kind: WatchItem["kind"], refId: string): string | null {
  return items.find((item) => item.kind === kind && item.ref_id === refId)?.id ?? null;
}
