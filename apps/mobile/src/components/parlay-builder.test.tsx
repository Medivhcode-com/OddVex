import { fireEvent, render, screen } from '@testing-library/react-native';

import type { ParlayResult } from '@/api/types';
import { legOptions, PARLAY_PROBABILITY_SENTENCES, ParlayBuilder, ParlayResultView, parlayPayload } from '@/components/parlay-builder';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { liveEvent, price } from '@/test/fixtures';

// What the API sends, word for word (services/api quant/parlay.py and quant_routes.py). This screen never sends
// a leg probability, so `computed` only appears here to show how it would be presented.
const result: ParlayResult = {
  legs: [],
  active_legs: 2,
  dropped_legs: 0,
  combined_decimal: 3.7931,
  combined_price: price(279, 3.7931, 0.263636),
  stake: 10,
  payout: 37.93,
  profit: 27.93,
  combined_probability: 0.2534,
  probability_status: 'computed',
  probability_note: 'assumes independence: the legs are from distinct events and their win probabilities were multiplied',
  correlation_warnings: [],
  steps: [
    'Iron Valley Forge ML: decimal 2.1800',
    'Cedar Bay ML: decimal 1.7400',
    'Combined decimal = 2.1800 x 1.7400 = 3.7932',
    'Payout = 10.00 x 3.7932 = 37.93 (profit +27.93)',
    'Combined probability = 0.4800 x 0.5280 = 25.34% (assumes independence)',
  ],
};

/** Two moneylines from different games, as the board sends them: no leg probabilities. */
const differentGames: ParlayResult = {
  ...result,
  combined_probability: null,
  probability_status: 'needs_leg_probabilities',
  probability_note: 'not computed: a win probability is required for every leg',
  steps: result.steps.slice(0, 4),
};

const sameGame: ParlayResult = {
  ...differentGames,
  probability_status: 'same_event_legs',
  probability_note: 'not computed: legs may be correlated',
  correlation_warnings: ['2 legs are from the same event (evt_1); their outcomes are correlated, so leg probabilities cannot be multiplied'],
};

/** A board leg and a custom leg: the custom leg has no event, so independence cannot be checked. */
const withCustomLeg: ParlayResult = {
  ...differentGames,
  probability_status: 'unverified_legs',
  probability_note: 'not computed: legs may be correlated',
  correlation_warnings: ['1 leg(s) have no event_id, so independence between legs cannot be verified'],
};

const noActiveLegs: ParlayResult = {
  ...differentGames,
  active_legs: 0,
  probability_status: 'no_active_legs',
  probability_note: 'no active legs remain',
};

const API_NOTES = /not computed|win probability is required|assumes independence:|no active legs remain|event_id/;

describe('legOptions', () => {
  it('offers the best moneyline on each side of games that are not over', () => {
    const options = legOptions([liveEvent, { ...liveEvent, id: 'evt_done', status: 'final' }]);
    expect(options.map((option) => [option.id, option.label, option.eventLabel, option.book, option.price.american])).toEqual([
      ['evt_1:away', 'Iron Valley Forge ML', 'IVF at HCG', 'Cedar Book', 118],
      ['evt_1:home', 'Harbor City Gulls ML', 'IVF at HCG', 'Northstar Sports', -135],
    ]);
  });
});

describe('parlayPayload', () => {
  it('sends each leg with its game and leaves the stake out when it is not a positive number', () => {
    const legs = [
      { key: 'a', label: 'Gulls ML', odds: '-135', eventId: 'evt_1', detail: '' },
      { key: 'b', label: 'Custom', odds: '+120', eventId: null, detail: '' },
    ];
    expect(parlayPayload(legs, '10')).toEqual({
      stake: 10,
      legs: [
        { odds: '-135', odds_format: 'american', label: 'Gulls ML', event_id: 'evt_1' },
        { odds: '+120', odds_format: 'american', label: 'Custom', event_id: null },
      ],
    });
    expect(parlayPayload(legs, '')).toMatchObject({ stake: null });
  });
});

