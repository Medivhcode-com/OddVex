import { createContext, use, useEffect, useMemo, useRef, type ReactNode } from 'react';
import { AppState } from 'react-native';

import { getFlags } from '@/api/client';
import type { Flags } from '@/api/types';
import { useResource } from '@/hooks/use-resource';
import { useSession } from '@/providers/session';

/** The flags this app acts on. The API may know more; the others are ignored here. */
export type FlagKey = 'value_screen' | 'tracker_analytics' | 'email_flows';

export type FlagsValue = {
  /** `loading` until the first answer; `error` when no answer has ever arrived. */
  status: 'loading' | 'ready' | 'error';
  /**
   * Whether a flagged feature should be offered. Off while the flags are loading, off when the call failed and
   * nothing was loaded earlier, and off for a flag the API did not list. Features that have no flag (games,
   * props, the tracker, calculators, alerts) never ask, so they are not affected by a failed call.
   */
  isOn: (flag: FlagKey) => boolean;
  reload: () => void;
};

/** What a set of flags answers. A missing key is off. */
export function flagOn(flags: Flags | undefined, flag: FlagKey): boolean {
  return flags?.[flag] === true;
}

const allOff: FlagsValue = { status: 'loading', isOn: () => false, reload: () => {} };

export const FlagsContext = createContext<FlagsValue>(allOff);

/**
 * Reads `GET /v1/flags` when the app starts, each time it returns to the foreground and after a sign-in.
 * If a later read fails, the last flags loaded stay in use. Sits inside the session provider.
 */
export function FlagsProvider({ children }: { children: ReactNode }) {
  const { user } = useSession();
  const flags = useResource('flags', getFlags);
  const { reload } = flags;

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') reload();
    });
    return () => subscription.remove();
  }, [reload]);

  const userId = user?.id ?? null;
  const lastUserId = useRef(userId);
  useEffect(() => {
    if (lastUserId.current === userId) return;
    lastUserId.current = userId;
    if (userId) reload();
  }, [userId, reload]);

  const value = useMemo<FlagsValue>(
    () => ({ status: flags.status, isOn: (flag) => flagOn(flags.data, flag), reload }),
    [flags.status, flags.data, reload],
  );
  return <FlagsContext value={value}>{children}</FlagsContext>;
}

export function useFlags(): FlagsValue {
  return use(FlagsContext);
}

export function useFlag(flag: FlagKey): boolean {
  return use(FlagsContext).isOn(flag);
}
