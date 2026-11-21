import { act, fireEvent, render, screen } from '@testing-library/react-native';

import { BET_SAVE_UNCONFIRMED, setAuthToken } from '@/api/client';
import type { OddsComparison } from '@/api/types';
import { QuickBet, quickBetOptions, quickBetPayload } from '@/components/quick-bet';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { liveEvent, moneyline, openBet, price } from '@/test/fixtures';
import { onPressOf } from '@/test/press';
import { CLIENT_REQUEST_ID } from '@/utils/request-id';

const spread: OddsComparison = {
  ...moneyline,
  market: 'spread',
  best: [
    { outcome_key: 'home', sportsbook_key: 'book_a', price: price(-108, 1.93, 0.5192), line: -3.5 },
    { outcome_key: 'away', sportsbook_key: 'book_zz', price: price(-102, 1.98, 0.505), line: 3.5 },
    { outcome_key: 'first_scorer', sportsbook_key: 'book_a', price: price(400, 5, 0.2) },
  ],
};

describe('quickBetOptions', () => {
  it('offers each best price with its side, book and "ML" on a moneyline', () => {
    expect(quickBetOptions(moneyline)).toEqual([
      { outcomeKey: 'away', label: 'Iron Valley Forge ML', line: null, american: 118, sportsbook: 'Northstar Sports' },
    ]);
  });

  it('carries the signed line on a spread and skips outcomes the tracker cannot grade', () => {
    expect(quickBetOptions(spread)).toEqual([
      { outcomeKey: 'home', label: 'Harbor City Gulls −3.5', line: -3.5, american: -108, sportsbook: 'Northstar Sports' },
      { outcomeKey: 'away', label: 'Iron Valley Forge +3.5', line: 3.5, american: -102, sportsbook: 'book_zz' },
    ]);
  });
});

describe('quickBetPayload', () => {
  it('ties the leg to the game, market, side, line, price and sportsbook', () => {
    expect(quickBetPayload(liveEvent, 'spread', quickBetOptions(spread)[0], 20)).toEqual({
      bet_type: 'straight',
      stake: 20,
      sportsbook: 'Northstar Sports',
      legs: [
        {
          selection: 'Harbor City Gulls −3.5',
          market: 'spread',
          league: 'nfl',
          event_id: 'evt_1',
          event_label: 'Iron Valley Forge at Harbor City Gulls',
          outcome_key: 'home',
          line: -3.5,
          odds: '-108',
          odds_format: 'american',
        },
      ],
    });
  });
});

