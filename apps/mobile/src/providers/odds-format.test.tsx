import AsyncStorage from '@react-native-async-storage/async-storage';
import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { Pressable, Text } from 'react-native';

import { ODDS_FORMAT_KEY, OddsFormatProvider, useOddsFormat } from '@/providers/odds-format';

function Probe() {
  const { format, setFormat } = useOddsFormat();
  return (
    <Pressable accessibilityRole="button" onPress={() => setFormat('decimal')}>
      <Text>{format}</Text>
    </Pressable>
  );
}

beforeEach(async () => {
  await AsyncStorage.clear();
});

describe('OddsFormatProvider', () => {
  it('defaults to American and saves a new choice on the device', async () => {
    await render(
      <OddsFormatProvider>
        <Probe />
      </OddsFormatProvider>,
    );
    expect(screen.getByText('american')).toBeOnTheScreen();

    await fireEvent.press(screen.getByRole('button'));
    expect(screen.getByText('decimal')).toBeOnTheScreen();
    await waitFor(async () => expect(await AsyncStorage.getItem(ODDS_FORMAT_KEY)).toBe('decimal'));
  });

  it('restores the saved choice and ignores values it does not recognise', async () => {
    await AsyncStorage.setItem(ODDS_FORMAT_KEY, 'decimal');
    const first = await render(
      <OddsFormatProvider>
        <Probe />
      </OddsFormatProvider>,
    );
    await waitFor(() => expect(screen.getByText('decimal')).toBeOnTheScreen());
    await first.unmount();

    await AsyncStorage.setItem(ODDS_FORMAT_KEY, 'fractional');
    await render(
      <OddsFormatProvider>
        <Probe />
      </OddsFormatProvider>,
    );
    await waitFor(async () => expect(await AsyncStorage.getItem(ODDS_FORMAT_KEY)).toBe('fractional'));
    expect(screen.getByText('american')).toBeOnTheScreen();
  });
});
