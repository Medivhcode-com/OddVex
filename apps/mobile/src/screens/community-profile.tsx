import { Stack, useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { blockProfile, describeError, followProfile, getBlockedProfiles, getCommunityPicks, getCommunityProfile, unblockProfile, unfollowProfile } from '@/api/client';
import type { CommunityProfile, MyCommunityProfile } from '@/api/types';
import { BLOCK_EFFECTS, communityError, countText, joinedText, PICKS_EXPLAINED, PRIVATE_PROFILE, UNBLOCK_EFFECTS } from '@/components/community-copy';
import { CommunityGate } from '@/components/community-gate';
import { CommunityRecordView } from '@/components/community-record';
import { PickCard } from '@/components/pick-card';
import { ReportControl } from '@/components/report-form';
import { Screen } from '@/components/screen';
import { Button, ErrorState, Notice, Panel, PanelHeading, SkeletonCards } from '@/components/states';
import { Txt } from '@/components/text';
import { useMyProfile } from '@/hooks/use-community';
import { useNow } from '@/hooks/use-now';
import { usePaged } from '@/hooks/use-paged';
import { useResource } from '@/hooks/use-resource';
import { useSession } from '@/providers/session';
import { space } from '@/theme';

/** Follow / Following, Block / Unblock (each after an inline confirmation that says what it does) and Report. */
function ProfileActions({ profile }: { profile: CommunityProfile }) {
  const { changed } = useSession();
  // What the last action answered, shown until the profile reloads with the same facts.
  const [following, setFollowing] = useState<boolean | null>(null);
  const [blocked, setBlocked] = useState<boolean | null>(null);
  const [confirming, setConfirming] = useState<'block' | 'unblock' | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isFollowing = following ?? profile.is_following;
  const isBlocked = blocked ?? profile.is_blocked;
  const name = `@${profile.handle}`;

  async function run(action: () => Promise<void>, fallback: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
      changed('community');
    } catch (caught) {
      setError(communityError(caught, fallback, 'follow'));
    } finally {
      setBusy(false);
      setConfirming(null);
    }
  }

  const toggleFollow = () =>
    run(async () => {
      if (isFollowing) {
        await unfollowProfile(profile.handle);
        setFollowing(false);
      } else {
        setFollowing((await followProfile(profile.handle)).is_following);
      }
    }, isFollowing ? 'You are still following this profile. Try again.' : 'The follow was not saved. Try again.');

  const block = () =>
    run(async () => {
      setBlocked((await blockProfile(profile.handle)).is_blocked);
      setFollowing(false);
    }, 'The profile was not blocked. Try again.');

  const unblock = () =>
    run(async () => {
      await unblockProfile(profile.handle);
      setBlocked(false);
    }, 'The profile was not unblocked. Try again.');

  return (
    <View style={styles.block}>
      {error ? <Notice tone="error" text={error} /> : null}
      {confirming ? (
        <View style={styles.block}>
          <Txt variant="secondary">
            {confirming === 'block' ? `Block ${name}? ${BLOCK_EFFECTS}` : `Unblock ${name}? ${UNBLOCK_EFFECTS}`}
          </Txt>
          <View style={styles.actions}>
            {confirming === 'block' ? (
              <Button label={busy ? 'Blocking' : 'Block profile'} variant="danger" compact disabled={busy} accessibilityLabel={`Block ${name}`} onPress={block} />
            ) : (
              <Button label={busy ? 'Unblocking' : 'Unblock profile'} compact disabled={busy} accessibilityLabel={`Unblock ${name}`} onPress={unblock} />
            )}
            <Button label="Cancel" variant="secondary" compact disabled={busy} onPress={() => setConfirming(null)} />
          </View>
        </View>
      ) : (
        <View style={styles.actions}>
          {isBlocked ? (
            <Txt variant="secondary" tone="muted" style={styles.stateLine}>
              You have blocked this profile.
            </Txt>
          ) : (
            <Button
              label={isFollowing ? '★ Following' : '☆ Follow'}
              variant={isFollowing ? 'secondary' : 'primary'}
              compact
              disabled={busy}
              selected={isFollowing}
              accessibilityLabel={isFollowing ? `Following ${name}` : `Follow ${name}`}
              accessibilityHint={isFollowing ? 'Stops following' : 'Shows their picks in your Following feed'}
              onPress={toggleFollow}
            />
          )}
          <Button
            label={isBlocked ? 'Unblock' : 'Block'}
            variant="ghost"
            compact
            disabled={busy}
            accessibilityLabel={isBlocked ? `Unblock ${name}` : `Block ${name}`}
            accessibilityHint="Asks you to confirm first"
            onPress={() => setConfirming(isBlocked ? 'unblock' : 'block')}
          />
        </View>
      )}
      <ReportControl targetType="profile" targetId={profile.handle} what={`the profile ${name}`} />
    </View>
  );
}

