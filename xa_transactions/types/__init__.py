"""Type definitions, protocols, and exceptions."""

from xa_transactions.types.types import (
    Decision,
    GlobalState,
    BranchState,
    XID,
    GlobalTransaction,
    BranchTransaction,
)
from xa_transactions.types.protocols import (
    StoreProtocol,
    XAAdapterProtocol,
    Connection,
    ConnectionFactory,
    TransactionHooks,
    RecoveryStrategy,
    MetricsCollector,
    LockManager,
    LockHandle,
)
from xa_transactions.types.exceptions import (
    XAError,
    XAAdapterError,
    StoreError,
    CoordinatorError,
    BranchError,
    FinalizationError,
    RecoveryError,
    ValidationError,
    LockError,
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
