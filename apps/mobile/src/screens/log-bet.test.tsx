import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';
import { useEffect } from 'react';

import { getUnreadCount, setAuthToken } from '@/api/client';
import { SessionProvider, useSession, type SessionValue } from '@/providers/session';
import { LogBetScreen } from '@/screens/log-bet';
import { clearSession } from '@/session/store';
import { errorResponse, installFetch, jsonResponse, serveRoutes } from '@/test/api';
import { auth, openBet, unverifiedUser } from '@/test/fixtures';

let session: SessionValue;

function Probe() {
  const value = useSession();
  useEffect(() => {
    session = value;
  }, [value]);
  return null;
}

const SIGNED_OUT = 'Log in to track your bets';
const KEPT = 'You were signed out, so nothing was saved. What you entered is still here.';
const expired = () => errorResponse(401, 'invalid_token', 'The access token is invalid or has expired');

/** The real session provider around the screen, signed in as the fixture user, with the form loaded. */
async function open(routes: Record<string, unknown> = {}) {
  const { fetchMock, sent } = installFetch();
  const serve = (extra: Record<string, unknown>) =>
    serveRoutes(fetchMock, {
      'GET /v1/leagues': [{ key: 'nfl', name: 'NFL' }],
      'GET /v1/sportsbooks': [{ key: 'book_a', name: 'Northstar Sports' }],
      'POST /v1/auth/login': auth,
      'POST /v1/auth/logout': () => jsonResponse(undefined, 204),
      ...extra,
    });
  serve(routes);
  await render(
    <SessionProvider>
      <Probe />
      <LogBetScreen />
    </SessionProvider>,
  );
  expect(await screen.findByText(SIGNED_OUT)).toBeOnTheScreen();
  await act(() => session.logIn('sam@example.test', 'correct horse battery'));
  expect(await screen.findByLabelText('Pick')).toBeOnTheScreen();
  return { sent, serve };
}

async function typeParlay() {
  await fireEvent.press(screen.getByRole('radio', { name: 'Bet type: Parlay' }));
  await fireEvent.press(screen.getByRole('radio', { name: 'Odds format: Decimal' }));
  await fireEvent.changeText(screen.getByLabelText('Sportsbook'), 'Cedar Book');
  await fireEvent.changeText(screen.getByLabelText('Leg 1 pick'), 'Gulls ML');
  await fireEvent.changeText(screen.getByLabelText('Leg 1 odds'), '1.91');
  await fireEvent.changeText(screen.getByLabelText('Leg 2 pick'), 'Over 44.5');
  await fireEvent.changeText(screen.getByLabelText('Leg 2 game (optional)'), 'Forge at Gulls');
  await fireEvent.press(screen.getByRole('radio', { name: 'Leg 2 market: Total' }));
  await fireEvent.changeText(screen.getByLabelText('Leg 2 odds'), '2.05');
  await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '25');
}

function expectParlayOnScreen() {
  expect(screen.getByRole('radio', { name: 'Bet type: Parlay' })).toBeChecked();
  expect(screen.getByRole('radio', { name: 'Odds format: Decimal' })).toBeChecked();
  expect(screen.getByLabelText('Sportsbook')).toHaveDisplayValue('Cedar Book');
  expect(screen.getByLabelText('Leg 1 pick')).toHaveDisplayValue('Gulls ML');
  expect(screen.getByLabelText('Leg 1 odds')).toHaveDisplayValue('1.91');
  expect(screen.getByLabelText('Leg 2 pick')).toHaveDisplayValue('Over 44.5');
  expect(screen.getByLabelText('Leg 2 game (optional)')).toHaveDisplayValue('Forge at Gulls');
  expect(screen.getByRole('radio', { name: 'Leg 2 market: Total' })).toBeChecked();
  expect(screen.getByLabelText('Leg 2 odds')).toHaveDisplayValue('2.05');
  expect(screen.getByLabelText('Stake ($)')).toHaveDisplayValue('25');
}

beforeEach(async () => {
  await clearSession();
  setAuthToken(null);
  jest.mocked(router.push).mockClear();
});

