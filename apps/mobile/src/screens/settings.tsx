import Constants from 'expo-constants';
import { useRouter } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { API_URL } from '@/api/client';
import { Segmented } from '@/components/choice';
import { ChangePasswordForm, DeleteAccountForm } from '@/components/account-forms';
import { Screen } from '@/components/screen';
import { Button, Panel, PanelHeading } from '@/components/states';
import { Num, Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { isSynthetic, useMeta } from '@/providers/meta';
import { useOddsFormat } from '@/providers/odds-format';
import { openLogin, useSession } from '@/providers/session';
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

function Fact({ label, value, plain = false }: { label: string; value: string; plain?: boolean }) {
  return (
    <View style={styles.fact} accessible accessibilityLabel={`${label}: ${value}`}>
      <Txt variant="secondary" tone="muted">
        {label}
      </Txt>
      {plain ? (
        <Txt variant="secondary" selectable style={styles.factValue}>
          {value}
        </Txt>
      ) : (
        <Num size={fontSize.secondary} selectable style={styles.factValue}>
          {value}
        </Num>
      )}
    </View>
  );
}

function Account() {
  const router = useRouter();
  const session = useSession();
  if (session.status === 'loading') {
    return (
      <Txt variant="secondary" tone="muted">
        Checking your account.
      </Txt>
    );
  }
  if (!session.user) {
    return (
      <View style={styles.block}>
        <Txt variant="secondary" tone="muted">
          You are not logged in. Odds, props and calculators work without an account; the tracker and watchlist need one.
        </Txt>
        <View style={styles.row}>
          <Button label="Log in" variant="secondary" onPress={openLogin} />
          <Button label="Create an account" variant="ghost" onPress={() => router.push('/signup')} />
        </View>
      </View>
    );
  }
  return (
    <View style={styles.block}>
      <Fact label="Name" value={session.user.display_name} plain />
      <Fact label="Email" value={session.user.email} plain />
      <Button label="Log out" variant="secondary" onPress={() => void session.logOut()} />
    </View>
  );
}

export function SettingsScreen() {
  const router = useRouter();
  const session = useSession();
  const meta = useMeta();
  const { format, setFormat } = useOddsFormat();

  return (
    <Screen>
      <Panel>
        <View style={styles.block}>
          <Txt variant="heading" accessibilityRole="header">
            Account
          </Txt>
          <Account />
        </View>
      </Panel>

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
          <PanelHeading title="OddVex AI" description="Answers from OddVex data and its calculation engine, with sources. It doesn't make picks." />
          <Button label="Ask OddVex AI" variant="secondary" onPress={() => router.push('/assistant')} />
        </View>
      </Panel>

      {session.user ? (
        <>
          <Panel>
            <View style={styles.block}>
              <PanelHeading title="Password" description="Changing it signs out every other device." />
              <ChangePasswordForm />
            </View>
          </Panel>
          <Panel>
            <View style={styles.block}>
              <PanelHeading
                title="Delete account"
                description="Removes your account, every bet you logged and any sync connections. This can't be undone."
              />
              <DeleteAccountForm />
            </View>
          </Panel>
        </>
      ) : null}

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
    </Screen>
  );
}

const styles = StyleSheet.create({
  block: { gap: space[3] },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: space[3] },
  synthetic: { gap: space[2], padding: space[3], borderLeftWidth: 3, borderRadius: 6 },
  fact: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: space[3] },
  factValue: { flexShrink: 1, textAlign: 'right' },
});
