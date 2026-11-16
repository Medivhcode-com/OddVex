import { Stack } from 'expo-router';

import { View } from 'react-native';

import { NotificationBell } from '@/components/notification-bell';
import { SyntheticBadge } from '@/components/synthetic-badge';
import { useStackOptions } from '@/hooks/use-stack-options';
import { space } from '@/theme';

/** The Games header: the bell with its unread count, then the "Synthetic data" badge every header has. */
function GamesHeaderRight() {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space[3] }}>
      <NotificationBell />
      <SyntheticBadge />
    </View>
  );
}

export default function GamesLayout() {
  const options = useStackOptions();
  return (
    <Stack screenOptions={options}>
      <Stack.Screen name="index" options={{ title: 'Games', headerRight: () => <GamesHeaderRight /> }} />
      <Stack.Screen name="event/[id]" options={{ title: 'Game' }} />
      <Stack.Screen name="assistant" options={{ title: 'OddVex AI' }} />
      <Stack.Screen name="notifications" options={{ title: 'Notifications' }} />
      {/* Behind the `community` flag: each screen shows "not available" while it is off. */}
      <Stack.Screen name="community/index" options={{ title: 'Community' }} />
      <Stack.Screen name="community/picks/[id]" options={{ title: 'Pick' }} />
      <Stack.Screen name="community/profiles/[handle]" options={{ title: 'Profile' }} />
      <Stack.Screen name="community/profile" options={{ title: 'Your profile' }} />
      <Stack.Screen name="community/leaderboard" options={{ title: 'Leaderboard' }} />
      <Stack.Screen name="community/guidelines" options={{ title: 'Community guidelines' }} />
    </Stack>
  );
}
