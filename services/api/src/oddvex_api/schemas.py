"""Schemas shared by several route groups."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from .quant import describe_price, parse_odds

DataMode = Literal["synthetic"]


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


class OddsInput(BaseModel):
    """A price in any supported format, e.g. american -110, decimal 1.91, fractional "10/11"."""

    format: Literal["american", "decimal", "fractional"]
    value: float | str = Field(examples=[-110, 2.5, "5/2"])

    def to_decimal(self) -> Decimal:
        return parse_odds(self.format, self.value)


class SportsbookRef(BaseModel):
    id: str
    name: str


class MessageOut(BaseModel):
    message: str
