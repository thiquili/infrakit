"""
Tests for InMemory repository implementation.

This module tests the InMemory implementation by:
1. Inheriting all contract tests from RepositoryContractTests
2. Implementing verification methods using direct access to internal storage
3. Adding InMemory-specific tests (entity model validation, insertion order)
"""

from collections.abc import Callable

from pydantic import BaseModel
import pytest
import pytest_asyncio
from ulid import ULID

from infrakit.repository import InMemory
from infrakit.repository.exceptions import EntityModelError
from tests.repository.test_contract import RepositoryContractTests


class User(BaseModel):
    id: str
    name: str


class TestInMemoryRepository(RepositoryContractTests[User, str]):
    """Test suite for InMemory repository implementation."""

    # ==================== Concrete Fixtures ====================

    @pytest.fixture
    def entity_factory(self) -> Callable[..., User]:
        """Factory to create User entities for testing."""

        def _create_user(entity_id: str | None = None, name: str = "Test User") -> User:
            return User(id=entity_id or str(ULID()), name=name)

        return _create_user

    @pytest.fixture
    def repository(self) -> InMemory[User, str]:
        """Create an empty InMemory repository."""
        return InMemory(entity_model=User)

    @pytest_asyncio.fixture
    async def repository_with_entities(
        self, repository: InMemory[User, str], entity_factory: Callable[..., User]
    ) -> InMemory[User, str]:
        """
        Create a repository with 10 pre-inserted entities.

        Uses direct access to internal storage (_entities) to avoid
        using repository.insert_one() in test setup.
        """
        for i in range(10):
            user = entity_factory(name=f"User {i}")
            # Direct access to internal storage (not via insert_one!)
            repository._entities[user.id] = user  # noqa: SLF001
        return repository

    @pytest.fixture
    def entity_ids(self, repository_with_entities: InMemory[User, str]) -> list[str]:
        """Get list of entity IDs from the repository."""
        # Direct access to internal storage (not via get_all!)
        return list(repository_with_entities.entities.keys())

    # ==================== Verification Methods ====================

    async def _verify_entity_exists(self, repo: InMemory[User, str], entity_id: str) -> bool:
        """Verify entity exists by directly checking internal storage."""
        # Access via property to get the _entities dict
        return str(entity_id) in repo.entities

    async def _verify_entity_count(self, repo: InMemory[User, str]) -> int:
        """Count entities by directly checking internal storage."""
        return len(repo.entities)

    async def _verify_entity_data(
        self, repo: InMemory[User, str], entity_id: str, expected_name: str
    ) -> bool:
        """Verify entity data by directly checking internal storage."""
        if str(entity_id) not in repo.entities:
            return False
        entity = repo.entities[str(entity_id)]
        return entity.name == expected_name

    # ==================== InMemory-Specific Tests ====================

    @pytest.mark.asyncio
    async def test_entity_model_raise_error(self, repository: InMemory[User, str]) -> None:
        """InMemory should validate that entities match the expected model type."""

        class Company(BaseModel):
            id: str
            company_name: str

        new_company = Company(id=str(ULID()), company_name="Acme Corp")

        # insert_one should reject wrong entity type
        with pytest.raises(EntityModelError, match="Entity must be of type User, got Company"):
            await repository.insert_one(new_company)  # type: ignore[arg-type]

        # insert_many should reject wrong entity type
        with pytest.raises(EntityModelError, match="Entity must be of type User, got Company"):
            await repository.insert_many([new_company])  # type: ignore[arg-type]

        # update should reject wrong entity type
        with pytest.raises(EntityModelError, match="Entity must be of type User, got Company"):
            await repository.update(new_company)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_get_all_preserves_insertion_order(self) -> None:
        """
        Verify that get_all() returns entities in insertion order.

        This is a documented behavior specific to InMemory implementation.
        InMemory uses Python's dict which preserves insertion order (Python 3.7+).
        """

        class Product(BaseModel):
            id: int
            name: str

        repo: InMemory[Product, int] = InMemory(entity_model=Product)

        # Insert with IDs in non-ascending order
        await repo.insert_one(Product(id=300, name="Third"))
        await repo.insert_one(Product(id=100, name="First"))
        await repo.insert_one(Product(id=200, name="Second"))

        result = await repo.get_all()

        # Should preserve insertion order, NOT sort by ID
        assert [p.id for p in result] == [300, 100, 200]
        assert [p.name for p in result] == ["Third", "First", "Second"]
