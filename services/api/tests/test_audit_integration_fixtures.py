"""The invalid snapshots in ``data/fixtures/invalid_payloads.sample.json`` carry their own
``updatedAt``, so each is refused for the defect it is named after even if the
normalizer's checks are reordered: a priced quote without ``updatedAt`` is refused for that
alone (``missing_timestamp``)."""

from __future__ import annotations

from typing import Any

import pytest

from oddvex_api.providers.normalize import ProviderContractError, normalize_odds_snapshot

from .test_provider_contract import FETCHED, SNAPSHOT_MESSAGES, SNAPSHOT_REASONS, load


@pytest.mark.parametrize(
    "case", load("invalid_payloads.sample.json")["snapshots"], ids=lambda case: case["reason"]
)
def test_each_invalid_snapshot_is_refused_for_its_reason_as_written(
    case: dict[str, Any],
) -> None:
    payload = case["payload"]
    assert isinstance(payload.get("updatedAt"), str), case["reason"]
    with pytest.raises(ProviderContractError) as caught:
        normalize_odds_snapshot(payload, "fixture", FETCHED)
    assert caught.value.reason == SNAPSHOT_REASONS[case["reason"]]
    assert SNAPSHOT_MESSAGES[case["reason"]] in str(caught.value)
