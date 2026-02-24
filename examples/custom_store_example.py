"""Example of using a custom store implementation with the Coordinator."""

import mysql.connector
from typing import List, Optional
from datetime import datetime, timezone
from xa_transactions import (
    XAAdapter,
    Coordinator,
    StoreProtocol,
    Decision,
    GlobalState,
    BranchState,
    GlobalTransaction,
    BranchTransaction,
)


class CustomStore:
    """Example custom store implementation using any backend you want.
    
    This could be Django ORM, SQLAlchemy, Redis, etc.
    """

    def __init__(self, connection):
        """Initialize custom store.
        
        Args:
            connection: Your backend connection (Django DB, SQLAlchemy session, etc.)
        """
        self.connection = connection
        # Initialize your schema/models here
        self.ensure_schema()

    def ensure_schema(self) -> None:
        """Ensure schema exists. Create tables/models as needed."""
        # Implement your schema creation logic
        # For Django: migrations handle this
        # For SQLAlchemy: Base.metadata.create_all()
        # For raw SQL: CREATE TABLE IF NOT EXISTS...
        pass

    def create_global(
        self,
        gtrid: str,
        expected_count: int,
        decision: Decision = Decision.UNKNOWN,
        state: GlobalState = GlobalState.ACTIVE,
    ) -> GlobalTransaction:
        """Create a global transaction record."""
        now = datetime.now(timezone.utc)
        # Implement using your backend (Django model, SQLAlchemy model, etc.)
        # Example with Django:
        #   global_tx = XAGlobal.objects.create(
        #       gtrid=gtrid,
        #       decision=decision.value,
        #       state=state.value,
        #       expected_count=expected_count,
        #       created_at=now,
        #       updated_at=now,
        #   )
        #   return self._to_global_transaction(global_tx)
        
        # For this example, we'll use a simple dict-based store
        if not hasattr(self, '_globals'):
            self._globals = {}
            self._branches = {}
        
        global_tx = GlobalTransaction(
            gtrid=gtrid,
            decision=decision,
            state=state,
            expected_count=expected_count,
            created_at=now,
            updated_at=now,
        )
        self._globals[gtrid] = global_tx
        return global_tx

    def get_global(self, gtrid: str) -> Optional[GlobalTransaction]:
        """Get global transaction by gtrid."""
        return self._globals.get(gtrid)

    def update_global(
        self,
        gtrid: str,
        decision: Optional[Decision] = None,
        state: Optional[GlobalState] = None,
        finalized_at: Optional[datetime] = None,
    ) -> None:
        """Update global transaction."""
        if gtrid not in self._globals:
            return
        global_tx = self._globals[gtrid]
        if decision is not None:
            global_tx.decision = decision
        if state is not None:
            global_tx.state = state
        if finalized_at is not None:
            global_tx.finalized_at = finalized_at
        global_tx.updated_at = datetime.now(timezone.utc)

    def create_branch(
        self,
        gtrid: str,
        bqual: str,
        state: BranchState = BranchState.EXPECTED,
        prepared_at: Optional[datetime] = None,
    ) -> BranchTransaction:
        """Create a branch transaction record."""
        now = datetime.now(timezone.utc)
        branch = BranchTransaction(
            gtrid=gtrid,
            bqual=bqual,
            state=state,
            created_at=now,
            updated_at=now,
            prepared_at=prepared_at,
        )
        self._branches[(gtrid, bqual)] = branch
        return branch

    def get_branch(
        self,
        gtrid: str,
        bqual: str,
    ) -> Optional[BranchTransaction]:
        """Get branch transaction."""
        return self._branches.get((gtrid, bqual))

    def update_branch(
        self,
        gtrid: str,
        bqual: str,
        state: Optional[BranchState] = None,
        prepared_at: Optional[datetime] = None,
    ) -> None:
        """Update branch transaction."""
        key = (gtrid, bqual)
        if key not in self._branches:
            return
        branch = self._branches[key]
        if state is not None:
            branch.state = state
        if prepared_at is not None:
            branch.prepared_at = prepared_at
        branch.updated_at = datetime.now(timezone.utc)

    def get_branches(self, gtrid: str) -> List[BranchTransaction]:
        """Get all branches for a global transaction."""
        return [
            branch for (g, b), branch in self._branches.items()
            if g == gtrid
        ]

    def get_prepared_branches(self, gtrid: str) -> List[BranchTransaction]:
        """Get all prepared branches."""
        return [
            branch for branch in self.get_branches(gtrid)
            if branch.state == BranchState.PREPARED
        ]

    def get_incomplete_globals(
        self,
        max_age_seconds: Optional[int] = None,
    ) -> List[GlobalTransaction]:
        """Get incomplete global transactions."""
        incomplete = [
            g for g in self._globals.values()
            if g.state not in (GlobalState.COMMITTED, GlobalState.ROLLED_BACK)
        ]
        if max_age_seconds:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
            incomplete = [g for g in incomplete if g.created_at < cutoff]
        return incomplete


# Type check: ensure CustomStore implements StoreProtocol
def _type_check(store: StoreProtocol) -> None:
    """Type check helper - ensures store implements the protocol."""
    pass


def main():
    """Example usage with custom store."""
    xa_conn = mysql.connector.connect(
        host="localhost",
        user="user",
        password="password",
        database="mydb",
    )

    # Create custom store (could be Django, SQLAlchemy, etc.)
    custom_store = CustomStore(connection=None)  # Your backend connection
    
    # Verify it implements the protocol (type checker will catch issues)
    _type_check(custom_store)

    # Use with Coordinator - works seamlessly!
    adapter = MySQLXAAdapter(xa_conn)
    coordinator = Coordinator(adapter, custom_store)

    # Now use coordinator as normal
    gtrid = coordinator.create_global(expected_branches=2)
    bquals = coordinator.create_branches(gtrid, count=2)
    
    print(f"Created transaction {gtrid} with branches {bquals}")
    print("Custom store implementation works!")


if __name__ == "__main__":
    from datetime import timedelta
    main()
