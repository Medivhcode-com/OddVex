import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';

import { setAuthToken } from '@/api/client';
import type { EventSummary, OddsComparison } from '@/api/types';
import { AlertForm, readMove, readThreshold, suggestedThreshold } from '@/components/alert-form';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { activeRule, liveEvent, moneyline, spread, upcomingEvent } from '@/test/fixtures';
import { fakeSession, WithSession } from '@/test/session';

const upcomingMoneyline: OddsComparison = { ...moneyline, event: upcomingEvent };

async function show(odds: OddsComparison, event: EventSummary = upcomingEvent, respond: () => unknown = () => jsonResponse(activeRule, 201)) {
  const { fetchMock, sent } = installFetch();
  fetchMock.mockImplementation(async () => respond());
  const session = fakeSession();
  await render(
    <WithSession value={session}>
      <AlertForm event={event} odds={odds} />
    </WithSession>,
  );
  return { fetchMock, sent, session };
}

const save = () => fireEvent.press(screen.getByRole('button', { name: 'Save alert' }));
const choose = (name: string) => fireEvent.press(screen.getByRole('radio', { name }));

beforeEach(() => {
  jest.mocked(router.push).mockClear();
  setAuthToken('token-1');
});
afterEach(() => setAuthToken(null));

describe('suggestedThreshold', () => {
  it('starts a little above the current best, skipping the gap between −100 and +100', () => {
    expect(suggestedThreshold(118)).toBe('+128');
    expect(suggestedThreshold(-140)).toBe('-130');
    expect(suggestedThreshold(-110)).toBe('-100');
    expect(suggestedThreshold(-108)).toBe('+102');
    expect(suggestedThreshold(-105)).toBe('+105');
    expect(suggestedThreshold(100)).toBe('+110');
  });
});

describe('readThreshold', () => {
  it('accepts signed American odds as typed and takes an unsigned number as plus', () => {
    expect(readThreshold('+150')).toEqual({ value: '+150' });
    expect(readThreshold(' -105 ')).toEqual({ value: '-105' });
    expect(readThreshold('−110')).toEqual({ value: '-110' });
    expect(readThreshold('150')).toEqual({ value: '+150' });
  });

  it('asks for a price when empty, malformed or between −100 and +100', () => {
    expect(readThreshold('  ')).toEqual({ error: 'Enter the price to reach in American odds, such as +150 or -105.' });
    expect(readThreshold('abc')).toEqual({ error: 'Use American odds: a plus or minus sign and a whole number, such as +150 or -105.' });
    expect(readThreshold('+-150')).toHaveProperty('error');
    expect(readThreshold('2.5')).toHaveProperty('error');
    expect(readThreshold('+50')).toEqual({ error: 'American odds are +100 or higher, or -100 or lower.' });
  });
});

describe('readMove', () => {
  it('needs a number above zero', () => {
    expect(readMove('1.5')).toEqual({ value: 1.5 });
    expect(readMove('1,5')).toEqual({ value: 1.5 });
    for (const bad of ['', '0', '-1', 'two']) expect(readMove(bad)).toHaveProperty('error');
  });
});

