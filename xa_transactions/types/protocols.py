"""Protocol definitions for pluggable implementations."""

from typing import Protocol, List, Optional, Tuple, Any
from contextlib import contextmanager
from datetime import datetime
from xa_transactions.types.types import (
    Decision,
    GlobalState,
    BranchState,
    GlobalTransaction,
    BranchTransaction,
    XID,
)


class StoreProtocol(Protocol):
    """Protocol for coordinator store implementations.

    This protocol allows any store implementation (MySQL, Django, SQLAlchemy, etc.)
    to be used with the Coordinator. All methods must be implemented.
    """

    def ensure_schema(self) -> None:
        """Ensure schema tables exist.

        This method should create the necessary tables/schema if they don't exist.
        It's called automatically during initialization.
        """
        ...

    def create_global(
        self,
        gtrid: str,
        expected_count: int,
        decision: Decision = Decision.UNKNOWN,
        state: GlobalState = GlobalState.ACTIVE,
    ) -> GlobalTransaction:
        """Create a global transaction record.

        Args:
            gtrid: Global transaction ID
            expected_count: Expected number of branches
            decision: Initial decision (default: UNKNOWN)
            state: Initial state (default: ACTIVE)

        Returns:
            GlobalTransaction record

        Raises:
            Exception: If creation fails
        """
        ...

    def get_global(self, gtrid: str) -> Optional[GlobalTransaction]:
        """Get global transaction by gtrid.

        Args:
            gtrid: Global transaction ID

        Returns:
            GlobalTransaction or None if not found
        """
        ...

    def update_global(
        self,
        gtrid: str,
        decision: Optional[Decision] = None,
        state: Optional[GlobalState] = None,
        finalized_at: Optional[datetime] = None,
    ) -> None:
        """Update global transaction.

        Args:
            gtrid: Global transaction ID
            decision: New decision (optional)
            state: New state (optional)
            finalized_at: Finalization timestamp (optional)
        """
        ...

    def create_branch(
        self,
        gtrid: str,
        bqual: str,
        state: BranchState = BranchState.EXPECTED,
        prepared_at: Optional[datetime] = None,
    ) -> BranchTransaction:
        """Create a branch transaction record.

        Args:
            gtrid: Global transaction ID
            bqual: Branch qualifier
            state: Initial state (default: EXPECTED)
            prepared_at: Optional preparation timestamp

        Returns:
            BranchTransaction record

        Raises:
            Exception: If creation fails
        """
        ...

    def get_branch(
        self,
        gtrid: str,
        bqual: str,
    ) -> Optional[BranchTransaction]:
        """Get branch transaction.

        Args:
            gtrid: Global transaction ID
            bqual: Branch qualifier

        Returns:
            BranchTransaction or None if not found
        """
        ...

    def update_branch(
        self,
        gtrid: str,
        bqual: str,
        state: Optional[BranchState] = None,
        prepared_at: Optional[datetime] = None,
    ) -> None:
        """Update branch transaction.

        Args:
            gtrid: Global transaction ID
            bqual: Branch qualifier
            state: New state (optional)
            prepared_at: Preparation timestamp (optional)
        """
        ...

    def get_branches(self, gtrid: str) -> List[BranchTransaction]:
        """Get all branches for a global transaction.

        Args:
            gtrid: Global transaction ID

        Returns:
            List of BranchTransaction records
        """
        ...

    def get_prepared_branches(self, gtrid: str) -> List[BranchTransaction]:
        """Get all prepared branches for a global transaction.

        Args:
            gtrid: Global transaction ID

        Returns:
            List of prepared BranchTransaction records
        """
        ...

    def get_incomplete_globals(
        self,
        max_age_seconds: Optional[int] = None,
    ) -> List[GlobalTransaction]:
        """Get incomplete global transactions.

        Args:
            max_age_seconds: Optional maximum age filter

        Returns:
            List of incomplete GlobalTransaction records
        """
        ...


class Connection(Protocol):
    """Protocol for database connection objects."""

    def cursor(self) -> Any:
        """Get a cursor for executing SQL."""
        ...

    def commit(self) -> None:
        """Commit the current transaction."""
        ...

    def rollback(self) -> None:
        """Rollback the current transaction."""
        ...

    def close(self) -> None:
        """Close the connection."""
        ...


