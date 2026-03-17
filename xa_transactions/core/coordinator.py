"""Coordinator for XA transaction management."""

from __future__ import annotations

import uuid
import time
from collections.abc import Callable
from contextlib import nullcontext
from datetime import datetime, timezone
from xa_transactions.core.adapter import MySQLXAAdapter
from xa_transactions.types.protocols import (
    Connection,
    StoreProtocol,
    XAAdapterProtocol,
    TransactionHooks,
    RecoveryStrategy,
    MetricsCollector,
    LockManager,
)
from xa_transactions.core.store import MySQLStore
from xa_transactions.observability.hooks import NoOpHooks
from xa_transactions.observability.metrics import NoOpMetrics
from xa_transactions.infrastructure.recovery import DefaultRecoveryStrategy
from xa_transactions.types.exceptions import (
    CoordinatorError,
    ValidationError,
    FinalizationError,
    LockError,
)
from xa_transactions.types.types import (
    Decision,
    GlobalState,
    BranchState,
    XID,
    GlobalTransaction,
    BranchTransaction,
)


def create_coordinator(
    adapter: XAAdapterProtocol,
    store_connection: Connection,
    branch_id_generator: Callable[[int], str] | None = None,
    hooks: TransactionHooks | None = None,
    metrics: MetricsCollector | None = None,
    lock_manager: LockManager | None = None,
    format_id: int = 1,
) -> Coordinator:
    """Convenience function to create a Coordinator with MySQLStore.

    This maintains backward compatibility with the old API where a connection
    was passed directly.

    Args:
        adapter: XA adapter for executing XA commands
        store_connection: MySQL connection for coordinator store
        branch_id_generator: Optional function to generate branch IDs
        hooks: Optional transaction lifecycle hooks
        metrics: Optional metrics collector
        lock_manager: Optional distributed lock manager
        format_id: XA format ID to distinguish this transaction manager's XIDs

    Returns:
        Coordinator instance with MySQLStore

    Example:
        coordinator = create_coordinator(adapter, store_connection)
    """
    store = MySQLStore(store_connection)
    return Coordinator(
        adapter,
        store,
        branch_id_generator=branch_id_generator,
        hooks=hooks,
        metrics=metrics,
        lock_manager=lock_manager,
        format_id=format_id,
    )


