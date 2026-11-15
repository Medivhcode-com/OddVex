"""Alert rule routes. Every query is scoped to the authenticated user."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..board import Board
from ..db import AlertRule, utcnow
from ..deps import BoardDep, CurrentUserDep, DbDep, write_audit
from ..errors import AUTH_ERROR_RESPONSES, NOT_FOUND_RESPONSE, ApiError, ErrorResponse, not_found
from . import service
from .schemas import (
    MAX_ACTIVE_ALERTS,
    MAX_TOTAL_ALERTS,
    AlertCreate,
    AlertEvaluationOut,
    AlertListOut,
    AlertRuleOut,
    AlertState,
    AlertUpdate,
)

router = APIRouter(prefix="/alerts", tags=["alerts"], responses=AUTH_ERROR_RESPONSES)

_FULL: dict[int | str, dict[str, object]] = {
    409: {"model": ErrorResponse, "description": "You have the maximum number of alerts"}
}


def _owned_rule(db: Session, user_id: str, rule_id: str) -> AlertRule:
    """Fetch a rule by id *and* owner. Another user's rule is indistinguishable from none."""
    rule = db.scalar(select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == user_id))
    if rule is None:
        raise not_found("Alert", rule_id)
    return rule


def _check_room(db: Session, user_id: str, adding_row: bool) -> None:
    if service.count_rules(db, user_id, "active") >= MAX_ACTIVE_ALERTS:
        raise ApiError(
            409,
            "alerts_full",
            f"You can have at most {MAX_ACTIVE_ALERTS} active alerts. Pause or delete one "
            "to add another.",
            details={"max_active": MAX_ACTIVE_ALERTS},
        )
    if adding_row and service.count_rules(db, user_id) >= MAX_TOTAL_ALERTS:
        raise ApiError(
            409,
            "alerts_full",
            f"You can keep at most {MAX_TOTAL_ALERTS} alerts, including triggered, expired "
            "and paused ones. Delete some to add another.",
            details={"max_total": MAX_TOTAL_ALERTS},
        )


def _details(rule: AlertRule) -> dict[str, object]:
    return {"kind": rule.kind, "event_id": rule.event_id, "team_id": rule.team_id}


@router.get(
    "",
    response_model=AlertListOut,
    operation_id="list_alerts",
    summary="Your alert rules, newest first",
    description=(
        "Each rule has a one-line `summary` and embeds the current event or team from the "
        "data provider. When the provider no longer has it, `available` is false."
    ),
)
def list_alerts(
    user: CurrentUserDep,
    db: DbDep,
    board: BoardDep,
    state: Annotated[AlertState | None, Query()] = None,
) -> AlertListOut:
    query = select(AlertRule).where(AlertRule.user_id == user.id)
    if state is not None:
        query = query.where(AlertRule.state == state)
    rules = db.scalars(query.order_by(AlertRule.created_at.desc(), AlertRule.id))
    return AlertListOut(items=[service.rule_out(board, rule) for rule in rules])


@router.post(
    "",
    response_model=AlertRuleOut,
    status_code=201,
    operation_id="create_alert",
    summary="Create an alert rule",
    description=(
        "`kind` selects the rule type and its fields. The event must exist "
        "(`422 unknown_event`) and must not be over (`422 event_not_open`); the market and "
        "outcome must fit it. Creating a rule identical to one of your active rules returns "
        f"that rule with 200. At most {MAX_ACTIVE_ALERTS} active rules per user.\n\n"
        "Alerts are delivered in the app only. There is no background worker: rules are "
        "evaluated when you read your notifications or call `POST /v1/alerts/evaluate`."
    ),
    responses={
        200: {"model": AlertRuleOut, "description": "An identical active rule exists"},
        **_FULL,
    },
)
def create_alert(
    body: AlertCreate,
    user: CurrentUserDep,
    db: DbDep,
    board: BoardDep,
    request: Request,
    response: Response,
) -> AlertRuleOut:
    rule = service.from_body(body)
    service.arm(board, rule)
    existing = service.find_active_duplicate(db, user.id, rule)
    if existing is not None:
        response.status_code = 200
        return service.rule_out(board, existing)
    _check_room(db, user.id, adding_row=True)
    rule.user_id = user.id
    db.add(rule)
    db.flush()
    write_audit(
        db,
        request,
        "alert.create",
        user_id=user.id,
        entity_type="alert_rule",
        entity_id=rule.id,
        details=_details(rule),
    )
    db.commit()
    return service.rule_out(board, rule)


