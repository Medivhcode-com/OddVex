import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ApiError, createCommunityPick } from '@/api/client';
import type { EventSummary, Market, OddsComparison, PickCreate } from '@/api/types';
import { ANALYSIS_MAX, communityError, PICKS_EXPLAINED, PRIVATE_PROFILE, TEXT_RULES } from '@/components/community-copy';
import { Choice } from '@/components/form';
import { LimitedText, tooLong } from '@/components/limited-text';
import { quickBetOptions, type QuickBetOption } from '@/components/quick-bet';
import { Button, Notice, Panel, PanelHeading } from '@/components/states';
import { Txt } from '@/components/text';
import { useMyProfile } from '@/hooks/use-community';
import { useFlag } from '@/providers/flags';
import { useSession } from '@/providers/session';
import { DRAFT_KEPT, useDraft, useDraftKept } from '@/session/drafts';
import { space } from '@/theme';
import { formatAmerican } from '@/utils/format';

/**
 * What `POST /v1/community/picks` takes: the game, the market, the side and, for spread and total, the line.
 * No price and no amount: the server records the best open price and the time itself.
 */
export function pickPayload(event: Pick<EventSummary, 'id'>, market: Market, option: QuickBetOption, analysis: string): PickCreate {
  const text = analysis.trim();
  return {
    event_id: event.id,
    market,
    outcome_key: option.outcomeKey,
    ...(market !== 'moneyline' && option.line !== null ? { line: option.line } : null),
    ...(text ? { analysis: text } : null),
  };
}

function existingPickId(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.code !== 'pick_exists') return null;
  const details = error.details;
  if (typeof details !== 'object' || details === null || !('pick_id' in details)) return null;
  return typeof details.pick_id === 'string' ? details.pick_id : null;
}

function SharePickForm({ event, market, options }: { event: EventSummary; market: Market; options: readonly QuickBetOption[] }) {
  const router = useRouter();
  const { changed } = useSession();
  // Drafts: the outcome and the reasoning come back if the session ends before the pick is posted.
  const draft = `share-pick:${event.id}:${market}`;
  const [choice, setChoice] = useDraft<string>(`${draft}:outcome`, options[0]?.outcomeKey ?? '');
  const [analysis, setAnalysis] = useDraft(`${draft}:analysis`, '');
  const [keptNotice, dismissKeptNotice, draftSaved] = useDraftKept(draft);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pickId, setPickId] = useState<string | null>(null);
  const [posted, setPosted] = useState(false);
  const option = options.find((item) => item.outcomeKey === choice);

  async function submit() {
    setPosted(false);
    dismissKeptNotice();
    if (!option) return setError('Choose an outcome.');
    if (tooLong(analysis, ANALYSIS_MAX)) return;
    setBusy(true);
    setError(null);
    setPickId(null);
    try {
      const pick = await createCommunityPick(pickPayload(event, market, option, analysis));
      setAnalysis('');
      draftSaved();
      setPickId(pick.id);
      setPosted(true);
      changed('community');
    } catch (caught) {
      setError(communityError(caught, 'The pick was not posted. Try again.', 'pick'));
      setPickId(existingPickId(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.form}>
      {keptNotice ? <Notice tone="neutral" text={DRAFT_KEPT} /> : null}
      <Choice
        label="Outcome, at the best current price"
        options={options.map((item): { value: string; label: string } => ({
          value: item.outcomeKey,
          label: `${item.label} ${formatAmerican(item.american)} at ${item.sportsbook}`,
        }))}
        value={choice}
        onChange={setChoice}
      />
      <Txt variant="caption" tone="muted">
        OddVex records the best open price and the time when you post. You can&apos;t set either, and a pick can&apos;t be edited.
      </Txt>
      <LimitedText label="Your reasoning (optional)" value={analysis} onChangeText={setAnalysis} max={ANALYSIS_MAX} />
      <Txt variant="caption" tone="muted">
        {TEXT_RULES} A pick is your opinion about a game, not advice to anyone.
      </Txt>
      {error ? <Notice tone="error" text={error} /> : null}
      {posted ? <Notice tone="accent" text="Pick posted. It will be graded from the final score." /> : null}
      <View style={styles.actions}>
        <Button label={busy ? 'Posting pick' : 'Post pick'} onPress={submit} disabled={busy} />
        {pickId ? (
          <Button label="Open your pick" variant="secondary" onPress={() => router.push({ pathname: '/community/picks/[id]', params: { id: pickId } })} />
        ) : null}
      </View>
    </View>
  );
}

/**
 * "Share a pick" on a game that has not started. Drawn only while the `community` flag is on and someone
 * is signed in. The form needs a public profile; without one the panel says so and links to the profile.
 */
export function SharePick({ event, odds }: { event: EventSummary; odds: OddsComparison }) {
  const router = useRouter();
  const community = useFlag('community');
  const session = useSession();
  const profile = useMyProfile(community);
  const options = quickBetOptions(odds);
  if (!community || !session.user || event.status !== 'upcoming' || options.length === 0) return null;
  return (
    <Panel>
      <View style={styles.form}>
        <PanelHeading title="Share a pick" description={PICKS_EXPLAINED} />
        {profile.status === 'loading' ? (
          <Txt variant="secondary" tone="muted" accessibilityLiveRegion="polite">
            Checking your community profile.
          </Txt>
        ) : profile.status === 'error' ? (
          <View style={styles.form} accessibilityRole="alert">
            <Txt variant="secondary" tone="muted">
              OddVex can&apos;t reach its data service, so your community profile did not load.
            </Txt>
            <Button label="Try again" variant="secondary" accessibilityLabel="Try loading your community profile again" onPress={profile.reload} />
          </View>
        ) : !profile.data ? (
          <>
            <Txt variant="secondary" tone="muted">
              Posting needs a public community profile. You don&apos;t have a profile yet.
            </Txt>
            <Button label="Set up your profile" variant="secondary" onPress={() => router.push('/community/profile')} />
          </>
        ) : !profile.data.can_post ? (
          <>
            <Txt variant="secondary" tone="muted">
              {profile.data.is_public ? 'Moderators have hidden your profile, so you can browse but not post.' : PRIVATE_PROFILE}
            </Txt>
            <Button label="Edit your profile" variant="secondary" onPress={() => router.push('/community/profile')} />
          </>
        ) : (
          <SharePickForm key={odds.market} event={event} market={odds.market} options={options} />
        )}
      </View>
    </Panel>
  );
}

const styles = StyleSheet.create({
  form: { gap: space[3] },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space[3] },
});
