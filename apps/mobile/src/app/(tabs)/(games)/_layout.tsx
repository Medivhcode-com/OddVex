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
    </Stack>
  );
}
