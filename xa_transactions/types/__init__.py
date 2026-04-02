"""Type definitions, protocols, and exceptions."""

from xa_transactions.types.exceptions import (
    BranchError,
    CoordinatorError,
    FinalizationError,
    LockError,
    RecoveryError,
    StoreError,
    ValidationError,
    XAAdapterError,
    XAError,
)
from xa_transactions.types.protocols import (
    Connection,
    ConnectionFactory,
    LockHandle,
    LockManager,
    MetricsCollector,
    RecoveryStrategy,
    StoreProtocol,
    TransactionHooks,
    XAAdapterProtocol,
)
from xa_transactions.types.types import (
    XID,
    BranchState,
    BranchTransaction,
    Decision,
    GlobalState,
    GlobalTransaction,
)

__all__ = [
    # Types
    "Decision",
    "GlobalState",
    "BranchState",
    "XID",
    "GlobalTransaction",
    "BranchTransaction",
    # Protocols
    "StoreProtocol",
    "XAAdapterProtocol",
    "Connection",
    "ConnectionFactory",
    "TransactionHooks",
    "RecoveryStrategy",
    "MetricsCollector",
    "LockManager",
    "LockHandle",
    # Exceptions
    "XAError",
    "XAAdapterError",
    "StoreError",
    "CoordinatorError",
    "BranchError",
    "FinalizationError",
    "RecoveryError",
    "ValidationError",
    "LockError",
]
