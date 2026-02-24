"""Celery integration example for XA transactions.

This example requires Celery to be installed. You can install it either:
    pip install xa-transactions[celery]
or:
    pip install celery
"""

try:
    from celery import Celery
except ImportError:
    raise ImportError(
        "This example requires Celery. Install it with: pip install xa-transactions[celery] "
        "or pip install celery"
    )

import mysql.connector
from xa_transactions import (
    MySQLXAAdapter,
    Coordinator,
    MySQLStore,
    Decision,
    xa_task,
    create_xa_chord,
)

app = Celery("xa_example")


# Connection factory for XA adapter
def get_xa_connection():
    return mysql.connector.connect(
        host="localhost",
        user="user",
        password="password",
        database="mydb",
    )


def get_adapter():
    return MySQLXAAdapter(get_xa_connection())


# Coordinator instance (shared)
store_conn = mysql.connector.connect(
    host="localhost",
    user="user",
    password="password",
    database="coordinator_db",
)
store = MySQLStore(store_conn)
coordinator = Coordinator(get_adapter(), store)


@app.task
@xa_task(get_adapter)
def process_branch(xa_gtrid, xa_bqual, data):
    """Process a single branch of the XA transaction."""
    adapter = get_adapter()
    
    # XA START, END, PREPARE are handled by the decorator
    # Just perform your writes
    adapter.execute(
        "INSERT INTO my_table (id, value) VALUES (%s, %s)",
        (data["id"], data["value"]),
    )
    
    # Mark as prepared
    coordinator.mark_branch_prepared(xa_gtrid, xa_bqual)
    
    return {"status": "success", "bqual": xa_bqual}


@app.task
def finalize_transaction(xa_gtrid, decision):
    """Finalize the global transaction."""
    coordinator.finalize(xa_gtrid, Decision[decision])
    return {"status": "finalized", "gtrid": xa_gtrid}


def run_parallel_work():
    """Run parallel work with XA coordination."""
    # Create global transaction
    gtrid = coordinator.create_global(expected_branches=3)
    
    # Create branch tasks
    branch_tasks = [
        process_branch.s(xa_gtrid=gtrid, data={"id": i, "value": f"value_{i}"})
        for i in range(3)
    ]
    
    # Create finalize task
    finalize = finalize_transaction.s(xa_gtrid=gtrid, decision="COMMIT")
    
    # Create chord
    gtrid, result = create_xa_chord(
        coordinator=coordinator,
        branch_tasks=branch_tasks,
        finalize_task=finalize,
    )
    
    return result


if __name__ == "__main__":
    result = run_parallel_work()
    print(f"Chord result: {result}")
