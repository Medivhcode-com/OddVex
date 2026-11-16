import { fireEvent, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';

import { FEATURE_UNAVAILABLE, setAuthToken } from '@/api/client';
import { PICK_LOCKED, PRIVATE_PROFILE, REPORT_SENT } from '@/components/community-copy';
import type { CommunityPick } from '@/api/types';
import { CommunityPickScreen, finalScoreText } from '@/screens/community-pick';
import { errorResponse, jsonResponse } from '@/test/api';
import { BANNED_COPY } from '@/test/banned-copy';
import { showCommunity } from '@/test/community';
import { comment, flagsAllOn, myGradedPick, myProfile, myUpcomingPick, privateProfile, upcomingPick, voidPick, wonPick } from '@/test/fixtures';
import { screenStrings } from '@/test/strings';

const PROFILE = 'GET /v1/community/profile';
const pickRoute = (id: string) => `GET /v1/community/picks/${id}`;
const commentsRoute = (id: string) => `GET /v1/community/picks/${id}/comments?limit=20`;
const page = (items: unknown[], next_before: string | null = null) => ({ items, next_before });
const noContent = () => ({ ok: true, status: 204, json: async () => null });
const theirs = comment('cmt_1');
const mine = comment('cmt_2', { author: { handle: 'sam_reads_lines' }, body: 'My own comment.', is_mine: true });

// A game that starts a year from now, so "upcoming" does not depend on the day the tests run.
const future = new Date(Date.now() + 365 * 86_400_000).toISOString();
const past = '2026-01-01T18:00:00Z';

function show(pick: CommunityPick, routes: Record<string, unknown> = {}, options?: Parameters<typeof showCommunity>[2]) {
  return showCommunity(<CommunityPickScreen pickId={pick.id} />, { [PROFILE]: myProfile, [pickRoute(pick.id)]: pick, [commentsRoute(pick.id)]: page([]), ...routes }, options);
}

beforeEach(() => {
  jest.mocked(router.push).mockClear();
  jest.mocked(router.back).mockClear();
  setAuthToken('token-1');
});
afterEach(() => setAuthToken(null));

describe('finalScoreText', () => {
  it('names the teams in the order of the label', () => {
    expect(finalScoreText({ event_label: 'Iron Valley Forge at Harbor City Gulls', final_score: { home: 17, away: 14 } })).toBe(
      'Final score: Iron Valley Forge 14, Harbor City Gulls 17',
    );
    expect(finalScoreText({ event_label: 'An unusual label', final_score: { home: 1, away: 2 } })).toBe('Final score: Away 2, Home 1');
    expect(finalScoreText({ event_label: 'A at B', final_score: null })).toBeNull();
  });
});

describe('CommunityPickScreen', () => {
  it('shows "not available" and asks for nothing while the flag is off', async () => {
    const { fetchMock } = await show(upcomingPick, {}, { flags: flagsAllOn });
    expect(screen.getByText(FEATURE_UNAVAILABLE)).toBeOnTheScreen();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('shows the card, and the final score once the pick is graded', async () => {
    await show(wonPick);

    expect(await screen.findByText('Harbor City Gulls moneyline')).toBeOnTheScreen();
    expect(screen.getByText('Won')).toBeOnTheScreen();
    expect(screen.getByText('Price when posted: −108 at Northstar Sports')).toBeOnTheScreen();
    expect(screen.getByText('Final score: Iron Valley Forge 14, Harbor City Gulls 17')).toBeOnTheScreen();
    expect(screen.getByText(/^Graded from this score/)).toBeOnTheScreen();
    expect(screen.getByText('Every pick is timestamped before the game and graded automatically from the final score.')).toBeOnTheScreen();
    expect(screen.getByText('No comments yet.')).toBeOnTheScreen();

    const strings = screenStrings();
    for (const text of strings) for (const banned of BANNED_COPY) expect(text).not.toMatch(banned);
  });

  it('has no final score on an upcoming pick and explains a void one', async () => {
    await show(upcomingPick);
    expect(await screen.findByText('Upcoming')).toBeOnTheScreen();
    expect(screen.queryByText(/^Final score/)).toBeNull();

    await show(voidPick);
    expect(await screen.findByText(/^This game left the data before a final score/)).toBeOnTheScreen();
  });

  it('answers 404 with a plain "nothing found"', async () => {
    await show(upcomingPick, { [pickRoute('pick_1')]: () => errorResponse(404, 'not_found', 'Pick not found') });
    expect(await screen.findByText('Nothing found here')).toBeOnTheScreen();
  });
});

describe('comments', () => {
  it('lists comments as plain text, with Report on other people’s and Delete on your own', async () => {
    await show(upcomingPick, { [commentsRoute('pick_1')]: page([theirs, mine]) });

    expect(await screen.findByText('Which book moved first? <script>alert(1)</script> www.example.test')).toBeOnTheScreen();
    expect(screen.getByText(/^@madeup_mara · /)).toBeOnTheScreen();
    expect(screen.getByText('My own comment.')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Report the comment by madeup_mara' })).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Delete your comment' })).toBeOnTheScreen();
    expect(screen.queryByRole('link', { name: /example/ })).toBeNull();
  });

  it('adds a comment, shows it first and reads the pick again for its count', async () => {
    const posted = comment('cmt_9', { author: { handle: 'sam_reads_lines' }, body: 'Good spot on the half point.', is_mine: true });
    const { sent, serve } = await show(upcomingPick, { [commentsRoute('pick_1')]: page([theirs]) });
    await screen.findByText(/^@madeup_mara · /);
    serve({
      [PROFILE]: myProfile,
      [pickRoute('pick_1')]: { ...upcomingPick, comment_count: 2 },
      'POST /v1/community/picks/pick_1/comments': () => jsonResponse(posted, 201),
    });

    expect(screen.getByText('0 / 500 characters')).toBeOnTheScreen();
    await fireEvent.changeText(screen.getByLabelText('Add a comment'), '  Good spot on the half point.  ');
    await fireEvent.press(screen.getByRole('button', { name: 'Post comment' }));

    expect(await screen.findByText('Good spot on the half point.')).toBeOnTheScreen();
    const request = sent().find((item) => item.method === 'POST');
    expect(request?.path).toBe('/v1/community/picks/pick_1/comments');
    expect(request?.body).toEqual({ body: 'Good spot on the half point.' });
    expect(screen.getByLabelText('Add a comment').props.value).toBe('');
    expect(await screen.findByText('2 comments')).toBeOnTheScreen();
    expect(screen.getByText(/^@madeup_mara · /)).toBeOnTheScreen();
  });

  it('does not send an empty comment or one over 500 characters', async () => {
    const { sent } = await show(upcomingPick);

    await fireEvent.press(await screen.findByRole('button', { name: 'Post comment' }));
    expect(screen.getByText('Write a comment first.')).toBeOnTheScreen();
    await fireEvent.changeText(screen.getByLabelText('Add a comment'), 'x'.repeat(501));
    expect(screen.getByText('501 / 500 characters. Shorten it to 500 or fewer.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Post comment' }));
    expect(sent().some((item) => item.method === 'POST')).toBe(false);
  });

  it.each([
    ['a link', errorResponse(422, 'links_not_allowed', 'Links are not allowed', { field: 'body', rule: 'links' }), "Links aren't allowed here. Remove the link and try again."],
    [
      'a promise about a result',
      errorResponse(422, 'content_not_allowed', 'Do not present a result as certain. No outcome is guaranteed.', { field: 'body', rule: 'guaranteed_outcome' }),
      'This reads as a promise about a result, and no result is certain. Reword it and try again.',
    ],
    [
      'contact details',
      errorResponse(422, 'content_not_allowed', 'Do not post contact details.', { field: 'body', rule: 'contact_details' }),
      "Phone numbers, email addresses and other contact details aren't allowed here. Remove them and try again.",
    ],
    ['the hourly limit', errorResponse(429, 'rate_limited', 'Too many requests.'), 'You have reached the hourly limit for comments. Try again later.'],
  ])('explains a comment rejected for %s and keeps the text', async (_case, response, message) => {
    await show(upcomingPick, { 'POST /v1/community/picks/pick_1/comments': () => response });

    await fireEvent.changeText(await screen.findByLabelText('Add a comment'), 'Something I typed.');
    await fireEvent.press(screen.getByRole('button', { name: 'Post comment' }));

    expect(await screen.findByText(message)).toBeOnTheScreen();
    expect(screen.getByLabelText('Add a comment').props.value).toBe('Something I typed.');
  });

  it('deletes your own comment after a confirmation', async () => {
    const { sent } = await show(upcomingPick, { [commentsRoute('pick_1')]: page([theirs, mine]), 'DELETE /v1/community/comments/cmt_2': noContent });

    await fireEvent.press(await screen.findByRole('button', { name: 'Delete your comment' }));
    expect(sent().some((item) => item.method === 'DELETE')).toBe(false);
    await fireEvent.press(screen.getByRole('button', { name: 'Delete comment' }));

    await waitFor(() => expect(screen.queryByText('My own comment.')).toBeNull());
    expect(sent().find((item) => item.method === 'DELETE')?.path).toBe('/v1/community/comments/cmt_2');
    expect(screen.getByText(/^@madeup_mara · /)).toBeOnTheScreen();
  });

  it('keeps the comment when "Keep comment" is chosen', async () => {
    const { sent } = await show(upcomingPick, { [commentsRoute('pick_1')]: page([mine]) });

    await fireEvent.press(await screen.findByRole('button', { name: 'Delete your comment' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Keep comment' }));
    expect(screen.getByText('My own comment.')).toBeOnTheScreen();
    expect(sent().some((item) => item.method === 'DELETE')).toBe(false);
  });

  it('pages older comments with the cursor', async () => {
    const older = comment('cmt_3', { body: 'An older comment.' });
    const { sent } = await show(upcomingPick, {
      [commentsRoute('pick_1')]: page([theirs], 'c-1'),
      'GET /v1/community/picks/pick_1/comments?before=c-1&limit=20': page([older]),
    });

    await fireEvent.press(await screen.findByRole('button', { name: 'Load more comments' }));
    expect(await screen.findByText('An older comment.')).toBeOnTheScreen();
    expect(sent().at(-1)?.path).toBe('/v1/community/picks/pick_1/comments?before=c-1&limit=20');
    expect(screen.queryByRole('button', { name: 'Load more comments' })).toBeNull();
  });

  it('lets a private profile read but not comment', async () => {
    await show(upcomingPick, { [PROFILE]: privateProfile, [commentsRoute('pick_1')]: page([theirs]) });

    expect(await screen.findByText(PRIVATE_PROFILE)).toBeOnTheScreen();
    expect(screen.getByText(/^@madeup_mara · /)).toBeOnTheScreen();
    expect(screen.queryByLabelText('Add a comment')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Post comment' })).toBeNull();
  });

  it("shows the moderators' note in place of your removed comment", async () => {
    await show(upcomingPick, { [commentsRoute('pick_1')]: page([{ ...mine, body: null, moderation_status: 'removed', moderation_note: 'Removed by moderators.' }]) });
    expect(await screen.findByText('Removed by moderators.')).toBeOnTheScreen();
  });
});

describe('deleting a pick', () => {
  it('lets the author delete while the game is upcoming, after a confirmation', async () => {
    const pick = { ...myUpcomingPick, event_start_time: future };
    const { sent, session } = await show(pick, { 'DELETE /v1/community/picks/pick_6': noContent });

    await fireEvent.press(await screen.findByRole('button', { name: 'Delete this pick' }));
    expect(screen.getByText(/^Delete this pick\? Its comments and likes are deleted with it\./)).toBeOnTheScreen();
    expect(sent().some((item) => item.method === 'DELETE')).toBe(false);
    await fireEvent.press(screen.getByRole('button', { name: 'Delete pick' }));

    await waitFor(() => expect(router.back).toHaveBeenCalledTimes(1));
    expect(sent().find((item) => item.method === 'DELETE')?.path).toBe('/v1/community/picks/pick_6');
    expect(session.changed).toHaveBeenCalledWith('community');
    // Your own pick has no Report button.
    expect(screen.queryByRole('button', { name: /^Report this pick/ })).toBeNull();
  });

  it('explains why a graded pick cannot be deleted, and offers no delete button', async () => {
    await show(myGradedPick);

    expect(await screen.findByText(PICK_LOCKED)).toBeOnTheScreen();
    expect(PICK_LOCKED).toBe("Picks can't be deleted after the game starts, so records stay honest.");
    expect(screen.queryByRole('button', { name: 'Delete this pick' })).toBeNull();
  });

  it('gives the same explanation once the start time has passed, even before grading', async () => {
    await show({ ...myUpcomingPick, event_start_time: past });

    expect(await screen.findByText(PICK_LOCKED)).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Delete this pick' })).toBeNull();
  });

  it('switches to the explanation when the API says the pick is locked', async () => {
    const pick = { ...myUpcomingPick, event_start_time: future };
    await show(pick, {
      'DELETE /v1/community/picks/pick_6': () => errorResponse(409, 'pick_locked', 'A pick cannot be deleted once its event has started', { event_status: 'live' }),
    });

    await fireEvent.press(await screen.findByRole('button', { name: 'Delete this pick' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Delete pick' }));

    expect(await screen.findByText(PICK_LOCKED)).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Delete this pick' })).toBeNull();
    expect(router.back).not.toHaveBeenCalled();
  });

  it('offers no delete on someone else’s pick', async () => {
    await show({ ...upcomingPick, event_start_time: future });
    expect(await screen.findByRole('button', { name: 'Report this pick by fictional_fox' })).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Delete this pick' })).toBeNull();
    expect(screen.queryByText(PICK_LOCKED)).toBeNull();
  });
});

describe('reporting', () => {
  it('reports the pick with the chosen reason and the details', async () => {
    const { sent } = await show(upcomingPick, { 'POST /v1/community/reports': () => jsonResponse({ id: 'rep_1', status: 'open' }, 201) });

    await fireEvent.press(await screen.findByRole('button', { name: 'Report this pick by fictional_fox' }));
    for (const label of ['Spam', 'Harassment', 'Encouraging betting', 'Misleading claims', 'Personal information', 'Other']) {
      expect(screen.getByRole('radio', { name: new RegExp(`: ${label}$`) })).toBeOnTheScreen();
    }
    expect(screen.getByRole('radio', { name: /: Spam$/ })).toBeChecked();
    await fireEvent.press(screen.getByRole('radio', { name: /: Encouraging betting$/ }));
    await fireEvent.changeText(screen.getByLabelText('Details (optional)'), '  Tells people to bet more.  ');
    await fireEvent.press(screen.getByRole('button', { name: 'Send report' }));

    expect(await screen.findByText(REPORT_SENT)).toBeOnTheScreen();
    expect(REPORT_SENT).toBe('Report sent. A moderator will review it. The person you reported is not told who sent it.');
    const request = sent().find((item) => item.path === '/v1/community/reports');
    expect(request?.method).toBe('POST');
    expect(request?.body).toEqual({ target_type: 'pick', target_id: 'pick_1', reason: 'inducement_to_bet', details: 'Tells people to bet more.' });
  });

  it('reports a comment by its id, with no details when none were written', async () => {
    const { sent } = await show(upcomingPick, {
      [commentsRoute('pick_1')]: page([theirs]),
      'POST /v1/community/reports': () => jsonResponse({ id: 'rep_2', status: 'open' }, 201),
    });

    await fireEvent.press(await screen.findByRole('button', { name: 'Report the comment by madeup_mara' }));
    await fireEvent.press(screen.getByRole('radio', { name: /: Harassment$/ }));
    await fireEvent.press(screen.getByRole('button', { name: 'Send report' }));

    expect(await screen.findByText(REPORT_SENT)).toBeOnTheScreen();
    expect(sent().find((item) => item.path === '/v1/community/reports')?.body).toEqual({ target_type: 'comment', target_id: 'cmt_1', reason: 'harassment' });
  });

  it('can be cancelled, and explains the hourly limit', async () => {
    const { sent } = await show(upcomingPick, { 'POST /v1/community/reports': () => errorResponse(429, 'rate_limited', 'Too many requests.') });

    await fireEvent.press(await screen.findByRole('button', { name: 'Report this pick by fictional_fox' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Cancel the report' }));
    expect(screen.queryByRole('button', { name: 'Send report' })).toBeNull();
    expect(sent().some((item) => item.path === '/v1/community/reports')).toBe(false);

    await fireEvent.press(screen.getByRole('button', { name: 'Report this pick by fictional_fox' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Send report' }));
    expect(await screen.findByText('You have reached the hourly limit for reports. Try again later.')).toBeOnTheScreen();
    expect(screen.queryByText(REPORT_SENT)).toBeNull();
  });
});
