import { createContext, use, useEffect, useRef, type ReactNode } from 'react';
import { AppState } from 'react-native';

import { getMeta } from '@/api/client';
import type { Meta } from '@/api/types';
import { useResource, type Resource } from '@/hooks/use-resource';

const MetaContext = createContext<Resource<Meta>>({
  status: 'loading',
  data: undefined,
  error: undefined,
  refreshing: false,
  reload: () => {},
});

/** How long to wait before asking again after each failed read in a row. The last pause repeats. */
export const META_RETRY_DELAYS_MS = [2_000, 5_000, 15_000, 30_000, 60_000] as const;

/**
 * Loads `GET /v1/meta` for the whole app. Screens use it to label synthetic data, so an unknown data mode
 * must not stay unknown: while no answer has ever arrived the read is repeated after a growing pause
 * (`META_RETRY_DELAYS_MS`), and it is repeated each time the app returns to the foreground. Once an answer
 * is in, a later read that fails leaves it in use. `useResource` itself never retries; the retry lives here.
 */
export function MetaProvider({ children }: { children: ReactNode }) {
  const meta = useResource('meta', getMeta);
  const { status, reload } = meta;
  const failures = useRef(0);

  useEffect(() => {
    if (status === 'ready') failures.current = 0;
    if (status !== 'error') return;
    const delay = META_RETRY_DELAYS_MS[Math.min(failures.current, META_RETRY_DELAYS_MS.length - 1)];
    failures.current += 1;
    // In the background nothing is on screen to label; the foreground listener below asks again.
    const timer = setTimeout(() => {
      if (AppState.currentState !== 'background') reload();
    }, delay);
    return () => clearTimeout(timer);
  }, [status, reload]);

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => {
      if (state !== 'active') return;
      failures.current = 0;
      reload();
    });
    return () => subscription.remove();
  }, [reload]);

  return <MetaContext value={meta}>{children}</MetaContext>;
}

export function useMeta(): Resource<Meta> {
  return use(MetaContext);
}

export function isSynthetic(meta: Meta | undefined): boolean {
  return meta?.data_mode === 'synthetic';
}

/** Real past games shifted in time, with simulated sportsbooks and prices. */
export function isReplay(meta: Meta | undefined): boolean {
  return meta?.data_mode === 'replay';
}
