import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';

import { setAuthToken } from '@/api/client';
import { BetCard, betTitle, editPayload, legSettlePayload, settlePayload } from '@/components/bet-card';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { lostSyncedBet, openBet, parlayBet, wonBet } from '@/test/fixtures';

beforeEach(() => setAuthToken('token-1'));
afterEach(() => setAuthToken(null));

describe('payload builders', () => {
  it('settles with a single result, and needs an amount to cash out', () => {
    expect(settlePayload('lost', '')).toEqual({ body: { result: 'lost' } });
    expect(settlePayload('cashout', '')).toEqual({ error: 'Enter the cash-out amount you received.' });
    expect(settlePayload('cashout', '-5')).toEqual({ error: 'Enter the cash-out amount you received.' });
    expect(settlePayload('cashout', '18.50')).toEqual({ body: { result: 'cashout', cashout_amount: 18.5 } });
    expect(settlePayload('cashout', '0')).toEqual({ body: { result: 'cashout', cashout_amount: 0 } });
  });

  it('settles a parlay with one result per leg', () => {
    expect(legSettlePayload(parlayBet, { leg_a: 'won', leg_b: 'push' })).toEqual({
      leg_results: [
        { leg_id: 'leg_a', result: 'won' },
        { leg_id: 'leg_b', result: 'push' },
      ],
    });
  });

  it('edits stake and sportsbook only while the bet is open, and closing odds only on a single leg', () => {
    const draft = { stake: '40', sportsbook: ' Cedar Book ', notes: ' Took the early number ', closing: '−120' };
    expect(editPayload(openBet, draft)).toEqual({
      body: {
        notes: 'Took the early number',
        stake: 40,
        sportsbook: 'Cedar Book',
        closing_odds: [{ leg_id: 'leg_1', closing_odds: '-120', odds_format: 'american' }],
      },
    });
    expect(editPayload(wonBet, { ...draft, notes: '', closing: '' })).toEqual({ body: { notes: null } });
    expect(editPayload(parlayBet, draft)).toEqual({ body: { notes: 'Took the early number', stake: 40, sportsbook: 'Cedar Book' } });
    expect(editPayload(openBet, { ...draft, stake: '0' })).toEqual({ error: 'Enter a stake greater than zero.' });
    expect(editPayload(openBet, { ...draft, sportsbook: '' })).toEqual({ error: 'Enter the sportsbook.' });
  });

  it('names a bet by its pick or its leg count', () => {
    expect(betTitle(openBet)).toBe('Harbor City Gulls ML');
    expect(betTitle(parlayBet)).toBe('2-leg parlay');
    expect(betTitle({ ...parlayBet, bet_type: 'sgp' })).toBe('2-leg same-game parlay');
  });
});

