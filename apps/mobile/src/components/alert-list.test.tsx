import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';

import { setAuthToken } from '@/api/client';
import { AlertList, evaluationText, groupAlerts } from '@/components/alert-list';
import { errorResponse, installFetch, serveRoutes } from '@/test/api';
import { activeRule, expiredRule, pausedRule, triggeredRule } from '@/test/fixtures';
import { fakeSession, WithSession } from '@/test/session';

const all = { items: [pausedRule, activeRule, expiredRule, triggeredRule] };
const noContent = () => ({ ok: true, status: 204, json: async () => undefined });

async function show(routes: Record<string, unknown>) {
  const { fetchMock, sent } = installFetch();
  serveRoutes(fetchMock, routes);
  const session = fakeSession();
  await render(
    <WithSession value={session}>
      <AlertList userId="usr_1" />
    </WithSession>,
  );
  return { fetchMock, sent, session };
}

beforeEach(() => {
  jest.mocked(router.push).mockClear();
  setAuthToken('token-1');
});
afterEach(() => setAuthToken(null));

describe('groupAlerts', () => {
  it('orders the groups Active, Triggered, Paused, Expired and drops empty ones', () => {
    expect(groupAlerts(all.items).map((group) => [group.title, group.rules.map((rule) => rule.id)])).toEqual([
      ['Active', ['alr_1']],
      ['Triggered', ['alr_2']],
      ['Paused', ['alr_3']],
      ['Expired', ['alr_4']],
    ]);
    expect(groupAlerts([pausedRule]).map((group) => group.title)).toEqual(['Paused']);
  });
});

describe('evaluationText', () => {
  it('reports what a check found', () => {
    expect(evaluationText({ evaluated: 4, fired: 1, expired: 0 })).toBe('Checked 4 alerts. 1 fired.');
    expect(evaluationText({ evaluated: 1, fired: 0, expired: 2 })).toBe('Checked 1 alert. 0 fired. 2 expired.');
  });
});

