"""In-memory session with transaction support."""

import copy
from types import TracebackType
from typing import Self

from infrakit.repository.exceptions import DatabaseError
from infrakit.repository.protocols import HasId


class InMemorySession:
    """Manages in-memory storage with transactional support.

    This class provides a session-like interface for in-memory data persistence,
    similar to SQLAlchemy's Session but adapted for in-memory data structures.

    The session supports two modes of operation:

    **1. Auto-commit mode** (default, no active transaction):
       - Changes are immediately persisted to storage
       - No staging area is used
       - Suitable for simple operations without atomicity requirements

    **2. Transaction mode** (after calling begin()):
       - Changes are staged in memory until commit()
       - Provides atomicity: all changes succeed or all are rolled back
       - Isolation: changes are not visible until committed
       - Rollback discards all staged changes

    Attributes:
        _staging: Temporary buffer for uncommitted changes during a transaction.
        _storage: Permanent storage for committed data.
        _in_transaction: Flag indicating if a transaction is currently active.

    Example - Auto-commit mode:
        >>> session = InMemorySession()
        >>> storage = session._get_active_storage(User)
        >>> storage["1"] = User(id="1", name="Alice")
        # Change is immediately in permanent storage

    Example - Transaction mode:
        >>> session = InMemorySession()
        >>> await session.begin()
        >>> storage = session._get_active_storage(User)
        >>> storage["1"] = User(id="1", name="Alice")
        >>> await session.commit()  # Now persisted
        # Or: await session.rollback()  # Discard changes

    Example - Context manager (recommended):
        >>> async with InMemorySession() as session:
        ...     storage = session._get_active_storage(User)
        ...     storage["1"] = User(id="1", name="Alice")
        ...     # Auto-commit on exit (or rollback if exception)
    """

    def __init__(self) -> None:
        """Initialize the session with empty storage and staging areas."""
        # Nested dict structure: {EntityType: {entity_id: entity_instance}}
        self._staging: dict[type[HasId], dict[str, HasId]] = {}
        self._storage: dict[type[HasId], dict[str, HasId]] = {}
        self._in_transaction = False

    async def begin(self) -> None:
        """Start a new transaction by creating a snapshot of the current storage.

        This creates a deep copy of the storage, allowing modifications to be made
        in isolation.

        After calling begin(), all repository operations will work on the staging
        area until commit() or rollback() is called.

        **Important**: Only modify storage through _get_active_storage() during
        a transaction. Direct modifications to _storage will not be rolled back.

        Raises:
            DatabaseError: If a transaction is already active. You must commit or
                          rollback the current transaction before starting a new one.
        """
        if self._in_transaction:
            msg = (
                "Transaction already in progress. "
                "Call commit() or rollback() before starting a new transaction."
            )
            raise DatabaseError(msg)
        self._in_transaction = True
        # Create a deep copy to ensure complete isolation
        self._staging = copy.deepcopy(self._storage)

    async def commit(self) -> None:
        """Commit the current transaction, applying all staged changes to storage.

        This operation is atomic: all changes across all entity types are applied
        together. After commit, the staging area is cleared and the transaction ends.

        If no transaction is active (auto-commit mode), this method does nothing.
        """
        if not self._in_transaction:
            return

        # Apply all staged changes atomically with deep copy to avoid reference issues
        self._storage = copy.deepcopy(self._staging)
        self._staging = {}
        self._in_transaction = False

    async def rollback(self) -> None:
        """Roll back the current transaction, discarding all staged changes.

        The staging area is cleared and the transaction ends. Changes made through
        _get_active_storage() are discarded since they only affected the staging area.

        **Important limitation**: This only discards changes made through the session API.
        If _storage was directly modified during the transaction (bad practice), those
        changes will NOT be rolled back. Always use _get_active_storage() to ensure
        proper transactional behavior.

        If no transaction is active, this method does nothing.
        """
        if not self._in_transaction:
            return

        self._staging = {}
        self._in_transaction = False

    async def close(self) -> None:
        """Close the session.

        If a transaction is active, it will be rolled back automatically.
        This ensures no uncommitted changes are left in an inconsistent state.
        """
        if self._in_transaction:
            await self.rollback()

    def _get_committed_storage(self, entity_type: type[HasId]) -> dict[str, HasId]:
        """Get the committed storage dictionary for a specific entity type.

        **Internal API**: This method is intended for use by InMemory repositories.
        End users should interact with repositories and unit of work, not sessions directly.

        This method provides direct access to the committed data storage,
        bypassing any active transaction. Always returns the permanent storage
        regardless of transaction state.

        Args:
            entity_type: The entity class to get storage for.

        Returns:
            The committed storage dictionary for the given entity type.
            Creates a new empty dict if none exists.
        """
        return self._storage.setdefault(entity_type, {})

    def _get_active_storage(self, entity_type: type[HasId]) -> dict[str, HasId]:
        """Get the active storage dictionary for a specific entity type.

        **Internal API**: This method is intended for use by InMemory repositories.
        End users should interact with repositories and unit of work, not sessions directly.

        This is the transaction-aware method repositories should use for normal operations.
        Returns the appropriate storage based on transaction state:
        - If in transaction: returns staging area (uncommitted changes)
        - If not in transaction: returns committed storage (auto-commit mode)

        Args:
            entity_type: The entity class to get storage for.

        Returns:
            The active storage dictionary - staging if in transaction,
            otherwise committed storage. Creates a new empty dict if none exists.
        """
        if self._in_transaction:
            return self._staging.setdefault(entity_type, {})
        # If no transaction is active, return committed storage (auto-commit mode)
        return self._get_committed_storage(entity_type)

    @property
    def in_transaction(self) -> bool:
        """Check if a transaction is currently active.

        Returns:
            True if a transaction is active (begin() was called), False otherwise.
        """
        return self._in_transaction

    async def __aenter__(self) -> Self:
        """Enter the async context manager, starting a transaction.

        Returns:
            The session instance with an active transaction.
        """
        await self.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the async context manager.

        If an exception occurred, the transaction is rolled back.
        Otherwise, the transaction is committed.
        Finally, the session is closed.

        Args:
            exc_type: Exception type if an exception occurred, None otherwise.
            exc_val: Exception value if an exception occurred, None otherwise.
            exc_tb: Exception traceback if an exception occurred, None otherwise.
        """
        try:
            if exc_type is not None:
                # Exception occurred, rollback
                await self.rollback()
            else:
                # No exception, commit
                await self.commit()
        finally:
            await self.close()
