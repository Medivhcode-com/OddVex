# Quant methodology

How every number OddVex shows is calculated. The code is `src/oddvex_api/quant/` (pure
functions, no I/O) and the tests are `tests/quant/`.

**OddVex claims no predictive edge.** Nothing here forecasts a result. The calculators
transform prices and count past outcomes. Where a calculation needs a win probability, the
user supplies it. All sports data in the current build is synthetic.

## Conventions

- Decimal odds `d` are the internal representation: total return per 1 staked, `d > 1`.
- Prices and money use `Decimal`. Money is rounded to cents, half up, at the end of a
  calculation. Probabilities are floats.
- Ratios are fractions (`0.05` = 5%) unless a field is named `..._percent`.
- Invalid input raises a validation error rather than being coerced: American odds strictly
  between -100 and +100, decimal odds `<= 1`, probabilities outside the open interval `(0, 1)`,
  non-positive stakes.

## Odds conversion

| From | To decimal |
| --- | --- |
| American `a >= +100` | `d = 1 + a/100` |
| American `a <= -100` | `d = 1 + 100/|a|` |
| Fractional `n/m` | `d = 1 + n/m` |

Back to American: `(d - 1) * 100` when `d >= 2`, otherwise `-100 / (d - 1)`, rounded to the
nearest whole number. Even money is always written `+100`. Back to fractional: the reduced
fraction closest to `d - 1` with a denominator of at most 100 (so `5/2`, `10/11`).

Limitation: American and fractional displays are rounded, so a round trip through them can
differ from the stored decimal in the last digit.

## Implied probability

`p_implied = 1 / d`. This includes the bookmaker's margin, so the implied probabilities of a
market add up to more than 1.

## No-vig (margin removal)

For a market with prices `d_1 ... d_n` (two-way, three-way or n-way):

```
q_i       = 1 / d_i
booksum   = sum(q_i)
overround = booksum - 1
hold      = 1 - 1 / booksum
fair_i    = q_i / booksum          (proportional / multiplicative method)
```

Check: `-110 / -110` gives `q = 0.5238` each, overround `4.76%`, hold `4.55%`, fair `50% / 50%`.

Limitations: the proportional method assumes the margin is spread in proportion to each
outcome's implied probability. Real books often load more margin on longshots, so the
proportional result tends to overstate longshots slightly. Other methods (additive, power,
Shin) exist and are not implemented. A no-vig probability is the market's own estimate with
the margin removed. It is not a forecast and not OddVex's opinion.

## Consensus and best price

Used on the odds screen and prop board.

- A quote is **stale** when it is older than the threshold (120 s live, 15 min pre-game by
  default, both configurable).
- Only books that are open and not stale are **usable**.
- For spread and total, the **consensus line** is the most common line among usable books
  (ties: nearest the median, then the lower line). Prices are only compared between books on
  that line, because a price at a different line is a different bet.
- **Best price** per outcome is the highest decimal price among those books.
- **Consensus probability** per outcome is the mean of each of those books' no-vig probability.
- **Hold** is shown per book for any book with a full set of prices.

Limitation: an unweighted mean treats every book alike. With few usable books the consensus is
noisy; `books_used` is always returned so that can be shown.

## Expected value

For a win probability `p` supplied by the user and decimal price `d`:

```
EV per unit = p * (d - 1) - (1 - p)
EV%         = EV per unit * 100
break-even  = 1 / d
edge        = p - break-even
```

Check: `+150` (`d = 2.5`) at `p = 0.45` gives `0.45 * 1.5 - 0.55 = +0.125`, or `+12.5%`.

Limitation: EV is exactly as reliable as `p`. OddVex does not estimate `p`. A small error in
`p` moves EV a lot, and positive EV on paper does not mean a bet will win.

## Payout, profit, ROI

```
payout = stake * d            profit = stake * (d - 1)
ROI    = total profit / total staked
```

In the tracker summary, totals cover settled bets only and void bets are left out of
`staked`. ROI is undefined (`null`) when nothing was staked.

## Closing line value

Price-based, for a price taken `d_bet` and the closing price of the same selection `d_close`:

```
CLV = d_bet / d_close - 1
```

When the closing price of the other side of a two-way market is supplied, the close is
de-vigged and two more figures are returned:

```
p_close_fair      = no-vig probability of the selection at the close
probability delta = p_close_fair - 1 / d_bet
EV at close %     = (p_close_fair * d_bet - 1) * 100
```

For a multi-leg bet, CLV uses the product of the leg prices against the product of the
closing prices, and only when every leg has a closing price.

Limitations: closing prices are entered by the user or the import source and are not verified.
The price-based figure still contains the closing margin. CLV describes price quality over
many bets; it says nothing about whether one bet wins. "EV at close" treats the no-vig close as
the true probability, which is an assumption.

## Historical hit rate

For past stat values `x_1 ... x_n` and a line `L`:

- `x > L` is an over, `x < L` an under, `x = L` a **push**.
- Pushes are excluded: `sample = overs + unders`, `rate = overs / sample`.
- The interval is the Wilson score interval at `z = 1.96` (about 95%):

```
centre = (p + z^2 / 2n) / (1 + z^2 / n)
half   = z * sqrt(p(1 - p)/n + z^2 / 4n^2) / (1 + z^2 / n)
```

Check: 7 of 10 gives `[0.397, 0.892]`.

The line used is the current consensus line. If no book is offering the market, the half-point
nearest the season median is used and labelled `line_source: "season_median"`.

Limitations: this is a count of what already happened in a small sample. It is not a
probability of a future result. It ignores opponent strength, minutes, injuries, role changes
and everything else that makes the next game different, and games are not independent draws
from a fixed distribution. The wide interval is the honest summary. Comparing a past rate at
today's line with past games played at other lines is also only approximate.

## Parlays

```
combined decimal = product of d_i over the legs still in the parlay
payout           = stake * combined decimal
```

Pushed and void legs drop out (they count as `1.0`). A half-won leg contributes
`1 + (d - 1)/2`, a half-lost leg `0.5`, and any lost leg loses the parlay.

A **combined probability** is only returned when every remaining leg has a user-supplied win
probability *and* every leg is from a different, identified event. It is the product of the leg
probabilities and is labelled "assumes independence". If two legs share an event, or a leg has
no event id, `combined_probability` is `null` and `correlation_warnings` explains why: outcomes
in the same game are correlated, so multiplying them would be wrong.

Limitations: legs from different events can still be correlated (weather, schedule, shared
news). Sportsbooks price same-game parlays with their own correlation models, so the product of
the leg prices is not what a book would pay; the tracker lets a bet carry its own price for
that reason.

## Settlement

| Result | Returned to the bettor |
| --- | --- |
| won | `stake * d` |
| lost | `0` |
| push, void | `stake` |
| half_won | `stake/2 * d + stake/2` |
| half_lost | `stake/2` |
| cashout | the cash-out amount entered |

`profit = returned - stake`. A parlay priced from its legs is settled from the leg results
using the parlay rules above. A bet with its own price is settled at that price.

Limitation: sportsbook house rules differ (dead heats, reduced-juice pushes, parlay
reductions). OddVex records what the user or the import source reports and applies the
standard rules above; the sportsbook's own settlement is authoritative.
