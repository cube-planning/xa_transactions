"""Recovery and garbage collection example."""

import mysql.connector
from xa_transactions import MySQLXAAdapter, Coordinator, MySQLStore


def main():
    # Setup
    xa_conn = mysql.connector.connect(
        host="localhost",
        user="user",
        password="password",
        database="mydb",
    )
    store_conn = mysql.connector.connect(
        host="localhost",
        user="user",
        password="password",
        database="coordinator_db",
    )

    adapter = MySQLXAAdapter(xa_conn)
    store = MySQLStore(store_conn)
    coordinator = Coordinator(adapter, store)

    # Run garbage collection
    # This will:
    # 1. Query XA RECOVER to find prepared transactions
    # 2. Reconcile with coordinator store
    # 3. Finalize in-doubt transactions based on decision
    # 4. Auto-rollback expired UNKNOWN transactions
    recovered_count = coordinator.gc(
        max_age_seconds=3600,  # 1 hour
        auto_rollback_expired=True,
    )

    print(f"Recovered {recovered_count} transactions")

    # Manual reconciliation of a specific branch
    gtrid = "some-gtrid"
    bqual = "some-bqual"
    state = coordinator.reconcile_branch(gtrid, bqual)
    if state:
        print(f"Branch {bqual} is {state}")
    else:
        print(f"Branch {bqual} not found in XA RECOVER")

    xa_conn.close()
    store_conn.close()


if __name__ == "__main__":
    main()