describe('AlertList', () => {
  it('groups the rules by state and shows each summary with its state in words', async () => {
    await show({ 'GET /v1/alerts': all });

    expect(await screen.findByText('Iron Valley Forge moneyline at +130 or higher')).toBeOnTheScreen();
    const headings = screen.getAllByRole('header').map((header) => header.props.children);
    expect(headings).toEqual(['Active', 'Triggered', 'Paused', 'Expired']);
    // The group title and the badge on the rule both say the state.
    for (const state of ['Active', 'Triggered', 'Paused', 'Expired']) expect(screen.getAllByText(state)).toHaveLength(2);
    expect(screen.getByText('Harbor City Gulls moneyline at -120 or higher')).toBeOnTheScreen();
    expect(screen.getByText('Each Harbor City Gulls game, 60 minutes before the start')).toBeOnTheScreen();
    expect(screen.getByText('This game is no longer in the data.')).toBeOnTheScreen();
    // Each state offers only its own action.
    expect(screen.getAllByRole('button', { name: /^Pause alert: / })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: /^Resume alert: / })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: /^Set alert again: / })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: /^Delete alert: / })).toHaveLength(4);
  });

  it('pauses an active rule', async () => {
    const { sent, session } = await show({ 'GET /v1/alerts': all, 'PATCH /v1/alerts/alr_1': { ...activeRule, state: 'paused' } });

    await fireEvent.press(await screen.findByRole('button', { name: 'Pause alert: Iron Valley Forge moneyline at +130 or higher' }));
    await waitFor(() => expect(session.changed).toHaveBeenCalledWith('alerts'));
    expect(sent().find((request) => request.method === 'PATCH')).toMatchObject({ path: '/v1/alerts/alr_1', body: { state: 'paused' } });
    // The list is read again after the change.
    expect(sent().filter((request) => request.path === '/v1/alerts')).toHaveLength(2);
  });

  it('resumes a paused rule and sets a triggered one again, both as state active', async () => {
    const { sent } = await show({
      'GET /v1/alerts': all,
      'PATCH /v1/alerts/alr_3': { ...pausedRule, state: 'active' },
      'PATCH /v1/alerts/alr_2': { ...triggeredRule, state: 'active' },
    });

    await fireEvent.press(await screen.findByRole('button', { name: /^Resume alert: / }));
    await waitFor(() => expect(sent().filter((request) => request.method === 'PATCH')).toHaveLength(1));
    await fireEvent.press(await screen.findByRole('button', { name: /^Set alert again: / }));
    await waitFor(() => expect(sent().filter((request) => request.method === 'PATCH')).toHaveLength(2));
    expect(sent().filter((request) => request.method === 'PATCH').map(({ path, body }) => ({ path, body }))).toEqual([
      { path: '/v1/alerts/alr_3', body: { state: 'active' } },
      { path: '/v1/alerts/alr_2', body: { state: 'active' } },
    ]);
  });

  it('deletes only after an inline confirmation', async () => {
    const { sent, fetchMock } = await show({ 'GET /v1/alerts': all, 'DELETE /v1/alerts/alr_1': noContent });

    await fireEvent.press(await screen.findByRole('button', { name: 'Delete alert: Iron Valley Forge moneyline at +130 or higher' }));
    expect(screen.getByText('Delete this alert? Notifications it already created are kept.')).toBeOnTheScreen();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await fireEvent.press(screen.getByRole('button', { name: 'Keep alert' }));
    expect(screen.queryByText('Delete this alert? Notifications it already created are kept.')).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await fireEvent.press(screen.getByRole('button', { name: 'Delete alert: Iron Valley Forge moneyline at +130 or higher' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Delete alert: Iron Valley Forge moneyline at +130 or higher' }));
    await waitFor(() => expect(sent().some((request) => request.method === 'DELETE')).toBe(true));
    expect(sent().find((request) => request.method === 'DELETE')).toMatchObject({ path: '/v1/alerts/alr_1', body: undefined });
  });

  it("shows the API's message when a change is refused", async () => {
    await show({ 'GET /v1/alerts': all, 'PATCH /v1/alerts/alr_2': () => errorResponse(409, 'alerts_full', 'You already have 100 active alerts. Pause or delete one first.') });

    await fireEvent.press(await screen.findByRole('button', { name: /^Set alert again: / }));
    expect(await screen.findByText('You already have 100 active alerts. Pause or delete one first.')).toBeOnTheScreen();
  });

  it('checks the alerts now and reports what happened', async () => {
    const { sent, session } = await show({ 'GET /v1/alerts': all, 'POST /v1/alerts/evaluate': { evaluated: 4, fired: 1, expired: 0 } });

    await fireEvent.press(await screen.findByRole('button', { name: 'Check now' }));
    expect(await screen.findByText('Checked 4 alerts. 1 fired.')).toBeOnTheScreen();
    expect(sent().find((request) => request.method === 'POST')!.path).toBe('/v1/alerts/evaluate');
    expect(session.changed).toHaveBeenCalledWith('notifications');
  });

  it('opens the game an alert is about, on its market', async () => {
    await show({ 'GET /v1/alerts': all });

    const open = await screen.findAllByRole('button', { name: 'Open game: Iron Valley Forge at Harbor City Gulls' });
    // The team alert has no single game and the expired one is no longer in the data.
    expect(open).toHaveLength(2);
    await fireEvent.press(open[0]);
    expect(router.push).toHaveBeenCalledWith({ pathname: '/event/[id]', params: { id: 'evt_2', market: 'moneyline' } });
  });

  it('explains that alerts are created from a game page when there are none', async () => {
    await show({ 'GET /v1/alerts': { items: [] } });

    expect(await screen.findByText('No alerts yet')).toBeOnTheScreen();
    expect(screen.getByText(/^Alerts are created from a game page\./)).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Check now' })).toBeNull();
  });

  it('says the data service cannot be reached', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));
    await render(
      <WithSession value={fakeSession()}>
        <AlertList userId="usr_1" />
      </WithSession>,
    );
    expect(await screen.findByText("OddVex can't reach its data service")).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeOnTheScreen();
  });
});
