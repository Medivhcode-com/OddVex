import { useCallback, useEffect, useEffectEvent, useRef, useState } from 'react';

import { getBets } from '@/api/client';
import type { Bet } from '@/api/types';

/** Settled bets asked for at a time. */
export const SETTLED_PAGE = 50;
/** The largest `limit` the API accepts on `GET /v1/bets`. */
const MAX_LIMIT = 1000;

export type SettledBets = {
  /** `loading`: nothing to show yet. `ready`: `bets` is set. `error`: the first load failed. */
  status: 'loading' | 'ready' | 'error';
  bets: Bet[];
  /** Set when the latest load failed. Can be set together with `bets` if a reload failed. */
  error: unknown;
  refreshing: boolean;
  /** The last answer filled its page, so there may be older bets. */
  hasMore: boolean;
  loadingMore: boolean;
  /** Set when "Show more" failed; the bets already loaded stay on screen. */
  moreError: unknown;
  reload: () => void;
  showMore: () => void;
};

type Settled = { key: string; token: string; bets: Bet[] | undefined; more: boolean; error: unknown };

/**
 * The user's settled bets, most recently placed first, read a page at a time with the API's `status`,
 * `limit` and `offset` parameters. `showMore()` asks for the next page and adds it. A reload (`reload()`, or
 * a change of `revision` after a bet was settled, edited or deleted) asks again for as many bets as are on
 * screen, in one request of up to 1,000, so the person keeps their place in the list. Like `useResource`:
 * no cache, no retries, no polling.
 */
export function useSettledBets(userId: string, revision = 0): SettledBets {
  const key = `bets-settled:${userId}`;
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled>({ key: '', token: '', bets: undefined, more: false, error: undefined });
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreFailure, setMoreFailure] = useState<{ key: string; error: unknown } | null>(null);
  // Goes up with every reload, so a "Show more" answer that arrives after one is dropped.
  const generation = useRef(0);
  const token = `${key}#${attempt}#${revision}`;
  const current = settled.key === key ? settled.bets : undefined;

  const load = useEffectEvent((signal: AbortSignal) => {
    const shown = current?.length ?? 0;
    const limit = Math.min(MAX_LIMIT, Math.max(SETTLED_PAGE, Math.ceil(shown / SETTLED_PAGE) * SETTLED_PAGE));
    return getBets({ status: 'settled', limit, offset: 0 }, signal).then((bets) => ({ bets, more: bets.length === limit }));
  });

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    generation.current += 1;
    load(controller.signal).then(
      ({ bets, more }) => {
        if (!active) return;
        setSettled({ key, token, bets, more, error: undefined });
        setMoreFailure(null);
      },
      (error: unknown) => {
        if (active) setSettled((prev) => ({ key, token, bets: prev.key === key ? prev.bets : undefined, more: prev.key === key && prev.more, error }));
      },
    );
    return () => {
      active = false;
      controller.abort();
    };
  }, [key, token]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  function showMore() {
    if (!current || !settled.more || loadingMore) return;
    const started = generation.current;
    setLoadingMore(true);
    setMoreFailure(null);
    getBets({ status: 'settled', limit: SETTLED_PAGE, offset: current.length }).then(
      (page) => {
        setLoadingMore(false);
        if (generation.current !== started) return;
        setSettled((now) => {
          if (now.key !== key || !now.bets) return now;
          const seen = new Set(now.bets.map((bet) => bet.id));
          return { ...now, bets: [...now.bets, ...page.filter((bet) => !seen.has(bet.id))], more: page.length === SETTLED_PAGE };
        });
      },
      (error: unknown) => {
        setLoadingMore(false);
        if (generation.current === started) setMoreFailure({ key, error });
      },
    );
  }

  const pending = settled.token !== token;
  const error = settled.key === key && !pending ? settled.error : undefined;
  return {
    status: current !== undefined ? 'ready' : error !== undefined ? 'error' : 'loading',
    bets: current ?? [],
    error,
    refreshing: pending && current !== undefined,
    hasMore: current !== undefined && settled.more,
    loadingMore,
    moreError: moreFailure?.key === key ? moreFailure.error : undefined,
    reload,
    showMore,
  };
}
