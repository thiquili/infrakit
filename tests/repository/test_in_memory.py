from collections.abc import Callable
import random

from pydantic import BaseModel
import pytest
import pytest_asyncio
from ulid import ULID

from infrakit.ports.repository.in_memory import (
    DuplicateError,
    EntityModelError,
    InMemory,
    NotFoundError,
    RepositoryError,
)


class User(BaseModel):
    id: ULID
    name: str


@pytest.fixture
def user_factory() -> Callable[..., User]:
    def _create_user(user_id: ULID, name: str = "name") -> User:
        return User(id=user_id, name=name)

    return _create_user


@pytest.fixture
def in_memory() -> InMemory[User, str]:
    in_memory: InMemory[User, str] = InMemory(entity_model=User)
    return in_memory


@pytest_asyncio.fixture
async def in_memory_full(
    in_memory: InMemory, user_factory: Callable[..., User]
) -> InMemory[User, str]:
    random.seed(42)
    for _i in range(10):
        ulid = ULID()
        await in_memory.insert_one(user_factory(user_id=ulid, name=f"name {ulid}"))
    return in_memory


@pytest.fixture
def keys_in_memory(in_memory_full: InMemory[User, str]) -> list[str]:
    return list(in_memory_full.entities.keys())


def test_init(in_memory: InMemory) -> None:
    assert in_memory.entities == {}


@pytest.mark.asyncio
async def test_get_by_id(
    in_memory_full: InMemory, keys_in_memory: list[str], user_factory: Callable[..., User]
) -> None:
    for ulid in keys_in_memory:
        assert await in_memory_full.get_by_id(entity_id=ulid) == user_factory(
            user_id=ulid, name=f"name {ulid}"
        )


@pytest.mark.asyncio
async def test_get_by_id_not_found(in_memory: InMemory) -> None:
    with pytest.raises(NotFoundError, match="id 999 not found"):
        await in_memory.get_by_id(entity_id=999)


@pytest.mark.asyncio
async def test_get_all(
    in_memory_full: InMemory, keys_in_memory: list[str], user_factory: Callable[..., User]
) -> None:
    all_result = await in_memory_full.get_all()
    assert len(all_result) == 10
    for index, entity in enumerate(all_result):
        assert isinstance(entity, User)
        assert entity.name == f"name {keys_in_memory[index]}"
        assert entity.id == keys_in_memory[index]


@pytest.mark.asyncio
async def test_get_all_with_limit_0(in_memory_full: InMemory) -> None:
    all_result = await in_memory_full.get_all(limit=0)
    assert len(all_result) == 0


@pytest.mark.asyncio
async def test_get_all_with_limit_5(
    in_memory_full: InMemory, keys_in_memory: list[str], user_factory: Callable[..., User]
) -> None:
    limit = 5
    all_result = await in_memory_full.get_all(limit=limit)
    assert len(all_result) == 5
    for index, entity in enumerate(all_result):
        assert isinstance(entity, User)
        assert entity.name == f"name {keys_in_memory[index]}"
        assert entity.id == keys_in_memory[index]


@pytest.mark.asyncio
async def test_get_all_with_limit_superior_to_len_entities(
    in_memory_full: InMemory, keys_in_memory: list[str], user_factory: Callable[..., User]
) -> None:
    all_result = await in_memory_full.get_all(limit=15)
    assert len(all_result) == 10
    for index, entity in enumerate(all_result):
        assert isinstance(entity, User)
        assert entity.name == f"name {keys_in_memory[index]}"
        assert entity.id == keys_in_memory[index]


@pytest.mark.asyncio
async def test_get_all_with_limit_negative(in_memory_full: InMemory) -> None:
    with pytest.raises(ValueError, match="limit must be non-negative"):
        await in_memory_full.get_all(limit=-1)


@pytest.mark.asyncio
async def test_get_all_with_offset(
    in_memory_full: InMemory, keys_in_memory: list[str], user_factory: Callable[..., User]
) -> None:
    offset = 6
    all_result = await in_memory_full.get_all(offset=offset)
    assert len(all_result) == 4
    for index, entity in enumerate(all_result):
        new_index = index + offset
        assert isinstance(entity, User)
        assert entity.name == f"name {keys_in_memory[new_index]}"
        assert entity.id == keys_in_memory[new_index]


