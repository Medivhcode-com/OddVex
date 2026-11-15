import { useCallback, useEffect, useEffectEvent, useState } from 'react';

export type Resource<T> = {
  /** `loading`: nothing to show yet. `ready`: `data` is set. `error`: the load failed and there is no data. */
  status: 'loading' | 'ready' | 'error';
  data: T | undefined;
  /** Set when the latest attempt failed. Can be set together with `data` if a refresh failed. */
  error: unknown;
  /** A reload is in flight while earlier data stays on screen (pull-to-refresh). */
  refreshing: boolean;
  /** Load again. Keeps current data visible; after an error it shows the loading state. */
  reload: () => void;
};

type Settled<T> = { key: string; token: string; data: T | undefined; error: unknown };

/**
 * Loads a resource and reloads it when `key` changes or `reload()` is called.
 * Deliberately small: no cache, no retries, no polling. Stale responses are dropped.
 * A change of `revision` reloads like `reload()` does, keeping the current data on screen meanwhile; screens
 * pass the session's bet or watchlist counter so a change made on one tab shows up on the others.
 */
export function useResource<T>(key: string, fetcher: (signal: AbortSignal) => Promise<T>, revision = 0): Resource<T> {
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled<T>>({ key: '', token: '', data: undefined, error: undefined });
  const token = `${key}#${attempt}#${revision}`;
  const load = useEffectEvent(fetcher);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    load(controller.signal).then(
      (data) => {
        if (active) setSettled({ key, token, data, error: undefined });
      },
      (error: unknown) => {
        if (active) setSettled((prev) => ({ key, token, data: prev.key === key ? prev.data : undefined, error }));
      },
    );
    return () => {
      active = false;
      controller.abort();
    };
  }, [key, token]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  const pending = settled.token !== token;
  const data = settled.key === key ? settled.data : undefined;
  const error = settled.key === key && !pending ? settled.error : undefined;
  const status = data !== undefined ? 'ready' : error !== undefined ? 'error' : 'loading';
  return { status, data, error, refreshing: pending && data !== undefined, reload };
}
