"""Recovery strategy implementations."""

from typing import List, Optional
from contextlib import nullcontext
from datetime import datetime, timezone
from xa_transactions.types.protocols import (
    RecoveryStrategy,
    XAAdapterProtocol,
    StoreProtocol,
    LockManager,
)
from xa_transactions.types.types import (
    Decision,
    GlobalState,
    BranchState,
    XID,
    GlobalTransaction,
    BranchTransaction,
)
from xa_transactions.types.exceptions import RecoveryError, FinalizationError


class DefaultRecoveryStrategy:
    """Default recovery strategy implementation.

    Implements the standard recovery logic:
    - Reconciles XA RECOVER with store
    - Finalizes transactions based on decision
    - Auto-rollbacks expired UNKNOWN transactions
    """

    def recover(
        self,
        incomplete_globals: List[GlobalTransaction],
        recovered_xids: List[XID],
        adapter: XAAdapterProtocol,
        store: StoreProtocol,
        max_age_seconds: int,
        auto_rollback_expired: bool,
        lock_manager: Optional[LockManager] = None,
    ) -> int:
        """Recover in-doubt transactions.

        Args:
            incomplete_globals: List of incomplete global transactions
            recovered_xids: List of XIDs from XA RECOVER
            adapter: XA adapter for executing XA commands
            store: Store for updating state
            max_age_seconds: Maximum age for expired transactions
            auto_rollback_expired: If True, auto-rollback expired UNKNOWN transactions
            lock_manager: Optional lock manager for per-transaction locking

        Returns:
            Number of transactions recovered

        Raises:
            RecoveryError: If recovery fails
        """
        recovered = 0
        recovered_gtrids = {xid.gtrid for xid in recovered_xids}

        for global_tx in incomplete_globals:
            if global_tx.state in (GlobalState.COMMITTED, GlobalState.ROLLED_BACK):
                continue

            # Use per-transaction locking if lock manager provided
            lock_key = f"xa:finalize:{global_tx.gtrid}"
            
            if lock_manager:
                lock_handle = lock_manager.try_acquire(lock_key, timeout=60.0)
                if not lock_handle:
                    # Another coordinator is handling this transaction
                    continue
                # Re-check state inside lock
                current_tx = store.get_global(global_tx.gtrid)
                if not current_tx or current_tx.state in (GlobalState.COMMITTED, GlobalState.ROLLED_BACK):
                    lock_handle.release()
                    continue
                # Use lock handle as context manager for automatic release
                lock_context = lock_handle
            else:
                lock_context = nullcontext()

            with lock_context:
                try:
                    branches = store.get_branches(global_tx.gtrid)
                    prepared_branches = [
                        b for b in branches if b.state == BranchState.PREPARED
                    ]

                    # Reconcile with XA RECOVER
                    if global_tx.gtrid in recovered_gtrids:
                        recovered_xids_for_gtrid = [
                            xid for xid in recovered_xids if xid.gtrid == global_tx.gtrid
                        ]

                        for xid in recovered_xids_for_gtrid:
                            branch = next(
                                (b for b in branches if b.bqual == xid.bqual), None
                            )
                            if branch and branch.state != BranchState.PREPARED:
                                store.update_branch(
                                    gtrid=global_tx.gtrid,
                                    bqual=xid.bqual,
                                    state=BranchState.PREPARED,
                                    prepared_at=datetime.now(timezone.utc),
                                )
                                prepared_branches.append(
                                    BranchTransaction(
                                        gtrid=global_tx.gtrid,
                                        bqual=xid.bqual,
                                        state=BranchState.PREPARED,
                                        created_at=datetime.now(timezone.utc),
                                        updated_at=datetime.now(timezone.utc),
                                        prepared_at=datetime.now(timezone.utc),
                                    )
                                )

                    # Finalize based on decision
                    if global_tx.decision == Decision.COMMIT:
                        if prepared_branches:
                            self._commit_global(
                                global_tx.gtrid, prepared_branches, adapter, store
                            )
                            recovered += 1
                    elif global_tx.decision == Decision.ROLLBACK:
                        if prepared_branches:
                            self._rollback_global(
                                global_tx.gtrid, prepared_branches, adapter, store
                            )
                            recovered += 1
                    elif global_tx.decision == Decision.UNKNOWN:
                        if auto_rollback_expired:
                            age = datetime.now(timezone.utc) - global_tx.created_at
                            if age.total_seconds() > max_age_seconds:
                                store.update_global(
                                    gtrid=global_tx.gtrid,
                                    decision=Decision.ROLLBACK,
                                )
                                if prepared_branches:
                                    self._rollback_global(
                                        global_tx.gtrid,
                                        prepared_branches,
                                        adapter,
                                        store,
                                    )
                                    recovered += 1
                except Exception as e:
                    raise RecoveryError(
                        f"Recovery failed for gtrid {global_tx.gtrid}: {e}"
                    ) from e

    def _commit_global(
        self,
        gtrid: str,
        branches: List[BranchTransaction],
        adapter: XAAdapterProtocol,
        store: StoreProtocol,
    ) -> None:
        """Commit a global transaction."""
        store.update_global(
            gtrid=gtrid,
            decision=Decision.COMMIT,
            state=GlobalState.COMMITTING,
        )

        for branch in branches:
            try:
                xid = XID(gtrid=gtrid, bqual=branch.bqual)
                adapter.xa_commit(xid)
                store.update_branch(
                    gtrid=gtrid,
                    bqual=branch.bqual,
                    state=BranchState.COMMITTED,
                )
            except Exception as e:
                raise FinalizationError(
                    f"Failed to commit branch {branch.bqual}: {e}"
                ) from e

        store.update_global(
            gtrid=gtrid,
            state=GlobalState.COMMITTED,
            finalized_at=datetime.now(timezone.utc),
        )

    def _rollback_global(
        self,
        gtrid: str,
        branches: List[BranchTransaction],
        adapter: XAAdapterProtocol,
        store: StoreProtocol,
    ) -> None:
        """Rollback a global transaction."""
        store.update_global(
            gtrid=gtrid,
            decision=Decision.ROLLBACK,
            state=GlobalState.ROLLING_BACK,
        )

        for branch in branches:
            try:
                xid = XID(gtrid=gtrid, bqual=branch.bqual)
                adapter.xa_rollback(xid)
                store.update_branch(
                    gtrid=gtrid,
                    bqual=branch.bqual,
                    state=BranchState.ROLLED_BACK,
                )
            except Exception as e:
                raise FinalizationError(
                    f"Failed to rollback branch {branch.bqual}: {e}"
                ) from e

        store.update_global(
            gtrid=gtrid,
            state=GlobalState.ROLLED_BACK,
            finalized_at=datetime.now(timezone.utc),
        )
