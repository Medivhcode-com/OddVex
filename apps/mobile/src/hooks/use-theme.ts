import { useColorScheme } from 'react-native';

import { colors, type ThemeColors } from '@/theme';

/** Dark-first: anything other than an explicit light system setting renders dark. */
export function useTheme(): ThemeColors {
  return useColorScheme() === 'light' ? colors.light : colors.dark;
}
