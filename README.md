# XA Transactions

A Python library for coordinating MySQL XA (2-phase commit) transactions across parallel workers with strict all-or-nothing semantics.

## Overview

This library provides a complete solution for managing distributed MySQL transactions using the XA protocol. It's designed for scenarios where:

- You need parallel writers (e.g., Celery tasks)
- Foreign key constraints must be respected
- Strict atomic commit/rollback is required
- A single-writer transaction is not feasible

## How It Works

The library coordinates a 2-phase commit protocol across parallel workers:

```mermaid
graph TD
    A[Create Global Transaction] --> B[Create Branches]
    B --> C[Parallel Branch Execution]
    C --> D[Each Branch: XA START → Writes → XA END → XA PREPARE]
    D --> E[All Branches Prepared?]
    E -->|Yes| F[Finalize: COMMIT or ROLLBACK]
    E -->|No| G[Wait/Recover]
    G --> E
    F --> H[Transaction Complete]
```

**Key Steps:**
1. **Create**: Coordinator creates a global transaction and branch records
2. **Execute**: Parallel workers each run `XA START`, perform writes, then `XA PREPARE`
3. **Finalize**: Once all branches are prepared, coordinator commits or rolls back atomically
4. **Recovery**: Automatic garbage collection recovers in-doubt transactions

## Features

- **XA Protocol Support**: Full implementation of MySQL XA commands (START, END, PREPARE, COMMIT, ROLLBACK, RECOVER)
- **Pluggable Store Backends**: Protocol-based architecture allows Django, SQLAlchemy, or custom implementations
- **Coordinator Store**: Durable state tracking for global transactions and branches
- **Recovery & GC**: Automatic recovery of in-doubt transactions and garbage collection
- **Celery Integration**: Optional helpers for seamless Celery task integration
- **Idempotent Operations**: All finalization operations are idempotent and restart-safe

## Installation

```bash
pip install xa-transactions
```

For Celery integration:

```bash
pip install xa-transactions[celery]
```

## Quick Start

```python
from xa_transactions import Coordinator, XAAdapter, MySQLStore
import mysql.connector

# Create XA adapter
adapter = XAAdapter(mysql.connector.connect(...))

# Create store (MySQL implementation)
store = MySQLStore(mysql.connector.connect(...))

# Create coordinator with store
coordinator = Coordinator(adapter, store)

# Create global transaction
gtrid = coordinator.create_global(expected_branches=3)

# Create branches
bquals = coordinator.create_branches(gtrid, count=3)

# In parallel workers:
for bqual in bquals:
    with adapter.branch_transaction(gtrid, bqual):
        # Perform your writes
        adapter.execute("INSERT INTO ...")
        adapter.execute("UPDATE ...")

# Finalize (commit or rollback)
coordinator.finalize(gtrid, decision="COMMIT")
```

## Pluggable Store Implementations

The library uses Protocol-based interfaces, allowing you to use any store backend:

```python
from xa_transactions import Coordinator, XAAdapter, StoreProtocol
from xa_transactions.store import MySQLStore

# Use built-in MySQL store
store = MySQLStore(mysql_connection)
coordinator = Coordinator(adapter, store)

# Or implement your own (Django, SQLAlchemy, Redis, etc.)
class DjangoStore:
    def ensure_schema(self): ...
    def create_global(self, ...): ...
    def get_global(self, ...): ...
    # ... implement all StoreProtocol methods

store = DjangoStore()
coordinator = Coordinator(adapter, store)  # Works seamlessly!
```

See [examples/custom_store_example.py](examples/custom_store_example.py) for a complete example.

## Documentation

- **[Architecture Guide](ARCHITECTURE.md)**: Detailed design documentation
- **[Django Integration Guide](docs/DJANGO.md)**: Using XA transactions with Django ORM
- **[Celery Integration Guide](docs/CELERY.md)**: Coordinating XA transactions across parallel Celery tasks

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design documentation.

## License

MIT
