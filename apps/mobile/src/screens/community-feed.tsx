import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { describeError, getCommunityFeed } from '@/api/client';
import type { FeedScope, MyCommunityProfile } from '@/api/types';
import { Segmented } from '@/components/choice';
import { PICKS_EXPLAINED, PRIVATE_PROFILE } from '@/components/community-copy';
import { CommunityGate } from '@/components/community-gate';
import { Guidelines } from '@/components/guidelines';
import { PickCard } from '@/components/pick-card';
import { ProfileForm } from '@/components/profile-form';
import { Screen } from '@/components/screen';
import { Button, EmptyState, ErrorState, Notice, Panel, PanelHeading, SkeletonCards } from '@/components/states';
import { Txt } from '@/components/text';
import { useMyProfile } from '@/hooks/use-community';
import { useNow } from '@/hooks/use-now';
import { usePaged } from '@/hooks/use-paged';
import { useFlag } from '@/providers/flags';
import { useSession } from '@/providers/session';
import { space } from '@/theme';

const SCOPES: readonly { value: FeedScope; label: string }[] = [
  { value: 'following', label: 'Following' },
  { value: 'everyone', label: 'Everyone' },
];

/** First entry: the rules as the API words them, then the profile form. Nothing is posted until a profile exists. */
function Setup() {
  return (
    <Screen>
      <Txt variant="secondary" tone="muted">
        The community is opt-in. Read the guidelines, then create a profile to join. Nobody sees anything about you until you do.
      </Txt>
      <Guidelines />
      <Panel>
        <View style={styles.block}>
          <PanelHeading title="Create your profile" description="You can change the handle, the bio and who can see the profile later." />
          <ProfileForm draft="community-setup-profile" />
        </View>
      </Panel>
    </Screen>
  );
}

function Feed({ userId, profile }: { userId: string; profile: MyCommunityProfile }) {
  const router = useRouter();
  const now = useNow();
  const { revision } = useSession();
  const leaderboard = useFlag('community_leaderboard');
  const [scope, setScope] = useState<FeedScope>('following');
  const feed = usePaged(`community-feed:${userId}:${scope}`, (before) => getCommunityFeed(scope, before), revision.community);

  return (
    <Screen refreshing={feed.refreshing} onRefresh={feed.refresh}>
      <Txt variant="secondary" tone="muted">
        {PICKS_EXPLAINED} A pick is one person&apos;s opinion, not advice from OddVex.
      </Txt>
      <View style={styles.links}>
        <Button
          label="Your profile"
          variant="secondary"
          compact
          onPress={() => router.push({ pathname: '/community/profiles/[handle]', params: { handle: profile.handle } })}
        />
        {leaderboard ? <Button label="Leaderboard" variant="secondary" compact onPress={() => router.push('/community/leaderboard')} /> : null}
        <Button label="Guidelines" variant="ghost" compact accessibilityLabel="Community guidelines" onPress={() => router.push('/community/guidelines')} />
      </View>
      {!profile.can_post ? (
        <Notice tone="neutral" title={profile.is_public ? 'Your profile is hidden' : 'Your profile is private'} text={profile.is_public ? (profile.moderation_note ?? 'Moderators have hidden your profile, so you can browse but not post.') : PRIVATE_PROFILE}>
          <Button label="Edit your profile" variant="secondary" compact onPress={() => router.push('/community/profile')} />
        </Notice>
      ) : null}
      <Segmented label="Show picks from" options={SCOPES} value={scope} onChange={setScope} />
      {feed.items === null ? (
        feed.error !== undefined ? (
          <ErrorState error={feed.error} onRetry={feed.retry} />
        ) : (
          <SkeletonCards label="Loading picks" />
        )
      ) : (
        <>
          {feed.error !== undefined ? <Notice text="Couldn't refresh. Showing the last picks loaded." /> : null}
          {feed.items.length === 0 ? (
            scope === 'following' ? (
              <EmptyState
                title="No picks from people you follow"
                body="Follow a profile to see its picks here, newest first. Everyone shows every public pick.">
                <Button label="Show everyone" variant="secondary" onPress={() => setScope('everyone')} />
              </EmptyState>
            ) : (
              <EmptyState
                title="No picks yet"
                body="Nobody has posted a pick. To share one, open a game that has not started and choose Share a pick."
              />
            )
          ) : (
            <>
              {feed.items.map((pick) => (
                <PickCard key={pick.id} pick={pick} now={now} onChange={(next) => feed.update((items) => items.map((item) => (item.id === next.id ? next : item)))} />
              ))}
              {feed.moreError !== undefined ? <Notice tone="error" text={describeError(feed.moreError, "Couldn't load more picks. Try again.")} /> : null}
              {feed.hasMore ? (
                <Button label={feed.loadingMore ? 'Loading more' : 'Load more'} variant="secondary" disabled={feed.loadingMore} onPress={feed.loadMore} />
              ) : (
                <Txt variant="caption" tone="muted" style={styles.end}>
                  That is every pick, newest first. Picks are ordered by time only, never by results.
                </Txt>
              )}
            </>
          )}
        </>
      )}
    </Screen>
  );
}

function Community({ userId }: { userId: string }) {
  const profile = useMyProfile();
  if (profile.status === 'loading') {
    return (
      <Screen>
        <SkeletonCards label="Loading the community" />
      </Screen>
    );
  }
  if (profile.data === undefined) {
    return (
      <Screen>
        <ErrorState error={profile.error} onRetry={profile.reload} />
      </Screen>
    );
  }
  return profile.data === null ? <Setup /> : <Feed userId={userId} profile={profile.data} />;
}

/**
 * The community's first screen (flag `community`): guidelines and profile setup for someone without a
 * profile, the pick feed for everyone else.
 */
export function CommunityFeedScreen() {
  return <CommunityGate>{(user) => (user ? <Community userId={user.id} /> : null)}</CommunityGate>;
}

const styles = StyleSheet.create({
  block: { gap: space[3] },
  links: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  end: { textAlign: 'center' },
});
