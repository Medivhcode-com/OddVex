import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';

import { setAuthToken } from '@/api/client';
import { NOTIFICATION_KIND_LABELS, NotificationList } from '@/components/notification-list';
import { errorResponse, installFetch, jsonResponse, serveRoutes } from '@/test/api';
import { finalNotification, priceNotification, settledNotification, stakeNotification } from '@/test/fixtures';
import { fakeSession, WithSession } from '@/test/session';

const firstPage = { items: [priceNotification, finalNotification, stakeNotification], unread_count: 2, next_before: null };
const LIST = 'GET /v1/notifications?limit=30';

async function show(routes: Record<string, unknown>) {
  const { fetchMock, sent } = installFetch();
  serveRoutes(fetchMock, routes);
  const session = fakeSession();
  await render(
    <WithSession value={session}>
      <NotificationList userId="usr_1" />
    </WithSession>,
  );
  return { fetchMock, sent, session };
}

beforeEach(() => {
  jest.mocked(router.push).mockClear();
  jest.mocked(router.navigate).mockClear();
  setAuthToken('token-1');
});
afterEach(() => setAuthToken(null));

const followerNotification = {
  ...priceNotification,
  id: 'ntf_c1',
  kind: 'new_follower' as const,
  title: 'New follower',
  body: 'fictional_fox started following you.',
  href: '/app/community/profiles/fictional_fox',
};
const commentNotification = {
  ...priceNotification,
  id: 'ntf_c2',
  kind: 'pick_comment' as const,
  title: 'New comment on your pick',
  body: 'madeup_mara commented on your pick, Harbor City Gulls moneyline.',
  href: '/app/community/picks/pick_6',
  read_at: '2026-11-15T19:00:00Z',
};
const gradedNotification = {
  ...priceNotification,
  id: 'ntf_c3',
  kind: 'pick_graded' as const,
  title: 'Pick graded: lost',
  body: 'Your pick, Harbor City Gulls moneyline, was graded as lost.',
  href: '/app/community/picks/pick_7',
  read_at: '2026-11-15T19:00:00Z',
};

describe('community notifications', () => {
  it('has a label for each of the three kinds', () => {
    expect(NOTIFICATION_KIND_LABELS.new_follower).toBe('New follower');
    expect(NOTIFICATION_KIND_LABELS.pick_comment).toBe('Comment on your pick');
    expect(NOTIFICATION_KIND_LABELS.pick_graded).toBe('Graded pick');
  });

  it('shows the kinds and opens the profile or the pick the link names', async () => {
    await show({
      [LIST]: { items: [followerNotification, commentNotification, gradedNotification], unread_count: 1, next_before: null },
      'POST /v1/notifications/ntf_c1/read': { ...followerNotification, read_at: '2026-11-15T20:00:00Z' },
    });

    expect(await screen.findByText(/^New follower · /)).toBeOnTheScreen();
    expect(screen.getByText(/^Comment on your pick · /)).toBeOnTheScreen();
    expect(screen.getByText(/^Graded pick · /)).toBeOnTheScreen();

    await fireEvent.press(screen.getByRole('button', { name: /^New\. New follower\./ }));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/community/profiles/[handle]', params: { handle: 'fictional_fox' } });
    await fireEvent.press(screen.getByRole('button', { name: /^Comment on your pick\./ }));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/community/picks/[id]', params: { id: 'pick_6' } });
    await fireEvent.press(screen.getByRole('button', { name: /^Graded pick\. Pick graded: lost\./ }));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/community/picks/[id]', params: { id: 'pick_7' } });
  });
});