@pytest.mark.asyncio
async def test_get_all_with_offset_superior_to_len_entities(in_memory_full: InMemory) -> None:
    offset = 15
    all_result = await in_memory_full.get_all(offset=offset)
    assert len(all_result) == 0


@pytest.mark.asyncio
async def test_get_all_with_offset_negative(in_memory_full: InMemory) -> None:
    with pytest.raises(ValueError, match="offset must be non-negative"):
        await in_memory_full.get_all(offset=-1)


@pytest.mark.asyncio
async def test_get_all_limit_with_offset_case_1(
    in_memory_full: InMemory, keys_in_memory: list[str], user_factory: Callable[..., User]
) -> None:
    offset = 2
    limit = 5
    all_result = await in_memory_full.get_all(limit=limit, offset=offset)
    assert len(all_result) == 5
    for index, entity in enumerate(all_result):
        new_index = index + offset
        assert isinstance(entity, User)
        assert entity.name == f"name {keys_in_memory[new_index]}"
        assert entity.id == keys_in_memory[new_index]


@pytest.mark.asyncio
async def test_get_all_limit_with_offset_case_2(
    in_memory_full: InMemory, keys_in_memory: list[str], user_factory: Callable[..., User]
) -> None:
    offset = 8
    limit = 5
    all_result = await in_memory_full.get_all(limit=limit, offset=offset)
    assert len(all_result) == 2
    for index, entity in enumerate(all_result):
        new_index = index + offset
        assert isinstance(entity, User)
        assert entity.name == f"name {keys_in_memory[new_index]}"
        assert entity.id == keys_in_memory[new_index]


@pytest.mark.asyncio
async def test_get_all_limit_with_offset_case_3(
    in_memory_full: InMemory, user_factory: Callable[..., User]
) -> None:
    offset = 10
    limit = 5
    all_result = await in_memory_full.get_all(limit=limit, offset=offset)
    assert len(all_result) == 0


@pytest.mark.asyncio
async def test_insert_one_empty_entities(
    in_memory: InMemory, user_factory: Callable[..., User]
) -> None:
    ulid = ULID()
    result = await in_memory.insert_one(user_factory(user_id=ulid, name="name 5"))
    assert isinstance(result, User)
    assert result.id == ulid
    assert result.name == "name 5"


@pytest.mark.asyncio
async def test_insert_one_with_id_taken(
    in_memory_full: InMemory, keys_in_memory: list[str], user_factory: Callable[..., User]
) -> None:
    with pytest.raises(DuplicateError, match=f"id {keys_in_memory[0]} already exists"):
        await in_memory_full.insert_one(user_factory(user_id=keys_in_memory[0], name="name 5"))


@pytest.mark.asyncio
async def test_delete_success(in_memory_full: InMemory, keys_in_memory: list[str]) -> None:
    await in_memory_full.delete_by_id(entity_id=keys_in_memory[0])
    with pytest.raises(NotFoundError, match=f"id {keys_in_memory[0]} not found"):
        await in_memory_full.get_by_id(entity_id=keys_in_memory[0])


@pytest.mark.asyncio
async def test_delete_failed(in_memory: InMemory) -> None:
    ulid = ULID()
    with pytest.raises(NotFoundError, match=f"id {ulid} not found"):
        await in_memory.delete_by_id(entity_id=ulid)


@pytest.mark.asyncio
async def test_delete_all_success(in_memory_full: InMemory) -> None:
    await in_memory_full.delete_all()
    assert await in_memory_full.get_all() == []


@pytest.mark.asyncio
async def test_delete_all_empty(in_memory: InMemory) -> None:
    await in_memory.delete_all()
    assert await in_memory.get_all() == []


@pytest.mark.asyncio
async def test_update_success(
    in_memory_full: InMemory, keys_in_memory: list[str], user_factory: Callable[..., User]
) -> None:
    update_user = user_factory(user_id=keys_in_memory[0], name="name toto")
    await in_memory_full.update(update_user)
    assert await in_memory_full.get_by_id(update_user.id) == update_user


@pytest.mark.asyncio
async def test_update_fail(in_memory: InMemory, user_factory: Callable[..., User]) -> None:
    ulid = ULID()
    update_user = user_factory(user_id=ulid, name="name 55")
    with pytest.raises(NotFoundError, match=f"id {ulid} not found"):
        await in_memory.update(update_user)


