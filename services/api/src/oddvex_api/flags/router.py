"""Public feature flags for clients."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..deps import DbDep
from . import service

router = APIRouter(tags=["meta"])


class FlagsOut(BaseModel):
    flags: dict[str, bool] = Field(
        description="Every known feature flag and whether it is on.",
        examples=[{"community": False, "value_screen": True}],
    )


@router.get(
    "/flags",
    response_model=FlagsOut,
    operation_id="list_flags",
    summary="Feature flags",
    description=(
        "Global on/off switches. A route behind a flag that is off answers "
        "`404 feature_disabled`. Clients use this to hide what is switched off."
    ),
)
def list_flags(db: DbDep) -> FlagsOut:
    return FlagsOut(flags=service.flag_states(db))
