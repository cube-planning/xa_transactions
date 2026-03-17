"""MySQL-based coordinator store implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from xa_transactions.types.types import (
    Decision,
    GlobalState,
    BranchState,
    GlobalTransaction,
    BranchTransaction,
)
from xa_transactions.types.protocols import Connection, StoreProtocol
from xa_transactions.types.exceptions import StoreError


class MySQLStore:
    """MySQL-based implementation of coordinator store.

    Uses raw SQL with MySQL connection. This is the default implementation.
    """

    def __init__(self, connection: Connection):
        """Initialize MySQL store.

        Args:
            connection: MySQL connection for the coordinator store
        """
        self.connection = connection
        self.ensure_schema()

    def ensure_schema(self) -> None:
        """Create schema tables if they don't exist."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS xa_global (
                    gtrid VARCHAR(255) PRIMARY KEY,
                    decision VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
                    state VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                    expected_count INT NOT NULL,
                    created_at DATETIME(6) NOT NULL,
                    updated_at DATETIME(6) NOT NULL,
                    finalized_at DATETIME(6) NULL,
                    INDEX idx_decision (decision),
                    INDEX idx_state (state),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS xa_branch (
                    gtrid VARCHAR(255) NOT NULL,
                    bqual VARCHAR(255) NOT NULL,
                    state VARCHAR(20) NOT NULL DEFAULT 'EXPECTED',
                    created_at DATETIME(6) NOT NULL,
                    updated_at DATETIME(6) NOT NULL,
                    prepared_at DATETIME(6) NULL,
                    PRIMARY KEY (gtrid, bqual),
                    INDEX idx_gtrid (gtrid),
                    INDEX idx_state (state),
                    FOREIGN KEY (gtrid) REFERENCES xa_global(gtrid) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

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
            StoreError: If creation fails
        """
        now = datetime.now(timezone.utc)
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO xa_global
                (gtrid, decision, state, expected_count, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (gtrid, decision.value, state.value, expected_count, now, now))
            self.connection.commit()
            return GlobalTransaction(
                gtrid=gtrid,
                decision=decision,
                state=state,
                expected_count=expected_count,
                created_at=now,
                updated_at=now,
            )
        except Exception as e:
            self.connection.rollback()
            raise StoreError(f"Failed to create global transaction: {e}") from e
        finally:
            cursor.close()

    def get_global(self, gtrid: str) -> GlobalTransaction | None:
        """Get global transaction by gtrid.

        Args:
            gtrid: Global transaction ID

        Returns:
            GlobalTransaction or None if not found
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT gtrid, decision, state, expected_count,
                       created_at, updated_at, finalized_at
                FROM xa_global
                WHERE gtrid = %s
            """, (gtrid,))
            row = cursor.fetchone()
            if not row:
                return None
            return GlobalTransaction(
                gtrid=row[0],
                decision=Decision(row[1]),
                state=GlobalState(row[2]),
                expected_count=row[3],
                created_at=row[4],
                updated_at=row[5],
                finalized_at=row[6],
            )
        finally:
            cursor.close()

    def update_global(
        self,
        gtrid: str,
        decision: Decision | None = None,
        state: GlobalState | None = None,
        finalized_at: datetime | None = None,
    ) -> None:
        """Update global transaction.

        Args:
            gtrid: Global transaction ID
            decision: New decision (optional)
            state: New state (optional)
            finalized_at: Finalization timestamp (optional)
        """
        updates = []
        params = []
        if decision is not None:
            updates.append("decision = %s")
            params.append(decision.value)
        if state is not None:
            updates.append("state = %s")
            params.append(state.value)
        if finalized_at is not None:
            updates.append("finalized_at = %s")
            params.append(finalized_at)
        updates.append("updated_at = %s")
        params.append(datetime.now(timezone.utc))
        params.append(gtrid)

        cursor = self.connection.cursor()
        try:
            cursor.execute(
                f"UPDATE xa_global SET {', '.join(updates)} WHERE gtrid = %s",
                params,
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def create_branch(
        self,
        gtrid: str,
        bqual: str,
        state: BranchState = BranchState.EXPECTED,
        prepared_at: datetime | None = None,
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
            StoreError: If creation fails
        """
        now = datetime.now(timezone.utc)
        cursor = self.connection.cursor()
        try:
            if prepared_at is not None:
                cursor.execute("""
                    INSERT INTO xa_branch
                    (gtrid, bqual, state, created_at, updated_at, prepared_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (gtrid, bqual, state.value, now, now, prepared_at))
            else:
                cursor.execute("""
                    INSERT INTO xa_branch
                    (gtrid, bqual, state, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                """, (gtrid, bqual, state.value, now, now))
            self.connection.commit()
            return BranchTransaction(
                gtrid=gtrid,
                bqual=bqual,
                state=state,
                created_at=now,
                updated_at=now,
                prepared_at=prepared_at,
            )
        except Exception as e:
            self.connection.rollback()
            raise StoreError(f"Failed to create branch: {e}") from e
        finally:
            cursor.close()

    def get_branch(self, gtrid: str, bqual: str) -> BranchTransaction | None:
        """Get branch transaction.

        Args:
            gtrid: Global transaction ID
            bqual: Branch qualifier

        Returns:
            BranchTransaction or None if not found
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT gtrid, bqual, state, created_at, updated_at, prepared_at
                FROM xa_branch
                WHERE gtrid = %s AND bqual = %s
            """, (gtrid, bqual))
            row = cursor.fetchone()
            if not row:
                return None
            return BranchTransaction(
                gtrid=row[0],
                bqual=row[1],
                state=BranchState(row[2]),
                created_at=row[3],
                updated_at=row[4],
                prepared_at=row[5],
            )
        finally:
            cursor.close()

    def update_branch(
        self,
        gtrid: str,
        bqual: str,
        state: BranchState | None = None,
        prepared_at: datetime | None = None,
    ) -> None:
        """Update branch transaction.

        Args:
            gtrid: Global transaction ID
            bqual: Branch qualifier
            state: New state (optional)
            prepared_at: Preparation timestamp (optional)
        """
        updates = []
        params = []
        if state is not None:
            updates.append("state = %s")
            params.append(state.value)
        if prepared_at is not None:
            updates.append("prepared_at = %s")
            params.append(prepared_at)
        updates.append("updated_at = %s")
        params.append(datetime.now(timezone.utc))
        params.extend([gtrid, bqual])

        cursor = self.connection.cursor()
        try:
            cursor.execute(
                f"UPDATE xa_branch SET {', '.join(updates)} WHERE gtrid = %s AND bqual = %s",
                params,
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def get_branches(self, gtrid: str) -> list[BranchTransaction]:
        """Get all branches for a global transaction.

        Args:
            gtrid: Global transaction ID

        Returns:
            List of BranchTransaction records
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT gtrid, bqual, state, created_at, updated_at, prepared_at
                FROM xa_branch
                WHERE gtrid = %s
                ORDER BY bqual
            """, (gtrid,))
            rows = cursor.fetchall()
            return [
                BranchTransaction(
                    gtrid=row[0],
                    bqual=row[1],
                    state=BranchState(row[2]),
                    created_at=row[3],
                    updated_at=row[4],
                    prepared_at=row[5],
                )
                for row in rows
            ]
        finally:
            cursor.close()

    def get_prepared_branches(self, gtrid: str) -> list[BranchTransaction]:
        """Get all prepared branches for a global transaction.

        Args:
            gtrid: Global transaction ID

        Returns:
            List of prepared BranchTransaction records
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT gtrid, bqual, state, created_at, updated_at, prepared_at
                FROM xa_branch
                WHERE gtrid = %s AND state = 'PREPARED'
                ORDER BY bqual
            """, (gtrid,))
            rows = cursor.fetchall()
            return [
                BranchTransaction(
                    gtrid=row[0],
                    bqual=row[1],
                    state=BranchState(row[2]),
                    created_at=row[3],
                    updated_at=row[4],
                    prepared_at=row[5],
                )
                for row in rows
            ]
        finally:
            cursor.close()

    def get_incomplete_globals(
        self,
        max_age_seconds: int | None = None,
    ) -> list[GlobalTransaction]:
        """Get incomplete global transactions.

        Args:
            max_age_seconds: Optional maximum age filter

        Returns:
            List of incomplete GlobalTransaction records
        """
        cursor = self.connection.cursor()
        try:
            if max_age_seconds:
                cursor.execute("""
                    SELECT gtrid, decision, state, expected_count,
                           created_at, updated_at, finalized_at
                    FROM xa_global
                    WHERE state NOT IN ('COMMITTED', 'ROLLED_BACK')
                    AND created_at < DATE_SUB(NOW(), INTERVAL %s SECOND)
                    ORDER BY created_at
                """, (max_age_seconds,))
            else:
                cursor.execute("""
                    SELECT gtrid, decision, state, expected_count,
                           created_at, updated_at, finalized_at
                    FROM xa_global
                    WHERE state NOT IN ('COMMITTED', 'ROLLED_BACK')
                    ORDER BY created_at
                """)
            rows = cursor.fetchall()
            return [
                GlobalTransaction(
                    gtrid=row[0],
                    decision=Decision(row[1]),
                    state=GlobalState(row[2]),
                    expected_count=row[3],
                    created_at=row[4],
                    updated_at=row[5],
                    finalized_at=row[6],
                )
                for row in rows
            ]
        finally:
            cursor.close()
