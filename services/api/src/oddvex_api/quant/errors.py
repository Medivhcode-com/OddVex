"""Errors raised by the pure quant library."""

from __future__ import annotations


class QuantError(ValueError):
    """Invalid input to a quant function.

    ``code`` is a stable machine-readable identifier that the HTTP layer maps
    into the error envelope.
    """

    def __init__(self, message: str, code: str = "invalid_quant_input") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
