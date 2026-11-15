import { fireEvent, render, screen } from '@testing-library/react-native';

import type { ParlayResult } from '@/api/types';
import { legOptions, ParlayBuilder, ParlayResultView, parlayPayload } from '@/components/parlay-builder';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { liveEvent, price } from '@/test/fixtures';

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
  probability_note: 'Combined probability multiplies the no-vig probabilities and assumes the legs are independent.',
  correlation_warnings: [],
  steps: ['2.18 x 1.74 = 3.7931'],
};

const correlated: ParlayResult = {
  ...result,
  combined_probability: null,
  correlation_warnings: ['Two legs come from the same game (IVF at HCG). Their outcomes are linked.'],
  probability_note: 'No combined probability is shown because the legs are correlated.',
};

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
  it('shows combined odds, payout, break-even and the combined probability', async () => {
    await render(<ParlayResultView result={result} />);

    expect(screen.getByLabelText('Combined odds, +279, 2 legs')).toBeOnTheScreen();
    expect(screen.getByLabelText('Payout, $37.93, $27.93 profit on $10.00')).toBeOnTheScreen();
    expect(screen.getByLabelText('Break-even, 26.36%, How often it must win')).toBeOnTheScreen();
    expect(screen.getByLabelText('Combined probability, 25.34%')).toBeOnTheScreen();
    expect(screen.getByText(result.probability_note)).toBeOnTheScreen();
    expect(screen.queryByText('These legs are correlated')).toBeNull();
  });

  it('warns about correlated legs and shows no combined probability', async () => {
    await render(<ParlayResultView result={correlated} />);

    expect(screen.getByLabelText('Combined probability, Not shown')).toBeOnTheScreen();
    expect(screen.getByText('These legs are correlated')).toBeOnTheScreen();
    expect(screen.getByText('Two legs come from the same game (IVF at HCG). Their outcomes are linked.')).toBeOnTheScreen();
    expect(screen.getByText('No combined probability is shown because the legs are correlated.')).toBeOnTheScreen();
    expect(screen.queryByText(/25\.34%/)).toBeNull();
  });

  it('says n/a for the payout when no stake was sent', async () => {
    await render(<ParlayResultView result={{ ...result, stake: null, payout: null, profit: null }} />);

    expect(screen.getByLabelText('Payout, n/a')).toBeOnTheScreen();
  });
});

describe('ParlayBuilder', () => {
  it('builds a parlay from the board and a custom leg, then shows the API result', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(correlated));
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

    expect(await screen.findByLabelText('Combined probability, Not shown')).toBeOnTheScreen();
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
