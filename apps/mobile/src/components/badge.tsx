import { StyleSheet, View, type ViewProps } from 'react-native';

import { Txt, type Tone } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { radius, space } from '@/theme';

type BadgeTone = 'neutral' | 'accent' | 'warn';

/** A small status pill. The mark is a shape cue (dot or diamond) so tone never relies on color alone. */
export function Badge({
  label,
  tone = 'neutral',
  mark,
  style,
  ...rest
}: ViewProps & { label: string; tone?: BadgeTone; mark?: 'dot' | 'diamond' }) {
  const theme = useTheme();
  const textTone: Tone = tone === 'accent' ? 'accent' : tone === 'warn' ? 'warn' : 'muted';
  const background = tone === 'accent' ? theme.accentSoft : tone === 'warn' ? theme.warnSoft : theme.raised;
  return (
    <View {...rest} style={[styles.badge, { backgroundColor: background }, style]}>
      {mark ? <Mark shape={mark} color={theme[textTone]} /> : null}
      <Txt variant="caption" tone={textTone} weight="medium">
        {label}
      </Txt>
    </View>
  );
}

export function Mark({ shape, color }: { shape: 'dot' | 'diamond'; color: string }) {
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no"
      style={[styles.mark, { backgroundColor: color }, shape === 'dot' ? styles.dot : styles.diamond]}
    />
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: space[1] + 2,
    paddingHorizontal: space[2],
    paddingVertical: space[1],
    borderRadius: radius.pill,
  },
  mark: { width: 6, height: 6 },
  dot: { borderRadius: 3 },
  diamond: { transform: [{ rotate: '45deg' }] },
});
