import { useRouter } from 'expo-router';
import { useEffect, useEffectEvent, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { deleteNotification, describeError, getNotifications, markAllNotificationsRead, markNotificationRead } from '@/api/client';
import type { Notification, NotificationKind } from '@/api/types';
import { Badge } from '@/components/badge';
import { Screen } from '@/components/screen';
import { Button, EmptyState, ErrorState, Notice, Panel, SkeletonCards } from '@/components/states';
import { Txt } from '@/components/text';
import { useNow } from '@/hooks/use-now';
import { useSession } from '@/providers/session';
import { space } from '@/theme';
import { formatAge } from '@/utils/format';
import { appRoute } from '@/utils/routes';

const PAGE_SIZE = 30;

export const NOTIFICATION_KIND_LABELS: Record<NotificationKind, string> = {
  price_alert: 'Price alert',
  line_move: 'Line move',
  game_start: 'Game start',
  game_final: 'Final score',
  bet_settled: 'Settled bet',
  sync_finished: 'Sync result',
  stake_reminder: 'Staking reminder',
};

type Feed = { items: Notification[]; unread: number; nextBefore: string | null };

/**
 * One notification. The title and body are the API's words, unchanged. Unread ones carry the word "New".
 * Tapping marks it read and opens the screen its link points to, when this app has one.
 */
function NotificationRow({
  item,
  now,
  busy,
  onOpen,
  onDelete,
}: {
  item: Notification;
  now: Date;
  busy: boolean;
  onOpen: () => void;
  onDelete: () => void;
}) {
  const unread = !item.read_at;
  const kind = NOTIFICATION_KIND_LABELS[item.kind] ?? 'Notification';
  const opens = item.href ? appRoute(item.href) !== null : false;
  return (
    <Panel>
      <View style={styles.row}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`${unread ? 'New. ' : ''}${kind}. ${item.title}. ${item.body}`}
          accessibilityHint={opens ? (unread ? 'Marks it as read and opens it' : 'Opens it') : unread ? 'Marks it as read' : undefined}
          onPress={onOpen}
          style={({ pressed }) => [styles.body, pressed && styles.pressed]}>
          <View style={styles.meta}>
            {unread ? <Badge label="New" tone="accent" mark="dot" /> : null}
            <Txt variant="caption" tone="muted">
              {kind} · {formatAge(item.created_at, now)}
            </Txt>
          </View>
          <Txt weight={unread ? 'semibold' : 'regular'}>{item.title}</Txt>
          <Txt variant="secondary" tone="muted">
            {item.body}
          </Txt>
        </Pressable>
        <Button
          label="Delete"
          variant="ghost"
          compact
          disabled={busy}
          accessibilityLabel={`Delete notification: ${item.title}`}
          onPress={onDelete}
        />
      </View>
    </Panel>
  );
}

/**
 * The signed-in user's notifications, newest first, with pull to refresh and "Load more".
 * Reading this list is also what makes the API check the user's alert rules: there is no push.
 */
