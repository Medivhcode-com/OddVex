import { Stack } from 'expo-router';

import { useStackOptions } from '@/hooks/use-stack-options';

export const unstable_settings = { anchor: 'tracker' };

export default function TrackerLayout() {
  const options = useStackOptions();
  return (
    <Stack screenOptions={options}>
      <Stack.Screen name="tracker" options={{ title: 'Bet tracker' }} />
      <Stack.Screen name="log-bet" options={{ title: 'Log a bet' }} />
      <Stack.Screen name="analytics" options={{ title: 'Analytics' }} />
    </Stack>
  );
}
