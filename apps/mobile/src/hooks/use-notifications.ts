import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef } from 'react';
import { AppState } from 'react-native';

import { getStakeReminder, getUnreadCount } from '@/api/client';
import type { StakeReminder } from '@/api/types';
import { useResource, type Resource } from '@/hooks/use-resource';
import { useSession } from '@/providers/session';

/**
 * Calls `reload` when the screen comes back into focus and when the app returns to the foreground.
 * The first focus is skipped: the resource has just loaded by itself.
 */
export function useReloadOnReturn(reload: () => void): void {
  const first = useRef(true);
  useFocusEffect(
    useCallback(() => {
      if (first.current) {
        first.current = false;
        return;
      }
      reload();
    }, [reload]),
  );
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') reload();
    });
    return () => subscription.remove();
  }, [reload]);
}

/**
 * How many unread notifications the signed-in user has; 0 when signed out. There is no push: asking for the
 * count is also what makes the API check the user's alert rules, so it is re-read on focus, when the app
 * returns to the foreground and after anything in the app changes a notification.
 */
export function useUnreadCount(): number {
  const { user, revision } = useSession();
  const unread = useResource(
    `unread:${user?.id ?? 'signed-out'}`,
    (signal) => (user ? getUnreadCount(signal) : Promise.resolve(0)),
    revision.notifications,
  );
  useReloadOnReturn(unread.reload);
  return unread.data ?? 0;
}

/** The weekly staking reminder with this week's total. Reloads when a bet or the reminder changes. */
export function useStakeReminder(userId: string): Resource<StakeReminder> {
  const { revision } = useSession();
  return useResource(`stake-reminder:${userId}`, getStakeReminder, revision.bets * 1000 + revision.reminder);
}
