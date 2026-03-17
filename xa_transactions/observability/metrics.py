"""Default implementations for metrics collection."""

from __future__ import annotations

from typing import Any
from xa_transactions.types.protocols import MetricsCollector
from xa_transactions.types.types import Decision


class NoOpMetrics:
    """No-op implementation of MetricsCollector.

    Use this when you don't need metrics collection.
    """

    def record_transaction_created(self, gtrid: str) -> None:
        pass

    def record_branch_prepared(
        self,
        gtrid: str,
        bqual: str,
        duration_ms: float,
    ) -> None:
        pass

    def record_finalization(
        self,
        gtrid: str,
        decision: Decision,
        success: bool,
        duration_ms: float,
    ) -> None:
        pass

    def record_gc_run(
        self,
        recovered_count: int,
        duration_ms: float,
    ) -> None:
        pass

    def record_error(
        self,
        error_type: str,
        gtrid: str | None = None,
    ) -> None:
        pass


class LoggingMetrics:
    """Metrics implementation that logs metrics.

    Uses Python's logging module to log metrics events.
    """

    def __init__(self, logger: Any | None = None):
        """Initialize logging metrics.

        Args:
            logger: Optional logger instance. If None, uses default logger.
        """
        import logging
        self.logger = logger or logging.getLogger(__name__)

    def record_transaction_created(self, gtrid: str) -> None:
        self.logger.debug(f"Metric: transaction_created, gtrid={gtrid}")

    def record_branch_prepared(
        self,
        gtrid: str,
        bqual: str,
        duration_ms: float,
    ) -> None:
        self.logger.debug(
            f"Metric: branch_prepared, gtrid={gtrid}, bqual={bqual}, duration_ms={duration_ms}"
        )

    def record_finalization(
        self,
        gtrid: str,
        decision: Decision,
        success: bool,
        duration_ms: float,
    ) -> None:
        self.logger.info(
            f"Metric: finalization, gtrid={gtrid}, decision={decision.value}, "
            f"success={success}, duration_ms={duration_ms}"
        )

    def record_gc_run(
        self,
        recovered_count: int,
        duration_ms: float,
    ) -> None:
        self.logger.info(
            f"Metric: gc_run, recovered_count={recovered_count}, duration_ms={duration_ms}"
        )

    def record_error(
        self,
        error_type: str,
        gtrid: str | None = None,
    ) -> None:
        self.logger.warning(f"Metric: error, type={error_type}, gtrid={gtrid}")
