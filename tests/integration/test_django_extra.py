"""Django integration smoke tests (opt-in locally; run in CI with [django] extra)."""

import pytest


@pytest.mark.django
def test_django_extra_importable() -> None:
    pytest.importorskip("django")
    from xa_transactions.integrations.django import enable_xa_aware_transactions

    assert enable_xa_aware_transactions is not None
