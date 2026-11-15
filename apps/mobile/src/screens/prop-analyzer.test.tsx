import { render, screen, within } from '@testing-library/react-native';

import { GameLogChart } from '@/components/game-log-chart';
import { PropAnalysisView, rangeText, sampleText } from '@/screens/prop-analyzer';
import { now, propAnalysis } from '@/test/fixtures';

describe('prop analyzer text', () => {
  it('states the sample as counts and mentions excluded pushes', () => {
    expect(sampleText(propAnalysis.hit_rate)).toBe('2 of 4 games, 1 push excluded');
    expect(sampleText({ ...propAnalysis.hit_rate, pushes: 0 })).toBe('2 of 4 games');
    expect(sampleText({ ...propAnalysis.hit_rate, pushes: 2 })).toBe('2 of 4 games, 2 pushes excluded');
  });

  it("shows the API's Wilson range, or n/a when there is none", () => {
    expect(rangeText(propAnalysis.hit_rate)).toBe('15% to 85%');
    expect(rangeText({ ...propAnalysis.hit_rate, ci_low: null, ci_high: null })).toBe('n/a');
  });
});

describe('PropAnalysisView', () => {
  it('shows the over rate with its sample and 95% range', async () => {
    await render(<PropAnalysisView data={propAnalysis} now={now} />);

    expect(screen.getByText('Points against the line')).toBeOnTheScreen();
    expect(screen.getByText('Consensus line 22.5')).toBeOnTheScreen();
    expect(screen.getByLabelText('Over rate, 50%, 2 of 4 games, 1 push excluded')).toBeOnTheScreen();
    expect(screen.getByLabelText('95% range, 15% to 85%, Wilson interval. Wider means less evidence.')).toBeOnTheScreen();
    expect(screen.getByLabelText('Average, this view, 23.4')).toBeOnTheScreen();
    expect(screen.getByLabelText('Season average, 21.9, Home 22.6, away 21.1')).toBeOnTheScreen();
  });

  it("shows the API's caveat under its title", async () => {
    await render(<PropAnalysisView data={propAnalysis} now={now} />);

    expect(screen.getByText('A record, not a forecast')).toBeOnTheScreen();
    expect(screen.getByText('Hit rate describes past games only. It is not a probability for the next one.')).toBeOnTheScreen();
  });

  it('labels offers Best, Stale, Suspended and Not offered in words', async () => {
    await render(<PropAnalysisView data={propAnalysis} now={now} />);

    expect(screen.getByLabelText('Over, −105, best price, implied probability 51.2%')).toBeOnTheScreen();
    expect(screen.getByLabelText('Under, −115, implied probability 53.5%')).toBeOnTheScreen();
    expect(screen.getAllByText('Best')).toHaveLength(1);
    expect(screen.getByText('42s ago')).toBeOnTheScreen();
    expect(screen.getByText('Stale, 9 min ago')).toBeOnTheScreen();
    expect(screen.getByLabelText('Line 23.5')).toBeOnTheScreen();
    expect(screen.getByText('Suspended')).toBeOnTheScreen();
    expect(screen.getByText('Market suspended by this book')).toBeOnTheScreen();
    expect(screen.getByText('Not offered by this book')).toBeOnTheScreen();
    // Beacon Bets is open but posts no under; the suspended and unavailable books say so in their own rows.
    expect(screen.getAllByText('Not offered')).toHaveLength(2);
  });

  it('lists the game log most recent first with the result in words', async () => {
    await render(<PropAnalysisView data={propAnalysis} now={now} />);

    expect(screen.getByText('5 games in this view, most recent first')).toBeOnTheScreen();
    const rows = screen.getAllByLabelText(/^Nov \d+, (vs|at) Iron Valley Forge/);
    expect(rows.map((row) => row.props.accessibilityLabel)).toEqual([
      'Nov 10, vs Iron Valley Forge, 28, Over',
      'Nov 8, at Iron Valley Forge, 19, Under',
      'Nov 6, vs Iron Valley Forge, 22.5, Push',
      'Nov 4, at Iron Valley Forge, 25, Over',
      'Nov 2, vs Iron Valley Forge, 17, Under',
    ]);
    expect(within(rows[0]).getByText('▲ Over')).toBeOnTheScreen();
    expect(within(rows[1]).getByText('▽ Under')).toBeOnTheScreen();
  });

  it('says there is nothing to measure when no line is posted', async () => {
    await render(<PropAnalysisView data={{ ...propAnalysis, consensus_line: null }} now={now} />);

    expect(screen.getByText('No line is posted, so there is nothing to measure against.')).toBeOnTheScreen();
    expect(screen.getByText('The game log will chart here once a line is posted.')).toBeOnTheScreen();
    expect(screen.queryByText('Line 22.5')).toBeNull();
  });
});

describe('GameLogChart', () => {
  it('labels every bar Over, Under or Push in text and draws a labelled line', async () => {
    const games = [...propAnalysis.game_log].reverse();
    await render(<GameLogChart games={games} line={22.5} summary="Corwin Ashdown Points: over 22.5 in 2 of 4 games shown" />);

    expect(screen.getByRole('image', { name: 'Corwin Ashdown Points: over 22.5 in 2 of 4 games shown' })).toBeOnTheScreen();
    const hidden = { includeHiddenElements: true };
    expect(screen.getAllByText('Over', hidden)).toHaveLength(2);
    expect(screen.getAllByText('Under', hidden)).toHaveLength(2);
    expect(screen.getAllByText('Push', hidden)).toHaveLength(1);
    expect(screen.getByText('Line 22.5', hidden)).toBeOnTheScreen();
    expect(screen.getByText('28', hidden)).toBeOnTheScreen();
    expect(screen.getAllByText('vIVF', hidden)).toHaveLength(3);
    expect(screen.getAllByText('@IVF', hidden)).toHaveLength(2);
  });
});
