"""MySQL XA transaction coordination library."""

# Core components
from xa_transactions.core import (
    Coordinator,
    MySQLStore,
    MySQLXAAdapter,
    XAAdapter,  # Backward compatibility alias
    create_coordinator,
)

# Infrastructure
from xa_transactions.infrastructure import (
    DefaultRecoveryStrategy,
    PooledConnectionFactory,
    SimpleConnectionFactory,
)

# Observability
from xa_transactions.observability import (
    LoggingHooks,
    LoggingMetrics,
    NoOpHooks,
    NoOpMetrics,
)

# Types and protocols
from xa_transactions.types import (
    XID,
    BranchError,
    BranchState,
    Connection,
    ConnectionFactory,
    CoordinatorError,
    # Types
    Decision,
    FinalizationError,
    GlobalState,
    LockError,
    LockHandle,
    LockManager,
    MetricsCollector,
    RecoveryError,
    RecoveryStrategy,
    StoreError,
    # Protocols
    StoreProtocol,
    TransactionHooks,
    ValidationError,
    XAAdapterError,
    XAAdapterProtocol,
    # Exceptions
    XAError,
)

# Integrations (optional)
# Celery
try:
    from xa_transactions.integrations.celery import (
        XATask,
        create_xa_chord,
        get_xa_context_from_task,
        xa_task,
    )
except ImportError:
    XATask = None
    xa_task = None
    create_xa_chord = None
    get_xa_context_from_task = None

# Django
try:
    from xa_transactions.integrations.django import (
        disable_xa_aware_transactions,
        enable_xa_aware_transactions,
        is_django_transaction_active,
        is_xa_active,
        is_xa_aware_enabled,
        set_xa_active,
        xa_aware_atomic,
    )
except ImportError:
    enable_xa_aware_transactions = None
    disable_xa_aware_transactions = None
    is_xa_aware_enabled = None
    xa_aware_atomic = None
    is_django_transaction_active = None
    is_xa_active = None
    set_xa_active = None

__version__ = "0.1.0"

__all__ = [
    # Adapters
    "MySQLXAAdapter",
    "XAAdapter",  # Backward compatibility alias
    "XAAdapterProtocol",
    # Coordinator
    "Coordinator",
    "create_coordinator",
    # Store
    "MySQLStore",
    "StoreProtocol",
    # Connections
    "Connection",
    "ConnectionFactory",
    "SimpleConnectionFactory",
    "PooledConnectionFactory",
    # Hooks
    "TransactionHooks",
    "NoOpHooks",
    "LoggingHooks",
    # Metrics
    "MetricsCollector",
    "NoOpMetrics",
    "LoggingMetrics",
    # Recovery
    "RecoveryStrategy",
    "DefaultRecoveryStrategy",
    # Locking
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
    # Types
    "Decision",
    "GlobalState",
    "BranchState",
    "XID",
]

# Add Celery integration if available
if XATask is not None:
    __all__.extend(
        [
            "XATask",
            "xa_task",
            "create_xa_chord",
            "get_xa_context_from_task",
        ]
    )

# Add Django integration if available
if enable_xa_aware_transactions is not None:
    __all__.extend(
        [
            "enable_xa_aware_transactions",
            "disable_xa_aware_transactions",
            "is_xa_aware_enabled",
            "xa_aware_atomic",
            "is_django_transaction_active",
            "is_xa_active",
            "set_xa_active",
        ]
    )