describe('BetCard', () => {
  it('shows an open bet with its numbers and status in words', async () => {
    await render(<BetCard bet={{ ...openBet, legs: [{ ...openBet.legs[0], gradeable: true }] }} leagueName="NFL" onChanged={() => {}} />);

    expect(screen.getByText('Harbor City Gulls ML')).toBeOnTheScreen();
    expect(screen.getByText(/^Forge at Gulls, NFL, Northstar Sports, Nov 1\d$/)).toBeOnTheScreen();
    expect(screen.getByText('−110')).toBeOnTheScreen();
    expect(screen.getByText('$25.00')).toBeOnTheScreen();
    expect(screen.getByText('To return')).toBeOnTheScreen();
    expect(screen.getByText('$47.73')).toBeOnTheScreen();
    expect(screen.getByText('Open')).toBeOnTheScreen();
    expect(screen.getByText('Tied to a game')).toBeOnTheScreen();
    expect(screen.queryByText('Synced')).toBeNull();
  });

  it('shows a settled win with signed profit, CLV and how it was settled', async () => {
    await render(<BetCard bet={wonBet} onChanged={() => {}} />);

    expect(screen.getByText('Won')).toBeOnTheScreen();
    expect(screen.getByText('+$22.73')).toBeOnTheScreen();
    expect(screen.getByText('+1.3%')).toBeOnTheScreen();
    expect(screen.getByText('Settled from final score')).toBeOnTheScreen();
    expect(screen.queryByText('Tied to a game')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Settle Harbor City Gulls ML' })).toBeNull();
  });

  it('shows a synced loss with a true minus sign', async () => {
    await render(<BetCard bet={lostSyncedBet} onChanged={() => {}} />);

    expect(screen.getByText('Lost')).toBeOnTheScreen();
    expect(screen.getByText('−$25.00')).toBeOnTheScreen();
    expect(screen.getByText('Synced')).toBeOnTheScreen();
  });

  it('settles a bet as lost', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ ...openBet, status: 'settled', result: 'lost' }));
    const onChanged = jest.fn();
    await render(<BetCard bet={openBet} onChanged={onChanged} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Settle Harbor City Gulls ML' }));
    await fireEvent.press(screen.getByRole('radio', { name: 'Result: Lost' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Settle bet' }));

    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(sent()[0]).toMatchObject({ method: 'POST', path: '/v1/bets/bet_1/settle', body: { result: 'lost' } });
    expect(sent()[0].headers.authorization).toBe('Bearer token-1');
  });

  it('asks for the amount before cashing out, then sends it', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(openBet));
    const onChanged = jest.fn();
    await render(<BetCard bet={openBet} onChanged={onChanged} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Settle Harbor City Gulls ML' }));
    await fireEvent.press(screen.getByRole('radio', { name: 'Result: Cashed out' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Settle bet' }));
    expect(screen.getByText('Enter the cash-out amount you received.')).toBeOnTheScreen();
    expect(fetchMock).not.toHaveBeenCalled();

    await fireEvent.changeText(screen.getByLabelText('Cash-out amount ($)'), '18.50');
    await fireEvent.press(screen.getByRole('button', { name: 'Settle bet' }));

    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(sent()[0].body).toEqual({ result: 'cashout', cashout_amount: 18.5 });
  });

  it('settles a parlay leg by leg', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(parlayBet));
    const onChanged = jest.fn();
    await render(<BetCard bet={parlayBet} onChanged={onChanged} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Settle 2-leg parlay' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Settle by leg' }));
    expect(screen.getByText('One lost leg loses the parlay. Pushed and void legs drop out and the odds are recalculated.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('radio', { name: 'Iron Valley Forge +3.5: Push' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Settle parlay' }));

    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(sent()[0]).toMatchObject({
      path: '/v1/bets/bet_2/settle',
      body: {
        leg_results: [
          { leg_id: 'leg_a', result: 'won' },
          { leg_id: 'leg_b', result: 'push' },
        ],
      },
    });
  });

  it('edits an open bet with PATCH', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse(openBet));
    const onChanged = jest.fn();
    await render(<BetCard bet={openBet} onChanged={onChanged} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Edit Harbor City Gulls ML' }));
    await fireEvent.changeText(screen.getByLabelText('Stake ($)'), '40');
    await fireEvent.changeText(screen.getByLabelText('Closing odds (American)'), '-120');
    await fireEvent.changeText(screen.getByLabelText('Notes'), 'Early number');
    await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(sent()[0]).toMatchObject({
      method: 'PATCH',
      path: '/v1/bets/bet_1',
      body: {
        stake: 40,
        sportsbook: 'Northstar Sports',
        notes: 'Early number',
        closing_odds: [{ leg_id: 'leg_1', closing_odds: '-120', odds_format: 'american' }],
      },
    });
  });

  it('deletes only after confirmation', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue({ ok: true, status: 204, json: async () => null });
    const onChanged = jest.fn();
    await render(<BetCard bet={openBet} onChanged={onChanged} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Delete Harbor City Gulls ML' }));
    expect(screen.getByText('Delete this bet for good?')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Keep' }));
    expect(fetchMock).not.toHaveBeenCalled();

    await fireEvent.press(screen.getByRole('button', { name: 'Delete Harbor City Gulls ML' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Delete bet' }));

    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(sent()[0]).toMatchObject({ method: 'DELETE', path: '/v1/bets/bet_1' });
  });

  it("keeps the form open and shows the API's message when a change fails", async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(409, 'already_settled', 'This bet is already settled.'));
    const onChanged = jest.fn();
    await render(<BetCard bet={openBet} onChanged={onChanged} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Settle Harbor City Gulls ML' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Settle bet' }));

    expect(await screen.findByText('This bet is already settled.')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Settle bet' })).toBeOnTheScreen();
    expect(onChanged).not.toHaveBeenCalled();
  });
});
