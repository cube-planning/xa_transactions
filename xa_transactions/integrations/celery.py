"""Celery integration helpers for XA transactions."""

from typing import Any, Callable, Optional, Dict
from functools import wraps

try:
    from celery import Task, current_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    Task = type("Task", (), {})  # Dummy class
    current_task = None

from xa_transactions.core.adapter import XAAdapter
from xa_transactions.types.protocols import XAAdapterProtocol
from xa_transactions.core.coordinator import Coordinator
from xa_transactions.types.types import XID


def _check_celery() -> None:
    """Check if Celery is available."""
    if not CELERY_AVAILABLE:
        raise ImportError(
            "Celery is not installed. Install it with: pip install xa-transactions[celery]"
        )


class XATask(Task):
    """Base Celery task class for XA transactions.

    Automatically handles XA START, END, and PREPARE around task execution.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        _check_celery()
        super().__init__(*args, **kwargs)
        self._xa_adapter: Optional[XAAdapter] = None
        self._xa_gtrid: Optional[str] = None
        self._xa_bqual: Optional[str] = None
        self._xa_format_id: int = 1

    def set_xa_context(
        self,
        adapter: XAAdapterProtocol,
        gtrid: str,
        bqual: str,
        format_id: int = 1,
    ) -> None:
        """Set XA context for this task.

        Args:
            adapter: XA adapter instance
            gtrid: Global transaction ID
            bqual: Branch qualifier
            format_id: XA format ID for XID construction
        """
        self._xa_adapter = adapter
        self._xa_gtrid = gtrid
        self._xa_bqual = bqual
        self._xa_format_id = format_id

    def get_xa_context(self) -> Optional[Dict[str, Any]]:
        """Get XA context from task.

        Returns:
            Dict with adapter, gtrid, bqual, format_id or None
        """
        if self._xa_adapter and self._xa_gtrid and self._xa_bqual:
            return {
                "adapter": self._xa_adapter,
                "gtrid": self._xa_gtrid,
                "bqual": self._xa_bqual,
                "format_id": self._xa_format_id,
            }
        return None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute task with XA transaction management."""
        xa_context = self.get_xa_context()
        if not xa_context:
            return super().__call__(*args, **kwargs)

        adapter = xa_context["adapter"]
        gtrid = xa_context["gtrid"]
        bqual = xa_context["bqual"]
        format_id = xa_context["format_id"]
        xid = XID(gtrid=gtrid, bqual=bqual, format_id=format_id)

        # Set XA state for Django integration
        try:
            from xa_transactions.integrations.django import set_xa_active
            set_xa_active(True)
        except ImportError:
            pass  # Django not available

        try:
            adapter.xa_start(xid)
            result = super().__call__(*args, **kwargs)
            adapter.xa_end(xid)
            adapter.xa_prepare(xid)
            return result
        except Exception:
            try:
                adapter.xa_rollback(xid)
            except Exception:
                pass
            raise
        finally:
            # Clear XA state
            try:
                from xa_transactions.integrations.django import set_xa_active
                set_xa_active(False)
            except ImportError:
                pass


def xa_task(
    adapter_factory: Callable[[], XAAdapterProtocol],
    gtrid_key: str = "xa_gtrid",
    bqual_key: str = "xa_bqual",
    format_id: int = 1,
):
    """Decorator for Celery tasks to automatically handle XA transactions.

    Args:
        adapter_factory: Function that returns an XAAdapter instance
        gtrid_key: Key in kwargs for global transaction ID
        bqual_key: Key in kwargs for branch qualifier
        format_id: XA format ID for XID construction

    Returns:
        Decorated task function

    Example:
        @app.task
        @xa_task(lambda: XAAdapter(get_connection()))
        def my_task(xa_gtrid, xa_bqual, **kwargs):
            adapter = current_task.get_xa_context()["adapter"]
            adapter.execute("INSERT INTO ...")
    """
    _check_celery()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            gtrid = kwargs.pop(gtrid_key, None)
            bqual = kwargs.pop(bqual_key, None)

            if not gtrid or not bqual:
                return func(*args, **kwargs)

            adapter = adapter_factory()
            xid = XID(gtrid=gtrid, bqual=bqual, format_id=format_id)

            # Set XA state for Django integration
            try:
                from xa_transactions.integrations.django import set_xa_active
                set_xa_active(True)
            except ImportError:
                pass  # Django not available

            try:
                adapter.xa_start(xid)
                result = func(*args, **kwargs)
                adapter.xa_end(xid)
                adapter.xa_prepare(xid)
                return result
            except Exception:
                try:
                    adapter.xa_rollback(xid)
                except Exception:
                    pass
                raise
            finally:
                # Clear XA state
                try:
                    from xa_transactions.integrations.django import set_xa_active
                    set_xa_active(False)
                except ImportError:
                    pass

        return wrapper

    return decorator


def create_xa_chord(
    coordinator: Coordinator,
    branch_tasks: list,
    finalize_task: Callable,
    expected_branches: Optional[int] = None,
) -> tuple:
    """Create a Celery chord for XA transaction coordination.

    Args:
        coordinator: Coordinator instance
        branch_tasks: List of Celery task signatures for branches
        finalize_task: Task to call after all branches complete
        expected_branches: Optional expected branch count (defaults to len(branch_tasks))

    Returns:
        Tuple of (gtrid, chord result)

    Example:
        from celery import chord
        from xa_transactions.celery import create_xa_chord

        gtrid, result = create_xa_chord(
            coordinator=coordinator,
            branch_tasks=[task1.s(...), task2.s(...)],
            finalize_task=finalize.s(gtrid=gtrid),
        )
    """
    _check_celery()
    from celery import chord

    if expected_branches is None:
        expected_branches = len(branch_tasks)

    gtrid = coordinator.create_global(expected_branches=expected_branches)
    bquals = coordinator.create_branches(gtrid, count=expected_branches)

    for i, task in enumerate(branch_tasks):
        task.kwargs["xa_gtrid"] = gtrid
        task.kwargs["xa_bqual"] = bquals[i]

    finalize_task.kwargs["xa_gtrid"] = gtrid

    chord_result = chord(branch_tasks)(finalize_task)

    return gtrid, chord_result


def get_xa_context_from_task() -> Optional[Dict[str, Any]]:
    """Get XA context from current Celery task.

    Returns:
        Dict with adapter, gtrid, bqual or None
    """
    _check_celery()
    task = current_task
    if task and isinstance(task, XATask):
        return task.get_xa_context()
    return None
