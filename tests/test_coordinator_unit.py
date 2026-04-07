"""Unit tests for Coordinator with mocked store and adapter (no MySQL)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from xa_transactions.core.coordinator import Coordinator
from xa_transactions.types.exceptions import ValidationError
from xa_transactions.types.types import (
    XID,
    BranchState,
    BranchTransaction,
    Decision,
    GlobalState,
    GlobalTransaction,
)


def _utc_now() -> datetime:
    return datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _global_tx(
    gtrid: str,
    *,
    expected_count: int = 1,
    state: GlobalState = GlobalState.ACTIVE,
) -> GlobalTransaction:
    t = _utc_now()
    return GlobalTransaction(
        gtrid=gtrid,
        decision=Decision.UNKNOWN,
        state=state,
        expected_count=expected_count,
        created_at=t,
        updated_at=t,
    )


def _branch(
    gtrid: str,
    bqual: str,
    *,
    state: BranchState = BranchState.PREPARED,
) -> BranchTransaction:
    t = _utc_now()
    return BranchTransaction(
        gtrid=gtrid,
        bqual=bqual,
        state=state,
        created_at=t,
        updated_at=t,
        prepared_at=t,
    )


def test_create_global_passes_expected_count_and_calls_store() -> None:
    store = MagicMock()
    adapter = MagicMock()
    coord = Coordinator(adapter, store)

    gid = coord.create_global(3, gtrid="fixed-gtrid")

    assert gid == "fixed-gtrid"
    store.create_global.assert_called_once()
    _, kwargs = store.create_global.call_args
    assert kwargs["gtrid"] == "fixed-gtrid"
    assert kwargs["expected_count"] == 3
    assert kwargs["decision"] == Decision.UNKNOWN
    assert kwargs["state"] == GlobalState.ACTIVE


def test_create_branches_raises_when_global_missing() -> None:
    store = MagicMock()
    store.get_global.return_value = None
    adapter = MagicMock()
    coord = Coordinator(adapter, store)

    with pytest.raises(ValidationError, match="not found"):
        coord.create_branches("missing-gtrid")


def test_finalize_unknown_decision_raises() -> None:
    store = MagicMock()
    adapter = MagicMock()
    coord = Coordinator(adapter, store)

    with pytest.raises(ValidationError, match="UNKNOWN"):
        coord.finalize("g", Decision.UNKNOWN)


def test_finalize_commit_calls_adapter_with_format_id() -> None:
    gtrid = "g1"
    store = MagicMock()
    store.get_global.return_value = _global_tx(gtrid, expected_count=1)
    store.get_branches.return_value = [_branch(gtrid, "bq1")]
    adapter = MagicMock()
    coord = Coordinator(adapter, store, format_id=7)

    coord.finalize(gtrid, Decision.COMMIT)

    adapter.xa_commit.assert_called_once()
    (xid_arg,) = adapter.xa_commit.call_args[0]
    assert isinstance(xid_arg, XID)
    assert xid_arg.gtrid == gtrid
    assert xid_arg.bqual == "bq1"
    assert xid_arg.format_id == 7


def test_finalize_idempotent_when_already_committed() -> None:
    gtrid = "g1"
    store = MagicMock()
    store.get_global.return_value = _global_tx(gtrid, state=GlobalState.COMMITTED)
    adapter = MagicMock()
    coord = Coordinator(adapter, store)

    coord.finalize(gtrid, Decision.COMMIT)

    adapter.xa_commit.assert_not_called()
    adapter.xa_rollback.assert_not_called()


def test_finalize_raises_when_not_enough_prepared_branches() -> None:
    gtrid = "g1"
    store = MagicMock()
    store.get_global.return_value = _global_tx(gtrid, expected_count=2)
    store.get_branches.return_value = [_branch(gtrid, "b1")]
    adapter = MagicMock()
    coord = Coordinator(adapter, store)

    with pytest.raises(ValidationError, match="Not all branches prepared"):
        coord.finalize(gtrid, Decision.COMMIT, force=False)


def test_finalize_rollback_calls_xa_rollback() -> None:
    gtrid = "g1"
    store = MagicMock()
    store.get_global.return_value = _global_tx(gtrid, expected_count=1)
    store.get_branches.return_value = [_branch(gtrid, "bq1")]
    adapter = MagicMock()
    coord = Coordinator(adapter, store, format_id=3)

    coord.finalize(gtrid, Decision.ROLLBACK)

    adapter.xa_rollback.assert_called_once()
    (xid_arg,) = adapter.xa_rollback.call_args[0]
    assert xid_arg.format_id == 3


def test_reconcile_branch_returns_none_when_no_matching_xid() -> None:
    store = MagicMock()
    adapter = MagicMock()
    adapter.xa_recover.return_value = [
        XID(gtrid="other", bqual="b", format_id=1),
    ]
    coord = Coordinator(adapter, store, format_id=1)

    assert coord.reconcile_branch("g1", "b1") is None


def test_reconcile_branch_creates_branch_when_recover_matches() -> None:
    store = MagicMock()
    store.get_branch.return_value = None
    adapter = MagicMock()
    adapter.xa_recover.return_value = [
        XID(gtrid="g1", bqual="b1", format_id=1),
    ]
    coord = Coordinator(adapter, store, format_id=1)

    result = coord.reconcile_branch("g1", "b1")

    assert result == BranchState.PREPARED
    store.create_branch.assert_called_once()
    _, kwargs = store.create_branch.call_args
    assert kwargs["gtrid"] == "g1"
    assert kwargs["bqual"] == "b1"
    assert kwargs["state"] == BranchState.PREPARED
