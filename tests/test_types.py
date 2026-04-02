"""Unit tests for pure types (no DB, no optional integrations)."""

from xa_transactions.types import XID, Decision


def test_decision_enum_values() -> None:
    assert Decision.COMMIT.value == "COMMIT"
    assert Decision.ROLLBACK.value == "ROLLBACK"


def test_xid_str_and_sql() -> None:
    xid = XID(gtrid="g1", bqual="b1", format_id=1)
    assert "'g1','b1',1" in str(xid)
    assert xid.to_sql() == str(xid)