describe('NotificationList', () => {
  it("lists notifications with the API's own words, their kind, and the word New on unread ones", async () => {
    const { session } = await show({ [LIST]: firstPage });

    expect(await screen.findByText('Price reached +120')).toBeOnTheScreen();
    expect(screen.getByText('Iron Valley Forge spread +3.5 is +120 at Cedar Book, at or above your +115 alert.')).toBeOnTheScreen();
    expect(screen.getByText('Final: IVF 14, HCG 17')).toBeOnTheScreen();
    expect(screen.getByText('You have staked $250.00 this week, at or above the $200.00 reminder you set.')).toBeOnTheScreen();
    expect(screen.getByText(/^Price alert · /)).toBeOnTheScreen();
    expect(screen.getByText(/^Final score · /)).toBeOnTheScreen();
    expect(screen.getByText(/^Staking reminder · /)).toBeOnTheScreen();
    // Two unread, one read: the word, not a color.
    expect(screen.getAllByText('New')).toHaveLength(2);
    expect(screen.getByText('2 unread')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: /^New\. Price alert\. Price reached \+120\./ })).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: /^Final score\. Final: IVF 14, HCG 17\./ })).toBeOnTheScreen();
    // Reading the list made the API check the alert rules, so the header badge is told to refresh.
    expect(session.changed).toHaveBeenCalledWith('notifications');
  });

  it('marks a notification read and opens its game on the market in the link', async () => {
    const { sent, session } = await show({
      [LIST]: firstPage,
      'POST /v1/notifications/ntf_1/read': { ...priceNotification, read_at: '2026-11-15T20:00:00Z' },
    });

    await fireEvent.press(await screen.findByRole('button', { name: /^New\. Price alert\./ }));
    expect(router.push).toHaveBeenCalledWith({ pathname: '/event/[id]', params: { id: 'evt_2', market: 'spread' } });
    await waitFor(() => expect(screen.getAllByText('New')).toHaveLength(1));
    expect(screen.getByText('1 unread')).toBeOnTheScreen();
    expect(sent().at(-1)).toMatchObject({ method: 'POST', path: '/v1/notifications/ntf_1/read' });
    expect(session.changed).toHaveBeenCalledTimes(2);
  });

  it('only marks read when the link has no screen in this app, and does not mark a read one again', async () => {
    const { sent, fetchMock } = await show({
      [LIST]: firstPage,
      'POST /v1/notifications/ntf_3/read': { ...stakeNotification, read_at: '2026-11-15T20:00:00Z' },
    });

    await fireEvent.press(await screen.findByRole('button', { name: /^New\. Staking reminder\./ }));
    await waitFor(() => expect(screen.getAllByText('New')).toHaveLength(1));
    expect(sent().at(-1)).toMatchObject({ method: 'POST', path: '/v1/notifications/ntf_3/read' });
    expect(router.push).not.toHaveBeenCalled();

    await fireEvent.press(screen.getByRole('button', { name: /^Final score\./ }));
    expect(router.push).toHaveBeenCalledWith({ pathname: '/event/[id]', params: { id: 'evt_1' } });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('marks everything as read', async () => {
    const { sent } = await show({ [LIST]: firstPage, 'POST /v1/notifications/read-all': { updated: 2 } });

    await fireEvent.press(await screen.findByRole('button', { name: 'Mark all as read' }));
    expect(await screen.findByText('Nothing unread')).toBeOnTheScreen();
    expect(screen.queryByText('New')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Mark all as read' })).toBeNull();
    expect(sent().at(-1)).toMatchObject({ method: 'POST', path: '/v1/notifications/read-all' });
  });

  it('deletes one notification from its own Delete button', async () => {
    const { sent } = await show({ [LIST]: firstPage, 'DELETE /v1/notifications/ntf_1': () => ({ ok: true, status: 204, json: async () => undefined }) });

    await fireEvent.press(await screen.findByRole('button', { name: 'Delete notification: Price reached +120' }));
    await waitFor(() => expect(screen.queryByText('Price reached +120')).toBeNull());
    expect(screen.getByText('1 unread')).toBeOnTheScreen();
    expect(screen.getByText('Final: IVF 14, HCG 17')).toBeOnTheScreen();
    expect(sent().at(-1)).toMatchObject({ method: 'DELETE', path: '/v1/notifications/ntf_1' });
  });

  it('says so when a delete fails and keeps the notification', async () => {
    await show({ [LIST]: firstPage, 'DELETE /v1/notifications/ntf_1': () => errorResponse(404, 'not_found', 'Notification not found') });

    await fireEvent.press(await screen.findByRole('button', { name: 'Delete notification: Price reached +120' }));
    expect(await screen.findByText('Notification not found')).toBeOnTheScreen();
    expect(screen.getByText('Price reached +120')).toBeOnTheScreen();
  });

  it('loads older notifications with the cursor from the page before', async () => {
    const { sent } = await show({
      [LIST]: { ...firstPage, next_before: 'cursor_1' },
      'GET /v1/notifications?limit=30&before=cursor_1': { items: [settledNotification], unread_count: 3, next_before: null },
    });

    await fireEvent.press(await screen.findByRole('button', { name: 'Load more' }));
    expect(await screen.findByText('Bet settled: won')).toBeOnTheScreen();
    expect(screen.getByText(/^Settled bet · /)).toBeOnTheScreen();
    expect(screen.getByText('Price reached +120')).toBeOnTheScreen();
    expect(screen.getByText('3 unread')).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull();
    expect(sent().at(-1)!.path).toBe('/v1/notifications?limit=30&before=cursor_1');
  });

  it('explains how to set an alert when there are no notifications', async () => {
    await show({ [LIST]: { items: [], unread_count: 0, next_before: null } });

    expect(await screen.findByText('No notifications yet')).toBeOnTheScreen();
    expect(screen.getByText(/^To set an alert, open a game and choose Set an alert\./)).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Browse games' }));
    expect(router.navigate).toHaveBeenCalledWith('/');
  });

  it('says the data service cannot be reached and loads on retry', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));
    await render(
      <WithSession value={fakeSession()}>
        <NotificationList userId="usr_1" />
      </WithSession>,
    );

    expect(await screen.findByText("OddVex can't reach its data service")).toBeOnTheScreen();
    fetchMock.mockImplementation(async () => jsonResponse(firstPage));
    await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Price reached +120')).toBeOnTheScreen();
  });
});
