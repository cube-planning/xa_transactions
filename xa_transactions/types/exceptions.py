"""Exception hierarchy for XA transactions."""


class XAError(Exception):
    """Base exception for all XA transaction errors."""

    pass


class XAAdapterError(XAError):
    """Errors from XA adapter operations.

    Raised when XA commands (START, PREPARE, COMMIT, etc.) fail.
    """

    pass


class StoreError(XAError):
    """Errors from store operations.

    Raised when store operations (create_global, update_branch, etc.) fail.
    """

    pass


class CoordinatorError(XAError):
    """Errors from coordinator operations.

    Base class for coordinator-related errors.
    """

    pass


class BranchError(CoordinatorError):
    """Errors related to branch transactions.

    Raised when branch operations fail (preparation, commit, rollback).
    """

    pass


class FinalizationError(CoordinatorError):
    """Errors during transaction finalization.

    Raised when commit or rollback operations fail.
    """

    pass


class RecoveryError(CoordinatorError):
    """Errors during recovery operations.

    Raised when garbage collection or recovery operations fail.
    """

    pass


class ValidationError(CoordinatorError):
    """Errors from validation operations.

    Raised when transaction validation fails (e.g., missing branches).
    """

    pass


class LockError(XAError):
    """Errors related to lock operations.

    Raised when lock acquisition fails or lock operations error.
    """

    pass
