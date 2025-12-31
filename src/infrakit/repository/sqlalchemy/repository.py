"""SQLAlchemy implementation of the Repository pattern."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError
from typing_extensions import override

from infrakit.repository.exceptions import EntityNotFoundError
from infrakit.repository.protocols import ID, Repository, T
from infrakit.repository.sqlalchemy.mapper import SqlAlchemyExceptionMapper

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemy(Repository[T, ID]):
    """SQLAlchemy implementation of the Repository pattern.

    This implementation uses SQLAlchemy's AsyncSession to perform database operations
    with optional auto-commit support.

    Type Parameters:
        T: The entity type managed by this repository (must have an id attribute).
        ID: The type of the entity's identifier (int, str, UUID, etc.).

    Attributes:
        session: The SQLAlchemy async session used for database operations.
        entity_model: The SQLAlchemy model class representing the entity type.
        auto_commit: Whether to automatically commit after each operation.

    Note:
        When auto_commit=False, transaction management should be handled externally
        (e.g., via a Unit of Work pattern).
    """

    def __init__(
        self, session: AsyncSession, entity_model: type[T], *, auto_commit: bool = False
    ) -> None:
        """Initialize the SQLAlchemy repository.

        Args:
            session: An AsyncSession instance for database operations.
            entity_model: The SQLAlchemy model class for the entity type.
            auto_commit: Whether to automatically commit after each operation.
        """
        self.session = session
        self.entity_model = entity_model
        self.auto_commit = auto_commit
        self._exception_mapper = SqlAlchemyExceptionMapper()

    async def _commit_if_enabled(
        self, entity_type: str | None = None, entity_id: str | None = None
    ) -> None:
        """Commit the session if auto_commit is enabled with error handling.

        Args:
            entity_type: Entity type name for error messages
            entity_id: Entity ID for error messages

        Raises:
            DatabaseError: If commit fails (mapped from any infrastructure exception)

        Note:
            When auto_commit=False, this method does nothing. Errors will be
            detected when the session is committed externally (e.g., by a Unit of Work).
        """
        if self.auto_commit:
            try:
                await self.session.commit()
            except Exception as e:
                await self.session.rollback()

                # Map infrastructure exception to domain exception
                # The mapper always returns a DatabaseError (specific or generic)
                domain_error = self._exception_mapper.map(
                    error=e,
                    entity_type=entity_type or self.entity_model.__name__,
                    entity_id=entity_id or "unknown",
                )
                raise domain_error from e

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
        entity = await self.session.get(self.entity_model, entity_id)
        if entity is None:
            raise EntityNotFoundError(
                entity_type=self.entity_model.__name__, entity_id=str(entity_id)
            )
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

        Raises:
            PaginationParameterError: If limit or offset is negative.
        """
        try:
            query = select(self.entity_model).limit(limit).offset(offset)
            entities = await self.session.execute(query)
            return list(entities.scalars().all())
        except DBAPIError as e:
            # Map database pagination errors to domain exception
            domain_error = self._exception_mapper.map(
                error=e, entity_type=self.entity_model.__name__, entity_id=None
            )
            raise domain_error from e

    @override
    async def insert_one(self, entity: T) -> T:
        """Insert a single entity into the repository.

        Args:
            entity: The entity to insert (with a pre-generated identifier).

        Returns:
            The inserted entity.

        Raises:
            EntityAlreadyExistsError: If an entity with the same ID already exists
                (only when auto_commit=True or when committed by a Unit of Work).
        """
        self.session.add(entity)
        await self._commit_if_enabled(
            entity_type=self.entity_model.__name__, entity_id=str(entity.id)
        )
        return entity

    @override
    async def insert_many(self, entities: list[T]) -> list[T]:
        """Insert multiple entities into the repository in a single operation.

        Args:
            entities: A list of entities to insert (with pre-generated identifiers).

        Returns:
            The list of inserted entities.

        Raises:
            EntityAlreadyExistsError: If one or more entities already exist
                (only when auto_commit=True or when committed by a Unit of Work).
        """
        if not entities:
            return []

        self.session.add_all(entities)
        await self._commit_if_enabled(
            entity_type=self.entity_model.__name__, entity_id="multiple entities"
        )
        return entities

    @override
    async def update(self, entity: T) -> T:
        """Update an existing entity in the repository.

        Verifies that the entity exists before updating.

        Args:
            entity: The entity with updated values. Must have a valid identifier.

        Returns:
            The updated entity as stored in the repository.

        Raises:
            EntityNotFoundError: If no entity exists with the given identifier.
        """
        await self.get_by_id(entity_id=entity.id)
        await self.session.merge(entity)
        await self._commit_if_enabled(
            entity_type=self.entity_model.__name__, entity_id=str(entity.id)
        )
        return entity

    @override
    async def delete_by_id(self, entity_id: ID) -> None:
        """Delete an entity from the repository by its identifier.

        Verifies that the entity exists before deleting.

        Args:
            entity_id: The unique identifier of the entity to delete.

        Raises:
            EntityNotFoundError: If no entity exists with the given identifier.
        """
        existing = await self.get_by_id(entity_id=entity_id)
        await self.session.delete(existing)
        await self._commit_if_enabled(
            entity_type=self.entity_model.__name__, entity_id=str(entity_id)
        )

    @override
    async def delete_all(self) -> None:
        """Delete all entities from the repository.

        Warning:
            This operation will delete all entities of this type from the database.
        """
        stmt = delete(self.entity_model)
        await self.session.execute(stmt)
        await self._commit_if_enabled(entity_type=self.entity_model.__name__, entity_id="all")
