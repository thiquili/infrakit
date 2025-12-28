"""
Abstract test suite for Repository contract.

This module defines the contract that ALL Repository implementations must satisfy.
Each concrete implementation (InMemory, SqlAlchemy, etc.) must inherit from
RepositoryContractTests and implement the abstract verification methods.

The verification methods ensure that we never test code with itself:
- For SqlAlchemy: use plain SQL (as per TESTING_RULES.md)
- For InMemory: use direct access to internal storage
- For other implementations: use their appropriate verification mechanism
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Generic, TypeVar

import pytest
from ulid import ULID

from infrakit.repository import Repository
from infrakit.repository.exceptions import (
    DatabaseError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    PaginationParameterError,
)

# Type variables for generic test class
EntityType = TypeVar("EntityType")
IDType = TypeVar("IDType")


class RepositoryContractTests(ABC, Generic[EntityType, IDType]):
    """
    Abstract base class defining the Repository contract tests.

    All Repository implementations must pass these tests to be considered
    compliant with the Repository interface.

    Subclasses must implement:
    - All abstract fixtures (repository, entity_factory, etc.)
    - All abstract verification methods (_verify_*, _setup_*)
    """

    # ==================== Abstract Fixtures ====================

    @pytest.fixture
    @abstractmethod
    def repository(self) -> Repository[EntityType, IDType]:
        """Return an empty repository instance to test."""

    @pytest.fixture
    @abstractmethod
    def entity_factory(self) -> Callable[..., EntityType]:
        """
        Return a factory function to create test entities.

        The factory should accept optional parameters:
        - entity_id: The ID to assign (or generate if None)
        - name: The name/label for the entity
        """

    @pytest.fixture
    @abstractmethod
    async def repository_with_entities(
        self, repository: Repository[EntityType, IDType]
    ) -> Repository[EntityType, IDType]:
        """
        Return a repository pre-populated with 10 entities.

        CRITICAL: Entities MUST be inserted WITHOUT using repository methods.
        - For SqlAlchemy: use plain SQL (text())
        - For InMemory: directly access internal storage
        - For others: use appropriate direct mechanism

        This ensures we don't test the repository with itself.
        """

    @pytest.fixture
    @abstractmethod
    def entity_ids(self, repository_with_entities: Repository[EntityType, IDType]) -> list[IDType]:
        """
        Return the list of entity IDs from repository_with_entities.

        CRITICAL: Must retrieve IDs WITHOUT using repository methods.
        """

    # ==================== Abstract Verification Methods ====================

    @abstractmethod
    async def _verify_entity_exists(
        self, repo: Repository[EntityType, IDType], entity_id: IDType
    ) -> bool:
        """
        Verify that an entity exists WITHOUT using repository methods.

        Args:
            repo: The repository instance to verify against
            entity_id: The entity ID to check

        For SqlAlchemy: SELECT COUNT(*) with text()
        For InMemory: check internal _entities dict
        """

    @abstractmethod
    async def _verify_entity_count(self, repo: Repository[EntityType, IDType]) -> int:
        """
        Count entities WITHOUT using repository methods.

        Args:
            repo: The repository instance to verify against

        For SqlAlchemy: SELECT COUNT(*) with text()
        For InMemory: len(_entities)
        """

    @abstractmethod
    async def _verify_entity_data(
        self, repo: Repository[EntityType, IDType], entity_id: IDType, expected_name: str
    ) -> bool:
        """
        Verify entity data WITHOUT using repository methods.

        Args:
            repo: The repository instance to verify against
            entity_id: The entity ID to check
            expected_name: The expected name value

        Returns:
            True if entity exists and name matches
        """

    # ==================== Contract Tests: get_by_id ====================

    @pytest.mark.asyncio
    async def test_get_by_id_success(
        self,
        repository_with_entities: Repository[EntityType, IDType],
        entity_ids: list[IDType],
    ) -> None:
        """get_by_id() should return the entity with the given ID."""
        entity = await repository_with_entities.get_by_id(entity_ids[0])
        assert entity.id == entity_ids[0]

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository: Repository[EntityType, IDType]) -> None:
        """get_by_id() should raise NotFoundError if ID doesn't exist."""
        with pytest.raises(EntityNotFoundError, match="not found"):
            await repository.get_by_id(entity_id=str(ULID()))

    # ==================== Contract Tests: get_all ====================

    @pytest.mark.asyncio
    async def test_get_all_returns_all_entities(
        self, repository_with_entities: Repository[EntityType, IDType]
    ) -> None:
        """get_all() without parameters should return all entities."""
        all_result = await repository_with_entities.get_all()
        assert len(all_result) == 10

    @pytest.mark.asyncio
    async def test_get_all_with_limit_0(
        self, repository_with_entities: Repository[EntityType, IDType]
    ) -> None:
        """get_all(limit=0) should return an empty list."""
        all_result = await repository_with_entities.get_all(limit=0)
        assert len(all_result) == 0

    @pytest.mark.asyncio
    async def test_get_all_with_limit_5(
        self,
        repository_with_entities: Repository[EntityType, IDType],
        entity_ids: list[IDType],
    ) -> None:
        """get_all(limit=5) should return exactly 5 entities."""
        limit = 5
        all_result = await repository_with_entities.get_all(limit=limit)
        assert len(all_result) == 5
        # Verify they are actual entities with valid IDs
        for entity in all_result:
            assert hasattr(entity, "id")
            assert hasattr(entity, "name")

    @pytest.mark.asyncio
    async def test_get_all_with_limit_superior_to_len_entities(
        self, repository_with_entities: Repository[EntityType, IDType]
    ) -> None:
        """get_all(limit=15) when only 10 exist should return 10 entities."""
        all_result = await repository_with_entities.get_all(limit=15)
        assert len(all_result) == 10

    @pytest.mark.asyncio
    async def test_get_all_with_limit_negative(
        self, repository_with_entities: Repository[EntityType, IDType]
    ) -> None:
        """get_all(limit=-1) should raise PaginationParameterError."""
        with pytest.raises(PaginationParameterError, match="limit must be non-negative"):
            await repository_with_entities.get_all(limit=-1)

    @pytest.mark.asyncio
    async def test_get_all_with_offset(
        self,
        repository_with_entities: Repository[EntityType, IDType],
        entity_ids: list[IDType],
    ) -> None:
        """get_all(offset=6) should skip first 6 entities."""
        offset = 6
        all_result = await repository_with_entities.get_all(offset=offset)
        assert len(all_result) == 4

    @pytest.mark.asyncio
    async def test_get_all_with_offset_superior_to_len_entities(
        self, repository_with_entities: Repository[EntityType, IDType]
    ) -> None:
        """get_all(offset=15) when only 10 exist should return empty list."""
        all_result = await repository_with_entities.get_all(offset=15)
        assert len(all_result) == 0

    @pytest.mark.asyncio
    async def test_get_all_with_offset_negative(
        self, repository_with_entities: Repository[EntityType, IDType]
    ) -> None:
        """get_all(offset=-1) should raise PaginationParameterError."""
        with pytest.raises(PaginationParameterError, match="offset must be non-negative"):
            await repository_with_entities.get_all(offset=-1)

    @pytest.mark.asyncio
    async def test_get_all_limit_with_offset_case_1(
        self, repository_with_entities: Repository[EntityType, IDType]
    ) -> None:
        """get_all(limit=5, offset=2) should return 5 entities starting from index 2."""
        offset = 2
        limit = 5
        all_result = await repository_with_entities.get_all(limit=limit, offset=offset)
        assert len(all_result) == 5

    @pytest.mark.asyncio
    async def test_get_all_limit_with_offset_case_2(
        self, repository_with_entities: Repository[EntityType, IDType]
    ) -> None:
        """get_all(limit=5, offset=8) should return only 2 entities (8, 9)."""
        offset = 8
        limit = 5
        all_result = await repository_with_entities.get_all(limit=limit, offset=offset)
        assert len(all_result) == 2

    @pytest.mark.asyncio
    async def test_get_all_limit_with_offset_case_3(
        self, repository_with_entities: Repository[EntityType, IDType]
    ) -> None:
        """get_all(limit=5, offset=10) should return empty list."""
        offset = 10
        limit = 5
        all_result = await repository_with_entities.get_all(limit=limit, offset=offset)
        assert len(all_result) == 0

    # ==================== Contract Tests: insert_one ====================

    @pytest.mark.asyncio
    async def test_insert_one_empty_entities(
        self,
        repository: Repository[EntityType, IDType],
        entity_factory: Callable[..., EntityType],
    ) -> None:
        """insert_one() on empty repository should succeed."""
        entity = entity_factory(name="Test Entity")
        result = await repository.insert_one(entity)

        assert result.id == entity.id
        assert result.name == "Test Entity"

        # Verify using abstract method (not repository.get_by_id!)
        assert await self._verify_entity_exists(repository, entity.id)
        assert await self._verify_entity_count(repository) == 1

    @pytest.mark.asyncio
    async def test_insert_one_with_id_taken(
        self,
        repository_with_entities: Repository[EntityType, IDType],
        entity_ids: list[IDType],
        entity_factory: Callable[..., EntityType],
    ) -> None:
        """insert_one() with existing ID should raise DuplicateError."""
        duplicate_entity = entity_factory(entity_id=entity_ids[0], name="Duplicate")

        with pytest.raises(EntityAlreadyExistsError, match="already exists"):
            await repository_with_entities.insert_one(duplicate_entity)

    # ==================== Contract Tests: insert_many ====================

    @pytest.mark.asyncio
    async def test_insert_many_success(
        self,
        repository_with_entities: Repository[EntityType, IDType],
        entity_factory: Callable[..., EntityType],
    ) -> None:
        """insert_many() with valid entities should insert all."""
        entities = [entity_factory(name=f"Entity {i}") for i in range(5)]
        result = await repository_with_entities.insert_many(entities)

        assert len(result) == 5
        assert await self._verify_entity_count(repository_with_entities) == 15  # 10 initial + 5 new

    @pytest.mark.asyncio
    async def test_insert_many_with_only_duplicate(
        self,
        repository_with_entities: Repository[EntityType, IDType],
        entity_ids: list[IDType],
        entity_factory: Callable[..., EntityType],
    ) -> None:
        """insert_many() with one duplicate should raise DuplicateError."""
        entities = [entity_factory(entity_id=entity_ids[0], name="Duplicate")]

        with pytest.raises(EntityAlreadyExistsError, match="already exists"):
            await repository_with_entities.insert_many(entities)

    @pytest.mark.asyncio
    async def test_insert_many_with_duplicates_in_list(
        self,
        repository: Repository[EntityType, IDType],
        entity_factory: Callable[..., EntityType],
    ) -> None:
        """insert_many() with duplicates in input list should raise DuplicateError."""
        # Create two entities with the same ID
        entity1 = entity_factory(name="First")
        entity2 = entity_factory(entity_id=entity1.id, name="Duplicate")
        entities = [entity1, entity2]

        with pytest.raises(EntityAlreadyExistsError, match="already exists"):
            await repository.insert_many(entities)

    @pytest.mark.asyncio
    async def test_insert_many_atomicity(
        self,
        repository_with_entities: Repository[EntityType, IDType],
        entity_ids: list[IDType],
        entity_factory: Callable[..., EntityType],
    ) -> None:
        """insert_many() should be atomic: failure means no entities inserted."""
        initial_count = await self._verify_entity_count(repository_with_entities)

        entities = [
            entity_factory(name="Valid Entity"),
            entity_factory(entity_id=entity_ids[0], name="Duplicate"),  # Will fail
        ]

        with pytest.raises(EntityAlreadyExistsError):
            await repository_with_entities.insert_many(entities)

        # Verify atomicity: count should be unchanged
        assert await self._verify_entity_count(repository_with_entities) == initial_count

    @pytest.mark.asyncio
    async def test_insert_many_empty_list(
        self,
        repository: Repository[EntityType, IDType],
    ) -> None:
        """insert_many([]) should return empty list and insert nothing."""
        result = await repository.insert_many([])
        assert result == []
        assert await self._verify_entity_count(repository) == 0

    # ==================== Contract Tests: update ====================

    @pytest.mark.asyncio
    async def test_update_success(
        self,
        repository_with_entities: Repository[EntityType, IDType],
        entity_ids: list[IDType],
        entity_factory: Callable[..., EntityType],
    ) -> None:
        """update() on existing entity should modify it."""
        updated_entity = entity_factory(entity_id=entity_ids[0], name="Updated Name")
        result = await repository_with_entities.update(updated_entity)

        assert result.name == "Updated Name"
        # Verify using abstract method
        assert await self._verify_entity_data(
            repository_with_entities, entity_ids[0], "Updated Name"
        )

    @pytest.mark.asyncio
    async def test_update_fail(
        self,
        repository: Repository[EntityType, IDType],
        entity_factory: Callable[..., EntityType],
    ) -> None:
        """update() on non-existent entity should raise NotFoundError."""
        entity = entity_factory(name="Non-existent")

        with pytest.raises(EntityNotFoundError, match="not found"):
            await repository.update(entity)

    # ==================== Contract Tests: delete_by_id ====================

    @pytest.mark.asyncio
    async def test_delete_success(
        self,
        repository_with_entities: Repository[EntityType, IDType],
        entity_ids: list[IDType],
    ) -> None:
        """delete_by_id() should remove the entity."""
        await repository_with_entities.delete_by_id(entity_id=entity_ids[0])

        # Verify deletion using abstract method
        assert not await self._verify_entity_exists(repository_with_entities, entity_ids[0])
        assert await self._verify_entity_count(repository_with_entities) == 9

    @pytest.mark.asyncio
    async def test_delete_failed(self, repository: Repository[EntityType, IDType]) -> None:
        """delete_by_id() on non-existent ID should raise NotFoundError."""
        with pytest.raises(EntityNotFoundError, match="not found"):
            await repository.delete_by_id(entity_id="nonexistent_id_67890")

    # ==================== Contract Tests: delete_all ====================

    @pytest.mark.asyncio
    async def test_delete_all_success(
        self,
        repository_with_entities: Repository[EntityType, IDType],
    ) -> None:
        """delete_all() should remove all entities."""
        await repository_with_entities.delete_all()
        assert await self._verify_entity_count(repository_with_entities) == 0

    @pytest.mark.asyncio
    async def test_delete_all_empty(
        self,
        repository: Repository[EntityType, IDType],
    ) -> None:
        """delete_all() on empty repository should succeed."""
        await repository.delete_all()
        assert await self._verify_entity_count(repository) == 0

    # ==================== Contract Tests: Integration ====================

    @pytest.mark.asyncio
    async def test_complete_crud_cycle(
        self,
        repository: Repository[EntityType, IDType],
        entity_factory: Callable[..., EntityType],
    ) -> None:
        """Full CRUD cycle: Create, Read, Update, Delete."""
        # Create
        entity = entity_factory(name="Original Name")
        await repository.insert_one(entity)
        assert await self._verify_entity_exists(repository, entity.id)

        # Read (via verification method to respect testing rules)
        assert await self._verify_entity_data(repository, entity.id, "Original Name")

        # Update
        entity.name = "Updated Name"
        await repository.update(entity)
        assert await self._verify_entity_data(repository, entity.id, "Updated Name")

        # Delete
        await repository.delete_by_id(entity_id=entity.id)
        assert not await self._verify_entity_exists(repository, entity.id)
        assert await self._verify_entity_count(repository) == 0

    # ==================== Contract Tests: Error Hierarchy ====================

    @pytest.mark.asyncio
    async def test_repository_error_hierarchy(
        self,
        repository: Repository[EntityType, IDType],
        entity_factory: Callable[..., EntityType],
    ) -> None:
        """All repository exceptions should inherit from RepositoryError."""
        # NotFoundError is a RepositoryError
        with pytest.raises(DatabaseError):
            await repository.get_by_id(entity_id="nonexistent")

        # DuplicateError is a RepositoryError
        entity = entity_factory(name="Test")
        await repository.insert_one(entity)
        # Create a NEW instance with the SAME ID to trigger duplicate error
        duplicate = entity_factory(entity_id=entity.id, name="Duplicate")
        with pytest.raises(DatabaseError):
            await repository.insert_one(duplicate)
