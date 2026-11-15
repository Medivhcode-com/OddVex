import { fireEvent, render, screen } from '@testing-library/react-native';

import { setAuthToken } from '@/api/client';
import type { OddsComparison } from '@/api/types';
import { QuickBet, quickBetOptions, quickBetPayload } from '@/components/quick-bet';
import { installFetch, jsonResponse } from '@/test/api';
import { liveEvent, moneyline, openBet, price } from '@/test/fixtures';

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
});
