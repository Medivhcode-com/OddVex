"""Pure betting math. No I/O, no global state, no clock access."""

from .clv import CLVResult, closing_line_value
from .errors import QuantError
from .ev import EVResult, expected_value, money, payout, profit, roi, validate_stake
from .hitrate import HitRate, hit_rate, wilson_interval
from .novig import NoVigResult, no_vig
from .odds import (
    OddsFormat,
    Price,
    american_to_decimal,
    decimal_to_american,
    decimal_to_fractional,
    describe_price,
    fractional_to_decimal,
    implied_probability,
    parse_odds,
    probability_to_decimal,
    validate_decimal_odds,
    validate_probability,
)
from .parlay import (
    BET_RESULTS,
    INDEPENDENCE_NOTE,
    LEG_RESULTS,
    ParlayLeg,
    ParlayResult,
    Settlement,
    combine_parlay,
    settle_bet,
    settle_parlay,
)

__all__ = [
    "BET_RESULTS",
    "INDEPENDENCE_NOTE",
    "LEG_RESULTS",
    "CLVResult",
    "EVResult",
    "HitRate",
    "NoVigResult",
    "OddsFormat",
    "ParlayLeg",
    "ParlayResult",
    "Price",
    "QuantError",
    "Settlement",
    "american_to_decimal",
    "closing_line_value",
    "combine_parlay",
    "decimal_to_american",
    "decimal_to_fractional",
    "describe_price",
    "expected_value",
    "fractional_to_decimal",
    "hit_rate",
    "implied_probability",
    "money",
    "no_vig",
    "parse_odds",
    "payout",
    "probability_to_decimal",
    "profit",
    "roi",
    "settle_bet",
    "settle_parlay",
    "validate_decimal_odds",
    "validate_probability",
    "validate_stake",
    "wilson_interval",
]
