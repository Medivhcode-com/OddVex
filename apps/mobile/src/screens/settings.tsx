import Constants from 'expo-constants';
import { ScrollView, StyleSheet, View } from 'react-native';

import { API_URL } from '@/api/client';
import { Segmented } from '@/components/choice';
import { Button, Panel } from '@/components/states';
import { Num, Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { isSynthetic, useMeta } from '@/providers/meta';
import { useOddsFormat } from '@/providers/odds-format';
import { fontSize, space } from '@/theme';
import type { OddsFormat } from '@/utils/format';

const FORMATS: readonly { value: OddsFormat; label: string }[] = [
  { value: 'american', label: 'American' },
  { value: 'decimal', label: 'Decimal' },
];

export const RESPONSIBLE_GAMBLING_LINE =
  'For adults 21+. OddVex never takes wagers. Gambling problem? Call or text 1-800-GAMBLER.';

function DataSource() {
  const theme = useTheme();
  const meta = useMeta();

  if (meta.status === 'loading') {
    return (
      <Txt variant="secondary" tone="muted">
        Checking the data source.
      </Txt>
    );
  }
  if (!meta.data) {
    return (
      <View style={styles.block}>
        <Txt variant="secondary" tone="muted">
          OddVex can&apos;t reach its data service, so the data source is unknown.
        </Txt>
        <Button label="Try again" onPress={meta.reload} />
      </View>
    );
  }
  if (isSynthetic(meta.data)) {
    return (
      <View style={[styles.synthetic, { backgroundColor: theme.warnSoft, borderLeftColor: theme.warn }]}>
        <Txt variant="secondary" tone="warn" weight="semibold">
          Synthetic data — fictional teams, players and sportsbooks
        </Txt>
        {meta.data.notice ? (
          <Txt variant="secondary" tone="muted">
            {meta.data.notice}
          </Txt>
        ) : null}
      </View>
    );
  }
  return (
    <Txt variant="secondary" tone="muted">
      Data mode: {meta.data.data_mode}. Provider: {meta.data.provider}.
    </Txt>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.fact}>
      <Txt variant="secondary" tone="muted">
        {label}
      </Txt>
      <Num size={fontSize.secondary} selectable style={styles.factValue}>
        {value}
      </Num>
    </View>
  );
}

export function SettingsScreen() {
  const theme = useTheme();
  const meta = useMeta();
  const { format, setFormat } = useOddsFormat();

  return (
    <ScrollView
      style={{ backgroundColor: theme.bg }}
      contentContainerStyle={styles.content}
      contentInsetAdjustmentBehavior="automatic">
      <Panel>
        <View style={styles.block}>
          <Txt variant="heading" accessibilityRole="header">
            Odds format
          </Txt>
          <Segmented label="Odds format" options={FORMATS} value={format} onChange={setFormat} />
          <Txt variant="caption" tone="muted">
            American shows prices like +150 or −110. Decimal shows the same prices as 2.50 or 1.91. Your choice is
            saved on this device.
          </Txt>
        </View>
      </Panel>

      <Panel>
        <View style={styles.block}>
          <Txt variant="heading" accessibilityRole="header">
            Data source
          </Txt>
          <DataSource />
        </View>
      </Panel>

      <Panel>
        <View style={styles.block}>
          <Txt variant="heading" accessibilityRole="header">
            Responsible gambling
          </Txt>
          <Txt variant="secondary" selectable>
            {RESPONSIBLE_GAMBLING_LINE}
          </Txt>
        </View>
      </Panel>

      <Panel>
        <View style={styles.block}>
          <Txt variant="heading" accessibilityRole="header">
            About
          </Txt>
          <Fact label="App version" value={Constants.expoConfig?.version ?? 'unknown'} />
          <Fact label="Data service version" value={meta.data?.version ?? 'unknown'} />
          <Fact label="Data service address" value={API_URL} />
        </View>
      </Panel>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: space[4], paddingBottom: space[8], gap: space[4] },
  block: { gap: space[3] },
  synthetic: { gap: space[2], padding: space[3], borderLeftWidth: 3, borderRadius: 6 },
  fact: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: space[3] },
  factValue: { flexShrink: 1, textAlign: 'right' },
});
