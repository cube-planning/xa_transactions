"""Core XA transaction coordination components."""

from xa_transactions.core.adapter import MySQLXAAdapter, XAAdapter
from xa_transactions.core.coordinator import Coordinator, create_coordinator
from xa_transactions.core.store import MySQLStore

__all__ = [
    "MySQLXAAdapter",
    "XAAdapter",  # Backward compatibility alias
    "Coordinator",
    "create_coordinator",
    "MySQLStore",
]
