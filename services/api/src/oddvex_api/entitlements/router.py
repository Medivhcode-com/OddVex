"""The caller's plan and what it includes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..deps import CurrentUserDep, DbDep
from ..errors import AUTH_ERROR_RESPONSES
from . import service

router = APIRouter(tags=["auth"])


class EntitlementOut(BaseModel):
    enabled: bool
    limit: int | None = Field(
        default=None, description="Numeric allowance, for features that have one."
    )


class EntitlementsOut(BaseModel):
    plan: Literal["free", "premium"]
    preview: bool = Field(
        description=(
            "True while plans are not enforced (flag `premium_gating` is off): every "
            "feature is enabled for every plan."
        )
    )
    features: dict[str, EntitlementOut]


@router.get(
    "/me/entitlements",
    response_model=EntitlementsOut,
    operation_id="get_entitlements",
    summary="Your plan and what it includes",
    description=(
        "Computed from one in-code catalog. There is no billing and no purchase route: a "
        "plan can only be set by an administrator. While `preview` is true nothing is gated."
    ),
    responses=AUTH_ERROR_RESPONSES,
)
def get_entitlements(user: CurrentUserDep, db: DbDep) -> EntitlementsOut:
    gating, features = service.entitlements_for(db, user)
    return EntitlementsOut(
        plan=user.plan,  # type: ignore[arg-type]
        preview=not gating,
        features={
            key: EntitlementOut(enabled=value.enabled, limit=value.limit)
            for key, value in features.items()
        },
    )
