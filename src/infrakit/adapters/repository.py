from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")
ID = TypeVar("ID")


class Repository(ABC, Generic[T, ID]):
    """Abstract base class for implementing the Repository pattern.

    This class provides a generic interface for data access operations (CRUD)
    that can be implemented for relational databases

    Type Parameters:
        T: The entity type managed by this repository.
        ID: The type of the entity's identifier (int, str, UUID, etc.).
    """

    @abstractmethod
    def get_by_id(self, entity_id: ID) -> T:
        """Retrieve an entity by its unique identifier.

        Args:
            entity_id: The unique identifier of the entity to retrieve.

        Returns:
            The entity matching the given identifier.

        Raises:
            NotFoundError: If no entity exists with the given identifier.
        """

    @abstractmethod
    def get_all(self, limit: int | None = None, offset: int = 0) -> list[T]:
        """Retrieve all entities from the repository.

        Args:
            limit: Maximum number of entities to retrieve. None for all entities.
            offset: Number of entities to skip before starting retrieval.

        Returns:
            A list of entities, respecting the limit and offset parameters.
        """

    @abstractmethod
    def insert_one(self, entity: T) -> T:
        """Insert a single entity into the repository.

        Args:
            entity: The entity to insert.

        Returns:
            The inserted entity, potentially with generated fields (e.g., ID, timestamps).

        Raises:
            DuplicateError: If an entity with the same identifier already exists.
        """

    @abstractmethod
    def insert_many(self, entities: list[T]) -> list[T]:
        """Insert multiple entities into the repository in a single operation.

        Args:
            entities: A list of entities to insert.

        Returns:
            The list of inserted entities, potentially with generated fields.

        Raises:
            DuplicateError: If one or more entities with the same identifiers already exist.
        """

    @abstractmethod
    def update(self, entity: T) -> T:
        """Update an existing entity in the repository.

        Args:
            entity: The entity with updated values. Must have a valid identifier.

        Returns:
            The updated entity as stored in the repository.

        Raises:
            NotFoundError: If no entity exists with the given identifier.
        """

    @abstractmethod
    def delete_by_id(self, entity_id: ID) -> None:
        """Delete an entity from the repository by its identifier.

        Args:
            entity_id: The unique identifier of the entity to delete.

        Raises:
            NotFoundError: If no entity exists with the given identifier.
        """