export function NotificationList({ userId, header }: { userId: string; header?: ReactNode }) {
  const router = useRouter();
  const now = useNow();
  const { changed } = useSession();
  const [feed, setFeed] = useState<Feed | null>(null);
  const [error, setError] = useState<unknown>(undefined);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  // The API has just checked the alert rules, so the header badge may be out of date.
  const badgeChanged = useEffectEvent(() => changed('notifications'));

  useEffect(() => {
    let active = true;
    getNotifications({ limit: PAGE_SIZE }).then(
      (page) => {
        if (!active) return;
        setFeed({ items: page.items, unread: page.unread_count, nextBefore: page.next_before ?? null });
        setError(undefined);
        setActionError(null);
        setRefreshing(false);
        badgeChanged();
      },
      (caught: unknown) => {
        if (!active) return;
        setError(caught);
        setRefreshing(false);
      },
    );
    return () => {
      active = false;
    };
  }, [userId, attempt]);

  const retry = () => {
    setError(undefined);
    setAttempt((n) => n + 1);
  };
  const refresh = () => {
    setRefreshing(true);
    setAttempt((n) => n + 1);
  };

  async function loadMore() {
    if (!feed?.nextBefore || loadingMore) return;
    setLoadingMore(true);
    setActionError(null);
    try {
      const page = await getNotifications({ limit: PAGE_SIZE, before: feed.nextBefore });
      setFeed((current) => {
        if (!current) return current;
        const seen = new Set(current.items.map((item) => item.id));
        return {
          items: [...current.items, ...page.items.filter((item) => !seen.has(item.id))],
          unread: page.unread_count,
          nextBefore: page.next_before ?? null,
        };
      });
    } catch (caught) {
      setActionError(describeError(caught, "Couldn't load more notifications. Try again."));
    } finally {
      setLoadingMore(false);
    }
  }

  function open(item: Notification) {
    if (!item.read_at) {
      markNotificationRead(item.id).then(
        (read) => {
          setFeed((current) =>
            current
              ? {
                  ...current,
                  items: current.items.map((other) => (other.id === read.id ? read : other)),
                  unread: Math.max(0, current.unread - 1),
                }
              : current,
          );
          changed('notifications');
        },
        (caught: unknown) => setActionError(describeError(caught, "Couldn't mark that as read. Try again.")),
      );
    }
    const route = item.href ? appRoute(item.href) : null;
    if (route) router.push(route);
  }

  async function markAll() {
    setBusy('all');
    setActionError(null);
    try {
      await markAllNotificationsRead();
      const readAt = new Date().toISOString();
      setFeed((current) =>
        current ? { ...current, unread: 0, items: current.items.map((item) => (item.read_at ? item : { ...item, read_at: readAt })) } : current,
      );
      changed('notifications');
    } catch (caught) {
      setActionError(describeError(caught, "Couldn't mark everything as read. Try again."));
    } finally {
      setBusy(null);
    }
  }

  async function remove(item: Notification) {
    setBusy(item.id);
    setActionError(null);
    try {
      await deleteNotification(item.id);
      setFeed((current) =>
        current
          ? {
              ...current,
              items: current.items.filter((other) => other.id !== item.id),
              unread: Math.max(0, current.unread - (item.read_at ? 0 : 1)),
            }
          : current,
      );
      changed('notifications');
    } catch (caught) {
      setActionError(describeError(caught, "Couldn't delete that notification. Try again."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      {header}
      {feed === null ? (
        error !== undefined ? (
          <ErrorState error={error} onRetry={retry} />
        ) : (
          <SkeletonCards label="Loading your notifications" />
        )
      ) : (
        <>
          {error !== undefined ? <Notice text="Couldn't refresh. Showing the last notifications loaded." /> : null}
          {feed.items.length === 0 ? (
            <EmptyState
              title="No notifications yet"
              body="To set an alert, open a game and choose Set an alert. Alerts are checked when you open the app, and what they find shows up here.">
              <Button label="Browse games" variant="secondary" onPress={() => router.navigate('/')} />
            </EmptyState>
          ) : (
            <>
              <View style={styles.summary}>
                <Txt variant="secondary" tone="muted" accessibilityLiveRegion="polite" style={styles.count}>
                  {feed.unread > 0 ? `${feed.unread} unread` : 'Nothing unread'}
                </Txt>
                {feed.unread > 0 ? (
                  <Button label="Mark all as read" variant="secondary" compact disabled={busy === 'all'} onPress={markAll} />
                ) : null}
              </View>
              {actionError ? <Notice tone="error" text={actionError} /> : null}
              {feed.items.map((item) => (
                <NotificationRow
                  key={item.id}
                  item={item}
                  now={now}
                  busy={busy === item.id}
                  onOpen={() => open(item)}
                  onDelete={() => void remove(item)}
                />
              ))}
              {feed.nextBefore ? (
                <Button label={loadingMore ? 'Loading more' : 'Load more'} variant="secondary" disabled={loadingMore} onPress={loadMore} />
              ) : (
                <Txt variant="caption" tone="muted" style={styles.end}>
                  That is everything. Notifications appear in the app only; there is no push or email yet.
                </Txt>
              )}
            </>
          )}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { gap: space[2] },
  body: { gap: space[1] + 2, minHeight: 44 },
  pressed: { opacity: 0.7 },
  meta: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: space[2] },
  summary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[3] },
  count: { flex: 1 },
  end: { textAlign: 'center' },
});