describe('QuickBet', () => {
  beforeEach(() => setAuthToken('token-1'));
  afterEach(() => setAuthToken(null));

  it('needs a stake before it saves', async () => {
    const { fetchMock } = installFetch();
    await render(<QuickBet event={liveEvent} market="moneyline" options={quickBetOptions(moneyline)} onSaved={() => {}} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Add to tracker' }));

    expect(screen.getByText('Enter a stake greater than zero.')).toBeOnTheScreen();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('logs the chosen side at the best price and says the tracker can settle it', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(openBet, 201));
    const onSaved = jest.fn();
    await render(<QuickBet event={liveEvent} market="spread" options={quickBetOptions(spread)} onSaved={onSaved} />);

    expect(screen.getByRole('radio', { name: 'Side, at the best current price: Harbor City Gulls −3.5 −108 at Northstar Sports' })).toBeChecked();
    await fireEvent.press(screen.getByRole('radio', { name: 'Side, at the best current price: Iron Valley Forge +3.5 −102 at book_zz' }));
    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '15');
    await fireEvent.press(screen.getByRole('button', { name: 'Add to tracker' }));

    expect(
      await screen.findByText('Bet saved. Because it is tied to this game, the tracker can settle it from the final score.'),
    ).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({
      method: 'POST',
      path: '/v1/bets',
      body: {
        bet_type: 'straight',
        stake: 15,
        sportsbook: 'book_zz',
        legs: [{ event_id: 'evt_1', market: 'spread', outcome_key: 'away', line: 3.5, odds: '-102', odds_format: 'american' }],
      },
    });
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Open the tracker' })).toBeOnTheScreen();
  });
  const ids = (sent: () => { body: unknown }[]) => sent().map((request) => (request.body as { client_request_id?: string }).client_request_id);
  const add = () => fireEvent.press(screen.getByRole('button', { name: 'Add to tracker' }));

  it('retries an unanswered save with the same id, points to the tracker, and takes 200 as saved', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockRejectedValueOnce(new TypeError('Network request failed')).mockResolvedValueOnce(jsonResponse(openBet, 200));
    const onSaved = jest.fn();
    await render(<QuickBet event={liveEvent} market="moneyline" options={quickBetOptions(moneyline)} onSaved={onSaved} />);

    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '15');
    await add();
    expect(await screen.findByText(BET_SAVE_UNCONFIRMED)).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Open the tracker' })).toBeOnTheScreen();
    expect(onSaved).not.toHaveBeenCalled();

    await add();
    expect(
      await screen.findByText('Bet saved. Because it is tied to this game, the tracker can settle it from the final score.'),
    ).toBeOnTheScreen();
    const [first, second] = ids(sent);
    expect(first).toMatch(CLIENT_REQUEST_ID);
    expect(second).toBe(first);
    expect(onSaved).toHaveBeenCalledTimes(1);
  });

  it('uses a new id when the side or stake changes after a failure', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockRejectedValueOnce(new TypeError('Network request failed')).mockResolvedValueOnce(jsonResponse(openBet, 201));
    await render(<QuickBet event={liveEvent} market="moneyline" options={quickBetOptions(moneyline)} onSaved={() => {}} />);

    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '15');
    await add();
    await screen.findByText(BET_SAVE_UNCONFIRMED);
    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '20');
    await add();
    await screen.findByText('Bet saved. Because it is tied to this game, the tracker can settle it from the final score.');

    const [first, second] = ids(sent);
    expect(second).toMatch(CLIENT_REQUEST_ID);
    expect(second).not.toBe(first);
  });

  it('keeps the id when only the refreshed best price or its book moved after an unanswered save', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock
      .mockRejectedValueOnce(new TypeError('Network request failed'))
      .mockRejectedValueOnce(new TypeError('Network request failed'))
      .mockResolvedValueOnce(jsonResponse(openBet, 200));
    const options = quickBetOptions(moneyline);
    const view = await render(<QuickBet event={liveEvent} market="moneyline" options={options} onSaved={() => {}} />);

    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '15');
    await add();
    await screen.findByText(BET_SAVE_UNCONFIRMED);
    // A pull to refresh reloads the board: the best price moves. The side and the stake are untouched.
    await view.rerender(
      <QuickBet event={liveEvent} market="moneyline" options={options.map((o) => ({ ...o, american: o.american + 2 }))} onSaved={() => {}} />,
    );
    await add();
    await screen.findByText(BET_SAVE_UNCONFIRMED);
    // Another refresh: the best price is now at another book.
    await view.rerender(
      <QuickBet
        event={liveEvent}
        market="moneyline"
        options={options.map((o) => ({ ...o, american: o.american + 4, sportsbook: 'Cedar Book' }))}
        onSaved={() => {}}
      />,
    );
    await add();
    await screen.findByText('Bet saved. Because it is tied to this game, the tracker can settle it from the final score.');

    const bodies = sent().map((request) => request.body as { sportsbook: string; legs: { odds: string }[] });
    expect(bodies.map((body) => [body.legs[0].odds, body.sportsbook])).toEqual([
      ['118', 'Northstar Sports'],
      ['120', 'Northstar Sports'],
      ['122', 'Cedar Book'],
    ]);
    const [first, second, third] = ids(sent);
    expect(first).toMatch(CLIENT_REQUEST_ID);
    expect(second).toBe(first);
    expect(third).toBe(first);
  });

  it('uses a new id when the side changes after a failure', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockRejectedValueOnce(new TypeError('Network request failed')).mockResolvedValueOnce(jsonResponse(openBet, 201));
    await render(<QuickBet event={liveEvent} market="spread" options={quickBetOptions(spread)} onSaved={() => {}} />);

    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '15');
    await add();
    await screen.findByText(BET_SAVE_UNCONFIRMED);
    await fireEvent.press(screen.getByRole('radio', { name: 'Side, at the best current price: Iron Valley Forge +3.5 −102 at book_zz' }));
    await add();
    await screen.findByText('Bet saved. Because it is tied to this game, the tracker can settle it from the final score.');

    const [first, second] = ids(sent);
    expect(second).toMatch(CLIENT_REQUEST_ID);
    expect(second).not.toBe(first);
  });

  it('sends one id for two presses in the same frame', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(openBet, 201));
    await render(<QuickBet event={liveEvent} market="moneyline" options={quickBetOptions(moneyline)} onSaved={() => {}} />);

    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '15');
    const button = screen.getByRole('button', { name: 'Add to tracker' });
    const press = onPressOf(button);
    await act(async () => {
      // Both presses run before React renders the disabled button.
      press();
      press();
    });
    await screen.findByText('Bet saved. Because it is tied to this game, the tracker can settle it from the final score.');

    const [first, second] = ids(sent);
    expect(first).toMatch(CLIENT_REQUEST_ID);
    expect(second).toBe(first);
  });

  it("shows the API's words for the bet cap and the write limit", async () => {
    const { fetchMock } = installFetch();
    fetchMock
      .mockResolvedValueOnce(errorResponse(409, 'bet_limit_reached', 'An account holds at most 5000 bets. Delete some to add another.'))
      .mockResolvedValueOnce(errorResponse(429, 'rate_limited', 'Too many requests. Try again in 12 seconds.'));
    await render(<QuickBet event={liveEvent} market="moneyline" options={quickBetOptions(moneyline)} onSaved={() => {}} />);

    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '15');
    await add();
    expect(await screen.findByText('An account holds at most 5000 bets. Delete some to add another.')).toBeOnTheScreen();
    await add();
    expect(await screen.findByText('Too many requests. Try again in 12 seconds.')).toBeOnTheScreen();
  });

  it('refuses a stake under one cent', async () => {
    const { fetchMock } = installFetch();
    await render(<QuickBet event={liveEvent} market="moneyline" options={quickBetOptions(moneyline)} onSaved={() => {}} />);

    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '0.001');
    await add();

    expect(screen.getByText('Enter a stake of at least $0.01.')).toBeOnTheScreen();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
