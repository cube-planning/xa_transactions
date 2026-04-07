"""Type definitions for XA transactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import NamedTuple


class Decision(str, Enum):
    """Global transaction decision."""

    UNKNOWN = "UNKNOWN"
    COMMIT = "COMMIT"
    ROLLBACK = "ROLLBACK"


class GlobalState(str, Enum):
    """Global transaction state."""

    ACTIVE = "ACTIVE"
    PREPARING = "PREPARING"
    PREPARED = "PREPARED"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"


class BranchState(str, Enum):
    """Branch transaction state."""

    EXPECTED = "EXPECTED"
    ACTIVE = "ACTIVE"
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"


class XID(NamedTuple):
    """XA Transaction ID."""

    gtrid: str
    bqual: str
    format_id: int = 1

    def __str__(self) -> str:
        return f"'{self.gtrid}','{self.bqual}',{self.format_id}"

    def to_sql(self) -> str:
        return str(self)


@dataclass
class GlobalTransaction:
    """Global transaction record."""

    gtrid: str
    decision: Decision
    state: GlobalState
    expected_count: int
    created_at: datetime
    updated_at: datetime
    finalized_at: datetime | None = None


@dataclass
class BranchTransaction:
    """Branch transaction record."""

    gtrid: str
    bqual: str
    state: BranchState
    created_at: datetime
    updated_at: datetime
    prepared_at: datetime | None = None
