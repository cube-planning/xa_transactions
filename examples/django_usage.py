"""Django integration example for XA transactions.

This example demonstrates how to use XA transactions with Django ORM.

Setup:
1. Enable XA-aware transactions (choose one method):
   
   Method 1: Explicit call (recommended)
   # In settings.py or startup code:
   from xa_transactions.integrations.django import enable_xa_aware_transactions
   enable_xa_aware_transactions()
   
   Method 2: Django settings
   # In settings.py:
   XA_TRANSACTIONS_ENABLE_DJANGO_INTEGRATION = True
   
   Method 3: Environment variable
   # export XA_ENABLE_DJANGO_INTEGRATION=1

2. Use XA transactions with Django ORM:
"""

from django.db import connection
from xa_transactions import (
    MySQLXAAdapter,
    Coordinator,
    MySQLStore,
    Decision,
    enable_xa_aware_transactions,
)

# Enable XA-aware transactions (if not enabled via settings/env)
# enable_xa_aware_transactions()

# Create adapter using Django's connection
def get_adapter():
    return MySQLXAAdapter(connection.connection)

# Create coordinator
store = MySQLStore(connection.connection)
coordinator = Coordinator(get_adapter(), store)


def process_branch_with_django_orm(gtrid: str, bqual: str):
    """Process a branch using Django ORM within an XA transaction."""
    from myapp.models import MyModel, OtherModel
    
    adapter = get_adapter()
    
    # XA transaction context manager
    with adapter.branch_transaction(gtrid, bqual):
        # Use Django ORM - works seamlessly!
        MyModel.objects.create(id=1, value="test")
        OtherModel.objects.filter(id=1).update(status="processed")
        
        # transaction.atomic() would also work here if enabled:
        # from django.db import transaction
        # with transaction.atomic():
        #     MyModel.objects.create(...)
    
    # Mark as prepared
    coordinator.mark_branch_prepared(gtrid, bqual)


def example_usage():
    """Example of using XA transactions with Django."""
    # Create global transaction
    gtrid = coordinator.create_global(expected_branches=2)
    
    # Create branches
    bquals = coordinator.create_branches(gtrid, count=2)
    
    # Process branches (could be in parallel workers)
    for bqual in bquals:
        process_branch_with_django_orm(gtrid, bqual)
    
    # Finalize
    coordinator.finalize(gtrid, Decision.COMMIT)
