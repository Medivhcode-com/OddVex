import { fireEvent, render, screen } from '@testing-library/react-native';
import { router } from 'expo-router';

import { FEATURE_UNAVAILABLE } from '@/api/client';
import { ValueEntry } from '@/components/value-entry';
import { consensusText, EDGE_LABEL, outcomeText, ValueScreen } from '@/screens/value';
import { errorResponse, installFetch, serveRoutes } from '@/test/api';
import { valueRow, valueScreen } from '@/test/fixtures';
import { screenStrings } from '@/test/strings';
import { formatSignedPercent } from '@/utils/format';

const leagues = [{ key: 'nfl', name: 'NFL' }];
/** BRAND_VOICE banned claims, plus the words this screen must never use for its number. */
const BANNED = [/guarantee/i, /free money/i, /\block(s|ed)?\b/i, /risk[- ]free/i, /\+\s?EV/i, /\bpicks?\b/i, /sure thing/i, /can't lose/i, /profit/i];

function expectNoBannedWords() {
  const strings = screenStrings();
  expect(strings.length).toBeGreaterThan(5);
  for (const text of strings) for (const banned of BANNED) expect(text).not.toMatch(banned);
}

beforeEach(() => jest.mocked(router.push).mockClear());

describe('display helpers', () => {
  it('writes the outcome with its line', () => {
    expect(outcomeText({ market: 'spread', outcome_name: 'Harbor City Gulls', line: -3.5 })).toBe('Harbor City Gulls −3.5');
    expect(outcomeText({ market: 'spread', outcome_name: 'Iron Valley Forge', line: 3.5 })).toBe('Iron Valley Forge +3.5');
    expect(outcomeText({ market: 'total', outcome_name: 'Over', line: 44.5 })).toBe('Over 44.5');
    expect(outcomeText({ market: 'moneyline', outcome_name: 'Harbor City Gulls', line: null })).toBe('Harbor City Gulls');
  });

  it('writes the consensus with how many other books are in it', () => {
    expect(consensusText({ books_in_consensus: 3, consensus_probability: 0.473 })).toBe('Consensus of 3 other books: 47.3%');
  });

  it('shows the edge as a signed percentage with a true minus', () => {
    expect(formatSignedPercent(0.0314)).toBe('+3.1%');
    expect(formatSignedPercent(-0.02)).toBe('−2.0%');
    expect(formatSignedPercent(-0.02)).not.toContain('-');
    expect(formatSignedPercent(0)).toBe('0.0%');
  });
});

describe('ValueScreen', () => {
  it("shows the API's caveat and method above the rows, and each row's numbers", async () => {
    const { fetchMock, sent } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/value': valueScreen, 'GET /v1/leagues': leagues });
    await render(<ValueScreen />);

    expect(await screen.findByText(valueScreen.caveat)).toBeOnTheScreen();
    expect(screen.getByText(/^A price above the consensus is not proof of an edge\./)).toBeOnTheScreen();
    expect(screen.getByText('What this does not tell you')).toBeOnTheScreen();
    expect(screen.getByText(valueScreen.method)).toBeOnTheScreen();
    expect(screen.getByText('How it is calculated')).toBeOnTheScreen();

    expect(screen.getAllByText('Iron Valley Forge at Harbor City Gulls')).toHaveLength(2);
    expect(screen.getByText('Harbor City Gulls −3.5')).toBeOnTheScreen();
    expect(screen.getByText('+105')).toBeOnTheScreen();
    expect(screen.getByText('at Cedar Book')).toBeOnTheScreen();
    expect(screen.getByText('Consensus of 3 other books: 50.3%')).toBeOnTheScreen();
    expect(screen.getAllByText('Break-even at this price: 48.8%')).toHaveLength(1);
    expect(screen.getAllByText(EDGE_LABEL)).toHaveLength(2);
    expect(screen.getByText('+3.1%')).toBeOnTheScreen();

    expect(screen.getByText('Over 44.5')).toBeOnTheScreen();
    expect(screen.getByText('−102')).toBeOnTheScreen();
    expect(screen.getByText('at Northstar Sports')).toBeOnTheScreen();
    expect(screen.getByText('Consensus of 2 other books: 51.1%')).toBeOnTheScreen();
    expect(screen.getByText('+1.2%')).toBeOnTheScreen();
    expect(screen.getByText(/^2 outcomes, largest first\./)).toBeOnTheScreen();

    expect(sent().find((request) => request.path.startsWith('/v1/value'))?.headers.authorization).toBeUndefined();
    expectNoBannedWords();
  });

  it('opens the game on the row’s market', async () => {
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/value': valueScreen, 'GET /v1/leagues': leagues });
    await render(<ValueScreen />);

    const row = await screen.findByRole('button', { name: /Spread: Harbor City Gulls −3\.5\. Best price \+105 at Cedar Book.*Edge vs consensus: \+3\.1%\.$/ });
    await fireEvent.press(row);
    expect(router.push).toHaveBeenCalledWith({ pathname: '/event/[id]', params: { id: 'evt_2', market: 'spread' } });

    await fireEvent.press(screen.getByRole('button', { name: /Total: Over 44\.5/ }));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/event/[id]', params: { id: 'evt_1', market: 'total' } });
  });

  it('sends the league, market and smallest edge the person chose', async () => {
    const { fetchMock, sent } = installFetch();
    serveRoutes(fetchMock, {
      'GET /v1/value': valueScreen,
      'GET /v1/leagues': leagues,
      'GET /v1/value?league=nfl': valueScreen,
      'GET /v1/value?league=nfl&market=spread': { ...valueScreen, rows: [valueRow] },
      'GET /v1/value?league=nfl&market=spread&min_edge=0.02': { ...valueScreen, rows: [valueRow], min_edge: 0.02 },
    });
    await render(<ValueScreen />);
    await screen.findByText('Over 44.5');

    await fireEvent.press(await screen.findByRole('button', { name: 'NFL' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Spread' }));
    await fireEvent.press(screen.getByRole('button', { name: '2% or more' }));

    expect(await screen.findByText(/^1 outcome, largest first\./)).toBeOnTheScreen();
    expect(screen.queryByText('Over 44.5')).toBeNull();
    expect(sent().map((request) => request.path)).toContain('/v1/value?league=nfl&market=spread&min_edge=0.02');
  });

  it('explains an empty screen instead of looking broken', async () => {
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, { 'GET /v1/value': { ...valueScreen, rows: [] }, 'GET /v1/leagues': leagues });
    await render(<ValueScreen />);

    expect(await screen.findByText('Nothing qualifies right now')).toBeOnTheScreen();
    expect(screen.getByText(/On many slates nothing qualifies, and that is normal\./)).toBeOnTheScreen();
    expect(screen.getByText(valueScreen.caveat)).toBeOnTheScreen();
    expectNoBannedWords();
  });

  it('offers a retry when the data service cannot be reached', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));
    await render(<ValueScreen />);

    expect(await screen.findByText("OddVex can't reach its data service")).toBeOnTheScreen();
    serveRoutes(fetchMock, { 'GET /v1/value': valueScreen, 'GET /v1/leagues': leagues });
    await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Harbor City Gulls −3.5')).toBeOnTheScreen();
  });

  it('says so plainly when the feature is switched off', async () => {
    const { fetchMock } = installFetch();
    serveRoutes(fetchMock, {
      'GET /v1/value': () => errorResponse(404, 'feature_disabled', 'This feature is not available'),
      'GET /v1/leagues': leagues,
    });
    await render(<ValueScreen />);

    expect(await screen.findByText(FEATURE_UNAVAILABLE)).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
    expectNoBannedWords();
  });
});

describe('ValueEntry', () => {
  it('opens the value screen from Tools and from Games without banned wording', async () => {
    await render(
      <>
        <ValueEntry />
        <ValueEntry compact />
      </>,
    );
    await fireEvent.press(screen.getByRole('button', { name: 'Open value screen' }));
    await fireEvent.press(screen.getByRole('link', { name: /^Value screen/ }));
    expect(router.push).toHaveBeenNthCalledWith(1, '/value');
    expect(router.push).toHaveBeenNthCalledWith(2, '/value');
    expectNoBannedWords();
  });
});
