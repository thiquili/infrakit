"""Repository protocol definition."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Generic, Protocol, TypeVar

ID = TypeVar("ID")


class HasId(Protocol):
    """Protocol for entities that have an id attribute.

    This allows the Repository to work with any class that has an id field,
    without requiring inheritance from a base class.
    """

    id: Any


T = TypeVar("T", bound=HasId)


class Repository(ABC, Generic[T, ID]):
    """Abstract base class for implementing the Repository pattern.

    This class provides a generic interface for data access operations (CRUD)
    that can be implemented for various storage backends.

    Type Parameters:
        T: The entity type managed by this repository.
        ID: The type of the entity's identifier (int, str, UUID, etc.).
    """

    @abstractmethod
    async def get_by_id(self, entity_id: ID) -> T:
        """Retrieve an entity by its unique identifier.

        Args:
            entity_id: The unique identifier of the entity to retrieve.

        Returns:
            The entity matching the given identifier.

        Raises:
            EntityNotFoundError: If no entity exists with the given identifier.
        """

    @abstractmethod
    async def get_all(self, limit: int | None = None, offset: int = 0) -> list[T]:
        """Retrieve all entities from the repository.

        Args:
            limit: Maximum number of entities to retrieve (must be >= 0 if provided).
                   None returns all entities.
            offset: Number of entities to skip before starting retrieval (must be >= 0).

        Returns:
            A list of entities, respecting the limit and offset parameters.

        Raises:
            ValueError: If limit or offset is negative.
        """

    @abstractmethod
    async def insert_one(self, entity: T) -> T:
        """Insert a single entity into the repository.

        Args:
            entity: The entity to insert.

        Returns:
            The inserted entity, potentially with generated fields (e.g., ID, timestamps).

        Raises:
            EntityAlreadyExistsError: If an entity with the same identifier already exists.
        """

    @abstractmethod
    async def insert_many(self, entities: list[T]) -> list[T]:
        """Insert multiple entities into the repository in a single operation.

        Args:
            entities: A list of entities to insert.

        Returns:
            The list of inserted entities, potentially with generated fields.

        Raises:
            EntityAlreadyExistsError: If one or more entities with the same identifiers already exist.
        """

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Update an existing entity in the repository.

        Args:
            entity: The entity with updated values. Must have a valid identifier.

        Returns:
            The updated entity as stored in the repository.

        Raises:
            EntityNotFoundError: If no entity exists with the given identifier.
        """

    @abstractmethod
    async def delete_by_id(self, entity_id: ID) -> None:
        """Delete an entity from the repository by its identifier.

        Args:
            entity_id: The unique identifier of the entity to delete.

        Raises:
            EntityNotFoundError: If no entity exists with the given identifier.
        """

    @abstractmethod
    async def delete_all(self) -> None:
        """Delete all entities from the repository.

        This operation clears the entire repository.
        """


class UnitOfWork(ABC):
    """Represents a unit of work for database operations.

    A unit of work encapsulates a set of database operations that should be treated as a single logical transaction.
    It ensures that all operations within the unit are executed atomically, either all succeed or all fail.
    """

    # TODO: fix typing
    repositories: Mapping[type, Repository]  # pyright: ignore[reportMissingTypeArgument]

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        await self.rollback()

    @abstractmethod
    async def commit(self) -> None:
        """Commit the changes made within this unit of work.

        This method should be called to finalize the unit of work and persist the changes to the database.
        If any operation within the unit fails, the entire unit will be rolled back.
        """

    @abstractmethod
    async def rollback(self) -> None:
        """
        Defines an abstract method for rolling back an operation.
        """
