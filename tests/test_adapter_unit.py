"""Unit tests for MySQLXAAdapter SQL and XA RECOVER parsing (mocked connection)."""

from unittest.mock import MagicMock, patch

import pytest
from xa_transactions.core.adapter import MySQLXAAdapter
from xa_transactions.types.exceptions import XAAdapterError
from xa_transactions.types.types import XID


def _conn_and_cursor() -> tuple[MagicMock, MagicMock]:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


@patch("xa_transactions.integrations.django.set_xa_active")
@patch(
    "xa_transactions.integrations.django.is_django_transaction_active",
    return_value=False,
)
def test_xa_start_executes_expected_sql(
    _mock_active: MagicMock,
    _mock_set_xa: MagicMock,
) -> None:
    conn, cursor = _conn_and_cursor()
    adapter = MySQLXAAdapter(conn, format_id=3)
    xid = XID(gtrid="a", bqual="b", format_id=3)

    adapter.xa_start(xid)

    cursor.execute.assert_called_once_with(f"XA START {xid.to_sql()}")
    cursor.close.assert_called_once()


def test_xa_end_prepare_commit_rollback_sql() -> None:
    conn, cursor = _conn_and_cursor()
    adapter = MySQLXAAdapter(conn, format_id=1)
    xid = XID(gtrid="g", bqual="q", format_id=1)

    adapter.xa_end(xid)
    assert cursor.execute.call_args[0][0] == f"XA END {xid.to_sql()}"

    adapter.xa_prepare(xid)
    assert cursor.execute.call_args[0][0] == f"XA PREPARE {xid.to_sql()}"

    adapter.xa_commit(xid, one_phase=False)
    assert cursor.execute.call_args[0][0] == f"XA COMMIT {xid.to_sql()}"

    adapter.xa_commit(xid, one_phase=True)
    assert cursor.execute.call_args[0][0] == f"XA COMMIT {xid.to_sql()} ONE PHASE"

    adapter.xa_rollback(xid)
    assert cursor.execute.call_args[0][0] == f"XA ROLLBACK {xid.to_sql()}"


def test_execute_delegates_to_cursor() -> None:
    conn, cursor = _conn_and_cursor()
    adapter = MySQLXAAdapter(conn)

    adapter.execute("SELECT 1", (1,))

    cursor.execute.assert_called_with("SELECT 1", (1,))


def test_execute_raises_xa_adapter_error_on_failure() -> None:
    conn, cursor = _conn_and_cursor()
    cursor.execute.side_effect = OSError("network")
    adapter = MySQLXAAdapter(conn)

    with pytest.raises(XAAdapterError, match="SQL execution failed"):
        adapter._execute("XA RECOVER")

    cursor.close.assert_called_once()


def test_xa_recover_parses_bytes_row() -> None:
    conn, cursor = _conn_and_cursor()
    gtrid, bqual = "ab", "cd"
    data = gtrid.encode() + bqual.encode()
    cursor.fetchall.return_value = [(1, len(gtrid), len(bqual), data)]
    adapter = MySQLXAAdapter(conn)

    xids = adapter.xa_recover()

    assert xids == [XID(gtrid=gtrid, bqual=bqual, format_id=1)]
    cursor.execute.assert_called_with("XA RECOVER")


def test_xa_recover_parses_str_row() -> None:
    conn, cursor = _conn_and_cursor()
    gtrid, bqual = "xy", "zz"
    data = gtrid + bqual
    cursor.fetchall.return_value = [(2, len(gtrid), len(bqual), data)]
    adapter = MySQLXAAdapter(conn)

    xids = adapter.xa_recover()

    assert xids == [XID(gtrid=gtrid, bqual=bqual, format_id=2)]


def test_xa_recover_skips_short_rows() -> None:
    conn, cursor = _conn_and_cursor()
    cursor.fetchall.return_value = [(1, 2)]
    adapter = MySQLXAAdapter(conn)

    assert adapter.xa_recover() == []


@patch("xa_transactions.integrations.django.set_xa_active")
@patch(
    "xa_transactions.integrations.django.is_django_transaction_active",
    return_value=False,
)
def test_branch_transaction_happy_path_order(
    _mock_active: MagicMock,
    _mock_set_xa: MagicMock,
) -> None:
    conn, cursor = _conn_and_cursor()
    adapter = MySQLXAAdapter(conn, format_id=5)
    xid = XID(gtrid="G", bqual="B", format_id=5)

    with adapter.branch_transaction("G", "B"):
        pass

    sqls = [c[0][0] for c in cursor.execute.call_args_list]
    assert sqls == [
        f"XA START {xid.to_sql()}",
        f"XA END {xid.to_sql()}",
        f"XA PREPARE {xid.to_sql()}",
    ]


@patch("xa_transactions.integrations.django.set_xa_active")
@patch(
    "xa_transactions.integrations.django.is_django_transaction_active",
    return_value=False,
)
def test_branch_transaction_failure_attempts_end_and_rollback(
    _mock_active: MagicMock,
    _mock_set_xa: MagicMock,
) -> None:
    conn, cursor = _conn_and_cursor()
    adapter = MySQLXAAdapter(conn)
    xid = XID(gtrid="G", bqual="B", format_id=1)

    def fail_on_prepare(sql: str, params: object | None = None) -> MagicMock:
        if "XA PREPARE" in sql:
            raise RuntimeError("prepare failed")
        return cursor

    cursor.execute.side_effect = fail_on_prepare

    with pytest.raises(XAAdapterError, match="prepare failed"):
        with adapter.branch_transaction("G", "B"):
            pass

    executed = [c[0][0] for c in cursor.execute.call_args_list]
    assert executed[0] == f"XA START {xid.to_sql()}"
    assert f"XA END {xid.to_sql()}" in executed
    assert f"XA ROLLBACK {xid.to_sql()}" in executed
