from typing import Self

from typing_extensions import override

from infrakit.repository import InMemory
from infrakit.repository.memory import InMemorySession
from infrakit.repository.protocols import HasId, UnitOfWork


class InMemoryUnitOfWork(UnitOfWork):
    session: InMemorySession

    def __init__(self, entity_models: list[type[HasId]]) -> None:
        self.entity_models = entity_models
        self.repositories = {}

    async def __aenter__(self) -> Self:
        self.session = InMemorySession()
        self.repositories = {
            entity_model: InMemory(
                entity_model=entity_model, auto_commit=False, session=self.session
            )
            for entity_model in self.entity_models
        }
        return self

    @override
    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        await self.session.close()

    @override
    async def commit(self) -> None:
        """Commit the current transaction, persisting all changes to the database.

        Raises:
            DatabaseError: If the commit fails (mapped from any infrastructure exception)
        """
        await self.session.commit()

    @override
    async def rollback(self) -> None:
        """Roll back the current transaction, discarding all uncommitted changes."""
        await self.session.rollback()
