"""Connection factory implementations."""

from __future__ import annotations

from typing import Any

from xa_transactions.types.protocols import Connection


class SimpleConnectionFactory:
    """Simple connection factory that returns a single connection.

    No pooling, just returns the connection as-is.
    """

    def __init__(self, connection: Connection):
        """Initialize with a connection.

        Args:
            connection: The connection to return
        """
        self.connection = connection

    def get_connection(self) -> Connection:
        """Get the connection.

        Returns:
            The connection
        """
        return self.connection

    def return_connection(self, connection: Connection) -> None:
        """Return connection (no-op for simple factory).

        Args:
            connection: Connection to return
        """
        pass


class PooledConnectionFactory:
    """Connection factory using a connection pool.

    Wraps a connection pool (e.g., SQLAlchemy pool) to provide
    ConnectionFactory interface.
    """

    def __init__(self, pool: Any):
        """Initialize with a connection pool.

        Args:
            pool: Connection pool object (must have get/return methods)
        """
        self.pool = pool

    def get_connection(self) -> Connection:
        """Get a connection from the pool.

        Returns:
            Connection from pool

        Raises:
            Exception: If connection cannot be obtained
        """
        return self.pool.get_connection()

    def return_connection(self, connection: Connection) -> None:
        """Return connection to pool.

        Args:
            connection: Connection to return
        """
        self.pool.return_connection(connection)
