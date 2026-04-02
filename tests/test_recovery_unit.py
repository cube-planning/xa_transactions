"""Unit tests for DefaultRecoveryStrategy (mocked store, adapter, lock manager)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from xa_transactions.infrastructure.recovery import DefaultRecoveryStrategy
from xa_transactions.types.exceptions import RecoveryError
from xa_transactions.types.types import (
    XID,
    BranchState,
    BranchTransaction,
    Decision,
    GlobalState,
    GlobalTransaction,
)

_T = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _global_tx(
    gtrid: str,
    *,
    decision: Decision = Decision.COMMIT,
    state: GlobalState = GlobalState.ACTIVE,
    created_at: datetime | None = None,
) -> GlobalTransaction:
    t = created_at or _T
    return GlobalTransaction(
        gtrid=gtrid,
        decision=decision,
        state=state,
        expected_count=1,
        created_at=t,
        updated_at=t,
    )


def _branch(
    gtrid: str,
    bqual: str,
    *,
    state: BranchState = BranchState.PREPARED,
) -> BranchTransaction:
    return BranchTransaction(
        gtrid=gtrid,
        bqual=bqual,
        state=state,
        created_at=_T,
        updated_at=_T,
        prepared_at=_T if state == BranchState.PREPARED else None,
    )


def test_skips_terminal_global_states() -> None:
    store = MagicMock()
    adapter = MagicMock()
    strat = DefaultRecoveryStrategy()
    incomplete = [
        _global_tx("g1", state=GlobalState.COMMITTED),
        _global_tx("g2", state=GlobalState.ROLLED_BACK),
    ]

    n = strat.recover(
        incomplete,
        [],
        adapter,
        store,
        max_age_seconds=3600,
        auto_rollback_expired=False,
    )

    assert n == 0
    store.get_branches.assert_not_called()
    adapter.xa_commit.assert_not_called()
    adapter.xa_rollback.assert_not_called()


def test_commit_prepared_branch_calls_xa_commit_and_format_id() -> None:
    store = MagicMock()
    store.get_branches.return_value = [_branch("g1", "b1")]
    adapter = MagicMock()
    strat = DefaultRecoveryStrategy()
    incomplete = [_global_tx("g1", decision=Decision.COMMIT)]

    n = strat.recover(
        incomplete,
        [],
        adapter,
        store,
        max_age_seconds=3600,
        auto_rollback_expired=False,
        format_id=9,
    )

    assert n == 1
    adapter.xa_commit.assert_called_once()
    (xid_arg,) = adapter.xa_commit.call_args[0]
    assert xid_arg.gtrid == "g1"
    assert xid_arg.bqual == "b1"
    assert xid_arg.format_id == 9


def test_commit_without_prepared_branches_no_recovery() -> None:
    store = MagicMock()
    store.get_branches.return_value = [
        _branch("g1", "b1", state=BranchState.EXPECTED),
    ]
    adapter = MagicMock()
    strat = DefaultRecoveryStrategy()

    n = strat.recover(
        [_global_tx("g1", decision=Decision.COMMIT)],
        [],
        adapter,
        store,
        max_age_seconds=3600,
        auto_rollback_expired=False,
    )

    assert n == 0
    adapter.xa_commit.assert_not_called()


def test_rollback_prepared_branch_calls_xa_rollback() -> None:
    store = MagicMock()
    store.get_branches.return_value = [_branch("g1", "b1")]
    adapter = MagicMock()
    strat = DefaultRecoveryStrategy()

    n = strat.recover(
        [_global_tx("g1", decision=Decision.ROLLBACK)],
        [],
        adapter,
        store,
        max_age_seconds=3600,
        auto_rollback_expired=False,
    )

    assert n == 1
    adapter.xa_rollback.assert_called_once()


def test_reconcile_expected_branch_from_recovered_xids_then_commits() -> None:
    store = MagicMock()
    store.get_branches.return_value = [
        _branch("g1", "b1", state=BranchState.EXPECTED),
    ]
    adapter = MagicMock()
    strat = DefaultRecoveryStrategy()
    recovered = [XID(gtrid="g1", bqual="b1", format_id=1)]

    n = strat.recover(
        [_global_tx("g1", decision=Decision.COMMIT)],
        recovered,
        adapter,
        store,
        max_age_seconds=3600,
        auto_rollback_expired=False,
    )

    assert n == 1
    prep_updates = [
        c
        for c in store.update_branch.call_args_list
        if c.kwargs.get("state") == BranchState.PREPARED
    ]
    assert len(prep_updates) == 1
    adapter.xa_commit.assert_called_once()


def test_unknown_expired_with_prepared_rolls_back() -> None:
    old = _T - timedelta(hours=2)
    store = MagicMock()
    store.get_branches.return_value = [_branch("g1", "b1")]
    adapter = MagicMock()
    strat = DefaultRecoveryStrategy()

    n = strat.recover(
        [_global_tx("g1", decision=Decision.UNKNOWN, created_at=old)],
        [],
        adapter,
        store,
        max_age_seconds=3600,
        auto_rollback_expired=True,
    )

    assert n == 1
    store.update_global.assert_any_call(gtrid="g1", decision=Decision.ROLLBACK)
    adapter.xa_rollback.assert_called_once()


def test_unknown_expired_without_prepared_only_updates_decision() -> None:
    old = _T - timedelta(hours=2)
    store = MagicMock()
    store.get_branches.return_value = [
        _branch("g1", "b1", state=BranchState.EXPECTED),
    ]
    adapter = MagicMock()
    strat = DefaultRecoveryStrategy()

    n = strat.recover(
        [_global_tx("g1", decision=Decision.UNKNOWN, created_at=old)],
        [],
        adapter,
        store,
        max_age_seconds=3600,
        auto_rollback_expired=True,
    )

    assert n == 0
    store.update_global.assert_any_call(gtrid="g1", decision=Decision.ROLLBACK)
    adapter.xa_rollback.assert_not_called()


def test_unknown_recent_not_auto_rolled_back() -> None:
    now = datetime.now(timezone.utc)
    recent = now - timedelta(seconds=30)
    store = MagicMock()
    store.get_branches.return_value = [_branch("g1", "b1")]
    adapter = MagicMock()
    strat = DefaultRecoveryStrategy()

    n = strat.recover(
        [_global_tx("g1", decision=Decision.UNKNOWN, created_at=recent)],
        [],
        adapter,
        store,
        max_age_seconds=3600,
        auto_rollback_expired=True,
    )

    assert n == 0
    adapter.xa_rollback.assert_not_called()


def test_lock_not_acquired_skips_global() -> None:
    lock_manager = MagicMock()
    lock_manager.try_acquire.return_value = None
    store = MagicMock()
    store.get_branches.return_value = [_branch("g1", "b1")]
    adapter = MagicMock()
    strat = DefaultRecoveryStrategy()

    n = strat.recover(
        [_global_tx("g1", decision=Decision.COMMIT)],
        [],
        adapter,
        store,
        max_age_seconds=3600,
        auto_rollback_expired=False,
        lock_manager=lock_manager,
    )

    assert n == 0
    lock_manager.try_acquire.assert_called_once_with("xa:finalize:g1", timeout=60.0)
    store.get_branches.assert_not_called()
    adapter.xa_commit.assert_not_called()


def test_lock_releases_when_global_already_terminal() -> None:
    lock_handle = MagicMock()
    lock_manager = MagicMock()
    lock_manager.try_acquire.return_value = lock_handle
    store = MagicMock()
    store.get_global.return_value = _global_tx("g1", state=GlobalState.COMMITTED)
    adapter = MagicMock()
    strat = DefaultRecoveryStrategy()

    n = strat.recover(
        [_global_tx("g1", decision=Decision.COMMIT)],
        [],
        adapter,
        store,
        max_age_seconds=3600,
        auto_rollback_expired=False,
        lock_manager=lock_manager,
    )

    assert n == 0
    lock_handle.release.assert_called_once()
    store.get_branches.assert_not_called()
    adapter.xa_commit.assert_not_called()


def test_inner_failure_wrapped_as_recovery_error() -> None:
    store = MagicMock()
    store.get_branches.side_effect = RuntimeError("boom")
    adapter = MagicMock()
    strat = DefaultRecoveryStrategy()

    with pytest.raises(RecoveryError, match="g1"):
        strat.recover(
            [_global_tx("g1", decision=Decision.COMMIT)],
            [],
            adapter,
            store,
            max_age_seconds=3600,
            auto_rollback_expired=False,
        )
