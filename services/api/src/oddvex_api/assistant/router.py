from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import BoardDep, DbDep, OptionalUserDep
from ..errors import ERROR_RESPONSES, RATE_LIMIT_RESPONSE, ErrorResponse
from ..ratelimit import rate_limit
from .engine import Assistant
from .schemas import AssistantQueryRequest, AssistantResponse

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post(
    "/query",
    response_model=AssistantResponse,
    operation_id="assistant_query",
    summary="Ask the rule-based assistant",
    description=(
        "Deterministic keyword routing to internal data tools with templated answers. No "
        "language model is connected and the assistant never produces a number that a tool "
        "did not compute. Authentication is optional; the bet summary intent needs it."
    ),
    dependencies=[Depends(rate_limit("assistant"))],
    responses={
        401: {"model": ErrorResponse, "description": "A token was sent but is invalid"},
        **ERROR_RESPONSES,
        **RATE_LIMIT_RESPONSE,
    },
)
def assistant_query(
    body: AssistantQueryRequest, board: BoardDep, db: DbDep, user: OptionalUserDep
) -> AssistantResponse:
    return Assistant(board, db=db, user=user).answer(body.message)
