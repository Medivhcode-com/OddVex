import { fireEvent, render, screen } from '@testing-library/react-native';

import type { EventSummary } from '@/api/types';
import { GameCard } from '@/components/game-card';
import { liveEvent } from '@/test/fixtures';

describe('GameCard', () => {
  it('shows status in words, teams, score and the best moneyline with its sportsbook', async () => {
    await render(<GameCard event={liveEvent} leagueName="NFL" />);

    expect(screen.getByText('Live, Q3 4:12')).toBeOnTheScreen();
    expect(screen.getByText('NFL')).toBeOnTheScreen();
    expect(screen.getByText('Iron Valley Forge')).toBeOnTheScreen();
    expect(screen.getByText('Harbor City Gulls')).toBeOnTheScreen();
    expect(screen.getByText('14')).toBeOnTheScreen();
    expect(screen.getByText('17')).toBeOnTheScreen();
    expect(screen.getByText('+118')).toBeOnTheScreen();
    expect(screen.getByText('Cedar Book')).toBeOnTheScreen();
    expect(screen.getByText('−135')).toBeOnTheScreen();
    expect(screen.getByText('Northstar Sports')).toBeOnTheScreen();
    expect(screen.getByText('Best moneyline')).toBeOnTheScreen();
  });

  it('is one button with a full spoken label and responds to a press', async () => {
    const onPress = jest.fn();
    await render(<GameCard event={liveEvent} leagueName="NFL" onPress={onPress} />);

    const card = screen.getByRole('button');
    expect(card.props.accessibilityLabel).toBe(
      'Iron Valley Forge at Harbor City Gulls. NFL. Live, Q3 4:12. ' +
        'Iron Valley Forge, 14, best moneyline +118 at Cedar Book. ' +
        'Harbor City Gulls, 17, best moneyline −135 at Northstar Sports',
    );
    await fireEvent.press(card);
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('says "No price" for a side nobody is pricing', async () => {
    const event: EventSummary = {
      ...liveEvent,
      status: 'upcoming',
      status_detail: null,
      score: null,
      best_moneyline: { home: liveEvent.best_moneyline?.home, away: null },
    };
    await render(<GameCard event={event} leagueName="NFL" />);

    expect(screen.getByText(/^Starts /)).toBeOnTheScreen();
    expect(screen.getByText('No price')).toBeOnTheScreen();
    expect(screen.getByText('−135')).toBeOnTheScreen();
  });

  it('adds the draw price for three-way markets', async () => {
    const event: EventSummary = {
      ...liveEvent,
      league: 'soccer',
      best_moneyline: {
        ...liveEvent.best_moneyline,
        draw: { price: { american: 240, decimal: 3.4, fractional: '12/5', implied_probability: 0.2941 }, sportsbook: { key: 'book_b', name: 'Beacon Bets' } },
      },
    };
    await render(<GameCard event={event} leagueName="Soccer" />);

    expect(screen.getByText('Draw')).toBeOnTheScreen();
    expect(screen.getByText('+240')).toBeOnTheScreen();
    expect(screen.getByText('Beacon Bets')).toBeOnTheScreen();
    expect(screen.getByRole('button').props.accessibilityLabel).toContain('Draw, best moneyline +240 at Beacon Bets');
  });

  it('shows a final game with its score and no prices', async () => {
    const event: EventSummary = { ...liveEvent, status: 'final', status_detail: null, score: { home: 24, away: 20 } };
    await render(<GameCard event={event} leagueName="NFL" />);

    expect(screen.getByText('Final')).toBeOnTheScreen();
    expect(screen.getByText('24')).toBeOnTheScreen();
    expect(screen.getByText('20')).toBeOnTheScreen();
    expect(screen.queryByText('Best moneyline')).toBeNull();
    expect(screen.queryByText('−135')).toBeNull();
  });
});
