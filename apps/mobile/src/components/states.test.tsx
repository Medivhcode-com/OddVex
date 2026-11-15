import { fireEvent, render, screen } from '@testing-library/react-native';

import { ApiError, ApiUnavailableError } from '@/api/client';
import { ErrorState } from '@/components/states';

describe('ErrorState', () => {
  it('says the data service cannot be reached and offers a retry', async () => {
    const onRetry = jest.fn();
    await render(<ErrorState error={new ApiUnavailableError()} onRetry={onRetry} />);

    expect(screen.getByText("OddVex can't reach its data service")).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("shows the API's own message when it answered with an error", async () => {
    await render(<ErrorState error={new ApiError(500, 'internal', 'The odds provider is unavailable.')} onRetry={() => {}} />);

    expect(screen.getByText('This screen failed to load')).toBeOnTheScreen();
    expect(screen.getByText('The odds provider is unavailable.')).toBeOnTheScreen();
  });
});
