import { useEffect, useEffectEvent, useState } from 'react';

type Page<T> = { items: T[]; next_before?: string | null };
type Loaded<T> = { key: string; items: T[]; next: string | null };

export type Paged<T> = {
  /** Null until the first page for this `key` has arrived. */
  items: T[] | null;
  /** Set when the latest load of the first page failed. Can be set together with `items` after a failed refresh. */
  error: unknown;
  refreshing: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  /** Set when "Load more" failed; the pages already loaded stay on screen. */
  moreError: unknown;
  refresh: () => void;
  retry: () => void;
  loadMore: () => void;
  /** Changes the loaded items in place, after a like, a delete or a new comment. */
  update: (change: (items: T[]) => T[]) => void;
};

/**
 * A newest-first list read a page at a time with the API's `before` cursor. Like `useResource` it has no
 * cache and no polling: the first page loads when `key` or `revision` changes, on `refresh()` and on
 * `retry()`. A page that arrives after `key` changed is dropped.
 */
export function usePaged<T extends { id: string }>(key: string, fetchPage: (before: string | null) => Promise<Page<T>>, revision = 0): Paged<T> {
  const [loaded, setLoaded] = useState<Loaded<T> | null>(null);
  const [failure, setFailure] = useState<{ key: string; error: unknown } | null>(null);
  const [moreFailure, setMoreFailure] = useState<{ key: string; error: unknown } | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const load = useEffectEvent(fetchPage);

  useEffect(() => {
    let active = true;
    load(null).then(
      (page) => {
        if (!active) return;
        setLoaded({ key, items: page.items, next: page.next_before ?? null });
        setFailure(null);
        setMoreFailure(null);
        setRefreshing(false);
      },
      (error: unknown) => {
        if (!active) return;
        setFailure({ key, error });
        setRefreshing(false);
      },
    );
    return () => {
      active = false;
    };
  }, [key, attempt, revision]);

  const current = loaded?.key === key ? loaded : null;

  function loadMore() {
    if (!current?.next || loadingMore) return;
    setLoadingMore(true);
    setMoreFailure(null);
    fetchPage(current.next).then(
      (page) => {
        setLoadingMore(false);
        setLoaded((now) => {
          if (!now || now.key !== key) return now;
          const seen = new Set(now.items.map((item) => item.id));
          return { key, items: [...now.items, ...page.items.filter((item) => !seen.has(item.id))], next: page.next_before ?? null };
        });
      },
      (error: unknown) => {
        setLoadingMore(false);
        setMoreFailure({ key, error });
      },
    );
  }

  return {
    items: current ? current.items : null,
    error: failure?.key === key ? failure.error : undefined,
    refreshing: refreshing && current !== null,
    hasMore: Boolean(current?.next),
    loadingMore,
    moreError: moreFailure?.key === key ? moreFailure.error : undefined,
    refresh: () => {
      setRefreshing(true);
      setAttempt((n) => n + 1);
    },
    retry: () => {
      setFailure(null);
      setAttempt((n) => n + 1);
    },
    loadMore,
    update: (change) => setLoaded((now) => (now && now.key === key ? { ...now, items: change(now.items) } : now)),
  };
}
