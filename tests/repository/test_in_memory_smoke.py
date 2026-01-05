"""Smoke tests for InMemory repository with int and UUID identifiers.

These tests verify basic functionality with different ID types:
- int: Simple integer identifiers
- UUID: UUID4 identifiers
"""

from uuid import UUID, uuid4

from pydantic import BaseModel
import pytest

from infrakit.repository import EntityAlreadyExistsError, EntityNotFoundError, InMemory


class Product(BaseModel):
    """Model with int ID for testing."""

    id: int
    name: str
    price: float


class Order(BaseModel):
    """Model with UUID ID for testing."""

    id: UUID
    order_number: str
    total: float


class TestInMemoryWithIntId:
    """Smoke tests for InMemory repository with integer identifiers."""

    @pytest.fixture
    def product_repo(self) -> InMemory[Product, int]:
        return InMemory(entity_model=Product, auto_commit=True)

    @pytest.mark.asyncio
    async def test_basic_crud(self, product_repo: InMemory[Product, int]) -> None:
        """Smoke test: Create, Read, Update, Delete with int IDs."""
        # Create
        product = Product(id=1, name="Laptop", price=999.99)
        inserted = await product_repo.insert_one(product)
        assert inserted.id == 1
        assert inserted.name == "Laptop"

        # Read
        retrieved = await product_repo.get_by_id(1)
        assert retrieved == product

        # Update
        product.price = 899.99
        updated = await product_repo.update(product)
        assert updated.price == 899.99
        assert (await product_repo.get_by_id(1)).price == 899.99

        # Delete
        await product_repo.delete_by_id(1)
        with pytest.raises(EntityNotFoundError):
            await product_repo.get_by_id(1)

    @pytest.mark.asyncio
    async def test_insert_many(self, product_repo: InMemory[Product, int]) -> None:
        """Smoke test: Insert multiple entities with int IDs."""
        products = [
            Product(id=1, name="Laptop", price=999.99),
            Product(id=2, name="Mouse", price=29.99),
            Product(id=3, name="Keyboard", price=79.99),
        ]

        result = await product_repo.insert_many(products)
        assert len(result) == 3

        all_products = await product_repo.get_all()
        assert len(all_products) == 3
        assert [p.id for p in all_products] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_duplicate_error(self, product_repo: InMemory[Product, int]) -> None:
        """Smoke test: Duplicate ID detection with int IDs."""
        product = Product(id=1, name="Laptop", price=999.99)
        await product_repo.insert_one(product)

        duplicate = Product(id=1, name="Different Product", price=500.00)
        with pytest.raises(EntityAlreadyExistsError, match="Product with id '1' already exists"):
            await product_repo.insert_one(duplicate)

    @pytest.mark.asyncio
    async def test_get_all_with_pagination(self, product_repo: InMemory[Product, int]) -> None:
        """Smoke test: Pagination with int IDs."""
        products = [Product(id=i, name=f"Product {i}", price=float(i * 10)) for i in range(1, 11)]
        await product_repo.insert_many(products)

        # Test limit
        limited = await product_repo.get_all(limit=5)
        assert len(limited) == 5
        assert [p.id for p in limited] == [1, 2, 3, 4, 5]

        # Test offset
        offset_result = await product_repo.get_all(offset=5)
        assert len(offset_result) == 5
        assert [p.id for p in offset_result] == [6, 7, 8, 9, 10]

        # Test limit + offset
        paginated = await product_repo.get_all(limit=3, offset=3)
        assert len(paginated) == 3
        assert [p.id for p in paginated] == [4, 5, 6]

    @pytest.mark.asyncio
    async def test_delete_all(self, product_repo: InMemory[Product, int]) -> None:
        """Smoke test: Delete all entities with int IDs."""
        products = [Product(id=i, name=f"Product {i}", price=10.0) for i in range(1, 6)]
        await product_repo.insert_many(products)

        assert len(await product_repo.get_all()) == 5

        await product_repo.delete_all()
        assert len(await product_repo.get_all()) == 0

    @pytest.mark.asyncio
    async def test_not_found_error(self, product_repo: InMemory[Order, UUID]) -> None:
        """Smoke test: NotFoundError with int IDs."""
        non_existent_id = uuid4()

        with pytest.raises(
            EntityNotFoundError, match=f"Product with id '{non_existent_id}' not found"
        ):
            await product_repo.get_by_id(non_existent_id)

        with pytest.raises(
            EntityNotFoundError, match=f"Product with id '{non_existent_id}' not found"
        ):
            await product_repo.delete_by_id(non_existent_id)

    @pytest.mark.asyncio
    async def test_insertion_order_preserved(self, product_repo: InMemory[Product, int]) -> None:
        """Smoke test: Verify insertion order is preserved with int IDs."""
        # Insert in non-sequential order
        products = [
            Product(id=300, name="Third", price=30.0),
            Product(id=100, name="First", price=10.0),
            Product(id=200, name="Second", price=20.0),
        ]

        for product in products:
            await product_repo.insert_one(product)

        result = await product_repo.get_all()
        # Should preserve insertion order, NOT sort by ID
        assert [p.id for p in result] == [300, 100, 200]


