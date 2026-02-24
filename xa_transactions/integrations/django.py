"""Django integration for XA transactions.

Provides seamless integration between Django's transaction.atomic() and XA transactions.
"""

import os
import threading
from contextlib import contextmanager
from typing import Optional

# Thread-local storage for XA transaction state
_xa_state = threading.local()

# Global flag for XA-aware transactions
_XA_AWARE_ENABLED = False
_ORIGINAL_ATOMIC = None


def set_xa_active(active: bool) -> None:
    """Mark that an XA transaction is active in this thread.
    
    Args:
        active: True if XA transaction is active, False otherwise
    """
    _xa_state.active = active


def is_xa_active() -> bool:
    """Check if an XA transaction is active in this thread.
    
    Returns:
        True if XA transaction is active, False otherwise
    """
    return getattr(_xa_state, 'active', False)


def is_django_transaction_active(using: Optional[str] = None) -> bool:
    """Check if a Django transaction is currently active.
    
    Args:
        using: Optional database alias (defaults to 'default')
    
    Returns:
        True if Django transaction is active, False otherwise
    
    Raises:
        ImportError: If Django is not installed
    """
    try:
        from django.db import transaction, connections
        
        if using is None:
            using = 'default'
        
        # Check Django's transaction state
        return not transaction.get_autocommit(using=using)
    except (ImportError, RuntimeError):
        return False


@contextmanager
def xa_aware_atomic(using=None, savepoint=True, durable=False):
    """Django transaction.atomic() wrapper that detects XA transactions.
    
    If an XA transaction is active, this becomes a no-op (or uses savepoints
    if MySQL allows it).
    
    Args:
        using: Database alias (Django parameter)
        savepoint: Whether to use savepoints (Django parameter)
        durable: Whether transaction is durable (Django parameter)
    
    Yields:
        None
    """
    try:
        from django.db import transaction as django_transaction
    except ImportError:
        raise ImportError("Django is not installed")
    
    if is_xa_active():
        # XA transaction is active - just yield (no-op)
        # Django ORM operations will work within the XA transaction
        yield
    else:
        # Normal Django transaction
        with django_transaction.atomic(using=using, savepoint=savepoint, durable=durable):
            yield


def enable_xa_aware_transactions() -> None:
    """Enable XA-aware transaction.atomic() for Django.
    
    This monkey-patches Django's transaction.atomic() to automatically
    detect XA transactions and handle them gracefully.
    
    Call this once in your Django settings.py or startup code.
    
    Example:
        # In settings.py
        from xa_transactions.integrations.django import enable_xa_aware_transactions
        enable_xa_aware_transactions()
    """
    global _XA_AWARE_ENABLED, _ORIGINAL_ATOMIC
    
    if _XA_AWARE_ENABLED:
        return  # Already enabled
    
    try:
        from django.db import transaction as django_transaction
    except ImportError:
        raise ImportError("Django is not installed. Cannot enable XA-aware transactions.")
    
    # Store original
    _ORIGINAL_ATOMIC = django_transaction.atomic
    
    # Create wrapper
    @contextmanager
    def _xa_aware_atomic_wrapper(using=None, savepoint=True, durable=False):
        if is_xa_active():
            # XA transaction is active - no-op
            yield
        else:
            # Normal behavior
            with _ORIGINAL_ATOMIC(using=using, savepoint=savepoint, durable=durable):
                yield
    
    # Monkey-patch
    django_transaction.atomic = _xa_aware_atomic_wrapper
    _XA_AWARE_ENABLED = True


def disable_xa_aware_transactions() -> None:
    """Disable XA-aware transaction.atomic() and restore original.
    
    Useful for testing or debugging.
    """
    global _XA_AWARE_ENABLED, _ORIGINAL_ATOMIC
    
    if not _XA_AWARE_ENABLED or _ORIGINAL_ATOMIC is None:
        return
    
    try:
        from django.db import transaction as django_transaction
    except ImportError:
        return
    
    # Restore original
    django_transaction.atomic = _ORIGINAL_ATOMIC
    _XA_AWARE_ENABLED = False
    _ORIGINAL_ATOMIC = None


def is_xa_aware_enabled() -> bool:
    """Check if XA-aware transactions are enabled.
    
    Returns:
        True if enabled, False otherwise
    """
    return _XA_AWARE_ENABLED


def _auto_enable_from_settings() -> None:
    """Auto-enable from Django settings if configured."""
    try:
        from django.conf import settings
        if getattr(settings, 'XA_TRANSACTIONS_ENABLE_DJANGO_INTEGRATION', False):
            enable_xa_aware_transactions()
    except (ImportError, RuntimeError):
        pass  # Django not configured yet


def _auto_enable_from_env() -> None:
    """Auto-enable from environment variable if set."""
    env_value = os.getenv('XA_ENABLE_DJANGO_INTEGRATION', '').lower()
    if env_value in ('1', 'true', 'yes', 'on'):
        try:
            enable_xa_aware_transactions()
        except ImportError:
            pass  # Django not available


# Try auto-enable on import (but don't fail if Django not ready)
try:
    _auto_enable_from_settings()
    _auto_enable_from_env()
except Exception:
    pass
