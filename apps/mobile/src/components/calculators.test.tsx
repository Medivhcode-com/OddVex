import { fireEvent, render, screen } from '@testing-library/react-native';

import { ClvCalculator, ConvertCalculator, EvCalculator, NoVigCalculator } from '@/components/calculators';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { price } from '@/test/fixtures';

const steps = ['Implied probability = 110 / (110 + 100) = 0.5238', 'Decimal = 1 + 100 / 110 = 1.9091'];

describe('ConvertCalculator', () => {
  it('sends what was typed to the API and shows every format it returns', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ price: { american: -110, decimal: 1.909091, fractional: '10/11', implied_probability: 0.52381 }, steps }));
    await render(<ConvertCalculator />);

    await fireEvent.changeText(screen.getByLabelText('Odds to convert'), ' −110 ');
    await fireEvent.press(screen.getByRole('button', { name: 'Convert' }));

    expect(await screen.findByLabelText('American, −110')).toBeOnTheScreen();
    expect(screen.getByLabelText('Decimal, 1.909')).toBeOnTheScreen();
    expect(screen.getByLabelText('Fractional, 10/11')).toBeOnTheScreen();
    expect(screen.getByLabelText('Implied probability, 52.38%')).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({ method: 'POST', path: '/v1/quant/convert', body: { odds: '-110', odds_format: 'american' } });
    expect(sent()[0].headers.authorization).toBeUndefined();
  });

  it('keeps the working folded away until asked', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ price: price(-110, 1.909091, 0.52381), steps }));
    await render(<ConvertCalculator />);
    await fireEvent.press(screen.getByRole('button', { name: 'Convert' }));

    const toggle = await screen.findByRole('button', { name: 'Show the working' });
    expect(toggle).toBeCollapsed();
    expect(screen.queryByText(/Implied probability = 110/)).toBeNull();

    await fireEvent.press(toggle);

    expect(screen.getByRole('button', { name: 'Hide the working' })).toBeExpanded();
    expect(screen.getByText(`1. ${steps[0]}`)).toBeOnTheScreen();
    expect(screen.getByText(`2. ${steps[1]}`)).toBeOnTheScreen();
  });

  it("shows the API's validation message and clears the old result", async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValueOnce(jsonResponse({ price: price(-110, 1.909091, 0.52381), steps }));
    await render(<ConvertCalculator />);
    await fireEvent.press(screen.getByRole('button', { name: 'Convert' }));
    await screen.findByLabelText('American, −110');

    fetchMock.mockResolvedValueOnce(errorResponse(422, 'invalid_odds', 'American odds cannot be between -100 and 100.'));
    await fireEvent.changeText(screen.getByLabelText('Odds to convert'), '50');
    await fireEvent.press(screen.getByRole('button', { name: 'Convert' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('American odds cannot be between -100 and 100.');
    expect(screen.queryByLabelText('American, −110')).toBeNull();
  });
});

describe('NoVigCalculator', () => {
  const outcome = (label: string, american: number, implied: number, noVig: number, fair: number) => ({
    label,
    price: price(american, 1.9, implied),
    implied_probability: implied,
    no_vig_probability: noVig,
    fair_price: price(fair, 2, noVig),
  });

  it('sends two sides by default and shows the no-vig result per side', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(
      jsonResponse({
        method: 'multiplicative',
        outcomes: [outcome('Side 1', -120, 0.545455, 0.5109, -104), outcome('Side 2', 100, 0.5, 0.4891, 104)],
        overround: 0.045455,
        hold: 0.043478,
        steps,
      }),
    );
    await render(<NoVigCalculator />);

    await fireEvent.changeText(screen.getByLabelText('Side 1'), '-120');
    await fireEvent.changeText(screen.getByLabelText('Side 2'), '+100');
    await fireEvent.press(screen.getByRole('button', { name: 'Remove the vig' }));

    expect(await screen.findByLabelText('Side 1: price −120, implied 54.55%, no-vig 51.09%, fair price −104')).toBeOnTheScreen();
    expect(screen.getByLabelText('Side 2: price +100, implied 50.00%, no-vig 48.91%, fair price +104')).toBeOnTheScreen();
    expect(screen.getByLabelText('Overround, 4.55%, Implied probabilities minus 100%')).toBeOnTheScreen();
    expect(screen.getByLabelText("Hold, 4.35%, The book's theoretical margin")).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({ path: '/v1/quant/no-vig', body: { odds: ['-120', '+100'], odds_format: 'american' } });
  });

  it('takes an optional third side', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(422, 'invalid_odds', 'Enter odds for every side.'));
    await render(<NoVigCalculator />);

    expect(screen.queryByLabelText('Side 3')).toBeNull();
    await fireEvent.press(screen.getByRole('button', { name: 'Add a third side' }));
    await fireEvent.changeText(screen.getByLabelText('Side 3'), '+240');
    await fireEvent.press(screen.getByRole('button', { name: 'Remove the vig' }));
    await screen.findByText('Enter odds for every side.');

    expect(sent()[0].body).toEqual({ odds: ['-110', '-110', '+240'], odds_format: 'american' });
    await fireEvent.press(screen.getByRole('button', { name: 'Use two sides' }));
    expect(screen.queryByLabelText('Side 3')).toBeNull();
  });
});

