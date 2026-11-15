import {
  cleanOdds,
  formatAge,
  formatAmerican,
  formatDay,
  formatDecimal,
  formatLine,
  formatMoney,
  formatPercent,
  formatPrice,
  formatSignedPercent,
  formatStart,
  showTypedAmerican,
  titleCase,
} from '@/utils/format';

describe('formatAmerican', () => {
  it('signs positive prices and uses a true minus for negatives', () => {
    expect(formatAmerican(142)).toBe('+142');
    expect(formatAmerican(-165)).toBe('−165');
    expect(formatAmerican(-165)).not.toContain('-');
    expect(formatAmerican(100)).toBe('+100');
  });
  it('rounds fractional American prices', () => {
    expect(formatAmerican(141.6)).toBe('+142');
  });
});

describe('formatDecimal and formatPrice', () => {
  const price = { american: -110, decimal: 1.9090909 };
  it('shows two decimal places', () => {
    expect(formatDecimal(2.5)).toBe('2.50');
    expect(formatDecimal(1.9090909)).toBe('1.91');
  });
  it('follows the chosen format without converting anything', () => {
    expect(formatPrice(price, 'american')).toBe('−110');
    expect(formatPrice(price, 'decimal')).toBe('1.91');
  });
});

describe('formatLine', () => {
  it('formats totals unsigned and spreads signed', () => {
    expect(formatLine(221.5)).toBe('221.5');
    expect(formatLine(-3.5, { signed: true })).toBe('−3.5');
    expect(formatLine(7, { signed: true })).toBe('+7');
    expect(formatLine(0, { signed: true })).toBe('PK');
  });
  it('returns an empty string when there is no line', () => {
    expect(formatLine(null)).toBe('');
    expect(formatLine(undefined)).toBe('');
  });
});

describe('formatPercent', () => {
  it('formats probabilities', () => {
    expect(formatPercent(0.4132)).toBe('41.3%');
    expect(formatPercent(0.5, 0)).toBe('50%');
  });
  it('does not invent a number for missing values', () => {
    expect(formatPercent(null)).toBe('n/a');
    expect(formatPercent(undefined)).toBe('n/a');
    expect(formatPercent(Number.NaN)).toBe('n/a');
  });
});

describe('formatAge', () => {
  const now = new Date('2026-11-15T12:00:00Z');
  it('picks a readable unit', () => {
    expect(formatAge('2026-11-15T11:59:18Z', now)).toBe('42s ago');
    expect(formatAge('2026-11-15T11:51:00Z', now)).toBe('9 min ago');
    expect(formatAge('2026-11-15T09:00:00Z', now)).toBe('3h ago');
    expect(formatAge('2026-11-12T12:00:00Z', now)).toBe('3d ago');
  });
  it('never reports a negative age when clocks disagree', () => {
    expect(formatAge('2026-11-15T12:00:30Z', now)).toBe('0s ago');
  });
});

describe('formatStart', () => {
  it('shows weekday, date and time in the given zone', () => {
    const text = formatStart('2026-11-15T18:00:00Z', 'America/New_York');
    expect(text).toContain('Sun');
    expect(text).toContain('Nov 15');
    expect(text).toMatch(/1:00\sPM/);
  });
});

describe('formatMoney', () => {
  it('groups thousands and always shows cents', () => {
    expect(formatMoney(1250)).toBe('$1,250.00');
    expect(formatMoney(1234567.891)).toBe('$1,234,567.89');
    expect(formatMoney(0)).toBe('$0.00');
    expect(formatMoney(999.999)).toBe('$1,000.00');
  });
  it('uses a true minus sign before the dollar sign for losses', () => {
    expect(formatMoney(-25)).toBe('−$25.00');
    expect(formatMoney(-25)).not.toContain('-');
  });
  it('signs profit when asked, and leaves zero unsigned', () => {
    expect(formatMoney(22.73, { signed: true })).toBe('+$22.73');
    expect(formatMoney(-25, { signed: true })).toBe('−$25.00');
    expect(formatMoney(0, { signed: true })).toBe('$0.00');
  });
});

describe('formatPercent and formatSignedPercent', () => {
  it('never shows a negative zero', () => {
    expect(formatPercent(-0.0004)).toBe('0.0%');
    expect(formatSignedPercent(-0.0004)).toBe('0.0%');
    expect(formatSignedPercent(0)).toBe('0.0%');
  });
  it('uses a true minus sign for negatives', () => {
    expect(formatPercent(-0.052)).toBe('−5.2%');
    expect(formatPercent(-0.052)).not.toContain('-');
  });
  it('signs gains and losses', () => {
    expect(formatSignedPercent(0.125)).toBe('+12.5%');
    expect(formatSignedPercent(-0.02)).toBe('−2.0%');
    expect(formatSignedPercent(0.0125, 2)).toBe('+1.25%');
  });
  it('says n/a when there is no value', () => {
    expect(formatPercent(null)).toBe('n/a');
    expect(formatSignedPercent(undefined)).toBe('n/a');
    expect(formatSignedPercent(Number.NaN)).toBe('n/a');
  });
});

describe('small display helpers', () => {
  it('formats a day, title-cases API keys and tidies typed odds', () => {
    expect(formatDay('2026-11-15T20:00:00Z', 'UTC')).toBe('Nov 15');
    expect(titleCase('player_prop')).toBe('Player Prop');
    expect(titleCase('half_won')).toBe('Half Won');
    expect(cleanOdds('  −110 ')).toBe('-110');
    expect(cleanOdds('–250')).toBe('-250');
    expect(showTypedAmerican('150')).toBe('+150');
    expect(showTypedAmerican('-110')).toBe('−110');
    expect(showTypedAmerican('+120')).toBe('+120');
  });
});
