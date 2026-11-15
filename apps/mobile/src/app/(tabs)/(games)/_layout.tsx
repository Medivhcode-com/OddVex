import { Stack } from 'expo-router';

import { useStackOptions } from '@/hooks/use-stack-options';

export default function GamesLayout() {
  const options = useStackOptions();
  return (
    <Stack screenOptions={options}>
      <Stack.Screen name="index" options={{ title: 'Games' }} />
      <Stack.Screen name="event/[id]" options={{ title: 'Game' }} />
      <Stack.Screen name="assistant" options={{ title: 'OddVex AI' }} />
    </Stack>
  );
}