class TestInMemoryWithUUID:
    """Smoke tests for InMemory repository with UUID identifiers."""

    @pytest.fixture
    def order_repo(self) -> InMemory[Order, UUID]:
        return InMemory(entity_model=Order, auto_commit=True)

    @pytest.mark.asyncio
    async def test_basic_crud(self, order_repo: InMemory[Order, UUID]) -> None:
        """Smoke test: Create, Read, Update, Delete with UUID IDs."""
        # Create
        order_id = uuid4()
        order = Order(id=order_id, order_number="ORD-001", total=150.00)
        inserted = await order_repo.insert_one(order)
        assert inserted.id == order_id
        assert inserted.order_number == "ORD-001"

        # Read
        retrieved = await order_repo.get_by_id(order_id)
        assert retrieved == order

        # Update
        order.total = 175.00
        updated = await order_repo.update(order)
        assert updated.total == 175.00
        assert (await order_repo.get_by_id(order_id)).total == 175.00

        # Delete
        await order_repo.delete_by_id(order_id)
        with pytest.raises(EntityNotFoundError):
            await order_repo.get_by_id(order_id)

    @pytest.mark.asyncio
    async def test_insert_many(self, order_repo: InMemory[Order, UUID]) -> None:
        """Smoke test: Insert multiple entities with UUID IDs."""
        orders = [
            Order(id=uuid4(), order_number=f"ORD-{i:03d}", total=float(i * 100))
            for i in range(1, 4)
        ]

        result = await order_repo.insert_many(orders)
        assert len(result) == 3

        all_orders = await order_repo.get_all()
        assert len(all_orders) == 3

    @pytest.mark.asyncio
    async def test_duplicate_error(self, order_repo: InMemory[Order, UUID]) -> None:
        """Smoke test: Duplicate ID detection with UUID IDs."""
        order_id = uuid4()
        order = Order(id=order_id, order_number="ORD-001", total=100.00)
        await order_repo.insert_one(order)

        duplicate = Order(id=order_id, order_number="ORD-002", total=200.00)
        with pytest.raises(
            EntityAlreadyExistsError, match=f"Order with id '{order_id}' already exists"
        ):
            await order_repo.insert_one(duplicate)

    @pytest.mark.asyncio
    async def test_get_all_with_pagination(self, order_repo: InMemory[Order, UUID]) -> None:
        """Smoke test: Pagination with UUID IDs."""
        order_ids = [uuid4() for _ in range(10)]
        orders = [
            Order(id=order_ids[i], order_number=f"ORD-{i:03d}", total=float(i * 50))
            for i in range(10)
        ]
        await order_repo.insert_many(orders)

        # Test limit
        limited = await order_repo.get_all(limit=5)
        assert len(limited) == 5

        # Test offset
        offset_result = await order_repo.get_all(offset=5)
        assert len(offset_result) == 5

        # Test limit + offset
        paginated = await order_repo.get_all(limit=3, offset=3)
        assert len(paginated) == 3

    @pytest.mark.asyncio
    async def test_delete_all(self, order_repo: InMemory[Order, UUID]) -> None:
        """Smoke test: Delete all entities with UUID IDs."""
        orders = [Order(id=uuid4(), order_number=f"ORD-{i:03d}", total=100.0) for i in range(5)]
        await order_repo.insert_many(orders)

        assert len(await order_repo.get_all()) == 5

        await order_repo.delete_all()
        assert len(await order_repo.get_all()) == 0

    @pytest.mark.asyncio
    async def test_not_found_error(self, order_repo: InMemory[Order, UUID]) -> None:
        """Smoke test: NotFoundError with UUID IDs."""
        non_existent_id = uuid4()

        with pytest.raises(
            EntityNotFoundError, match=f"Order with id '{non_existent_id}' not found"
        ):
            await order_repo.get_by_id(non_existent_id)

        with pytest.raises(
            EntityNotFoundError, match=f"Order with id '{non_existent_id}' not found"
        ):
            await order_repo.delete_by_id(non_existent_id)

    @pytest.mark.asyncio
    async def test_insertion_order_preserved(self, order_repo: InMemory[Order, UUID]) -> None:
        """Smoke test: Verify insertion order is preserved with UUID IDs."""
        order_ids = [uuid4() for _ in range(3)]
        orders = [
            Order(id=order_ids[0], order_number="ORD-001", total=100.0),
            Order(id=order_ids[1], order_number="ORD-002", total=200.0),
            Order(id=order_ids[2], order_number="ORD-003", total=300.0),
        ]

        for order in orders:
            await order_repo.insert_one(order)

        result = await order_repo.get_all()
        # Should preserve insertion order
        assert [o.id for o in result] == order_ids