class ConnectionFactory(Protocol):
    """Protocol for connection management.

    Allows connection pooling, reuse, and custom connection strategies.
    """

    def get_connection(self) -> Connection:
        """Get a database connection.

        Returns:
            Database connection object

        Raises:
            Exception: If connection cannot be obtained
        """
        ...

    def return_connection(self, connection: Connection) -> None:
        """Return a connection to the pool/factory.

        Args:
            connection: Connection to return
        """
        ...


class XAAdapterProtocol(Protocol):
    """Protocol for XA adapter implementations.

    Allows different database implementations (MySQL, PostgreSQL, etc.)
    to provide XA transaction support.
    """

    def xa_start(self, xid: XID, auto_commit_django: bool = False) -> None:
        """Start an XA transaction.

        Args:
            xid: XA transaction ID
            auto_commit_django: If True, auto-commits Django transaction if active.
                Default: False (raises error if Django transaction is active)

        Raises:
            XAAdapterError: If XA START fails or Django transaction is active
        """
        ...

    def xa_end(self, xid: XID) -> None:
        """End an XA transaction (suspend it).

        Args:
            xid: XA transaction ID

        Raises:
            XAAdapterError: If XA END fails
        """
        ...

    def xa_prepare(self, xid: XID) -> None:
        """Prepare an XA transaction for commit.

        Args:
            xid: XA transaction ID

        Raises:
            XAAdapterError: If XA PREPARE fails
        """
        ...

    def xa_commit(self, xid: XID, one_phase: bool = False) -> None:
        """Commit an XA transaction.

        Args:
            xid: XA transaction ID
            one_phase: If True, use one-phase commit (skip PREPARE)

        Raises:
            XAAdapterError: If XA COMMIT fails
        """
        ...

    def xa_rollback(self, xid: XID) -> None:
        """Rollback an XA transaction.

        Args:
            xid: XA transaction ID

        Raises:
            XAAdapterError: If XA ROLLBACK fails
        """
        ...

    def xa_recover(self) -> List[XID]:
        """Recover prepared XA transactions.

        Returns:
            List of XID tuples for prepared transactions

        Raises:
            XAAdapterError: If XA RECOVER fails
        """
        ...

    def execute(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> Any:
        """Execute a regular SQL statement within the current XA transaction.

        Args:
            sql: SQL statement
            params: Optional parameters

        Returns:
            Cursor result

        Raises:
            XAAdapterError: If execution fails
        """
        ...


class TransactionHooks(Protocol):
    """Protocol for transaction lifecycle hooks.

    Allows observing and intercepting transaction lifecycle events.
    """

    def on_global_created(self, gtrid: str, expected_count: int) -> None:
        """Called when a global transaction is created.

        Args:
            gtrid: Global transaction ID
            expected_count: Expected number of branches
        """
        ...

    def on_branch_created(self, gtrid: str, bqual: str) -> None:
        """Called when a branch is created.

        Args:
            gtrid: Global transaction ID
            bqual: Branch qualifier
        """
        ...

    def on_branch_prepared(self, gtrid: str, bqual: str) -> None:
        """Called when a branch is successfully prepared.

        Args:
            gtrid: Global transaction ID
            bqual: Branch qualifier
        """
        ...

    def on_finalization_started(
        self,
        gtrid: str,
        decision: Decision,
    ) -> None:
        """Called when finalization (commit/rollback) starts.

        Args:
            gtrid: Global transaction ID
            decision: COMMIT or ROLLBACK
        """
        ...

    def on_finalization_completed(
        self,
        gtrid: str,
        decision: Decision,
    ) -> None:
        """Called when finalization (commit/rollback) completes successfully.

        Args:
            gtrid: Global transaction ID
            decision: COMMIT or ROLLBACK
        """
        ...

    def on_finalization_failed(
        self,
        gtrid: str,
        decision: Decision,
        error: Exception,
    ) -> None:
        """Called when finalization (commit/rollback) fails.

        Args:
            gtrid: Global transaction ID
            decision: COMMIT or ROLLBACK
            error: The exception that occurred
        """
        ...


class RecoveryStrategy(Protocol):
    """Protocol for recovery strategies.

    Allows pluggable recovery/garbage collection strategies.
    """

    def recover(
        self,
        incomplete_globals: List[GlobalTransaction],
        recovered_xids: List[XID],
        adapter: XAAdapterProtocol,
        store: StoreProtocol,
        max_age_seconds: int,
        auto_rollback_expired: bool,
    ) -> int:
        """Recover in-doubt transactions.

        Args:
            incomplete_globals: List of incomplete global transactions
            recovered_xids: List of XIDs from XA RECOVER
            adapter: XA adapter for executing XA commands
            store: Store for updating state
            max_age_seconds: Maximum age for expired transactions
            auto_rollback_expired: If True, auto-rollback expired UNKNOWN transactions

        Returns:
            Number of transactions recovered
        """
        ...


class MetricsCollector(Protocol):
    """Protocol for metrics collection and monitoring.

    Allows integration with monitoring systems (Prometheus, StatsD, etc.).
    """

    def record_transaction_created(self, gtrid: str) -> None:
        """Record that a transaction was created.

        Args:
            gtrid: Global transaction ID
        """
        ...

    def record_branch_prepared(
        self,
        gtrid: str,
        bqual: str,
        duration_ms: float,
    ) -> None:
        """Record that a branch was prepared.

        Args:
            gtrid: Global transaction ID
            bqual: Branch qualifier
            duration_ms: Time taken to prepare in milliseconds
        """
        ...

    def record_finalization(
        self,
        gtrid: str,
        decision: Decision,
        success: bool,
        duration_ms: float,
    ) -> None:
        """Record a finalization attempt.

        Args:
            gtrid: Global transaction ID
            decision: COMMIT or ROLLBACK
            success: Whether finalization succeeded
            duration_ms: Time taken in milliseconds
        """
        ...

    def record_gc_run(
        self,
        recovered_count: int,
        duration_ms: float,
    ) -> None:
        """Record a garbage collection run.

        Args:
            recovered_count: Number of transactions recovered
            duration_ms: Time taken in milliseconds
        """
        ...

    def record_error(
        self,
        error_type: str,
        gtrid: Optional[str] = None,
    ) -> None:
        """Record an error occurrence.

        Args:
            error_type: Type of error (e.g., 'finalization_failed')
            gtrid: Optional global transaction ID
        """
        ...


class LockHandle(Protocol):
    """Handle to an acquired distributed lock.

    Used for lock renewal and explicit release. Can be used as a context manager.
    """

    def __enter__(self) -> "LockHandle":
        """Enter context manager."""
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and release lock."""
        ...

    def renew(self, additional_time: float) -> bool:
        """Renew the lock by extending its expiration time.

        Args:
            additional_time: Additional time in seconds to extend the lock

        Returns:
            True if renewal succeeded, False otherwise
        """
        ...

    def release(self) -> None:
        """Explicitly release the lock.

        Note: Locks are automatically released when exiting the context manager,
        but this allows explicit release if needed.
        """
        ...


class LockManager(Protocol):
    """Protocol for distributed lock managers.

    IMPORTANT: This protocol is for DISTRIBUTED locks that work across
    multiple coordinator instances. Single-process or connection-local locks
    are NOT sufficient for multi-coordinator scenarios.

    Implementations should use distributed systems like:
    - Redis with SET NX EX
    - etcd/Consul with TTL
    - Database advisory locks (if shared across instances)
    - Zookeeper
    """

    @contextmanager
    def acquire(
        self,
        key: str,
        timeout: Optional[float] = None,
        blocking: bool = True,
    ):
        """Acquire a distributed lock.

        Args:
            key: Lock key (should be namespaced, e.g., "xa:finalize:{gtrid}")
            timeout: Lock duration in seconds. If None, uses implementation default.
                The lock will automatically expire after this time.
            blocking: If True, block until lock is acquired or timeout.
                If False, raise LockError immediately if lock unavailable.

        Yields:
            LockHandle for lock renewal or explicit release

        Raises:
            LockError: If lock cannot be acquired (when blocking=False or timeout exceeded)

        Example:
            with lock_manager.acquire("xa:finalize:123", timeout=30.0):
                # Critical section - lock is held
                do_work()
        """
        ...

    def try_acquire(
        self,
        key: str,
        timeout: Optional[float] = None,
    ) -> Optional[LockHandle]:
        """Try to acquire a lock without blocking.

        Args:
            key: Lock key
            timeout: Lock duration in seconds

        Returns:
            LockHandle if lock was acquired, None if lock is already held

        Example:
            handle = lock_manager.try_acquire("xa:finalize:123")
            if handle:
                try:
                    do_work()
                finally:
                    handle.release()
        """
        ...