describe('EvCalculator', () => {
  const result = {
    price: price(150, 2.5, 0.4),
    win_probability: 0.45,
    ev_percent: 12.5,
    ev_per_unit: 0.125,
    expected_profit: 12.5,
    breakeven_probability: 0.4,
    edge: 0.05,
    stake: 100,
    steps,
    caveat: 'Expected value is only as reliable as the win probability you supply.',
  };

  it('checks the probability on the device before asking the API', async () => {
    const { fetchMock } = installFetch();
    await render(<EvCalculator />);

    await fireEvent.changeText(screen.getByLabelText('Your win probability (%)'), '140');
    await fireEvent.press(screen.getByRole('button', { name: 'Calculate expected value' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Enter a win probability between 0 and 100.');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the API's numbers, signed, with its caveat", async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(result));
    await render(<EvCalculator />);

    await fireEvent.press(screen.getByRole('button', { name: 'Calculate expected value' }));

    expect(await screen.findByLabelText('Expected value, +12.50%, Per dollar staked')).toBeOnTheScreen();
    expect(screen.getByLabelText('Expected profit, +$12.50, On a $100.00 stake')).toBeOnTheScreen();
    expect(screen.getByLabelText('Break-even, 40.00%, Win rate needed at this price')).toBeOnTheScreen();
    expect(screen.getByLabelText('Edge, +5.00%, Your probability minus break-even')).toBeOnTheScreen();
    expect(screen.getByText('Only as good as the probability you entered')).toBeOnTheScreen();
    expect(screen.getByText('Expected value is only as reliable as the win probability you supply.')).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({ path: '/v1/quant/ev', body: { odds: '+150', odds_format: 'american', win_probability: 0.45, stake: 100 } });
  });

  it('shows a negative expected value with a true minus sign', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ ...result, ev_per_unit: -0.0455, expected_profit: -4.55, edge: -0.0238 }));
    await render(<EvCalculator />);

    await fireEvent.press(screen.getByRole('button', { name: 'Calculate expected value' }));

    expect(await screen.findByLabelText('Expected value, −4.55%, Per dollar staked')).toBeOnTheScreen();
    expect(screen.getByLabelText('Expected profit, −$4.55, On a $100.00 stake')).toBeOnTheScreen();
  });
});

describe('ClvCalculator', () => {
  const result = {
    price: price(150, 2.5, 0.4),
    closing_price: price(135, 2.35, 0.4255),
    clv: 0.0638,
    clv_percent: 6.38,
    beat_close: true,
    closing_no_vig_probability: null,
    no_vig_probability_delta: null,
    steps,
  };

  it('sends no other-side price when it is left empty, and says so in the result', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(result));
    await render(<ClvCalculator />);

    await fireEvent.press(screen.getByRole('button', { name: 'Calculate closing line value' }));

    expect(await screen.findByLabelText('Closing line value, +6.38%, You beat the close')).toBeOnTheScreen();
    expect(screen.getByLabelText("Closing no-vig probability, n/a, Needs the other side's closing price")).toBeOnTheScreen();
    expect(screen.getByLabelText('Probability gained, n/a, Closing no-vig minus your break-even')).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({
      path: '/v1/quant/clv',
      body: { odds: '+150', closing_odds: '+135', closing_opposite_odds: null, odds_format: 'american' },
    });
  });

  it('shows a worse-than-close result without softening it', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(
      jsonResponse({ ...result, clv: -0.0426, beat_close: false, closing_no_vig_probability: 0.4183, no_vig_probability_delta: -0.0183 }),
    );
    await render(<ClvCalculator />);

    await fireEvent.changeText(screen.getByLabelText('Closing price, other side'), '−160');
    await fireEvent.press(screen.getByRole('button', { name: 'Calculate closing line value' }));

    expect(await screen.findByLabelText('Closing line value, −4.26%, The close was as good or better')).toBeOnTheScreen();
    expect(screen.getByLabelText("Closing no-vig probability, 41.83%, Needs the other side's closing price")).toBeOnTheScreen();
    expect(screen.getByLabelText('Probability gained, −1.83%, Closing no-vig minus your break-even')).toBeOnTheScreen();
    expect(sent()[0].body).toMatchObject({ closing_opposite_odds: '-160' });
  });

  it("shows the API's validation message", async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(422, 'invalid_odds', 'Could not read "abc" as American odds.'));
    await render(<ClvCalculator />);

    await fireEvent.changeText(screen.getByLabelText('Closing price'), 'abc');
    await fireEvent.press(screen.getByRole('button', { name: 'Calculate closing line value' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not read "abc" as American odds.');
  });
});
