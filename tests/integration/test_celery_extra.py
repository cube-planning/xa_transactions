"""Celery integration smoke tests (opt-in locally; run in CI with [celery] extra)."""

import pytest


@pytest.mark.celery
def test_celery_extra_available() -> None:
    pytest.importorskip("celery")
    from xa_transactions.integrations import celery as mod

    assert mod.CELERY_AVAILABLE is True
    assert mod.XATask is not None
