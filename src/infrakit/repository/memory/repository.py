"""In-memory implementation of the Repository pattern."""

from __future__ import annotations

from typing_extensions import override

from infrakit.repository.exceptions import (
    EntityAlreadyExistsError,
    EntityModelError,
    EntityNotFoundError,
    PaginationParameterError,
)
from infrakit.repository.memory.session import InMemorySession
from infrakit.repository.protocols import ID, Repository, T


class InMemory(Repository[T, ID]):
    """In-memory implementation of the Repository pattern.

    This implementation stores entities in a dictionary for fast access
    with optional auto-commit support via InMemorySession.

    Type Parameters:
        T: The entity type managed by this repository.
        ID: The type of the entity's identifier as stored in the entity itself
            (int, str, UUID, ULID, etc.).

    Attributes:
        session: The InMemorySession used for storage and transaction management.
        entity_model: The entity class representing the entity type.
        auto_commit: Whether to automatically commit after each operation.

    Important Note:
        While ID represents the type of identifiers in your entities, the internal
        dictionary always uses string keys (via str(entity.id)) to ensure compatibility
        with non-hashable types like ULID. When calling repository methods, you can
        pass IDs in their original type - they will be automatically converted to
        strings internally.

        Example:
            # Entity has id: ULID
            class User(BaseModel):
                id: ULID
                name: str

            # Auto-commit mode: session created automatically
            repo = InMemory(entity_model=User, auto_commit=True)

            # Transaction mode: session must be provided
            session = InMemorySession()
            repo = InMemory(entity_model=User, auto_commit=False, session=session)

    Note:
        When auto_commit=False, transaction management should be handled externally
        (e.g., via a Unit of Work pattern).
    """

    def __init__(
        self,
        entity_model: type[T],
        *,
        auto_commit: bool,
        session: InMemorySession | None = None,
    ) -> None:
        """Initialize an in-memory repository.

        Args:
            entity_model: The entity class that this repository will manage.
            auto_commit: Whether to automatically commit after each operation.
                         Must be explicitly specified.
            session: An InMemorySession instance for storage and transaction management.
                     Required when auto_commit=False. If None and auto_commit=True,
                     a new session is created automatically.

        Raises:
            ValueError: If session is None and auto_commit is False.
        """
        if session is None:
            if not auto_commit:
                msg = "session is required when auto_commit=False"
                raise ValueError(msg)
            session = InMemorySession()
        self.session = session
        self.entity_model = entity_model
        self.auto_commit = auto_commit

    @property
    def entities(self) -> dict[str, T]:
        """Get read-only access to the committed entities' dictionary.

        Returns:
            Dictionary mapping entity IDs (as strings) to entity instances.

        Note:
            This property exposes internal storage for testing purposes.
            Returns committed storage, not staged changes during a transaction.
            Direct modification bypasses validation - use insert_one(),
            update(), and delete_by_id() methods instead.
        """
        return self.session.get_committed_storage(self.entity_model)

    def _get_storage(self) -> dict[str, T]:
        """Get the active storage dictionary for this entity type.

        Returns:
            The active storage dictionary - staging if in transaction,
            otherwise committed storage.
        """
        return self.session.get_active_storage(self.entity_model)

    async def _commit_if_enabled(self) -> None:
        """Commit the session if auto_commit is enabled.

        Note:
            When auto_commit=False, this method does nothing. Changes will be
            committed when the session is committed externally (e.g., by a Unit of Work).
        """
        if self.auto_commit:
            await self.session.commit()

    def _ensure_entity_model(self, entity: T) -> None:
        """Ensure an entity is of the correct model type.

        Args:
            entity: The entity to validate.

        Raises:
            EntityModelError: If the entity is not of the expected model type.
        """
        if not isinstance(entity, self.entity_model):
            actual_type = entity.__class__.__name__
            msg = f"Entity must be of type {self.entity_model.__name__}, got {actual_type}"
            raise EntityModelError(msg)

    def _ensure_entity_exists(self, entity_id: ID) -> None:
        """Ensure an entity with the given ID exists in the repository.

        Args:
            entity_id: The unique identifier to check.

        Raises:
            EntityNotFoundError: If no entity exists with the given identifier.
        """
        if str(entity_id) not in self._get_storage():
            raise EntityNotFoundError(
                entity_type=self.entity_model.__name__, entity_id=str(entity_id)
            )

    def _ensure_entity_not_exists(self, entity_id: ID) -> None:
        """Ensure an entity with the given ID does not exist in the repository.

        Args:
            entity_id: The unique identifier to check.

        Raises:
            EntityAlreadyExistsError: If an entity with the given identifier already exists.
        """
        if str(entity_id) in self._get_storage():
            raise EntityAlreadyExistsError(
                entity_type=self.entity_model.__name__, entity_id=str(entity_id)
            )

    @override
    async def get_by_id(self, entity_id: ID) -> T:
        """Retrieve an entity by its unique identifier.

        Args:
            entity_id: The unique identifier of the entity to retrieve.

        Returns:
            The entity matching the given identifier.

        Raises:
            EntityNotFoundError: If no entity exists with the given identifier.
        """
        self._ensure_entity_exists(entity_id)
        return self._get_storage()[str(entity_id)]

    @override
    async def get_all(self, limit: int | None = None, offset: int = 0) -> list[T]:
        """Retrieve all entities from the repository.

        Entities are returned in insertion order (the order in which they were added
        to the repository).

        Args:
            limit: Maximum number of entities to retrieve (must be >= 0 if provided).
                   None returns all entities.
            offset: Number of entities to skip before starting retrieval (must be >= 0).

        Returns:
            A list of entities in insertion order, respecting the limit and offset parameters.

        Raises:
            PaginationParameterError: If limit or offset is negative.
        """
        if limit is not None and limit < 0:
            msg = "limit"
            raise PaginationParameterError(msg, limit)
        if offset < 0:
            msg = "offset"
            raise PaginationParameterError(msg, offset)
        result: list[T] = list(self._get_storage().values())
        if limit is None:
            if offset > 0:
                return result[offset:]
            return result
        if offset > 0:
            return result[offset : offset + limit]
        return result[:limit]

    @override
    async def insert_one(self, entity: T) -> T:
        """Insert a single entity into the repository.

        Args:
            entity: The entity to insert.

        Returns:
            The inserted entity.

        Raises:
            EntityAlreadyExistsError: If an entity with the same identifier already exists
                (only when auto_commit=True or when committed by a Unit of Work).
        """
        self._ensure_entity_model(entity)
        self._ensure_entity_not_exists(entity_id=entity.id)
        self._get_storage()[str(entity.id)] = entity
        await self._commit_if_enabled()
        return entity

    @override
    async def insert_many(self, entities: list[T]) -> list[T]:
        """Insert multiple entities into the repository in a single operation.

        This operation is atomic: if any entity fails validation, no entities
        are inserted.

        Args:
            entities: A list of entities to insert.

        Returns:
            The list of inserted entities.

        Raises:
            EntityAlreadyExistsError: If one or more entities with the same identifiers
                           already exist in the repository, or if duplicate IDs
                           are found within the input list
                           (only when auto_commit=True or when committed by a Unit of Work).
        """
        if not entities:
            return []

        inserts: dict[str, T] = {}
        for entity in entities:
            self._ensure_entity_model(entity)
            self._ensure_entity_not_exists(entity_id=entity.id)
            # Check for duplicates within the input list
            if str(entity.id) in inserts:
                raise EntityAlreadyExistsError(
                    entity_type=self.entity_model.__name__,
                    entity_id=str(entity.id),
                )
            inserts[str(entity.id)] = entity
        self._get_storage().update(inserts)
        await self._commit_if_enabled()
        return entities

    @override
    async def delete_by_id(self, entity_id: ID) -> None:
        """Delete an entity from the repository by its identifier.

        Args:
            entity_id: The unique identifier of the entity to delete.

        Raises:
            EntityNotFoundError: If no entity exists with the given identifier.
        """
        self._ensure_entity_exists(entity_id)
        del self._get_storage()[str(entity_id)]
        await self._commit_if_enabled()

    @override
    async def delete_all(self) -> None:
        """Delete all entities from the repository.

        This operation clears the entire repository.
        """
        self._get_storage().clear()
        await self._commit_if_enabled()

    @override
    async def update(self, entity: T) -> T:
        """Update an existing entity in the repository.

        Args:
            entity: The entity with updated values. Must have a valid identifier.

        Returns:
            The updated entity as stored in the repository.

        Raises:
            EntityNotFoundError: If no entity exists with the given identifier.
        """
        self._ensure_entity_model(entity)
        self._ensure_entity_exists(entity.id)
        self._get_storage()[str(entity.id)] = entity
        await self._commit_if_enabled()
        return entity
