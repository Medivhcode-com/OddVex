import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { AlertList } from '@/components/alert-list';
import { Segmented } from '@/components/choice';
import { NotificationList } from '@/components/notification-list';
import { Screen } from '@/components/screen';
import { Button, EmptyState, SkeletonCards } from '@/components/states';
import { openLogin, useSession } from '@/providers/session';
import { space } from '@/theme';

export type InboxTab = 'notifications' | 'alerts';

const TABS: readonly { value: InboxTab; label: string }[] = [
  { value: 'notifications', label: 'Notifications' },
  { value: 'alerts', label: 'Alerts' },
];

/**
 * Notifications and the alert rules behind them, one segment each. Signed out, it asks you to log in.
 * Everything here is in-app: there is no push.
 */
export function NotificationsScreen({ initialTab = 'notifications' }: { initialTab?: InboxTab }) {
  const router = useRouter();
  const session = useSession();
  const [tab, setTab] = useState<InboxTab>(initialTab);

  if (session.status === 'loading') {
    return (
      <Screen>
        <SkeletonCards label="Checking your account" count={2} />
      </Screen>
    );
  }
  if (!session.user) {
    return (
      <Screen>
        <EmptyState
          title="Log in to see your notifications"
          body="Alerts and notifications belong to your account. Odds, props and calculators work without one.">
          <View style={styles.row}>
            <Button label="Log in" onPress={openLogin} />
            <Button label="Create an account" variant="secondary" onPress={() => router.push('/signup')} />
          </View>
        </EmptyState>
      </Screen>
    );
  }

  const header = <Segmented label="Show" options={TABS} value={tab} onChange={setTab} />;
  return tab === 'alerts' ? (
    <AlertList userId={session.user.id} header={header} />
  ) : (
    <NotificationList userId={session.user.id} header={header} />
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: space[3] },
});