@pytest.mark.asyncio
async def test_insert_many_success(
    in_memory_full: InMemory, user_factory: Callable[..., User]
) -> None:
    users = [user_factory(user_id=ULID(), name=f"name {i}") for i in range(5)]
    result = await in_memory_full.insert_many(users)
    assert len(result) == 5
    assert len(await in_memory_full.get_all()) == 15


@pytest.mark.asyncio
async def test_insert_many_with__only_duplicate(
    in_memory_full: InMemory, keys_in_memory: list[str], user_factory: Callable[..., User]
) -> None:
    users = [user_factory(user_id=keys_in_memory[0], name="duplicate")]
    with pytest.raises(DuplicateError, match=f"id {keys_in_memory[0]} already exists"):
        await in_memory_full.insert_many(users)


@pytest.mark.asyncio
async def test_insert_many_with_duplicates_in_list(
    in_memory: InMemory, user_factory: Callable[..., User]
) -> None:
    ulid = ULID()
    users = [
        user_factory(user_id=ulid, name="first"),
        user_factory(user_id=ulid, name="duplicate"),
    ]
    with pytest.raises(DuplicateError, match=f"duplicate id {ulid} in input list"):
        await in_memory.insert_many(users)


@pytest.mark.asyncio
async def test_insert_many_atomicity(
    in_memory_full: InMemory, keys_in_memory: list[str], user_factory: Callable[..., User]
) -> None:
    initial_count = len(await in_memory_full.get_all())
    ulid = ULID()
    users = [
        user_factory(user_id=ulid, name="new"),
        user_factory(user_id=keys_in_memory[0], name="duplicate"),  # Va échouer
    ]
    with pytest.raises(DuplicateError):
        await in_memory_full.insert_many(users)
    assert len(await in_memory_full.get_all()) == initial_count
    with pytest.raises(NotFoundError):
        await in_memory_full.get_by_id(ulid)


@pytest.mark.asyncio
async def test_insert_many_empty_list(in_memory: InMemory) -> None:
    result = await in_memory.insert_many([])
    assert result == []
    assert len(await in_memory.get_all()) == 0


@pytest.mark.asyncio
async def test_complete(in_memory: InMemory, user_factory: Callable[..., User]) -> None:
    ulid = ULID()
    user = user_factory(user_id=ulid, name="new")
    await in_memory.insert_one(user)
    assert await in_memory.get_by_id(entity_id=ulid) == user
    assert await in_memory.get_all() == [user]
    user.name = "update"
    await in_memory.update(user)
    update_user = await in_memory.get_by_id(entity_id=ulid)
    update_user.name = "update"
    await in_memory.delete_by_id(entity_id=ulid)
    assert await in_memory.get_all() == []
    with pytest.raises(NotFoundError):
        await in_memory.get_by_id(entity_id=ulid)


@pytest.mark.asyncio
async def test_entity_model_raise_error(in_memory: InMemory) -> None:
    class Company(BaseModel):
        id: ULID
        company_name: str

    new_company = Company(id=ULID(), company_name="new")
    with pytest.raises(EntityModelError, match="Entity must be of type User, got Company"):
        await in_memory.insert_one(new_company)
    with pytest.raises(EntityModelError, match="Entity must be of type User, got Company"):
        await in_memory.insert_many([new_company])
    with pytest.raises(EntityModelError, match="Entity must be of type User, got Company"):
        await in_memory.update(new_company)


@pytest.mark.asyncio
async def test_get_all_preserves_insertion_order() -> None:
    """Verify that get_all() returns entities in insertion order, not sorted by ID."""

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


@pytest.mark.asyncio
async def test_repository_error_hierarchy(
    in_memory: InMemory, user_factory: Callable[..., User]
) -> None:
    """Verify that all repository exceptions inherit from RepositoryError."""
    ulid = ULID()

    # NotFoundError is a RepositoryError
    with pytest.raises(RepositoryError):
        await in_memory.get_by_id(entity_id=ulid)

    # DuplicateError is a RepositoryError
    user = user_factory(user_id=ulid, name="test")
    await in_memory.insert_one(user)
    with pytest.raises(RepositoryError):
        await in_memory.insert_one(user)

    # EntityModelError is a RepositoryError
    class Company(BaseModel):
        id: ULID
        company_name: str

    company = Company(id=ULID(), company_name="test")
    with pytest.raises(RepositoryError):
        await in_memory.insert_one(company)
