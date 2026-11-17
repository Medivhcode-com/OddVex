"""Schemas shared by several route groups."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from .quant import describe_price, parse_odds

DataMode = Literal["synthetic", "replay"]


class PriceOut(BaseModel):
    """One price in every display format."""

    american: int = Field(examples=[-110])
    decimal: float = Field(examples=[1.9091])
    fractional: str = Field(examples=["10/11"])
    implied_probability: float = Field(
        description="1/decimal. Includes the bookmaker margin.", examples=[0.52381]
    )


def price_out(decimal_odds: Decimal | float | int | str) -> PriceOut:
    price = describe_price(decimal_odds)
    return PriceOut(
        american=price.american,
        decimal=round(float(price.decimal), 4),
        fractional=price.fractional,
        implied_probability=round(price.implied_probability, 6),
    )


def price_from_american(american: int) -> PriceOut:
    return price_out(parse_odds("american", american))


OddsFormatIn = Literal["american", "decimal", "fractional"]
#: A price as typed by a user: -110, 2.5, "+150" or "5/2".
OddsValue = float | str


def odds_to_decimal(value: float | str, odds_format: str) -> Decimal:
    """Normalise a user-supplied price to decimal odds (raises ``QuantError``)."""
    if isinstance(value, str):
        text = value.strip()
        if odds_format != "fractional" and text.startswith("+"):
            text = text[1:]
        return parse_odds(odds_format, text)
    if odds_format == "american" and float(value).is_integer():
        return parse_odds(odds_format, int(value))
    return parse_odds(odds_format, value)


class SportsbookRef(BaseModel):
    key: str
    name: str


class TeamRef(BaseModel):
    id: str
    name: str
    abbreviation: str


class BestPriceOut(BaseModel):
    """The best available price for one side and the sportsbook offering it."""

    price: PriceOut
    sportsbook: SportsbookRef


class MessageOut(BaseModel):
    message: str