class Coordinator:
    """Main coordinator for XA transaction management."""

    def __init__(
        self,
        adapter: XAAdapterProtocol,
        store: StoreProtocol,
        branch_id_generator: Callable[[int], str] | None = None,
        hooks: TransactionHooks | None = None,
        metrics: MetricsCollector | None = None,
        recovery_strategy: RecoveryStrategy | None = None,
        lock_manager: LockManager | None = None,
        format_id: int = 1,
    ):
        """Initialize coordinator.

        Args:
            adapter: XA adapter for executing XA commands
            store: Store implementation (MySQLStore, DjangoStore, etc.)
            branch_id_generator: Optional function to generate branch IDs.
                Defaults to UUID-based generator.
            hooks: Optional transaction lifecycle hooks
            metrics: Optional metrics collector
            recovery_strategy: Optional recovery strategy (defaults to DefaultRecoveryStrategy)
            lock_manager: Optional distributed lock manager for multi-coordinator coordination.
                MUST be a distributed lock (Redis, etcd, etc.) - not a local/process lock.
                If None, assumes single-coordinator scenario (no locking).
            format_id: XA format ID to distinguish this transaction manager's XIDs.
                Per the XA spec, different transaction managers sharing a database
                should use different format_id values.
        """
        self.adapter = adapter
        self.store = store
        self.hooks = hooks or NoOpHooks()
        self.metrics = metrics or NoOpMetrics()
        self.recovery_strategy = recovery_strategy or DefaultRecoveryStrategy()
        self.lock_manager = lock_manager
        self.format_id = format_id
        self._branch_id_generator = branch_id_generator or (
            lambda idx: f"branch_{idx:04d}_{uuid.uuid4().hex[:8]}"
        )

    def create_global(self, expected_branches: int, gtrid: str | None = None) -> str:
        """Create a new global transaction.

        Args:
            expected_branches: Number of expected branches
            gtrid: Optional global transaction ID (defaults to UUID)

        Returns:
            Global transaction ID (gtrid)
        """
        if gtrid is None:
            gtrid = str(uuid.uuid4())

        self.store.create_global(
            gtrid=gtrid,
            expected_count=expected_branches,
            decision=Decision.UNKNOWN,
            state=GlobalState.ACTIVE,
        )
        self.hooks.on_global_created(gtrid, expected_branches)
        self.metrics.record_transaction_created(gtrid)
        return gtrid

    def create_branches(
        self,
        gtrid: str,
        count: int | None = None,
        bquals: list[str] | None = None,
    ) -> list[str]:
        """Create branch transaction records.

        Args:
            gtrid: Global transaction ID
            count: Number of branches to create (if bquals not provided)
            bquals: Optional list of specific branch qualifiers

        Returns:
            List of branch qualifiers

        Raises:
            ValidationError: If global transaction not found
        """
        global_tx = self.store.get_global(gtrid)
        if not global_tx:
            raise ValidationError(f"Global transaction {gtrid} not found")

        if bquals is None:
            if count is None:
                count = global_tx.expected_count
            bquals = [self._branch_id_generator(i) for i in range(count)]

        for bqual in bquals:
            self.store.create_branch(
                gtrid=gtrid,
                bqual=bqual,
                state=BranchState.EXPECTED,
            )
            self.hooks.on_branch_created(gtrid, bqual)

        return bquals

    def mark_branch_prepared(self, gtrid: str, bqual: str, duration_ms: float = 0.0) -> None:
        """Mark a branch as prepared.

        Should be called after XA PREPARE succeeds.

        Args:
            gtrid: Global transaction ID
            bqual: Branch qualifier
            duration_ms: Optional duration in milliseconds
        """
        # Optional per-branch locking (less critical than finalize)
        lock_key = f"xa:branch:{gtrid}:{bqual}"
        
        if self.lock_manager:
            lock_context = self.lock_manager.acquire(lock_key, timeout=10.0, blocking=True)
        else:
            lock_context = nullcontext()

        with lock_context:
            self.store.update_branch(
                gtrid=gtrid,
                bqual=bqual,
                state=BranchState.PREPARED,
                prepared_at=datetime.now(timezone.utc),
            )
            self.hooks.on_branch_prepared(gtrid, bqual)
            self.metrics.record_branch_prepared(gtrid, bqual, duration_ms)

    def finalize(
        self,
        gtrid: str,
        decision: Decision,
        force: bool = False,
    ) -> None:
        """Finalize a global transaction (commit or rollback).

        This operation is idempotent and restart-safe.

        Args:
            gtrid: Global transaction ID
            decision: COMMIT or ROLLBACK
            force: If True, finalize even if not all branches are prepared

        Raises:
            CoordinatorError: If finalization fails
            LockError: If lock cannot be acquired (when lock_manager is provided)
        """
        if decision == Decision.UNKNOWN:
            raise ValidationError("Cannot finalize with UNKNOWN decision")

        lock_key = f"xa:finalize:{gtrid}"
        
        # Acquire lock FIRST to prevent TOCTOU race conditions
        if self.lock_manager:
            lock_context = self.lock_manager.acquire(lock_key, timeout=60.0, blocking=True)
        else:
            # No-op context manager when no lock manager
            lock_context = nullcontext()

        with lock_context:
            # Re-check state inside lock (critical for idempotency)
            global_tx = self.store.get_global(gtrid)
            if not global_tx:
                raise CoordinatorError(f"Global transaction {gtrid} not found")

            if global_tx.state in (GlobalState.COMMITTED, GlobalState.ROLLED_BACK):
                return  # Already finalized - idempotent

            branches = self.store.get_branches(gtrid)
            prepared_branches = [b for b in branches if b.state == BranchState.PREPARED]

            if not force and len(prepared_branches) < global_tx.expected_count:
                raise ValidationError(
                    f"Not all branches prepared: {len(prepared_branches)}/{global_tx.expected_count}"
                )

            start_time = time.time()
            self.hooks.on_finalization_started(gtrid, decision)
            
            try:
                if decision == Decision.COMMIT:
                    self._commit_global(gtrid, prepared_branches)
                else:
                    self._rollback_global(gtrid, prepared_branches)
                
                duration_ms = (time.time() - start_time) * 1000
                self.hooks.on_finalization_completed(gtrid, decision)
                self.metrics.record_finalization(gtrid, decision, True, duration_ms)
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self.hooks.on_finalization_failed(gtrid, decision, e)
                self.metrics.record_finalization(gtrid, decision, False, duration_ms)
                self.metrics.record_error("finalization_failed", gtrid)
                raise

    def _commit_global(
        self,
        gtrid: str,
        branches: list[BranchTransaction],
    ) -> None:
        """Commit a global transaction.

        Args:
            gtrid: Global transaction ID
            branches: List of prepared branches to commit
        """
        self.store.update_global(
            gtrid=gtrid,
            decision=Decision.COMMIT,
            state=GlobalState.COMMITTING,
        )

        for branch in branches:
            try:
                xid = XID(gtrid=gtrid, bqual=branch.bqual, format_id=self.format_id)
                self.adapter.xa_commit(xid)
                self.store.update_branch(
                    gtrid=gtrid,
                    bqual=branch.bqual,
                    state=BranchState.COMMITTED,
                )
            except Exception as e:
                raise FinalizationError(
                    f"Failed to commit branch {branch.bqual}: {e}"
                ) from e

        self.store.update_global(
            gtrid=gtrid,
            state=GlobalState.COMMITTED,
            finalized_at=datetime.now(timezone.utc),
        )

    def _rollback_global(
        self,
        gtrid: str,
        branches: list[BranchTransaction],
    ) -> None:
        """Rollback a global transaction.

        Args:
            gtrid: Global transaction ID
            branches: List of prepared branches to rollback
        """
        self.store.update_global(
            gtrid=gtrid,
            decision=Decision.ROLLBACK,
            state=GlobalState.ROLLING_BACK,
        )

        for branch in branches:
            try:
                xid = XID(gtrid=gtrid, bqual=branch.bqual, format_id=self.format_id)
                self.adapter.xa_rollback(xid)
                self.store.update_branch(
                    gtrid=gtrid,
                    bqual=branch.bqual,
                    state=BranchState.ROLLED_BACK,
                )
            except Exception as e:
                raise FinalizationError(
                    f"Failed to rollback branch {branch.bqual}: {e}"
                ) from e

        self.store.update_global(
            gtrid=gtrid,
            state=GlobalState.ROLLED_BACK,
            finalized_at=datetime.now(timezone.utc),
        )

    def gc(
        self,
        max_age_seconds: int = 3600,
        auto_rollback_expired: bool = True,
    ) -> int:
        """Garbage collect and recover in-doubt transactions.

        Uses per-transaction locking (not global lock) to allow parallel GC
        across multiple coordinators while preventing conflicts.

        Args:
            max_age_seconds: Maximum age for transactions to consider expired
            auto_rollback_expired: If True, automatically rollback expired UNKNOWN transactions

        Returns:
            Number of transactions recovered
        """
        start_time = time.time()
        
        try:
            recovered_xids = self.adapter.xa_recover()
            incomplete_globals = self.store.get_incomplete_globals(
                max_age_seconds=max_age_seconds,
            )
            
            recovered = self.recovery_strategy.recover(
                incomplete_globals=incomplete_globals,
                recovered_xids=recovered_xids,
                adapter=self.adapter,
                store=self.store,
                max_age_seconds=max_age_seconds,
                auto_rollback_expired=auto_rollback_expired,
                lock_manager=self.lock_manager,
                format_id=self.format_id,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            self.metrics.record_gc_run(recovered, duration_ms)
            return recovered
        except Exception:
            duration_ms = (time.time() - start_time) * 1000
            self.metrics.record_error("gc_failed")
            self.metrics.record_gc_run(0, duration_ms)
            raise

    def reconcile_branch(
        self,
        gtrid: str,
        bqual: str,
        format_id: int | None = None,
    ) -> BranchState | None:
        """Reconcile branch state by checking XA RECOVER.

        Useful for determining if a branch was prepared after connection loss.
        Creates branch record if it doesn't exist in the store.

        Args:
            gtrid: Global transaction ID
            bqual: Branch qualifier
            format_id: Optional format ID to match. If None, defaults to
                self.format_id. Pass an explicit value to override.

        Returns:
            BranchState if found in XA RECOVER, None otherwise

        Note:
            This method calls xa_recover() which fetches ALL prepared transactions
            from the database. For batch reconciliation of multiple transactions,
            use gc() instead, which is more efficient.
        """
        effective_format_id = format_id if format_id is not None else self.format_id
        recovered_xids = self.adapter.xa_recover()
        
        # Search for matching XID with early exit
        matching_xid = None
        for recovered_xid in recovered_xids:
            if recovered_xid.gtrid != gtrid or recovered_xid.bqual != bqual:
                continue

            if recovered_xid.format_id != effective_format_id:
                continue

            matching_xid = recovered_xid
            break
        
        if matching_xid is None:
            return None
        
        # Branch is prepared in database - reconcile with store
        branch = self.store.get_branch(gtrid, bqual)
        prepared_time = datetime.now(timezone.utc)
        
        if not branch:
            # Branch doesn't exist in store - create it
            self.store.create_branch(
                gtrid=gtrid,
                bqual=bqual,
                state=BranchState.PREPARED,
                prepared_at=prepared_time,
            )
        elif branch.state != BranchState.PREPARED:
            # Branch exists but state is wrong - update it
            self.store.update_branch(
                gtrid=gtrid,
                bqual=bqual,
                state=BranchState.PREPARED,
                prepared_at=prepared_time,
            )
        
        return BranchState.PREPARED
