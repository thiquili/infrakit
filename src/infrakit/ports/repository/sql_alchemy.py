from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from typing_extensions import override

from infrakit.adapters.exception import EntityAlreadyExistError, EntityNotFoundError
from infrakit.adapters.repository import ID, Repository, T

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemy(Repository[T, ID]):
    """SQLAlchemy implementation of the Repository pattern.

    This implementation uses SQLAlchemy's AsyncSession to perform database operations
    without managing transactions directly. Transaction management (commit/rollback)
    should be handled by a Unit of Work pattern.

    Type Parameters:
        T: The entity type managed by this repository (must have an id attribute).
        ID: The type of the entity's identifier (int, str, UUID, etc.).

    Attributes:
        session: The SQLAlchemy async session used for database operations.
        entity_model: The SQLAlchemy model class representing the entity type.

    Note:
        This repository does not call session.commit() or session.rollback().
        These operations should be managed by the Unit of Work pattern.
    """

    def __init__(
        self, session: AsyncSession, entity_model: type[T], *, auto_commit: bool = False
    ) -> None:
        """Initialize the SQLAlchemy repository.

        Args:
            session: An AsyncSession instance for database operations.
            entity_model: The SQLAlchemy model class for the entity type.
        """
        self.session = session
        self.entity_model = entity_model
        self.auto_commit = auto_commit

    async def _commit_if_enabled(self) -> None:
        """Commit the session if auto_commit is enabled."""
        if self.auto_commit:
            try:
                await self.session.commit()
            except IntegrityError as e:
                msg = str(e)
                raise EntityAlreadyExistError(msg) from e

    @override
    async def get_by_id(self, entity_id: ID) -> T:
        """Retrieve an entity by its unique identifier.

        Args:
            entity_id: The unique identifier of the entity to retrieve.

        Returns:
            The entity matching the given identifier.

        Raises:
            NotFoundError: If no entity exists with the given identifier.
        """
        entity = await self.session.get(self.entity_model, entity_id)
        if entity is None:
            msg = f"id {entity_id} not found"
            raise EntityNotFoundError(msg)
        return entity

    @override
    async def get_all(self, limit: int | None = None, offset: int = 0) -> list[T]:
        """Retrieve all entities from the repository.

        Args:
            limit: Maximum number of entities to retrieve.
                   None returns all entities.
            offset: Number of entities to skip before starting retrieval.

        Returns:
            A list of entities, respecting the limit and offset parameters.
        """
        query = select(self.entity_model).limit(limit).offset(offset)
        entities = await self.session.execute(query)
        return list(entities.scalars().all())

    @override
    async def insert_one(self, entity: T) -> T:
        """Insert a single entity into the repository.

        The entity's identifier must be set before calling this method.
        This method adds the entity to the session but does not commit.

        Args:
            entity: The entity to insert (with a pre-generated identifier).

        Returns:
            The inserted entity.

        Note:
            IntegrityError exceptions are caught and handled by the Unit of Work.
        """
        self.session.add(entity)
        await self._commit_if_enabled()
        return entity

    @override
    async def insert_many(self, entities: list[T]) -> list[T]:
        """Insert multiple entities into the repository in a single operation.

        All entities' identifiers must be set before calling this method.
        This method adds the entities to the session but does not commit.

        Args:
            entities: A list of entities to insert (with pre-generated identifiers).

        Returns:
            The list of inserted entities.

        Note:
            IntegrityError exceptions are caught and handled by the Unit of Work.
        """
        self.session.add_all(entities)
        await self._commit_if_enabled()
        return entities

    @override
    async def update(self, entity: T) -> T:
        """Update an existing entity in the repository.

        Verifies that the entity exists before updating.
        This method merges the entity into the session but does not commit.

        Args:
            entity: The entity with updated values. Must have a valid identifier.

        Returns:
            The updated entity as stored in the repository.

        Raises:
            NotFoundError: If no entity exists with the given identifier.
        """
        await self.get_by_id(entity_id=entity.id)
        await self.session.merge(entity)
        await self._commit_if_enabled()
        return entity

    @override
    async def delete_by_id(self, entity_id: ID) -> None:
        """Delete an entity from the repository by its identifier.

        Verifies that the entity exists before deleting.
        This method marks the entity for deletion in the session but does not commit.

        Args:
            entity_id: The unique identifier of the entity to delete.

        Raises:
            NotFoundError: If no entity exists with the given identifier.
        """
        existing = await self.get_by_id(entity_id=entity_id)
        await self.session.delete(existing)
        await self._commit_if_enabled()

    @override
    async def delete_all(self) -> None:
        """Delete all entities from the repository.

        This method executes a DELETE statement for all entities but does not commit.

        Warning:
            This operation will delete all entities of this type from the database
            when the transaction is committed.
        """
        stmt = delete(self.entity_model)
        await self.session.execute(stmt)
        await self._commit_if_enabled()