describe('ParlayResultView', () => {
  it('shows combined odds, payout, break-even and, when the API computed one, the probability marked as assuming independence', async () => {
    await render(<ParlayResultView result={result} />);

    expect(screen.getByLabelText('Combined odds, +279, 2 legs')).toBeOnTheScreen();
    expect(screen.getByLabelText('Payout, $37.93, $27.93 profit on $10.00')).toBeOnTheScreen();
    expect(screen.getByLabelText('Break-even, 26.36%, How often it must win')).toBeOnTheScreen();
    expect(screen.getByLabelText('Combined probability, 25.34%, Assumes the legs are independent')).toBeOnTheScreen();
    expect(screen.queryByText(result.probability_note)).toBeNull();
    expect(screen.queryByText('These legs are correlated')).toBeNull();
  });

  it('shows no probability stat and no instruction for legs from different games without leg probabilities', async () => {
    await render(<ParlayResultView result={differentGames} />);

    expect(screen.getByLabelText('Combined odds, +279, 2 legs')).toBeOnTheScreen();
    expect(screen.getByLabelText('Break-even, 26.36%, How often it must win')).toBeOnTheScreen();
    expect(screen.queryByText('Combined probability')).toBeNull();
    expect(screen.queryByText('Not shown')).toBeNull();
    expect(screen.queryByText(API_NOTES)).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('says in one plain sentence that legs from the same game are linked', async () => {
    await render(<ParlayResultView result={sameGame} />);

    expect(screen.getByText('These legs are correlated')).toBeOnTheScreen();
    expect(screen.getByText(PARLAY_PROBABILITY_SENTENCES.same_event_legs)).toBeOnTheScreen();
    expect(screen.queryByText('Combined probability')).toBeNull();
    expect(screen.queryByText(API_NOTES)).toBeNull();
    expect(screen.queryByText(/25\.34%/)).toBeNull();
  });

  it('says a custom leg cannot be checked for independence, without calling the legs correlated', async () => {
    await render(<ParlayResultView result={withCustomLeg} />);

    expect(screen.getByText(PARLAY_PROBABILITY_SENTENCES.unverified_legs)).toBeOnTheScreen();
    expect(screen.queryByText('These legs are correlated')).toBeNull();
    expect(screen.queryByText('Combined probability')).toBeNull();
    expect(screen.queryByText(API_NOTES)).toBeNull();
  });

  it('says when every leg pushed or was voided', async () => {
    await render(<ParlayResultView result={noActiveLegs} />);

    expect(screen.getByText(PARLAY_PROBABILITY_SENTENCES.no_active_legs)).toBeOnTheScreen();
    expect(screen.queryByText(API_NOTES)).toBeNull();
  });

  it('words each reason plainly, with no request for input the form cannot take', () => {
    for (const sentence of Object.values(PARLAY_PROBABILITY_SENTENCES)) {
      expect(sentence).not.toMatch(/required|enter|provide|add a/i);
      expect(sentence).toMatch(/\.$/);
    }
  });

  it('says n/a for the payout when no stake was sent', async () => {
    await render(<ParlayResultView result={{ ...result, stake: null, payout: null, profit: null }} />);

    expect(screen.getByLabelText('Payout, n/a')).toBeOnTheScreen();
  });
});

describe('ParlayBuilder', () => {
  it('builds a parlay from the board and a custom leg, then shows the API result', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(withCustomLeg));
    await render(<ParlayBuilder options={legOptions([liveEvent])} />);

    expect(screen.getByText('No legs yet. Add two or more to see the combined price.')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Calculate parlay' })).toBeDisabled();

    await fireEvent.press(screen.getByRole('button', { name: 'Add a moneyline from the board' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Add Iron Valley Forge ML +118, IVF at HCG' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Add Harbor City Gulls ML −135, IVF at HCG' }));
    await fireEvent.changeText(screen.getByLabelText('Custom leg'), 'Ashdown over 22.5 points');
    await fireEvent.changeText(screen.getByLabelText('American odds'), '−115');
    await fireEvent.press(screen.getByRole('button', { name: 'Add custom leg' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Remove Harbor City Gulls ML' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Calculate parlay' }));

    expect(await screen.findByText(PARLAY_PROBABILITY_SENTENCES.unverified_legs)).toBeOnTheScreen();
    expect(screen.queryByText(API_NOTES)).toBeNull();
    expect(sent()[0]).toMatchObject({
      method: 'POST',
      path: '/v1/quant/parlay',
      body: {
        stake: 10,
        legs: [
          { odds: '118', odds_format: 'american', label: 'Iron Valley Forge ML', event_id: 'evt_1' },
          { odds: '-115', odds_format: 'american', label: 'Ashdown over 22.5 points', event_id: null },
        ],
      },
    });
  });

  it('asks for both parts of a custom leg', async () => {
    installFetch();
    await render(<ParlayBuilder options={[]} />);

    await fireEvent.changeText(screen.getByLabelText('Custom leg'), 'Half a leg');
    await fireEvent.press(screen.getByRole('button', { name: 'Add custom leg' }));

    expect(screen.getByRole('alert')).toHaveTextContent('A custom leg needs a name and American odds.');
  });

  it("shows the API's message when the parlay cannot be calculated", async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(422, 'invalid_odds', 'Could not read "abc" as American odds.'));
    await render(<ParlayBuilder options={[]} />);

    for (const [label, odds] of [
      ['Leg one', '+120'],
      ['Leg two', 'abc'],
    ]) {
      await fireEvent.changeText(screen.getByLabelText('Custom leg'), label);
      await fireEvent.changeText(screen.getByLabelText('American odds'), odds);
      await fireEvent.press(screen.getByRole('button', { name: 'Add custom leg' }));
    }
    await fireEvent.press(screen.getByRole('button', { name: 'Calculate parlay' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not read "abc" as American odds.');
    expect(screen.getByText('The combined price and payout appear here.')).toBeOnTheScreen();
  });
});
