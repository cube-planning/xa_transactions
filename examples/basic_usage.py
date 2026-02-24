"""Basic usage example for XA transactions."""

import mysql.connector
from xa_transactions import MySQLXAAdapter, Coordinator, MySQLStore, Decision


def main():
    # Create database connections
    # Connection for XA operations (your application database)
    xa_conn = mysql.connector.connect(
        host="localhost",
        user="user",
        password="password",
        database="mydb",
    )

    # Connection for coordinator store (can be same or different database)
    store_conn = mysql.connector.connect(
        host="localhost",
        user="user",
        password="password",
        database="coordinator_db",
    )

    # Create adapter and coordinator
    adapter = MySQLXAAdapter(xa_conn)
    store = MySQLStore(store_conn)
    coordinator = Coordinator(adapter, store)

    # Create global transaction
    gtrid = coordinator.create_global(expected_branches=3)
    print(f"Created global transaction: {gtrid}")

    # Create branches
    bquals = coordinator.create_branches(gtrid, count=3)
    print(f"Created branches: {bquals}")

    # Simulate parallel workers
    for i, bqual in enumerate(bquals):
        print(f"Worker {i} processing branch {bqual}")
        try:
            with adapter.branch_transaction(gtrid, bqual):
                # Perform your writes
                adapter.execute(
                    f"INSERT INTO my_table (id, value) VALUES (%s, %s)",
                    (i, f"value_{i}"),
                )
                adapter.execute(
                    f"UPDATE other_table SET status = %s WHERE id = %s",
                    ("processed", i),
                )
            # Mark branch as prepared (done automatically by context manager)
            coordinator.mark_branch_prepared(gtrid, bqual)
            print(f"Branch {bqual} prepared successfully")
        except Exception as e:
            print(f"Branch {bqual} failed: {e}")
            # Finalize with rollback
            coordinator.finalize(gtrid, Decision.ROLLBACK, force=True)
            raise

    # Finalize (commit or rollback)
    try:
        coordinator.finalize(gtrid, Decision.COMMIT)
        print(f"Global transaction {gtrid} committed")
    except Exception as e:
        print(f"Finalization failed: {e}")
        coordinator.finalize(gtrid, Decision.ROLLBACK, force=True)

    # Clean up
    xa_conn.close()
    store_conn.close()


if __name__ == "__main__":
    main()
