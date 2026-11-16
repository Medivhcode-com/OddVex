import { Stack } from 'expo-router';

import { useStackOptions } from '@/hooks/use-stack-options';

export const unstable_settings = { anchor: 'tools' };

export default function ToolsLayout() {
  const options = useStackOptions();
  return (
    <Stack screenOptions={options}>
      <Stack.Screen name="tools" options={{ title: 'Calculators' }} />
      <Stack.Screen name="parlay" options={{ title: 'Parlay research' }} />
      <Stack.Screen name="value" options={{ title: 'Value screen' }} />
    </Stack>
  );
}
