import type { ComponentProps } from 'react';
import type { Stack } from 'expo-router';

import { SyntheticBadge } from '@/components/synthetic-badge';
import { useTheme } from '@/hooks/use-theme';

type StackOptions = NonNullable<ComponentProps<typeof Stack>['screenOptions']>;

/** Header styling shared by every stack, including the persistent "Synthetic data" badge. */
export function useStackOptions(): StackOptions {
  const theme = useTheme();
  return {
    headerStyle: { backgroundColor: theme.bg },
    headerTintColor: theme.text,
    headerTitleStyle: { color: theme.text, fontWeight: '600' },
    headerShadowVisible: false,
    headerBackButtonDisplayMode: 'minimal',
    contentStyle: { backgroundColor: theme.bg },
    headerRight: () => <SyntheticBadge />,
  };
}
