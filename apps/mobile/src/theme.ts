/**
 * OddVex design tokens for React Native. Mirrors docs/design/DESIGN_SYSTEM.md and apps/web/src/app/globals.css.
 * Components read colors through `useTheme()` and never use raw hex.
 */
import { Platform } from 'react-native';

export type ThemeColors = {
  bg: string;
  surface: string;
  raised: string;
  border: string;
  borderStrong: string;
  text: string;
  muted: string;
  accent: string;
  /** Text and icons placed on a solid accent fill. */
  accentInk: string;
  /** Tint behind the best-price cell. */
  accentSoft: string;
  second: string;
  warn: string;
  warnSoft: string;
  error: string;
  errorSoft: string;
};

export const colors: { dark: ThemeColors; light: ThemeColors } = {
  dark: {
    bg: '#090D16',
    surface: '#121A29',
    raised: '#1B2638',
    border: '#2A3648',
    borderStrong: '#3B4A61',
    text: '#F5F8FC',
    muted: '#98A7BA',
    accent: '#43E6B1',
    accentInk: '#04241A',
    accentSoft: 'rgba(67, 230, 177, 0.12)',
    second: '#748BFF',
    warn: '#F5B84B',
    warnSoft: 'rgba(245, 184, 75, 0.12)',
    error: '#F16B77',
    errorSoft: 'rgba(241, 107, 119, 0.12)',
  },
  light: {
    bg: '#F4F6FA',
    surface: '#FFFFFF',
    raised: '#EBEFF5',
    border: '#D3DAE5',
    borderStrong: '#AAB5C5',
    text: '#0D1422',
    muted: '#515F75',
    accent: '#06694B',
    accentInk: '#FFFFFF',
    accentSoft: 'rgba(6, 105, 75, 0.10)',
    second: '#3F52D0',
    warn: '#8F5A00',
    warnSoft: 'rgba(143, 90, 0, 0.10)',
    error: '#BD2F40',
    errorSoft: 'rgba(189, 47, 64, 0.08)',
  },
};

/** 4pt grid. */
export const space = { 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32, 10: 40 } as const;

export const radius = { cell: 6, panel: 12, pill: 999 } as const;

export const fontSize = { caption: 12, secondary: 14, heading: 15, body: 16, score: 18, title: 24 } as const;

/** Minimum height and width of anything tappable. */
export const touchTarget = 44;

/** Loaded in the root layout. Until then (or if loading fails) numbers use the platform monospace face. */
export const monoFont = {
  regular: 'IBMPlexMono_400Regular',
  medium: 'IBMPlexMono_500Medium',
  semibold: 'IBMPlexMono_600SemiBold',
} as const;

export const monoFallback = Platform.select({ ios: 'Menlo', default: 'monospace' });

/** Caps Dynamic Type growth inside dense price cells so three outcomes still fit on one row. */
export const maxNumberScale = 1.5;
