"""Unit tests for pure types (no DB, no optional integrations)."""

from datetime import datetime, timezone

from xa_transactions.types import (
    XID,
    BranchState,
    BranchTransaction,
    Decision,
    GlobalState,
    GlobalTransaction,
)


def test_decision_enum_values() -> None:
    assert Decision.COMMIT.value == "COMMIT"
    assert Decision.ROLLBACK.value == "ROLLBACK"
    assert Decision.UNKNOWN.value == "UNKNOWN"


def test_global_state_and_branch_state_enum() -> None:
    assert GlobalState.ACTIVE.value == "ACTIVE"
    assert GlobalState.COMMITTED.value == "COMMITTED"
    assert BranchState.PREPARED.value == "PREPARED"


def test_xid_str_and_sql() -> None:
    xid = XID(gtrid="g1", bqual="b1", format_id=1)
    assert "'g1','b1',1" in str(xid)
    assert xid.to_sql() == str(xid)


def test_xid_default_format_id() -> None:
    xid = XID(gtrid="a", bqual="b")
    assert xid.format_id == 1


def test_xid_nondefault_format_id() -> None:
    xid = XID(gtrid="x", bqual="y", format_id=42)
    assert str(xid) == "'x','y',42"


def test_global_and_branch_dataclasses() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    g = GlobalTransaction(
        gtrid="g",
        decision=Decision.UNKNOWN,
        state=GlobalState.ACTIVE,
        expected_count=2,
        created_at=now,
        updated_at=now,
    )
    assert g.expected_count == 2
    assert g.finalized_at is None

    b = BranchTransaction(
        gtrid="g",
        bqual="b1",
        state=BranchState.EXPECTED,
        created_at=now,
        updated_at=now,
    )
    assert b.prepared_at is None
