"""Historical hit rate with a Wilson score confidence interval."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .errors import QuantError


def wilson_interval(hits: int, sample_size: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (default ~95%)."""
    if sample_size <= 0:
        raise QuantError("sample size must be positive", code="invalid_sample")
    if hits < 0 or hits > sample_size:
        raise QuantError("hits must be between 0 and the sample size", code="invalid_sample")
    if z <= 0:
        raise QuantError("z must be positive", code="invalid_sample")
    n = float(sample_size)
    p = hits / n
    z2 = z * z
    denominator = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denominator
    half_width = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denominator
    return max(0.0, centre - half_width), min(1.0, centre + half_width)


@dataclass(frozen=True, slots=True)
class HitRate:
    line: float
    direction: str
    hits: int
    misses: int
    pushes: int
    #: Games counted in the rate (pushes excluded).
    sample_size: int
    rate: float | None
    ci_low: float | None
    ci_high: float | None
    confidence_level: float = 0.95


def hit_rate(
    values: Sequence[float],
    line: float,
    direction: Literal["over", "under"] = "over",
    z: float = 1.96,
) -> HitRate:
    """Share of past results that cleared ``line``.

    Results exactly on the line are pushes and are excluded from the sample.
    With no usable games the rate and interval are ``None``.
    """
    if direction not in ("over", "under"):
        raise QuantError("direction must be 'over' or 'under'", code="invalid_direction")
    if not math.isfinite(line):
        raise QuantError("line must be finite", code="invalid_line")
    pushes = sum(1 for v in values if v == line)
    overs = sum(1 for v in values if v > line)
    unders = sum(1 for v in values if v < line)
    hits = overs if direction == "over" else unders
    sample = overs + unders
    if sample == 0:
        return HitRate(line, direction, 0, 0, pushes, 0, None, None, None)
    low, high = wilson_interval(hits, sample, z)
    return HitRate(
        line=line,
        direction=direction,
        hits=hits,
        misses=sample - hits,
        pushes=pushes,
        sample_size=sample,
        rate=hits / sample,
        ci_low=low,
        ci_high=high,
    )
