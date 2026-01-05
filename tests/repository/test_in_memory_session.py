"""Tests for InMemorySession.

This module tests the InMemorySession implementation which provides
transaction support for in-memory storage, including:
- Auto-commit mode (no transaction)
- Transaction mode with begin/commit/rollback
- Context manager support
- Deep copy isolation between staging and storage
"""

from dataclasses import dataclass

import pytest

from infrakit.repository.exceptions import DatabaseError
from infrakit.repository.memory.session import InMemorySession


@dataclass
class User:
    """Test entity with id attribute."""

    id: str
    name: str


@dataclass
class Order:
    """Test entity for multi-type storage tests."""

    id: str
    total: int


class TestInMemorySessionActiveRecordPattern:
    """Tests for Active Record pattern (immediate writes, no transaction).

    This pattern simulates ORMs like Tortoise ORM where changes are
    immediately persisted without explicit transaction management.
    """

    @pytest.mark.asyncio
    async def test_get_active_storage_returns_storage_when_no_transaction(self) -> None:
        """Test that get_active_storage returns storage when no transaction is active."""
        session = InMemorySession()

        # Add data directly to internal storage (not via get_committed_storage!)
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # Test: get_active_storage should return the same storage
        staging = session.get_active_storage(User)

        # Verify: compare with direct access to _storage
        assert staging is session._storage[User]  # noqa: SLF001
        assert "1" in staging

    @pytest.mark.asyncio
    async def test_changes_are_immediately_in_storage(self) -> None:
        """Test that changes via get_active_storage are immediately in storage when no transaction."""
        session = InMemorySession()

        # Test: modify via get_active_storage
        staging = session.get_active_storage(User)
        staging["1"] = User(id="1", name="Alice")

        # Verify: check directly in _storage (not via get_committed_storage!)
        assert "1" in session._storage[User]  # noqa: SLF001
        assert session._storage[User]["1"].name == "Alice"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_commit_does_nothing_when_no_transaction(self) -> None:
        """Test that commit() is a no-op when no transaction is active."""
        session = InMemorySession()

        # Setup: add data directly to _storage
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # Test: commit should do nothing (no error)
        await session.commit()

        # Verify: data should still be there
        assert "1" in session._storage[User]  # noqa: SLF001
        assert not session.in_transaction

    @pytest.mark.asyncio
    async def test_rollback_does_nothing_when_no_transaction(self) -> None:
        """Test that rollback() is a no-op when no transaction is active."""
        session = InMemorySession()

        # Setup: add data directly to _storage
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # Test: rollback should do nothing (no error)
        await session.rollback()

        # Verify: data should still be there
        assert "1" in session._storage[User]  # noqa: SLF001
        assert not session.in_transaction


