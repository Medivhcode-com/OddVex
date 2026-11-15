import { getWatchlist } from '@/api/client';
import type { WatchItem, WatchKind } from '@/api/types';
import { useResource, type Resource } from '@/hooks/use-resource';
import { useSession } from '@/providers/session';

/** The signed-in user's watchlist; an empty list when signed out. Reloads whenever a follow changes anywhere. */
export function useWatchlist(): Resource<WatchItem[]> {
  const { user, revision } = useSession();
  return useResource(
    `watchlist:${user?.id ?? 'signed-out'}`,
    (signal) => (user ? getWatchlist(signal) : Promise.resolve<WatchItem[]>([])),
    revision.watchlist,
  );
}

/** The watchlist item id for this team, player or game, or null when it is not followed. */
export function watchId(items: readonly WatchItem[] | undefined, kind: WatchKind, refId: string): string | null {
  return items?.find((item) => item.kind === kind && item.ref_id === refId)?.id ?? null;
}
