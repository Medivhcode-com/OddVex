import { fireEvent, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';

import { setAuthToken } from '@/api/client';
import { PICKS_EXPLAINED, PRIVATE_PROFILE } from '@/components/community-copy';
import { quickBetOptions } from '@/components/quick-bet';
import { pickPayload, SharePick } from '@/components/share-pick';
import { GameDetailScreen } from '@/screens/game-detail';
import { errorResponse, jsonResponse } from '@/test/api';
import { showCommunity } from '@/test/community';
import { flagsAllOn, liveEvent, moneyline, myProfile, myUpcomingPick, privateProfile, spread, upcomingEvent } from '@/test/fixtures';
import { fakeSession } from '@/test/session';
import { screenStrings } from '@/test/strings';

const PROFILE = 'GET /v1/community/profile';
const POST = 'POST /v1/community/picks';
const upcomingMoneyline = { ...moneyline, event: upcomingEvent };
const total = {
  ...spread,
  market: 'total' as const,
  best: [
    { outcome_key: 'over', sportsbook_key: 'book_a', price: spread.best[0].price, line: 44.5 },
    { outcome_key: 'under', sportsbook_key: 'book_b', price: spread.best[1].price, line: 44.5 },
  ],
  consensus: { outcomes: [{ key: 'over', name: 'Over', no_vig_probability: 0.5 }, { key: 'under', name: 'Under', no_vig_probability: 0.5 }], books_used: 2 },
};

beforeEach(() => {
  jest.mocked(router.push).mockClear();
  setAuthToken('token-1');
});
afterEach(() => setAuthToken(null));

describe('pickPayload', () => {
  it('sends a moneyline with no line', () => {
    const body = pickPayload(upcomingEvent, 'moneyline', quickBetOptions(upcomingMoneyline)[0], '');
    expect(body).toEqual({ event_id: 'evt_2', market: 'moneyline', outcome_key: 'away' });
    expect('line' in body).toBe(false);
  });

  it('sends a spread with the line of the chosen side, and a total with its line', () => {
    const [away, home] = quickBetOptions(spread);
    expect(pickPayload(upcomingEvent, 'spread', home, '')).toEqual({ event_id: 'evt_2', market: 'spread', outcome_key: 'home', line: -3.5 });
    expect(pickPayload(upcomingEvent, 'spread', away, '')).toEqual({ event_id: 'evt_2', market: 'spread', outcome_key: 'away', line: 3.5 });
    expect(pickPayload(upcomingEvent, 'total', quickBetOptions(total)[1], '')).toEqual({ event_id: 'evt_2', market: 'total', outcome_key: 'under', line: 44.5 });
  });

  it('adds the analysis only when something was written, and never a price or an amount', () => {
    const body = pickPayload(upcomingEvent, 'spread', quickBetOptions(spread)[1], '  Line moved half a point.  ');
    expect(body).toEqual({ event_id: 'evt_2', market: 'spread', outcome_key: 'home', line: -3.5, analysis: 'Line moved half a point.' });
    expect(Object.keys(body).sort()).toEqual(['analysis', 'event_id', 'line', 'market', 'outcome_key']);
  });
});

describe('SharePick, where it appears', () => {
  it('is not drawn and asks for nothing while the flag is off', async () => {
    const { fetchMock } = await showCommunity(<SharePick event={upcomingEvent} odds={spread} />, { [PROFILE]: myProfile }, { flags: flagsAllOn });
    expect(screen.queryByText('Share a pick')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('is not drawn signed out', async () => {
    const { fetchMock } = await showCommunity(<SharePick event={upcomingEvent} odds={spread} />, {}, { session: fakeSession({ user: null }) });
    expect(screen.queryByText('Share a pick')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('is not drawn once the game has started', async () => {
    await showCommunity(<SharePick event={liveEvent} odds={moneyline} />, { [PROFILE]: myProfile });
    expect(screen.queryByText('Share a pick')).toBeNull();
    await showCommunity(<SharePick event={{ ...liveEvent, status: 'final' }} odds={moneyline} />, { [PROFILE]: myProfile });
    expect(screen.queryByText('Share a pick')).toBeNull();
  });

  it('sends someone without a profile to set one up', async () => {
    await showCommunity(<SharePick event={upcomingEvent} odds={spread} />, { [PROFILE]: () => errorResponse(404, 'not_found', 'You have no community profile yet') });

    expect(await screen.findByText("Posting needs a public community profile. You don't have a profile yet.")).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Post pick' })).toBeNull();
    await fireEvent.press(screen.getByRole('button', { name: 'Set up your profile' }));
    expect(router.push).toHaveBeenCalledWith('/community/profile');
  });

  it('tells someone with a private profile that they can browse but not post', async () => {
    await showCommunity(<SharePick event={upcomingEvent} odds={spread} />, { [PROFILE]: privateProfile });

    expect(await screen.findByText(PRIVATE_PROFILE)).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Post pick' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Edit your profile' })).toBeOnTheScreen();
  });
});

describe('Game detail', () => {
  const detail = { ...upcomingEvent, available_markets: ['moneyline', 'spread'], league_name: 'NFL', has_draw: false, players: [], as_of: spread.as_of, data_mode: 'synthetic' };
  const routes = { 'GET /v1/events/evt_2': detail, 'GET /v1/events/evt_2/odds?market=spread': spread, 'GET /v1/watchlist': { items: [] }, [PROFILE]: myProfile };

  it('has "Share a pick" on an upcoming game while the flag is on', async () => {
    await showCommunity(<GameDetailScreen eventId="evt_2" initialMarket="spread" />, routes);

    expect(await screen.findByText('Share a pick')).toBeOnTheScreen();
    expect(await screen.findByRole('button', { name: 'Post pick' })).toBeOnTheScreen();
    expect(screen.getByText('Track a bet on this game')).toBeOnTheScreen();
  });

  it('has no trace of it while the flag is off', async () => {
    const { sent } = await showCommunity(<GameDetailScreen eventId="evt_2" initialMarket="spread" />, routes, { flags: flagsAllOn });

    expect(await screen.findByText('Track a bet on this game')).toBeOnTheScreen();
    expect(screen.queryByText('Share a pick')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Post pick' })).toBeNull();
    expect(sent().some((item) => item.path.startsWith('/v1/community'))).toBe(false);
  });
});

describe('SharePick form', () => {
  const show = (odds = spread, routes: Record<string, unknown> = {}) => showCommunity(<SharePick event={upcomingEvent} odds={odds} />, { [PROFILE]: myProfile, ...routes });

  it('offers the outcomes at the best current prices, a rules reminder, and no stake, size or confidence field', async () => {
    await show();

    expect(await screen.findByRole('radio', { name: 'Outcome, at the best current price: Iron Valley Forge +3.5 −105 at Beacon Bets' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'Outcome, at the best current price: Harbor City Gulls −3.5 −108 at Northstar Sports' })).not.toBeChecked();
    expect(screen.getByText(PICKS_EXPLAINED)).toBeOnTheScreen();
    expect(screen.getByText(/^Plain text only\. No links, no contact details, no selling, and no promises about a result\./)).toBeOnTheScreen();
    expect(screen.getByText('0 / 1000 characters')).toBeOnTheScreen();

    const labels = screenStrings().join('\n');
    expect(labels).not.toMatch(/stake|confidence|\bunits?\b|how much|wager/i);
    expect(screen.queryByLabelText(/stake/i)).toBeNull();
  });

  it('posts a spread pick with the line of the chosen side', async () => {
    const { sent, session } = await show(spread, { [POST]: () => jsonResponse(myUpcomingPick, 201) });

    await fireEvent.press(await screen.findByRole('radio', { name: /Harbor City Gulls −3\.5/ }));
    await fireEvent.changeText(screen.getByLabelText('Your reasoning (optional)'), 'Line moved half a point.');
    expect(screen.getByText('24 / 1000 characters')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Post pick' }));

    expect(await screen.findByText('Pick posted. It will be graded from the final score.')).toBeOnTheScreen();
    const request = sent().find((item) => item.method === 'POST');
    expect(request?.path).toBe('/v1/community/picks');
    expect(request?.body).toEqual({ event_id: 'evt_2', market: 'spread', outcome_key: 'home', line: -3.5, analysis: 'Line moved half a point.' });
    expect(request?.headers.authorization).toBe('Bearer token-1');
    expect(session.changed).toHaveBeenCalledWith('community');

    await fireEvent.press(screen.getByRole('button', { name: 'Open your pick' }));
    expect(router.push).toHaveBeenCalledWith({ pathname: '/community/picks/[id]', params: { id: 'pick_6' } });
  });

  it('posts a moneyline pick without a line or an analysis', async () => {
    const { sent } = await show(upcomingMoneyline, { [POST]: () => jsonResponse(myUpcomingPick, 201) });

    await fireEvent.press(await screen.findByRole('button', { name: 'Post pick' }));
    await waitFor(() => expect(sent().some((item) => item.method === 'POST')).toBe(true));
    expect(sent().find((item) => item.method === 'POST')?.body).toEqual({ event_id: 'evt_2', market: 'moneyline', outcome_key: 'away' });
  });

  it('stops an analysis longer than 1000 characters before it is sent', async () => {
    const { sent } = await show();

    await fireEvent.changeText(await screen.findByLabelText('Your reasoning (optional)'), 'x'.repeat(1001));
    expect(screen.getByText('1001 / 1000 characters. Shorten it to 1000 or fewer.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Post pick' }));
    expect(sent().some((item) => item.method === 'POST')).toBe(false);
  });

  it.each([
    [
      'a promise about a result',
      errorResponse(422, 'content_not_allowed', 'Do not present a result as certain.', { field: 'analysis', rule: 'guaranteed_outcome' }),
      'This reads as a promise about a result, and no result is certain. Reword it and try again.',
    ],
    [
      'pressure to bet',
      errorResponse(422, 'content_not_allowed', 'Do not push other people to bet.', { field: 'analysis', rule: 'inducement_to_bet' }),
      'This reads as pressure to bet, to bet more or to win money back. Reword it and try again.',
    ],
    ['a link', errorResponse(422, 'links_not_allowed', 'Links are not allowed', { field: 'analysis', rule: 'links' }), "Links aren't allowed here. Remove the link and try again."],
    ['a game that has started', errorResponse(422, 'event_not_open', 'Picks can only be posted on upcoming events'), 'This game has already started, so picks on it are closed.'],
    [
      'a second pick on the same game and market',
      errorResponse(409, 'pick_exists', 'You already have a pick on this market of this event'),
      'You already have a pick on this market for this game. One pick per game and market.',
    ],
    ['the daily limit', errorResponse(429, 'rate_limited', 'Too many requests. Try again in 3600 seconds.', { retry_after_seconds: 3600 }), 'You have reached the daily limit for picks. Try again tomorrow.'],
    ['a private profile', errorResponse(403, 'profile_required', 'A public community profile is required for this', { reason: 'not_public' }), 'You need a public community profile to do this.'],
    [
      'no open price',
      errorResponse(422, 'price_not_available', 'No sportsbook has an open price'),
      "No sportsbook has an open price for this selection right now, so it can't be posted. Try again in a moment.",
    ],
  ])('explains %s', async (_case, response, message) => {
    const { session } = await show(spread, { [POST]: () => response });

    await fireEvent.changeText(await screen.findByLabelText('Your reasoning (optional)'), 'My reasoning.');
    await fireEvent.press(screen.getByRole('button', { name: 'Post pick' }));

    expect(await screen.findByText(message)).toBeOnTheScreen();
    expect(screen.queryByText('Pick posted. It will be graded from the final score.')).toBeNull();
    expect(screen.getByLabelText('Your reasoning (optional)').props.value).toBe('My reasoning.');
    expect(session.changed).not.toHaveBeenCalled();
  });

  it('links to the pick that already exists', async () => {
    await show(spread, { [POST]: () => errorResponse(409, 'pick_exists', 'You already have a pick on this market of this event', { pick_id: 'pick_6' }) });

    await fireEvent.press(await screen.findByRole('button', { name: 'Post pick' }));
    await fireEvent.press(await screen.findByRole('button', { name: 'Open your pick' }));
    expect(router.push).toHaveBeenCalledWith({ pathname: '/community/picks/[id]', params: { id: 'pick_6' } });
  });
});