@router.post(
    "/evaluate",
    response_model=AlertEvaluationOut,
    operation_id="evaluate_alerts",
    summary="Evaluate your active alert rules now",
    description=(
        "Checks every active rule against the current data, creates the notifications that "
        "are due and updates rule states. Calling it again right away changes nothing."
    ),
)
def evaluate_alerts(
    user: CurrentUserDep, db: DbDep, board: BoardDep, request: Request
) -> AlertEvaluationOut:
    result = service.evaluate_user_alerts(db, user, board.now, board, request)
    db.commit()
    request.app.state.alert_throttle.mark(user.id, board.now)
    return AlertEvaluationOut(
        evaluated=result.evaluated, fired=result.fired, expired=result.expired
    )


def _transition(db: Session, board: Board, rule: AlertRule, target: str) -> str | None:
    """Apply a state change. Returns the audit action, or ``None`` when nothing changed."""
    if rule.state == target:
        return None
    if target == "paused":
        if rule.state != "active":
            raise ApiError(
                409,
                "invalid_state_transition",
                f"Only an active alert can be paused; this one is {rule.state}",
            )
        rule.state = "paused"
        return "alert.pause"
    # target == "active": resume a paused rule, or re-arm a triggered / expired one.
    resuming = rule.state == "paused"
    if resuming:
        service.mark_finished_games_handled(board, rule)
    else:
        service.arm(board, rule)
    if service.find_active_duplicate(db, rule.user_id, rule) is not None:
        raise ApiError(409, "alert_duplicate", "You already have an identical active alert")
    _check_room(db, rule.user_id, adding_row=False)
    if not resuming:
        rule.arm_count += 1
        rule.triggered_at = None
    rule.state = "active"
    return "alert.resume" if resuming else "alert.rearm"


@router.patch(
    "/{alert_id}",
    response_model=AlertRuleOut,
    operation_id="update_alert",
    summary="Pause, resume or re-arm an alert rule",
    description=(
        "`state: paused` pauses an active rule. `state: active` resumes a paused rule or "
        "re-arms a triggered one so it can fire again; a re-armed `line_move` rule takes "
        "the current consensus line as its new baseline. Re-arming needs the event to "
        "still be open (`422 event_not_open`)."
    ),
    responses={
        **NOT_FOUND_RESPONSE,
        409: {
            "model": ErrorResponse,
            "description": "Not possible from the rule's state, or you are at the limit",
        },
    },
)
def update_alert(
    alert_id: str,
    body: AlertUpdate,
    user: CurrentUserDep,
    db: DbDep,
    board: BoardDep,
    request: Request,
) -> AlertRuleOut:
    rule = _owned_rule(db, user.id, alert_id)
    action = _transition(db, board, rule, body.state)
    if action is not None:
        rule.updated_at = utcnow()
        write_audit(
            db,
            request,
            action,
            user_id=user.id,
            entity_type="alert_rule",
            entity_id=rule.id,
            details=_details(rule),
        )
        db.commit()
    return service.rule_out(board, rule)


@router.delete(
    "/{alert_id}",
    status_code=204,
    operation_id="delete_alert",
    summary="Delete an alert rule",
    description="Notifications the rule already created are kept.",
    responses=NOT_FOUND_RESPONSE,
)
def delete_alert(alert_id: str, user: CurrentUserDep, db: DbDep, request: Request) -> Response:
    rule = _owned_rule(db, user.id, alert_id)
    details = _details(rule)
    db.delete(rule)
    write_audit(
        db,
        request,
        "alert.delete",
        user_id=user.id,
        entity_type="alert_rule",
        entity_id=alert_id,
        details=details,
    )
    db.commit()
    return Response(status_code=204)
