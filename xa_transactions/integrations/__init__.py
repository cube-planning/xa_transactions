"""Integration components for XA transactions."""

# Celery integration
try:
    from xa_transactions.integrations.celery import (
        XATask,
        xa_task,
        create_xa_chord,
        get_xa_context_from_task,
    )
    _celery_exports = [
        "XATask",
        "xa_task",
        "create_xa_chord",
        "get_xa_context_from_task",
    ]
except ImportError:
    _celery_exports = []

# Django integration
try:
    from xa_transactions.integrations.django import (
        enable_xa_aware_transactions,
        disable_xa_aware_transactions,
        is_xa_aware_enabled,
        xa_aware_atomic,
        is_django_transaction_active,
        is_xa_active,
        set_xa_active,
    )
    _django_exports = [
        "enable_xa_aware_transactions",
        "disable_xa_aware_transactions",
        "is_xa_aware_enabled",
        "xa_aware_atomic",
        "is_django_transaction_active",
        "is_xa_active",
        "set_xa_active",
    ]
except ImportError:
    _django_exports = []

__all__ = _celery_exports + _django_exports
