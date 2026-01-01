# Repository Testing Rules

## The Golden Rule

**In each test, we test ONLY ONE method of the Repository class.**

**All other operations (setup, verification) MUST be done in plain SQL.**

This approach ensures we never test code with itself, which is a fundamental principle of unit testing.

---

## Testing Patterns by Method

### test_insert_one()

- **We test**: `repository.insert_one()`
- **We verify**: SELECT with `text()` (plain SQL)

### test_get_by_id()

- **We prepare**: INSERT with `text()` (plain SQL)
- **We test**: `repository.get_by_id()`

### test_get_all()

- **We prepare**: INSERT with `text()` (plain SQL)
- **We test**: `repository.get_all()`
- **We verify**: SELECT COUNT with `text()` (plain SQL)

### test_update()

- **We prepare**: INSERT with `text()` (plain SQL)
- **We test**: `repository.update()`
- **We verify**: SELECT with `text()` (plain SQL)

### test_delete_by_id()

- **We prepare**: INSERT with `text()` (plain SQL)
- **We test**: `repository.delete_by_id()`
- **We verify**: SELECT COUNT with `text()` (plain SQL)

---

## Why These Rules?

### Isolation

Each test verifies exactly one piece of functionality without depending on other methods.

### Reliability

If a test fails, you know exactly which method is broken.

### Independence

Tests don't cascade failures - a bug in `get_by_id()` won't cause `test_update()` to fail.

### Trust

Using plain SQL as ground truth ensures our repository implementation is actually correct.

---

## Anti-Patterns to Avoid

### Using Repository Methods for Setup/Verification

❌ **Don't do this:**

```python
async def test_delete_by_id(session: AsyncSession) -> None:
    # BAD: Using repository.insert_one() to prepare
    await repository.insert_one(user)

    # BAD: Using repository.get_by_id() to verify
    with pytest.raises(NotFoundError):
        await repository.get_by_id(user_id)
```

✅ **Do this instead:**

```python
async def test_delete_by_id(session: AsyncSession) -> None:
    # GOOD: Using plain SQL to prepare
    await session.execute(text("INSERT INTO users ..."))

    await repository.delete_by_id(user_id)

    # GOOD: Using plain SQL to verify
    result = await session.execute(text("SELECT COUNT(*) ..."))
    assert result.scalar() == 0
```

### Using autouse Fixtures and Implicit Mocks

❌ **Don't do this:**

```python
@pytest.fixture(autouse=True)  # BAD: autouse=True hides dependencies
def mock_external_service(mocker):
    return mocker.patch("module.external_service")

async def test_something(session: AsyncSession) -> None:
    # BAD: Mock is implicit, not visible in function signature
    result = await repository.some_method()
    assert result is not None
```

✅ **Do this instead:**

```python
@pytest.fixture
def mock_external_service(mocker):  # GOOD: No autouse
    return mocker.patch("module.external_service")

async def test_something(
    session: AsyncSession,
    mock_external_service,  # GOOD: Mock is explicit in parameters
) -> None:
    # GOOD: Dependencies are visible and clear
    result = await repository.some_method()
    assert result is not None
```

**Why?** Explicit dependencies make tests more readable and maintainable. Anyone reading the test signature knows exactly what mocks and fixtures are involved.

### Using Context Manager `with patch()` Instead of Decorator

❌ **Don't do this:**

```python
async def test_commit_error(session: AsyncSession) -> None:
    # BAD: Using context manager with patch()
    with patch.object(session, 'commit', side_effect=OperationalError("error")):
        with patch.object(session, 'rollback', new_callable=AsyncMock) as mock_rollback:
            with pytest.raises(DatabaseError):
                await repository.insert_one(user)
            mock_rollback.assert_called_once()
```

✅ **Do this instead:**

```python
@pytest.mark.asyncio
@patch("sqlalchemy.ext.asyncio.AsyncSession.commit")
@patch("sqlalchemy.ext.asyncio.AsyncSession.rollback")
async def test_commit_error(
    mock_rollback: AsyncMock,
    mock_commit: AsyncMock,
    session: AsyncSession,
) -> None:
    # GOOD: Using decorators makes mocks explicit in parameters
    mock_commit.side_effect = OperationalError("error")

    with pytest.raises(DatabaseError):
        await repository.insert_one(user)

    mock_rollback.assert_called_once()
```

**Why?**

- Decorators make mocks **explicit in the function signature**
- Reduces nesting and improves readability
- Mocks are visible as parameters, making dependencies clear
- Consistent with explicit dependency principle

---

## Documentation Rules

### Docstrings on Every Test

**Always add a docstring to each unit test to explicitly state its objective.**

✅ **Good example:**

```python
async def test_insert_one_creates_user_in_database(session: AsyncSession) -> None:
    """Test that insert_one() correctly creates a user in the database."""
    user = User(id=1, name="Alice", email="alice@example.com")

    await repository.insert_one(user)

    result = await session.execute(text("SELECT * FROM users WHERE id = 1"))
    assert result.scalar() is not None
```

**Why?** Docstrings make the test's purpose immediately clear, improving readability and maintainability.
