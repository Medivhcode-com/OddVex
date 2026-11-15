import { createContext, use, type ReactNode } from 'react';

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

/** Loads `GET /v1/meta` once for the whole app. Screens use it to label synthetic data. */
export function MetaProvider({ children }: { children: ReactNode }) {
  const meta = useResource('meta', getMeta);
  return <MetaContext value={meta}>{children}</MetaContext>;
}

export function useMeta(): Resource<Meta> {
  return use(MetaContext);
}

export function isSynthetic(meta: Meta | undefined): boolean {
  return meta?.data_mode === 'synthetic';
}
