import { useRouter } from 'expo-router';
import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import type { User } from '@/api/types';
import { Screen } from '@/components/screen';
import { Button, EmptyState, FeatureUnavailable, SkeletonCards } from '@/components/states';
import { useFlags } from '@/providers/flags';
import { openLogin, useSession } from '@/providers/session';
import { space } from '@/theme';

/**
 * Stands in front of every community screen. While the `community` flag is off (or not known yet, or the
 * leaderboard's own flag is off) it shows "This feature isn't available right now." and asks the API for
 * nothing, so a notification link that arrives with the flag off lands on that plain state. Signed out, it
 * asks the person to log in: every community route except the guidelines needs an account.
 */
export function CommunityGate({
  leaderboard = false,
  account = true,
  children,
}: {
  /** Also require `community_leaderboard`. */
  leaderboard?: boolean;
  /** False for the guidelines, which need no sign-in. */
  account?: boolean;
  children: (user: User | null) => ReactNode;
}) {
  const router = useRouter();
  const flags = useFlags();
  const session = useSession();

  if (flags.status === 'loading') {
    return (
      <Screen>
        <SkeletonCards label="Checking what is available" count={2} />
      </Screen>
    );
  }
  if (!flags.isOn('community') || (leaderboard && !flags.isOn('community_leaderboard'))) {
    return (
      <Screen>
        <FeatureUnavailable />
      </Screen>
    );
  }
  if (!account) return <>{children(session.user)}</>;
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
          title="Log in to see the community"
          body="Picks, comments and profiles belong to accounts. Odds, props and calculators work without one.">
          <View style={styles.row}>
            <Button label="Log in" onPress={openLogin} />
            <Button label="Create an account" variant="secondary" onPress={() => router.push('/signup')} />
          </View>
        </EmptyState>
      </Screen>
    );
  }
  return <>{children(session.user)}</>;
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: space[3] },
});
