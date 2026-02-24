"""Default implementations for transaction hooks."""

from typing import Optional, Any
from xa_transactions.types.protocols import TransactionHooks
from xa_transactions.types.types import Decision


class NoOpHooks:
    """No-op implementation of TransactionHooks.

    Use this when you don't need any hooks.
    """

    def on_global_created(self, gtrid: str, expected_count: int) -> None:
        pass

    def on_branch_created(self, gtrid: str, bqual: str) -> None:
        pass

    def on_branch_prepared(self, gtrid: str, bqual: str) -> None:
        pass

    def on_finalization_started(self, gtrid: str, decision: Decision) -> None:
        pass

    def on_finalization_completed(self, gtrid: str, decision: Decision) -> None:
        pass

    def on_finalization_failed(
        self,
        gtrid: str,
        decision: Decision,
        error: Exception,
    ) -> None:
        pass


class LoggingHooks:
    """Hooks implementation that logs events.

    Uses Python's logging module to log transaction lifecycle events.
    """

    def __init__(self, logger: Optional[Any] = None):
        """Initialize logging hooks.

        Args:
            logger: Optional logger instance. If None, uses default logger.
        """
        import logging
        self.logger = logger or logging.getLogger(__name__)

    def on_global_created(self, gtrid: str, expected_count: int) -> None:
        self.logger.info(
            f"Global transaction created: gtrid={gtrid}, expected_branches={expected_count}"
        )

    def on_branch_created(self, gtrid: str, bqual: str) -> None:
        self.logger.debug(f"Branch created: gtrid={gtrid}, bqual={bqual}")

    def on_branch_prepared(self, gtrid: str, bqual: str) -> None:
        self.logger.info(f"Branch prepared: gtrid={gtrid}, bqual={bqual}")

    def on_finalization_started(self, gtrid: str, decision: Decision) -> None:
        self.logger.info(f"Finalization started: gtrid={gtrid}, decision={decision.value}")

    def on_finalization_completed(self, gtrid: str, decision: Decision) -> None:
        self.logger.info(f"Finalization completed: gtrid={gtrid}, decision={decision.value}")

    def on_finalization_failed(
        self,
        gtrid: str,
        decision: Decision,
        error: Exception,
    ) -> None:
        self.logger.error(
            f"Finalization failed: gtrid={gtrid}, decision={decision.value}, error={error}",
            exc_info=error,
        )