/** Your own block list, each with Unblock. Follows a block removed are not restored by unblocking. */
function BlockedList({ userId }: { userId: string }) {
  const { revision, changed } = useSession();
  const blocks = useResource(`community-blocks:${userId}`, getBlockedProfiles, revision.community);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function unblock(handle: string) {
    setBusy(handle);
    setError(null);
    try {
      await unblockProfile(handle);
      changed('community');
    } catch (caught) {
      setError(communityError(caught, 'The profile was not unblocked. Try again.'));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Panel>
      <View style={styles.block}>
        <PanelHeading title="Blocked profiles" description={UNBLOCK_EFFECTS} />
        {error ? <Notice tone="error" text={error} /> : null}
        {blocks.data === undefined ? (
          blocks.status === 'error' ? (
            <View style={styles.block} accessibilityRole="alert">
              <Txt variant="secondary" tone="muted">
                {describeError(blocks.error, 'Your blocked profiles did not load.')}
              </Txt>
              <Button label="Try again" variant="secondary" compact accessibilityLabel="Try loading your blocked profiles again" onPress={blocks.reload} />
            </View>
          ) : (
            <Txt variant="secondary" tone="muted" accessibilityLiveRegion="polite">
              Loading your blocked profiles.
            </Txt>
          )
        ) : blocks.data.length === 0 ? (
          <Txt variant="secondary" tone="muted">
            You have not blocked anyone.
          </Txt>
        ) : (
          blocks.data.map((entry) => (
            <View key={entry.handle} style={styles.blockedRow}>
              <Txt variant="secondary" style={styles.grow}>
                @{entry.handle}
              </Txt>
              <Button
                label={busy === entry.handle ? 'Unblocking' : 'Unblock'}
                variant="secondary"
                compact
                disabled={busy !== null}
                accessibilityLabel={`Unblock @${entry.handle}`}
                onPress={() => void unblock(entry.handle)}
              />
            </View>
          ))
        )}
      </View>
    </Panel>
  );
}

function ProfilePicks({ handle }: { handle: string }) {
  const now = useNow();
  const { revision } = useSession();
  const picks = usePaged(`community-profile-picks:${handle}`, (before) => getCommunityPicks({ handle, before }), revision.community);
  if (picks.items === null) {
    return picks.error !== undefined ? <ErrorState error={picks.error} onRetry={picks.retry} /> : <SkeletonCards label="Loading picks" count={2} />;
  }
  return (
    <>
      {picks.error !== undefined ? <Notice text="Couldn't refresh. Showing the last picks loaded." /> : null}
      {picks.items.length === 0 ? (
        <Txt variant="secondary" tone="muted">
          No picks to show.
        </Txt>
      ) : (
        picks.items.map((pick) => (
          <PickCard key={pick.id} pick={pick} now={now} onChange={(next) => picks.update((items) => items.map((item) => (item.id === next.id ? next : item)))} />
        ))
      )}
      {picks.moreError !== undefined ? <Notice tone="error" text={describeError(picks.moreError, "Couldn't load more picks. Try again.")} /> : null}
      {picks.hasMore ? (
        <Button label={picks.loadingMore ? 'Loading more' : 'Load more'} variant="secondary" disabled={picks.loadingMore} onPress={picks.loadMore} />
      ) : null}
    </>
  );
}

function Profile({ userId, handle, own, reloadOwn }: { userId: string; handle: string; own: MyCommunityProfile | null; reloadOwn: () => void }) {
  const router = useRouter();
  const { revision } = useSession();
  // Your own profile comes from `GET /v1/community/profile`, which also answers while it is private.
  const other = useResource(
    `community-profile:${handle}:${own ? 'own' : 'other'}`,
    (signal): Promise<CommunityProfile> => (own ? Promise.resolve(own) : getCommunityProfile(handle, signal)),
    revision.community,
  );
  const profile: CommunityProfile | undefined = own ?? other.data;

  if (!profile) {
    return (
      <Screen>
        {other.status === 'error' ? <ErrorState error={other.error} onRetry={other.reload} /> : <SkeletonCards label="Loading the profile" count={2} />}
      </Screen>
    );
  }
  return (
    <Screen refreshing={other.refreshing} onRefresh={own ? reloadOwn : other.reload}>
      <Stack.Screen options={{ title: `@${profile.handle}` }} />
      {other.error !== undefined && !own ? <Notice text="Couldn't refresh. Showing the profile as last loaded." /> : null}
      <Panel>
        <View style={styles.block}>
          <Txt variant="title" accessibilityRole="header">
            @{profile.handle}
          </Txt>
          {profile.bio ? <Txt variant="secondary">{profile.bio}</Txt> : null}
          <Txt variant="secondary" tone="muted">
            Joined {joinedText(profile.joined)} · {countText(profile.follower_count, 'follower', 'followers')} · {profile.following_count} following
          </Txt>
          {own ? (
            <>
              <Txt variant="secondary" tone="muted">
                {own.moderation_status !== 'visible'
                  ? (own.moderation_note ?? 'Moderators have hidden your profile, so you can browse but not post.')
                  : own.is_public
                    ? 'This is your profile. It is public.'
                    : PRIVATE_PROFILE}
              </Txt>
              <Button label="Edit profile" variant="secondary" compact onPress={() => router.push('/community/profile')} />
            </>
          ) : (
            <ProfileActions key={profile.handle} profile={profile} />
          )}
        </View>
      </Panel>
      <Panel>
        <View style={styles.block}>
          <PanelHeading title="Graded record" description={PICKS_EXPLAINED} />
          <CommunityRecordView record={profile.record} />
        </View>
      </Panel>
      <Txt variant="heading" accessibilityRole="header">
        Picks
      </Txt>
      <ProfilePicks handle={profile.handle} />
      {own ? <BlockedList userId={userId} /> : null}
    </Screen>
  );
}

function ProfileLoader({ userId, handle }: { userId: string; handle: string }) {
  const mine = useMyProfile();
  // Wait for your own profile first: it decides whether this handle is you.
  if (mine.status === 'loading') {
    return (
      <Screen>
        <SkeletonCards label="Loading the profile" count={2} />
      </Screen>
    );
  }
  const own = mine.data && mine.data.handle === handle.toLowerCase() ? mine.data : null;
  return <Profile key={handle} userId={userId} handle={handle} own={own} reloadOwn={mine.reload} />;
}

/** A community profile: who they are by handle only, their graded record and their picks (flag `community`). */
export function CommunityProfileScreen({ handle }: { handle: string }) {
  return <CommunityGate>{(user) => (user ? <ProfileLoader userId={user.id} handle={handle} /> : null)}</CommunityGate>;
}

const styles = StyleSheet.create({
  block: { gap: space[3] },
  actions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: space[3] },
  stateLine: { flexShrink: 1 },
  blockedRow: { flexDirection: 'row', alignItems: 'center', gap: space[3] },
  grow: { flex: 1 },
});
