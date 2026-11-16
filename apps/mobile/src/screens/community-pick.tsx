import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ApiError, createPickComment, deleteCommunityPick, deletePickComment, describeError, getCommunityPick, getPickComments } from '@/api/client';
import type { CommunityPick, MyCommunityProfile, PickComment } from '@/api/types';
import { COMMENT_MAX, communityError, PICK_LOCKED, PICKS_EXPLAINED, PRIVATE_PROFILE, TEXT_RULES } from '@/components/community-copy';
import { CommunityGate } from '@/components/community-gate';
import { LimitedText, tooLong } from '@/components/limited-text';
import { PickCard } from '@/components/pick-card';
import { ReportControl } from '@/components/report-form';
import { Screen } from '@/components/screen';
import { Button, ErrorState, Notice, Panel, PanelHeading, SkeletonCards } from '@/components/states';
import { Txt } from '@/components/text';
import { useMyProfile } from '@/hooks/use-community';
import { useNow } from '@/hooks/use-now';
import { usePaged, type Paged } from '@/hooks/use-paged';
import { useResource } from '@/hooks/use-resource';
import { useSession } from '@/providers/session';
import { space } from '@/theme';
import { formatAge } from '@/utils/format';

/** "Final score: Iron Valley Forge 14, Harbor City Gulls 17", in the order of the API's "away at home" label. */
export function finalScoreText(pick: Pick<CommunityPick, 'event_label' | 'final_score'>): string | null {
  const score = pick.final_score;
  if (!score) return null;
  const teams = pick.event_label.split(' at ');
  const [away, home] = teams.length === 2 ? teams : ['Away', 'Home'];
  return `Final score: ${away} ${score.away}, ${home} ${score.home}`;
}

/** The author's own controls: delete while the game is upcoming, and the reason it is not offered afterwards. */
function AuthorActions({ pick, now, onDeleted }: { pick: CommunityPick; now: Date; onDeleted: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const upcoming = pick.status === 'pending' && new Date(pick.event_start_time).getTime() > now.getTime();

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await deleteCommunityPick(pick.id);
      onDeleted();
    } catch (caught) {
      // The game started between loading this screen and pressing the button.
      if (caught instanceof ApiError && caught.code === 'pick_locked') setLocked(true);
      else setError(communityError(caught, 'The pick was not deleted. Try again.'));
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  }

  if (!upcoming || locked) {
    return (
      <Txt variant="secondary" tone="muted" accessibilityRole={locked ? 'alert' : undefined}>
        {PICK_LOCKED}
      </Txt>
    );
  }
  return (
    <View style={styles.block}>
      {error ? <Notice tone="error" text={error} /> : null}
      {confirming ? (
        <>
          <Txt variant="secondary">Delete this pick? Its comments and likes are deleted with it. You can only do this until the game starts.</Txt>
          <View style={styles.actions}>
            <Button label={busy ? 'Deleting' : 'Delete pick'} variant="danger" compact disabled={busy} onPress={remove} />
            <Button label="Keep pick" variant="secondary" compact disabled={busy} onPress={() => setConfirming(false)} />
          </View>
        </>
      ) : (
        <Button label="Delete" variant="ghost" compact accessibilityLabel="Delete this pick" onPress={() => setConfirming(true)} />
      )}
    </View>
  );
}

function CommentRow({ comment, now, onDeleted }: { comment: PickComment; now: Date; onDeleted: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await deletePickComment(comment.id);
      onDeleted();
    } catch (caught) {
      setError(communityError(caught, 'The comment was not deleted. Try again.'));
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <Panel>
      <View style={styles.block}>
        <Txt variant="caption" tone="muted">
          @{comment.author.handle} · {formatAge(comment.created_at, now)}
        </Txt>
        {comment.body !== null && comment.body !== undefined ? (
          <Txt variant="secondary">{comment.body}</Txt>
        ) : (
          <Txt variant="secondary" tone="muted">
            {comment.moderation_note ?? 'Removed by moderators.'}
          </Txt>
        )}
        {error ? <Notice tone="error" text={error} /> : null}
        {comment.is_mine ? (
          confirming ? (
            <View style={styles.actions}>
              <Button label={busy ? 'Deleting' : 'Delete comment'} variant="danger" compact disabled={busy} onPress={remove} />
              <Button label="Keep comment" variant="secondary" compact disabled={busy} onPress={() => setConfirming(false)} />
            </View>
          ) : (
            <Button label="Delete" variant="ghost" compact accessibilityLabel="Delete your comment" onPress={() => setConfirming(true)} />
          )
        ) : (
          <ReportControl targetType="comment" targetId={comment.id} what={`the comment by ${comment.author.handle}`} />
        )}
      </View>
    </Panel>
  );
}

