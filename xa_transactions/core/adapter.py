"""MySQL XA adapter implementation."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from contextlib import contextmanager
from xa_transactions.types.types import XID
from xa_transactions.types.protocols import Connection, XAAdapterProtocol
from xa_transactions.types.exceptions import XAAdapterError


class MySQLXAAdapter:
    """MySQL implementation of XA adapter.

    Driver-agnostic adapter for MySQL XA operations.
    Works with mysql.connector, PyMySQL, mysqlclient, etc.
    """

    def __init__(self, connection: Connection, format_id: int = 1):
        """Initialize MySQL XA adapter.

        Args:
            connection: MySQL connection object (mysql.connector, PyMySQL, etc.)
            format_id: XA format ID to use when constructing XIDs
        """
        self.connection = connection
        self.format_id = format_id

    def _execute(self, sql: str, params: tuple[Any, ...] | None = None) -> Any:
        """Execute SQL statement.

        Args:
            sql: SQL statement
            params: Optional parameters for parameterized queries

        Returns:
            Cursor result

        Raises:
            XAAdapterError: If execution fails
        """
        cursor = self.connection.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return cursor
        except Exception as e:
            cursor.close()
            raise XAAdapterError(f"SQL execution failed: {e}") from e

    def xa_start(self, xid: XID, auto_commit_django: bool = False) -> None:
        """Start an XA transaction.

        Args:
            xid: XA transaction ID
            auto_commit_django: If True, auto-commits Django transaction if active.
                Default: False (raises error if Django transaction is active)

        Raises:
            XAAdapterError: If XA START fails or Django transaction is active
        """
        # Check for Django transaction
        try:
            from xa_transactions.integrations.django import is_django_transaction_active
            
            if is_django_transaction_active():
                if not auto_commit_django:
                    raise XAAdapterError(
                        "Cannot start XA transaction while Django transaction is active. "
                        "XA transactions must be the outer transaction. "
                        "Either exit the Django transaction first, or use auto_commit_django=True"
                    )
                # Auto-commit Django transaction if requested
                try:
                    from django.db import transaction
                    transaction.commit()
                except Exception as e:
                    raise XAAdapterError(
                        f"Failed to commit Django transaction before XA START: {e}"
                    ) from e
        except ImportError:
            pass  # Django not available
        
        try:
            sql = f"XA START {xid.to_sql()}"
            cursor = self._execute(sql)
            cursor.close()
        except XAAdapterError:
            raise
        except Exception as e:
            raise XAAdapterError(f"XA START failed: {e}") from e

    def xa_end(self, xid: XID) -> None:
        """End an XA transaction (suspend it).

        Args:
            xid: XA transaction ID

        Raises:
            XAAdapterError: If XA END fails
        """
        try:
            sql = f"XA END {xid.to_sql()}"
            cursor = self._execute(sql)
            cursor.close()
        except XAAdapterError:
            raise
        except Exception as e:
            raise XAAdapterError(f"XA END failed: {e}") from e

    def xa_prepare(self, xid: XID) -> None:
        """Prepare an XA transaction for commit.

        Args:
            xid: XA transaction ID

        Raises:
            XAAdapterError: If XA PREPARE fails
        """
        try:
            sql = f"XA PREPARE {xid.to_sql()}"
            cursor = self._execute(sql)
            cursor.close()
        except XAAdapterError:
            raise
        except Exception as e:
            raise XAAdapterError(f"XA PREPARE failed: {e}") from e

    def xa_commit(self, xid: XID, one_phase: bool = False) -> None:
        """Commit an XA transaction.

        Args:
            xid: XA transaction ID
            one_phase: If True, use one-phase commit (skip PREPARE)

        Raises:
            XAAdapterError: If XA COMMIT fails
        """
        try:
            phase = "ONE PHASE" if one_phase else ""
            sql = f"XA COMMIT {xid.to_sql()} {phase}".strip()
            cursor = self._execute(sql)
            cursor.close()
        except XAAdapterError:
            raise
        except Exception as e:
            raise XAAdapterError(f"XA COMMIT failed: {e}") from e

    def xa_rollback(self, xid: XID) -> None:
        """Rollback an XA transaction.

        Args:
            xid: XA transaction ID

        Raises:
            XAAdapterError: If XA ROLLBACK fails
        """
        try:
            sql = f"XA ROLLBACK {xid.to_sql()}"
            cursor = self._execute(sql)
            cursor.close()
        except XAAdapterError:
            raise
        except Exception as e:
            raise XAAdapterError(f"XA ROLLBACK failed: {e}") from e

    def xa_recover(self) -> list[XID]:
        """Recover prepared XA transactions.

        Returns:
            List of XID tuples for prepared transactions

        Raises:
            XAAdapterError: If XA RECOVER fails
        """
        try:
            sql = "XA RECOVER"
            cursor = self._execute(sql)
            try:
                rows = cursor.fetchall()
                xids = []
                for row in rows:
                    if len(row) < 4:
                        continue
                    format_id, gtrid_len, bqual_len, data = row[0], row[1], row[2], row[3]
                    
                    if isinstance(data, bytes):
                        gtrid = data[:gtrid_len].decode("utf-8")
                        bqual = data[gtrid_len : gtrid_len + bqual_len].decode("utf-8")
                    elif isinstance(data, str):
                        gtrid = data[:gtrid_len]
                        bqual = data[gtrid_len : gtrid_len + bqual_len]
                    else:
                        continue
                        
                    xids.append(XID(gtrid=gtrid, bqual=bqual, format_id=format_id))
                return xids
            finally:
                cursor.close()
        except XAAdapterError:
            raise
        except Exception as e:
            raise XAAdapterError(f"XA RECOVER failed: {e}") from e

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> Any:
        """Execute a regular SQL statement within the current XA transaction.

        Args:
            sql: SQL statement
            params: Optional parameters

        Returns:
            Cursor result
        """
        return self._execute(sql, params)

    @contextmanager
    def branch_transaction(self, gtrid: str, bqual: str, auto_commit_django: bool = False) -> Generator[MySQLXAAdapter, None, None]:
        """Context manager for a branch transaction.

        Automatically handles XA START, END, and PREPARE.
        Also tracks XA state for Django integration.

        Args:
            gtrid: Global transaction ID
            bqual: Branch qualifier
            auto_commit_django: If True, auto-commits Django transaction if active.
                Default: False (raises error if Django transaction is active)

        Yields:
            Self for executing SQL statements

        Example:
            with adapter.branch_transaction(gtrid, bqual):
                adapter.execute("INSERT INTO ...")
        """
        xid = XID(gtrid=gtrid, bqual=bqual, format_id=self.format_id)
        
        # Set XA state for Django integration
        try:
            from xa_transactions.integrations.django import set_xa_active
            set_xa_active(True)
        except ImportError:
            pass  # Django not available
        
        try:
            self.xa_start(xid, auto_commit_django=auto_commit_django)
            yield self
            self.xa_end(xid)
            self.xa_prepare(xid)
        except Exception:
            try:
                self.xa_end(xid)
            except XAAdapterError:
                pass
            try:
                self.xa_rollback(xid)
            except XAAdapterError:
                pass
            raise
        finally:
            # Clear XA state
            try:
                from xa_transactions.integrations.django import set_xa_active
                set_xa_active(False)
            except ImportError:
                pass


# Backward compatibility alias
XAAdapter = MySQLXAAdapter
