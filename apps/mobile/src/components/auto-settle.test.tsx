import { fireEvent, render, screen } from '@testing-library/react-native';

import { setAuthToken } from '@/api/client';
import type { AutoSettle } from '@/api/types';
import { AutoSettleButton, autoSettleMessage } from '@/components/auto-settle';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { wonBet } from '@/test/fixtures';

const skip = (bet_id: string, reason: AutoSettle['skipped'][number]['reason']) => ({ bet_id, reason });

describe('autoSettleMessage', () => {
  it('counts what was settled, with the right plural', () => {
    expect(autoSettleMessage({ checked: 1, has_more: false, settled: [wonBet], skipped: [] })).toBe('1 bet settled from final scores.');
    expect(autoSettleMessage({ checked: 0, has_more: false, settled: [], skipped: [] })).toBe('0 bets settled from final scores.');
  });

  it('says why the rest were left open, grouped by reason', () => {
    const out: AutoSettle = {
      checked: 6,
      has_more: false,
      settled: [wonBet, wonBet],
      skipped: [
        skip('a', 'event_not_final'),
        skip('b', 'not_gradeable'),
        skip('c', 'event_not_final'),
        skip('d', 'event_unavailable'),
        skip('e', 'manual_result_required'),
      ],
    };
    expect(autoSettleMessage(out)).toBe(
      '2 bets settled from final scores. Left open: 2 game not finished, 1 not tied to a game and side, 1 game no longer available, 1 manual_result_required.',
    );
  });
});

describe('AutoSettleButton', () => {
  beforeEach(() => setAuthToken('token-1'));
  afterEach(() => setAuthToken(null));

  it('asks the API to settle and reports the outcome', async () => {
    const { fetchMock, sent } = installFetch();
    fetchMock.mockResolvedValue(jsonResponse({ checked: 2, settled: [wonBet], skipped: [skip('x', 'event_not_final')] }));
    const onSettled = jest.fn();
    await render(<AutoSettleButton onSettled={onSettled} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Settle from final scores' }));

    expect(await screen.findByText('1 bet settled from final scores. Left open: 1 game not finished.')).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({ method: 'POST', path: '/v1/bets/auto-settle', body: {} });
    expect(onSettled).toHaveBeenCalledTimes(1);
  });

  it('announces a failure and settles nothing', async () => {
    const { fetchMock } = installFetch();
    fetchMock.mockResolvedValue(errorResponse(503, 'unavailable', 'Scores are unavailable right now.'));
    const onSettled = jest.fn();
    await render(<AutoSettleButton onSettled={onSettled} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Settle from final scores' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Scores are unavailable right now.');
    expect(onSettled).not.toHaveBeenCalled();
  });
});