class TestInMemorySessionSessionBasedPattern:
    """Tests for Session-Based pattern (staging + commit).

    This pattern simulates ORMs like SQLAlchemy where changes are staged
    in memory and require explicit commit() to be persisted.
    """

    @pytest.mark.asyncio
    async def test_begin_sets_transaction_flag(self) -> None:
        """Test that begin() sets the in_transaction flag to True."""
        session = InMemorySession()

        assert not session.in_transaction

        await session.begin()

        assert session.in_transaction

    @pytest.mark.asyncio
    async def test_begin_creates_snapshot_of_storage(self) -> None:
        """Test that begin() creates a deep copy snapshot of storage into staging."""
        session = InMemorySession()

        # Setup: add initial data directly to _storage
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # Test: begin transaction
        await session.begin()

        # Verify: staging should have the data (snapshot) - check via direct access
        assert session._staging == session._storage  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_changes_in_transaction_go_to_staging(self) -> None:
        """Test that changes during a transaction go to staging, not storage."""
        session = InMemorySession()

        # Begin transaction
        await session.begin()

        # Test: add data via get_active_storage
        session.get_active_storage(User)["1"] = User(id="1", name="Alice")

        # Verify: should be in _staging
        assert "1" in session._staging[User]  # noqa: SLF001

        # Verify: should NOT be in _storage yet
        assert User not in session._storage or "1" not in session._storage.get(User, {})  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_commit_applies_staging_to_storage(self) -> None:
        """Test that commit() applies all staged changes to storage."""
        session = InMemorySession()

        # Begin transaction
        await session.begin()

        # Setup: add data to staging via get_active_storage
        session.get_active_storage(User)["1"] = User(id="1", name="Alice")
        session.get_active_storage(User)["2"] = User(id="2", name="Bob")

        # Test: commit
        await session.commit()

        # Verify: should now be in _storage (direct access)
        assert "1" in session._storage[User]  # noqa: SLF001
        assert "2" in session._storage[User]  # noqa: SLF001
        assert session._storage[User]["1"].name == "Alice"  # noqa: SLF001
        assert session._storage[User]["2"].name == "Bob"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_commit_clears_transaction_flag(self) -> None:
        """Test that commit() sets in_transaction flag to False."""
        session = InMemorySession()

        await session.begin()
        assert session.in_transaction

        await session.commit()

        assert not session.in_transaction

    @pytest.mark.asyncio
    async def test_commit_clears_staging(self) -> None:
        """Test that commit() clears the staging area."""
        session = InMemorySession()

        await session.begin()
        session.get_active_storage(User)["1"] = User(id="1", name="Alice")

        # Test: commit
        await session.commit()

        # Verify: staging should be empty (direct access)
        assert session._staging == {}  # noqa: SLF001
        # Verify: storage should have the data
        assert "1" in session._storage[User]  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_rollback_discards_staged_changes(self) -> None:
        """Test that rollback() discards all staged changes.

        **Rollback behavior**: rollback() properly handles all types of modifications:
        - Modified entities: Changes are discarded, original values restored
        - New entities: Additions are discarded
        - Deleted entities: Would be restored (not tested here but same mechanism)
        - Multiple entity types: All changes across all types are discarded atomically

        The rollback works by simply clearing the staging area and restoring the
        in_transaction flag. The original storage remains untouched throughout
        the transaction.
        """
        session = InMemorySession()

        # Setup: add initial data directly to _storage
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # Begin transaction
        await session.begin()

        # Modify in staging via get_active_storage
        session.get_active_storage(User)["1"] = User(id="1", name="Modified Alice")
        session.get_active_storage(User)["2"] = User(id="2", name="Bob")

        # Test: rollback
        await session.rollback()

        # Verify: storage should be unchanged (direct access)
        assert session._storage[User] == {"1": User(id="1", name="Alice")}  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_rollback_clears_transaction_flag(self) -> None:
        """Test that rollback() sets in_transaction flag to False."""
        session = InMemorySession()

        await session.begin()
        assert session.in_transaction

        await session.rollback()

        assert not session.in_transaction

    @pytest.mark.asyncio
    async def test_multiple_entity_types_in_transaction(self) -> None:
        """Test that transactions work correctly with multiple entity types."""
        session = InMemorySession()

        await session.begin()

        # Add different entity types via get_active_storage
        session.get_active_storage(User)["1"] = User(id="1", name="Alice")
        session.get_active_storage(Order)["100"] = Order(id="100", total=500)

        # Test: commit
        await session.commit()

        # Verify: both should be in _storage (direct access)
        assert "1" in session._storage[User]  # noqa: SLF001
        assert "100" in session._storage[Order]  # noqa: SLF001


class TestInMemorySessionIsolation:
    """Tests for deep copy isolation between staging and storage."""

    @pytest.mark.asyncio
    async def test_modifying_staging_does_not_affect_storage(self) -> None:
        """Test that modifying staging entities does not affect storage (deep copy)."""
        session = InMemorySession()

        # Setup: add initial data directly to _storage
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # Begin transaction (creates snapshot)
        await session.begin()

        # Test: modify the entity in staging via get_active_storage
        session.get_active_storage(User)["1"].name = "Modified Alice"

        # Verify: storage should be unchanged (direct access)
        assert session._storage[User]["1"].name == "Alice"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_commit_creates_independent_copy(self) -> None:
        """Test that commit() creates an independent copy from staging to storage."""
        session = InMemorySession()

        await session.begin()

        # Add data to staging via get_active_storage
        user = User(id="1", name="Alice")
        session.get_active_storage(User)["1"] = user

        # Test: commit
        await session.commit()

        # Verify: get the user from _storage (direct access)
        stored_user = session._storage[User]["1"]  # noqa: SLF001

        # They should have the same data but be different objects
        assert stored_user.name == "Alice"
        assert stored_user is not user  # Different objects due to deep copy

    @pytest.mark.asyncio
    async def test_modifying_original_object_after_begin_does_not_affect_staging(self) -> None:
        """Test that modifying the original object in storage doesn't affect staging snapshot.

        This verifies that begin() creates a true deep copy, not just a shallow copy
        or a reference. If the deep copy isn't working, modifying the original object
        would also modify the snapshot in staging.
        """
        session = InMemorySession()

        # Setup: Create a user and add to storage
        user = User(id="1", name="Alice")
        session._storage[User] = {"1": user}  # noqa: SLF001

        # Begin transaction (should create deep copy snapshot)
        await session.begin()

        # Test: Modify the ORIGINAL object in storage (not via session API)
        user.name = "Modified Alice"

        # Verify: The staging snapshot should still have the original value
        assert session._staging[User]["1"].name == "Alice"  # noqa: SLF001

        # Verify: Storage has the modified value
        assert session._storage[User]["1"].name == "Modified Alice"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_modifying_staging_after_commit_does_not_affect_storage(self) -> None:
        """Test that modifying staging dict after commit doesn't affect committed storage.

        This verifies that commit() creates a deep copy when applying changes,
        not just a reference assignment. Without deep copy, holding a reference
        to the old staging dict could allow post-commit modifications.
        """
        session = InMemorySession()

        await session.begin()

        # Add user to staging
        user = User(id="1", name="Alice")
        staging_dict = session.get_active_storage(User)
        staging_dict["1"] = user

        # Keep a reference to staging before commit
        old_staging_ref = session._staging[User]  # noqa: SLF001

        # Commit (should deep copy staging to storage)
        await session.commit()

        # Test: Modify via the old staging reference
        old_staging_ref["1"].name = "Hacked"

        # Verify: Storage should NOT be affected (deep copy protection)
        assert session._storage[User]["1"].name == "Alice"  # noqa: SLF001