function AddComment({
  pickId,
  profile,
  loading,
  onAdded,
}: {
  pickId: string;
  profile: MyCommunityProfile | null | undefined;
  loading: boolean;
  onAdded: (comment: PickComment) => void;
}) {
  const router = useRouter();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (loading) {
    return (
      <Txt variant="secondary" tone="muted" accessibilityLiveRegion="polite">
        Checking your community profile.
      </Txt>
    );
  }
  if (!profile?.can_post) {
    return (
      <View style={styles.block}>
        <Txt variant="secondary" tone="muted">
          {profile === null
            ? 'Commenting needs a public community profile. You can read without one.'
            : profile === undefined
              ? 'Your community profile did not load, so commenting is not available right now.'
              : profile.is_public
                ? 'Moderators have hidden your profile, so you can browse but not post.'
                : PRIVATE_PROFILE}
        </Txt>
        {profile !== undefined ? (
          <Button label={profile === null ? 'Set up your profile' : 'Edit your profile'} variant="secondary" compact onPress={() => router.push('/community/profile')} />
        ) : null}
      </View>
    );
  }

  async function submit() {
    const body = text.trim();
    if (!body) return setError('Write a comment first.');
    if (tooLong(text, COMMENT_MAX)) return;
    setBusy(true);
    setError(null);
    try {
      onAdded(await createPickComment(pickId, body));
      setText('');
    } catch (caught) {
      setError(communityError(caught, 'The comment was not posted. Try again.', 'comment'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.block}>
      <LimitedText label="Add a comment" value={text} onChangeText={setText} max={COMMENT_MAX} />
      <Txt variant="caption" tone="muted">
        {TEXT_RULES} Discuss the pick, not the person.
      </Txt>
      {error ? <Notice tone="error" text={error} /> : null}
      <Button label={busy ? 'Posting comment' : 'Post comment'} compact disabled={busy} onPress={submit} />
    </View>
  );
}

function Comments({ comments, now, onDeleted }: { comments: Paged<PickComment>; now: Date; onDeleted: (comment: PickComment) => void }) {
  if (comments.items === null) {
    return comments.error !== undefined ? <ErrorState error={comments.error} onRetry={comments.retry} /> : <SkeletonCards label="Loading comments" count={1} />;
  }
  return (
    <>
      {comments.error !== undefined ? <Notice text="Couldn't refresh. Showing the last comments loaded." /> : null}
      {comments.items.length === 0 ? (
        <Txt variant="secondary" tone="muted">
          No comments yet.
        </Txt>
      ) : (
        comments.items.map((comment) => <CommentRow key={comment.id} comment={comment} now={now} onDeleted={() => onDeleted(comment)} />)
      )}
      {comments.moreError !== undefined ? <Notice tone="error" text={describeError(comments.moreError, "Couldn't load more comments. Try again.")} /> : null}
      {comments.hasMore ? (
        <Button
          label={comments.loadingMore ? 'Loading more' : 'Load more comments'}
          variant="secondary"
          disabled={comments.loadingMore}
          onPress={comments.loadMore}
        />
      ) : null}
    </>
  );
}

function PickDetail({ pickId }: { pickId: string }) {
  const router = useRouter();
  const now = useNow();
  const { changed } = useSession();
  const profile = useMyProfile();
  const loaded = useResource(`community-pick:${pickId}`, (signal) => getCommunityPick(pickId, signal));
  // The answer to the last like, shown until the next load replaces what it was based on.
  const [liked, setLiked] = useState<{ base: CommunityPick | undefined; value: CommunityPick } | null>(null);
  const comments = usePaged(`community-comments:${pickId}`, (before) => getPickComments(pickId, before));
  const pick = liked && liked.base === loaded.data ? liked.value : loaded.data;
  const refresh = () => {
    loaded.reload();
    comments.refresh();
  };

  if (!pick) {
    return (
      <Screen>
        {loaded.status === 'error' ? <ErrorState error={loaded.error} onRetry={loaded.reload} /> : <SkeletonCards label="Loading the pick" count={2} />}
      </Screen>
    );
  }
  const score = finalScoreText(pick);
  return (
    <Screen refreshing={loaded.refreshing || comments.refreshing} onRefresh={refresh}>
      {loaded.error !== undefined ? <Notice text="Couldn't refresh. Showing the pick as last loaded." /> : null}
      <PickCard pick={pick} now={now} link={false} onChange={(next) => setLiked({ base: loaded.data, value: next })} />
      {score ? (
        <Panel>
          <View style={styles.block}>
            <Txt weight="medium">{score}</Txt>
            <Txt variant="caption" tone="muted">
              Graded from this score{pick.graded_at ? `, ${formatAge(pick.graded_at, now)}` : ''}.
            </Txt>
          </View>
        </Panel>
      ) : null}
      {pick.status === 'void' ? (
        <Notice tone="neutral" title="Void" text="This game left the data before a final score, so the pick was not graded and counts in no record." />
      ) : null}
      <Txt variant="caption" tone="muted">
        {PICKS_EXPLAINED}
      </Txt>
      <View style={styles.actions}>
        <Button label="Open game" variant="secondary" compact onPress={() => router.push({ pathname: '/event/[id]', params: { id: pick.event_id, market: pick.market } })} />
      </View>
      {pick.is_mine ? (
        <AuthorActions
          pick={pick}
          now={now}
          onDeleted={() => {
            changed('community');
            if (router.canGoBack()) router.back();
            else router.replace('/community');
          }}
        />
      ) : (
        <ReportControl targetType="pick" targetId={pick.id} what={`this pick by ${pick.author.handle}`} />
      )}
      <Panel>
        <View style={styles.block}>
          <PanelHeading title="Comments" />
          <AddComment
            pickId={pick.id}
            profile={profile.data}
            loading={profile.status === 'loading'}
            onAdded={(comment) => {
              comments.update((items) => [comment, ...items]);
              loaded.reload();
            }}
          />
        </View>
      </Panel>
      <Comments
        comments={comments}
        now={now}
        onDeleted={(comment) => {
          comments.update((items) => items.filter((item) => item.id !== comment.id));
          loaded.reload();
        }}
      />
    </Screen>
  );
}

/** One pick with its final score once graded, its comments, and report and delete controls (flag `community`). */
export function CommunityPickScreen({ pickId }: { pickId: string }) {
  return <CommunityGate>{(user) => (user ? <PickDetail key={pickId} pickId={pickId} /> : null)}</CommunityGate>;
}

const styles = StyleSheet.create({
  block: { gap: space[3] },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space[3] },
});
