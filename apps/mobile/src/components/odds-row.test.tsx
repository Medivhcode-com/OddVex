import { render, screen } from '@testing-library/react-native';

import { ConsensusRow, OddsRow, lineText } from '@/components/odds-row';
import { columns, moneyline, now, openBook, outcome, price, staleBook, suspendedBook, unavailableBook } from '@/test/fixtures';

describe('OddsRow', () => {
  it('labels the best price with the word "Best" and shows freshness and hold', async () => {
    await render(<OddsRow book={openBook} market="moneyline" columns={columns} hold={0.042} now={now} />);

    expect(screen.getByText('Northstar Sports')).toBeOnTheScreen();
    expect(screen.getByText('+118')).toBeOnTheScreen();
    expect(screen.getByText('−140')).toBeOnTheScreen();
    expect(screen.getAllByText('Best')).toHaveLength(1);
    expect(screen.getByLabelText('Iron Valley Forge, +118, best price, implied probability 45.9%')).toBeOnTheScreen();
    expect(screen.getByLabelText('Harbor City Gulls, −140, implied probability 58.3%')).toBeOnTheScreen();
    expect(screen.getByText('58.3%')).toBeOnTheScreen();
    expect(screen.getByText('42s ago')).toBeOnTheScreen();
    expect(screen.queryByText(/Stale/)).toBeNull();
    expect(screen.getByText('4.2%')).toBeOnTheScreen();
  });

  it('spells out a stale book and gives it no "Best" label', async () => {
    await render(<OddsRow book={staleBook} market="moneyline" columns={columns} hold={0.0444} now={now} />);

    expect(screen.getByText('Stale, 9 min ago')).toBeOnTheScreen();
    expect(screen.queryByText('Best')).toBeNull();
    expect(screen.getByText('+125')).toBeOnTheScreen();
  });

  it('spells out a suspended market instead of showing prices', async () => {
    await render(<OddsRow book={suspendedBook} market="moneyline" columns={columns} now={now} />);

    expect(screen.getByText('Suspended')).toBeOnTheScreen();
    expect(screen.getByText('Market suspended by this book')).toBeOnTheScreen();
    expect(screen.queryByText('Best')).toBeNull();
    expect(screen.queryByText(/ago/)).toBeNull();
  });

  it('spells out a market the book does not offer', async () => {
    await render(<OddsRow book={unavailableBook} market="moneyline" columns={columns} now={now} />);

    expect(screen.getByText('Not offered')).toBeOnTheScreen();
    expect(screen.getByText('Not offered by this book')).toBeOnTheScreen();
  });

  it('says "Not offered" for a single outcome an open book is missing', async () => {
    const book = { ...openBook, outcomes: [openBook.outcomes[0]] };
    await render(<OddsRow book={book} market="moneyline" columns={columns} now={now} />);

    expect(screen.getByText('Not offered')).toBeOnTheScreen();
    expect(screen.getByText('+118')).toBeOnTheScreen();
  });

  it('shows the line next to the price for spreads and totals', async () => {
    const spread = {
      ...openBook,
      outcomes: [
        outcome('away', 'Iron Valley Forge', price(-108, 1.93, 0.5192), { line: 3.5 }),
        outcome('home', 'Harbor City Gulls', price(-112, 1.89, 0.5283), { line: -3.5 }),
      ],
    };
    await render(<OddsRow book={spread} market="spread" columns={columns} now={now} />);

    expect(screen.getByText('+3.5')).toBeOnTheScreen();
    expect(screen.getByText('−3.5')).toBeOnTheScreen();
    expect(screen.getByText('−108')).toBeOnTheScreen();
  });
});

describe('lineText', () => {
  it('signs spreads and prefixes totals', () => {
    expect(lineText('spread', { key: 'home', line: -3.5 })).toBe('−3.5');
    expect(lineText('total', { key: 'over', line: 44.5 })).toBe('O 44.5');
    expect(lineText('total', { key: 'under', line: 44.5 })).toBe('U 44.5');
    expect(lineText('moneyline', { key: 'home', line: null })).toBeNull();
  });
});

describe('ConsensusRow', () => {
  it('shows the no-vig probability per outcome and the number of books used', async () => {
    await render(<ConsensusRow outcomes={moneyline.consensus.outcomes} booksUsed={moneyline.consensus.books_used} />);

    expect(screen.getByText('No-vig consensus')).toBeOnTheScreen();
    expect(screen.getByText('1 book')).toBeOnTheScreen();
    expect(screen.getByText('44.0%')).toBeOnTheScreen();
    expect(screen.getByText('56.0%')).toBeOnTheScreen();
  });
});
