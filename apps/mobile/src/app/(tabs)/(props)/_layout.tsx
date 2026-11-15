import { Stack } from 'expo-router';

import { useStackOptions } from '@/hooks/use-stack-options';

// A link straight to a player (from the watchlist or the assistant) still gets the prop board underneath.
export const unstable_settings = { anchor: 'props' };

export default function PropsLayout() {
  const options = useStackOptions();
  return (
    <Stack screenOptions={options}>
      <Stack.Screen name="props" options={{ title: 'Player props' }} />
      <Stack.Screen name="player/[id]" options={{ title: 'Player props' }} />
    </Stack>
  );
}
