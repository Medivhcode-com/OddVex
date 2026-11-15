import { Text, type TextProps } from 'react-native';

import { useTheme } from '@/hooks/use-theme';
import { useMonoFontLoaded } from '@/providers/fonts';
import { fontSize, maxNumberScale, monoFallback, monoFont, type ThemeColors } from '@/theme';

export type Tone = 'text' | 'muted' | 'accent' | 'accentInk' | 'second' | 'warn' | 'error';
type Weight = 'regular' | 'medium' | 'semibold';

const fontWeight = { regular: '400', medium: '500', semibold: '600' } as const;

function toneColor(theme: ThemeColors, tone: Tone): string {
  return theme[tone];
}

type TxtProps = TextProps & {
  variant?: 'title' | 'heading' | 'body' | 'secondary' | 'caption';
  tone?: Tone;
  weight?: Weight;
};

/** Interface text in the system face. Sentence case is a copy rule, so nothing here transforms case. */
export function Txt({ variant = 'body', tone = 'text', weight, style, ...rest }: TxtProps) {
  const theme = useTheme();
  const resolvedWeight = weight ?? (variant === 'title' || variant === 'heading' ? 'semibold' : 'regular');
  return (
    <Text
      {...rest}
      style={[
        { color: toneColor(theme, tone), fontSize: fontSize[variant], fontWeight: fontWeight[resolvedWeight] },
        variant === 'title' && { letterSpacing: -0.5 },
        style,
      ]}
    />
  );
}

type NumProps = TextProps & { size?: number; tone?: Tone; weight?: Weight };

/** Anything compared digit by digit: prices, lines, scores, percentages. Monospace and tabular. */
export function Num({ size = fontSize.body, tone = 'text', weight = 'medium', style, ...rest }: NumProps) {
  const theme = useTheme();
  const loaded = useMonoFontLoaded();
  return (
    <Text
      maxFontSizeMultiplier={maxNumberScale}
      {...rest}
      style={[
        { color: toneColor(theme, tone), fontSize: size, fontVariant: ['tabular-nums'] },
        loaded ? { fontFamily: monoFont[weight] } : { fontFamily: monoFallback, fontWeight: fontWeight[weight] },
        style,
      ]}
    />
  );
}