describe('LogBetScreen when the session ends', () => {
  it('keeps what was typed when Save is answered 401, and saves it after logging in again', async () => {
    const { sent, serve } = await open({ 'POST /v1/bets': expired });
    await typeParlay();
    await fireEvent.press(screen.getByRole('button', { name: 'Save bet' }));

    // The API rejected the token: the session ends and the log in screen opens over this one.
    expect(await screen.findByText(SIGNED_OUT)).toBeOnTheScreen();
    expect(router.push).toHaveBeenCalledWith('/login');
    expect(screen.queryByLabelText('Stake ($)')).toBeNull();

    await act(() => session.logIn('sam@example.test', 'correct horse battery'));

    expect(await screen.findByLabelText('Stake ($)')).toBeOnTheScreen();
    expectParlayOnScreen();
    expect(screen.getByText(KEPT)).toBeOnTheScreen();

    serve({ 'POST /v1/bets': () => jsonResponse(openBet, 201) });
    await fireEvent.press(screen.getByRole('button', { name: 'Save bet' }));
    expect(await screen.findByText('Bet saved. It is in your open bets.')).toBeOnTheScreen();
    const saves = sent().filter((request) => request.method === 'POST' && request.path === '/v1/bets');
    expect(saves).toHaveLength(2);
    expect(saves[1].body).toEqual(saves[0].body);
    expect(saves[1].body).toMatchObject({
      bet_type: 'parlay',
      stake: 25,
      sportsbook: 'Cedar Book',
      legs: [
        { selection: 'Gulls ML', market: 'moneyline', odds: '1.91', odds_format: 'decimal' },
        { selection: 'Over 44.5', market: 'total', event_label: 'Forge at Gulls', odds: '2.05', odds_format: 'decimal' },
      ],
    });
    expect(screen.queryByText(KEPT)).toBeNull();
  });

  it('keeps it when another request ends the session before Save is pressed', async () => {
    await open({ 'GET /v1/notifications/unread-count': expired });
    await typeParlay();

    // What the bell does when the app returns to the foreground.
    await act(async () => {
      await getUnreadCount().catch(() => {});
    });
    expect(await screen.findByText(SIGNED_OUT)).toBeOnTheScreen();

    await act(() => session.logIn('sam@example.test', 'correct horse battery'));
    expect(await screen.findByLabelText('Stake ($)')).toBeOnTheScreen();
    expectParlayOnScreen();
  });

  it('does not bring back a bet that was saved, or say that nothing was saved', async () => {
    const { sent } = await open({ 'POST /v1/bets': () => jsonResponse(openBet, 201), 'GET /v1/notifications/unread-count': expired });
    await typeParlay();
    await fireEvent.press(screen.getByRole('button', { name: 'Save bet' }));
    expect(await screen.findByText('Bet saved. It is in your open bets.')).toBeOnTheScreen();

    // The form stays on screen as a parlay with two empty legs, which is not how it was first drawn.
    await act(async () => {
      await getUnreadCount().catch(() => {});
    });
    expect(await screen.findByText(SIGNED_OUT)).toBeOnTheScreen();
    await act(() => session.logIn('sam@example.test', 'correct horse battery'));

    expect(await screen.findByLabelText('Pick')).toHaveDisplayValue('');
    expect(screen.getByRole('radio', { name: 'Bet type: Straight' })).toBeChecked();
    expect(screen.getByLabelText('Stake ($)')).toHaveDisplayValue('');
    expect(screen.queryByText(KEPT)).toBeNull();
    expect(sent().filter((request) => request.method === 'POST' && request.path === '/v1/bets')).toHaveLength(1);
  });

  it('shows an empty form when a different account logs in', async () => {
    const { serve } = await open({ 'POST /v1/bets': expired });
    await typeParlay();
    await fireEvent.press(screen.getByRole('button', { name: 'Save bet' }));
    expect(await screen.findByText(SIGNED_OUT)).toBeOnTheScreen();

    serve({ 'POST /v1/auth/login': { ...auth, access_token: 'token-2', user: unverifiedUser } });
    await act(() => session.logIn('riley@example.test', 'correct horse battery'));

    expect(await screen.findByLabelText('Pick')).toHaveDisplayValue('');
    expect(screen.getByLabelText('Stake ($)')).toHaveDisplayValue('');
    expect(screen.getByRole('radio', { name: 'Bet type: Straight' })).toBeChecked();
    expect(screen.queryByText(KEPT)).toBeNull();
  });

  it('shows an empty form after logging out on purpose', async () => {
    await open();
    await typeParlay();

    await act(() => session.logOut());
    expect(await screen.findByText(SIGNED_OUT)).toBeOnTheScreen();
    await act(() => session.logIn('sam@example.test', 'correct horse battery'));

    expect(await screen.findByLabelText('Pick')).toHaveDisplayValue('');
    expect(screen.getByLabelText('Stake ($)')).toHaveDisplayValue('');
    expect(screen.queryByText(KEPT)).toBeNull();
  });

  it('shows an empty form after the account was suspended', async () => {
    await open({ 'POST /v1/bets': () => errorResponse(401, 'account_suspended', 'This account is suspended') });
    await typeParlay();
    await fireEvent.press(screen.getByRole('button', { name: 'Save bet' }));
    expect(await screen.findByText(SIGNED_OUT)).toBeOnTheScreen();
    await waitFor(() => expect(session.suspended).toBe(true));

    await act(() => session.logIn('sam@example.test', 'correct horse battery'));

    expect(await screen.findByLabelText('Pick')).toHaveDisplayValue('');
    expect(screen.getByLabelText('Stake ($)')).toHaveDisplayValue('');
  });
});
