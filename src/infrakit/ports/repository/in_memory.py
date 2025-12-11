from typing_extensions import override

from infrakit.adapters.repository import ID, Repository, T


class RepositoryError(Exception):
    """Base exception for all repository-related errors."""


class NotFoundError(RepositoryError):
    """Raised when an entity with the specified ID cannot be found."""


class DuplicateError(RepositoryError):
    """Raised when attempting to insert an entity with an existing ID."""


class EntityModelError(RepositoryError):
    """Raised when the model of an entity does not match with the one instantiated."""


class InMemory(Repository[T, ID]):
    """In-memory implementation of the Repository pattern.

    This implementation stores entities in a dictionary for fast access.
    All operations are performed in-memory and data is not persisted.

    Type Parameters:
        T: The entity type managed by this repository.
        ID: The type of the entity's identifier as stored in the entity itself
            (int, str, UUID, ULID, etc.).

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

            # Repository uses str as dictionary keys internally
            repo: InMemory[User, str] = InMemory(entity_model=User)

            # But you can pass ULID objects to methods
            user = User(id=ULID(), name="John")
            repo.insert_one(user)
            repo.get_by_id(user.id)  # Works with ULID object
    """

    def __init__(self, entity_model: type[T]) -> None:
        """Initialize an empty in-memory repository.

        Args:
            entity_model: The entity class that this repository will manage.
        """
        self._entities: dict[str, T] = {}
        self.entity_model = entity_model

    @property
    def entities(self) -> dict[str, T]:
        """Get read-only access to the entities dictionary.

        Returns:
            Dictionary mapping entity IDs (as strings) to entity instances.

        Note:
            This property exposes internal storage for testing purposes.
            Direct modification bypasses validation - use insert_one(),
            update(), and delete_by_id() methods instead.
        """
        return self._entities

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
            NotFoundError: If no entity exists with the given identifier.
        """
        if str(entity_id) not in self.entities:
            msg = f"id {entity_id} not found"
            raise NotFoundError(msg)

    def _ensure_entity_not_exists(self, entity_id: ID) -> None:
        """Ensure an entity with the given ID does not exist in the repository.

        Args:
            entity_id: The unique identifier to check.

        Raises:
            DuplicateError: If an entity with the given identifier already exists.
        """
        if str(entity_id) in self.entities:
            msg = f"id {entity_id} already exists"
            raise DuplicateError(msg)

    @override
    def get_by_id(self, entity_id: ID) -> T:
        """Retrieve an entity by its unique identifier.

        Args:
            entity_id: The unique identifier of the entity to retrieve.

        Returns:
            The entity matching the given identifier.

        Raises:
            NotFoundError: If no entity exists with the given identifier.
        """
        self._ensure_entity_exists(entity_id)
        return self.entities[str(entity_id)]

    @override
    def get_all(self, limit: int | None = None, offset: int = 0) -> list[T]:
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
            ValueError: If limit or offset is negative.
        """
        if limit is not None and limit < 0:
            msg = "limit must be non-negative"
            raise ValueError(msg)
        if offset < 0:
            msg = "offset must be non-negative"
            raise ValueError(msg)
        result: list[T] = list(self.entities.values())
        if limit is None:
            if offset > 0:
                return result[offset:]
            return result
        if offset > 0:
            return result[offset : offset + limit]
        return result[:limit]

    @override
    def insert_one(self, entity: T) -> T:
        """Insert a single entity into the repository.

        Args:
            entity: The entity to insert.

        Returns:
            The inserted entity.

        Raises:
            DuplicateError: If an entity with the same identifier already exists.
        """
        self._ensure_entity_model(entity)
        self._ensure_entity_not_exists(entity_id=entity.id)
        self.entities[str(entity.id)] = entity
        return entity

    @override
    def insert_many(self, entities: list[T]) -> list[T]:
        """Insert multiple entities into the repository in a single operation.

        This operation is atomic: if any entity fails validation, no entities
        are inserted.

        Args:
            entities: A list of entities to insert.

        Returns:
            The list of inserted entities.

        Raises:
            DuplicateError: If one or more entities with the same identifiers
                           already exist in the repository, or if duplicate IDs
                           are found within the input list.
        """
        inserts: dict[str, T] = {}
        for entity in entities:
            self._ensure_entity_model(entity)
            self._ensure_entity_not_exists(entity_id=entity.id)
            if str(entity.id) in inserts:
                msg = f"duplicate id {entity.id} in input list"
                raise DuplicateError(msg)
            inserts[str(entity.id)] = entity
        self.entities.update(inserts)
        return entities

    @override
    def delete_by_id(self, entity_id: ID) -> None:
        """Delete an entity from the repository by its identifier.

        Args:
            entity_id: The unique identifier of the entity to delete.

        Raises:
            NotFoundError: If no entity exists with the given identifier.
        """
        self._ensure_entity_exists(entity_id)
        del self.entities[str(entity_id)]

    @override
    def delete_all(self) -> None:
        """Delete all entities from the repository.

        This operation clears the entire repository.
        """
        self._entities = {}

    @override
    def update(self, entity: T) -> T:
        """Update an existing entity in the repository.

        Args:
            entity: The entity with updated values. Must have a valid identifier.

        Returns:
            The updated entity as stored in the repository.

        Raises:
            NotFoundError: If no entity exists with the given identifier.
        """
        self._ensure_entity_model(entity)
        self._ensure_entity_exists(entity.id)
        self.entities[str(entity.id)] = entity
        return entity