describe('AlertForm', () => {
  it('saves a moneyline price alert without a line, prefilled a little above the current best', async () => {
    const { sent, session } = await show(upcomingMoneyline);

    expect(screen.getByRole('radio', { name: 'Alert me when: Price reaches' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'Side, on the moneyline market: Iron Valley Forge ML, best now +118 at Northstar Sports' })).toBeChecked();
    expect(screen.getByLabelText('Price to reach (American odds)')).toHaveDisplayValue('+128');
    await fireEvent.changeText(screen.getByLabelText('Price to reach (American odds)'), '+150');
    await save();

    expect(await screen.findByText('Alert saved.')).toBeOnTheScreen();
    expect(sent()).toHaveLength(1);
    expect(sent()[0]).toMatchObject({ method: 'POST', path: '/v1/alerts' });
    expect(sent()[0].body).toEqual({ kind: 'price_at_least', event_id: 'evt_2', market: 'moneyline', outcome_key: 'away', threshold: '+150', odds_format: 'american' });
    expect(sent()[0].body).not.toHaveProperty('line');
    expect(sent()[0].headers.authorization).toBe('Bearer token-1');
    expect(session.changed).toHaveBeenCalledWith('alerts');

    await fireEvent.press(screen.getByRole('button', { name: 'See your alerts' }));
    expect(router.push).toHaveBeenCalledWith({ pathname: '/notifications', params: { tab: 'alerts' } });
  });

  it('saves a spread price alert with the line of the chosen side', async () => {
    const { sent } = await show(spread);

    expect(screen.getByLabelText('Price to reach (American odds)')).toHaveDisplayValue('+105');
    await choose('Side, on the spread market: Harbor City Gulls −3.5, best now −108 at Northstar Sports');
    // The suggestion follows the side while nothing has been typed for it.
    expect(screen.getByLabelText('Price to reach (American odds)')).toHaveDisplayValue('+102');
    await save();

    expect(await screen.findByText('Alert saved.')).toBeOnTheScreen();
    expect(sent()[0].body).toEqual({
      kind: 'price_at_least',
      event_id: 'evt_2',
      market: 'spread',
      outcome_key: 'home',
      line: -3.5,
      threshold: '+102',
      odds_format: 'american',
    });
  });

  it('checks the price before sending anything', async () => {
    const { fetchMock } = await show(upcomingMoneyline);

    await fireEvent.changeText(screen.getByLabelText('Price to reach (American odds)'), '');
    await save();
    expect(screen.getByRole('alert')).toHaveTextContent('Enter the price to reach in American odds, such as +150 or -105.');

    await fireEvent.changeText(screen.getByLabelText('Price to reach (American odds)'), '+1x0');
    await save();
    expect(screen.getByRole('alert')).toHaveTextContent('Use American odds: a plus or minus sign and a whole number, such as +150 or -105.');

    await fireEvent.changeText(screen.getByLabelText('Price to reach (American odds)'), '-50');
    await save();
    expect(screen.getByRole('alert')).toHaveTextContent('American odds are +100 or higher, or -100 or lower.');
    expect(screen.queryByText('Alert saved.')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('saves a line move alert on the spread, one point by default', async () => {
    const { sent, fetchMock } = await show(spread);

    await choose('Alert me when: Line moves');
    expect(screen.getByLabelText('Move, in points')).toHaveDisplayValue('1');

    await fireEvent.changeText(screen.getByLabelText('Move, in points'), '0');
    await save();
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a move greater than zero, in points, such as 1 or 1.5.');
    expect(fetchMock).not.toHaveBeenCalled();

    await fireEvent.changeText(screen.getByLabelText('Move, in points'), '1.5');
    await save();
    expect(await screen.findByText('Alert saved.')).toBeOnTheScreen();
    expect(sent()[0].body).toEqual({ kind: 'line_move', event_id: 'evt_2', market: 'spread', outcome_key: 'away', min_move: 1.5 });
  });

  it('asks for the spread or the total before a line alert on the moneyline', async () => {
    const { fetchMock } = await show(upcomingMoneyline);

    await choose('Alert me when: Line moves');
    expect(screen.getByText('Line alerts follow the spread or the total. Choose Spread or Total in the market switcher above.')).toBeOnTheScreen();
    expect(screen.queryByLabelText('Move, in points')).toBeNull();
    await save();
    expect(screen.getByText('Choose Spread or Total in the market switcher first.')).toBeOnTheScreen();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('saves a game start alert with the minutes picked', async () => {
    const { sent } = await show(upcomingMoneyline);

    await choose('Alert me when: Before the game starts');
    expect(screen.getByRole('radio', { name: 'How long before the start: 30 minutes' })).toBeChecked();
    for (const label of ['15 minutes', '1 hour', '2 hours']) expect(screen.getByRole('radio', { name: `How long before the start: ${label}` })).toBeOnTheScreen();
    await choose('How long before the start: 2 hours');
    await save();

    expect(await screen.findByText('Alert saved.')).toBeOnTheScreen();
    expect(sent()[0].body).toEqual({ kind: 'game_start', event_id: 'evt_2', minutes_before: 120 });
  });

  it('saves a final score alert', async () => {
    const { sent } = await show(upcomingMoneyline);

    await choose('Alert me when: When the game ends');
    await save();

    expect(await screen.findByText('Alert saved.')).toBeOnTheScreen();
    expect(sent()[0].body).toEqual({ kind: 'game_final', event_id: 'evt_2' });
  });

  it('does not offer a start alert once the game is live', async () => {
    await show(moneyline, liveEvent);

    expect(screen.queryByRole('radio', { name: 'Alert me when: Before the game starts' })).toBeNull();
    expect(screen.getByRole('radio', { name: 'Alert me when: When the game ends' })).toBeOnTheScreen();
  });

  it("shows the API's 422 message as sent, under the form", async () => {
    await show(spread, upcomingEvent, () => errorResponse(422, 'line_not_available', 'There is no current line for this market, so a line alert cannot start.'));

    await choose('Alert me when: Line moves');
    await save();

    expect(await screen.findByText('There is no current line for this market, so a line alert cannot start.')).toBeOnTheScreen();
    expect(screen.queryByText('Alert saved.')).toBeNull();
  });

  it('saves a team alert for 60 minutes before each of its games', async () => {
    const { sent } = await show(upcomingMoneyline);

    await fireEvent.press(screen.getByRole('button', { name: "Alert me before Harbor City Gulls's games" }));
    expect(await screen.findByText('Alert saved.')).toBeOnTheScreen();
    await waitFor(() => expect(sent()).toHaveLength(1));
    expect(sent()[0].body).toEqual({ kind: 'game_start', team_id: 't_home', minutes_before: 60 });
    expect(screen.getByRole('button', { name: "Alert me before Iron Valley Forge's games" })).toBeOnTheScreen();
  });

  it('says alerts are in-app only', async () => {
    await show(upcomingMoneyline);
    expect(
      screen.getByText('Alerts show up under Notifications in this app. There is no push yet, so they are checked when you open the app.'),
    ).toBeOnTheScreen();
  });
});