class TestInMemorySessionContextManager:
    """Tests for async context manager support."""

    @pytest.mark.asyncio
    async def test_context_manager_calls_begin(self) -> None:
        """Test that entering the context manager calls begin()."""
        session = InMemorySession()

        async with session:
            assert session.in_transaction

    @pytest.mark.asyncio
    async def test_context_manager_commits_on_success(self) -> None:
        """Test that exiting the context manager commits changes on success."""
        session = InMemorySession()

        async with session:
            session.get_active_storage(User)["1"] = User(id="1", name="Alice")

        # Verify: should be committed (direct access to _storage)
        assert "1" in session._storage[User]  # noqa: SLF001
        assert not session.in_transaction

    @pytest.mark.asyncio
    async def test_context_manager_rolls_back_on_exception(self) -> None:
        """Test that exiting the context manager rolls back on exception."""
        session = InMemorySession()

        # Setup: add initial data directly to _storage
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        try:
            async with session:
                session.get_active_storage(User)["2"] = User(id="2", name="Bob")
                msg = "Test error"
                raise ValueError(msg)  # noqa: TRY301
        except ValueError:
            pass

        # Verify: original data should be intact (direct access)
        assert "1" in session._storage[User]  # noqa: SLF001

        # Verify: new data should be rolled back
        assert "2" not in session._storage[User]  # noqa: SLF001

        # Transaction should be closed
        assert not session.in_transaction

    @pytest.mark.asyncio
    async def test_context_manager_calls_close(self) -> None:
        """Test that exiting the context manager calls close()."""
        session = InMemorySession()

        async with session:
            pass

        # After exit, transaction should be closed
        assert not session.in_transaction


class TestInMemorySessionClose:
    """Tests for close() method."""

    @pytest.mark.asyncio
    async def test_close_rolls_back_active_transaction(self) -> None:
        """Test that close() rolls back any active transaction."""
        session = InMemorySession()

        # Setup: add initial data directly to _storage
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # Begin transaction and make changes
        await session.begin()
        session.get_active_storage(User)["2"] = User(id="2", name="Bob")

        # Test: close without commit
        await session.close()

        # Verify: transaction should be rolled back
        assert not session.in_transaction
        assert "1" in session._storage[User]  # noqa: SLF001
        assert "2" not in session._storage[User]  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_close_does_nothing_when_no_transaction(self) -> None:
        """Test that close() is safe to call when no transaction is active."""
        session = InMemorySession()

        # Setup: add data directly to _storage
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # Test: close without transaction
        await session.close()

        # Verify: data should still be there
        assert "1" in session._storage[User]  # noqa: SLF001
        assert not session.in_transaction


class TestInMemorySessionEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_begins_raises_error(self) -> None:
        """Test that calling begin() during an active transaction raises DatabaseError."""
        session = InMemorySession()

        # Setup: add initial data directly to _storage
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # First begin
        await session.begin()
        session.get_active_storage(User)["2"] = User(id="2", name="Bob")

        # Test: second begin should raise DatabaseError
        with pytest.raises(
            DatabaseError,
            match=r"Transaction already in progress. Call commit\(\) or rollback\(\) before starting a new transaction.",
        ):
            await session.begin()

        # Verify: staging should still have the changes from first transaction
        assert "2" in session._staging[User]  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_empty_transaction_commit(self) -> None:
        """Test that committing a transaction with no changes works correctly."""
        session = InMemorySession()

        # Setup: add initial data directly to _storage
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # Begin and commit without changes
        await session.begin()
        await session.commit()

        # Verify: data should still be there
        assert "1" in session._storage[User]  # noqa: SLF001
        assert not session.in_transaction

    @pytest.mark.asyncio
    async def test_get_committed_storage_creates_empty_dict_for_new_entity_type(self) -> None:
        """Test that get_committed_storage creates an empty dict for new entity types."""
        session = InMemorySession()

        # Test: call get_committed_storage for new entity type
        storage = session.get_committed_storage(User)

        # Verify: should return empty dict
        assert storage == {}
        assert isinstance(storage, dict)
        # Verify: should be in _storage now (direct access)
        assert User in session._storage  # noqa: SLF001
        assert session._storage[User] == {}  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_get_active_storage_creates_empty_dict_for_new_entity_type_in_transaction(
        self,
    ) -> None:
        """Test that get_active_storage creates an empty dict for new entity types during transaction."""
        session = InMemorySession()

        await session.begin()

        # Test: call get_active_storage for new entity type
        staging = session.get_active_storage(User)

        # Verify: should return empty dict
        assert staging == {}
        assert isinstance(staging, dict)
        # Verify: should be in _staging now (direct access)
        assert User in session._staging  # noqa: SLF001
        assert session._staging[User] == {}  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_direct_storage_modification_during_transaction_is_lost_on_commit(
        self,
    ) -> None:
        """Test what happens if storage is modified directly during a transaction.

        **Important**: This is a BAD PRACTICE but we document the behavior.
        When someone bypasses the session API and modifies _storage directly
        during a transaction, those changes will be LOST on commit because
        commit() replaces storage with staging.

        The staging is a snapshot taken at begin() time, so:
        1. Initial storage is copied to staging at begin()
        2. Changes via session API go to staging
        3. Direct storage modifications are ignored
        4. On commit, storage is replaced by staging (direct mods lost)
        """
        session = InMemorySession()

        # Setup: Add initial data
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # Begin transaction (staging = copy of storage with "1")
        await session.begin()

        # Add user via session (correct way - goes to staging)
        session.get_active_storage(User)["2"] = User(id="2", name="Bob")

        # BAD PRACTICE: Someone modifies storage directly during transaction
        session._storage[User]["3"] = User(id="3", name="Hacker")  # noqa: SLF001

        # Commit (storage = staging)
        await session.commit()

        # Verify: Only staging changes are persisted
        assert "1" in session._storage[User]  # noqa: SLF001 - Original from staging
        assert "2" in session._storage[User]  # noqa: SLF001 - Added via session API
        assert "3" not in session._storage[User]  # noqa: SLF001 - Direct mod LOST!

    @pytest.mark.asyncio
    async def test_rollback_without_changes(self) -> None:
        """Test that rolling back a transaction with no changes works correctly."""
        session = InMemorySession()

        # Setup: Initial data
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # Begin and rollback without making any changes
        await session.begin()
        await session.rollback()

        # Verify: Data still intact
        assert "1" in session._storage[User]  # noqa: SLF001
        assert not session.in_transaction

    @pytest.mark.asyncio
    async def test_rollback_does_not_restore_direct_storage_modifications(self) -> None:
        """Test that rollback() does NOT restore direct storage modifications.

        **Important limitation**: This documents a known limitation of the session.
        Rollback only discards staged changes (changes made via get_active_storage).
        If someone directly modifies _storage during a transaction, those changes
        will persist even after rollback.

        This is by design to avoid the performance cost of maintaining a second
        deep copy snapshot. Repositories should NEVER directly modify _storage
        during a transaction - always use get_active_storage().
        """
        session = InMemorySession()

        # Setup: Initial data
        session._storage[User] = {"1": User(id="1", name="Alice")}  # noqa: SLF001

        # Begin transaction
        await session.begin()

        # Modify via session (correct way - goes to staging)
        session.get_active_storage(User)["2"] = User(id="2", name="Bob")

        # BAD PRACTICE: Modify storage directly (bypass session)
        session._storage[User]["3"] = User(id="3", name="Hacker")  # noqa: SLF001
        session._storage[User]["1"].name = "Modified Alice"  # noqa: SLF001

        # Rollback
        await session.rollback()

        # Verify: Staged changes are discarded
        assert "2" not in session._storage[User]  # noqa: SLF001 - Staged change discarded ✓

        # Verify: Direct storage modifications PERSIST (limitation)
        assert "3" in session._storage[User]  # noqa: SLF001 - Direct mod NOT rolled back!
        assert session._storage[User]["1"].name == "Modified Alice"  # noqa: SLF001 - NOT rolled back!

        # This documents why repositories MUST use get_active_storage()
