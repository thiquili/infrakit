# infrakit

A Python toolkit for infrastructure-agnostic applications with swappable backends and instant in-memory testing.

## Objective organisation repo

infrakit/
├── src/
│   └── infrakit/
│       ├── __init__.py
│       │
│       ├── ports/                     # Interfaces (Protocol)
│       │   ├── __init__.py
│       │   ├── repository.py          # Repository[T]
│       │   ├── storage.py             # Storage
│       │   ├── queue.py               # Queue
│       │   ├── cache.py               # Cache
│       │   ├── email.py               # Mailer
│       │   └── vectordb.py            # VectorStore
│       │
│       ├── adapters/                  # Implementations
│       │   ├── __init__.py
│       │   │
│       │   ├── repository/
│       │   │   ├── __init__.py
│       │   │   ├── memory.py          # InMemoryRepository
│       │   │   ├── postgres.py        # AsyncPostgresRepository
│       │   │   └── mongo.py           # AsyncMongoRepository
│       │   │
│       │   ├── storage/
│       │   │   ├── __init__.py
│       │   │   ├── memory.py          # InMemoryStorage
│       │   │   ├── local.py           # LocalFileStorage
│       │   │   ├── s3.py              # S3Storage
│       │   │   └── azure.py           # AzureBlobStorage
│       │   │
│       │   ├── queue/
│       │   │   ├── __init__.py
│       │   │   ├── memory.py          # InMemoryQueue
│       │   │   └── rabbitmq.py        # RabbitMQQueue
│       │   │
│       │   ├── cache/
│       │   │   ├── __init__.py
│       │   │   ├── memory.py          # InMemoryCache
│       │   │   └── redis.py           # RedisCache
│       │   │
│       │   ├── email/
│       │   │   ├── __init__.py
│       │   │   ├── memory.py          # InMemoryMailer
│       │   │   ├── smtp.py            # SMTPMailer
│       │   │   └── sendgrid.py        # SendGridMailer
│       │   │
│       │   └── vectordb/
│       │       ├── __init__.py
│       │       ├── memory.py          # InMemoryVectorStore
│       │       ├── pinecone.py        # PineconeVectorStore
│       │       └── qdrant.py          # QdrantVectorStore
│       │
│       └── testing/                   # Pytest fixtures
│           ├── __init__.py
│           ├── fixtures.py            # Common fixtures
│           ├── postgres.py            # pg_session, pg_container
│           ├── mongo.py               # mongo_session, mongo_container
│           ├── s3.py                  # s3_client (localstack)
│           ├── redis.py               # redis_client
│           └── rabbitmq.py            # rabbitmq_channel
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/                          # Tests avec InMemory
│   │   ├── test_repository.py
│   │   ├── test_storage.py
│   │   └── ...
│   └── integration/                   # Tests avec Testcontainers
│       ├── test_postgres.py
│       ├── test_s3.py
│       └── ...
│

## 🛠️ Development Tools

This project uses modern Python tooling to ensure code quality, maintainability, and reliability.

| Tool          | Purpose                 | Config File                |
|---------------|-------------------------|----------------------------|
| __Ruff__      | Fast linter & formatter | `pyproject.toml`           |
| __Pyright__   | Strict type checker     | `pyrightconfig.json`       |
| __Pytest__    | Testing framework       | `pyproject.toml`           |
| __Coverage__  | Code coverage           | `pyproject.toml`           |
| __Pre-commit__| Automated Git hooks     | `.pre-commit-config.yaml`  |

---

## 🚀 Quick Start

```bash
# Clone and setup
git clone <repo-url>
cd <project-name>
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

---

## 🔍 Ruff - Linting & Formatting

Ruff is an extremely fast Python linter and formatter (written in Rust) that replaces Black, isort, flake8, and more.

__Key features:__

- Code style checks (PEP 8)
- Auto-fix common issues
- Import sorting
- Security checks (Bandit)
- Code modernization (pyupgrade)

### Ruff Commands

```bash
ruff check .              # Check code
ruff check . --fix        # Fix issues automatically
ruff format .             # Format code
```

### Common patterns

```python
# Ignore a specific rule on one line
result = eval(user_input)  # noqa: S307

# Ignore multiple rules
x = 1  # noqa: E501, W293
```

__Configuration:__ See `[tool.ruff]` in `pyproject.toml`

---

## 🎯 Pyright - Type Checking

Pyright is Microsoft's strict type checker for Python, used by VS Code/Pylance.

__Why type checking?__

- Catch errors before runtime
- Better IDE autocomplete
- Self-documenting code
- Easier refactoring

### Pyright Commands

```bash
pyright                   # Check entire project
pyright src/module.py     # Check specific file
```

### Example

```python
# ✅ Well-typed function
def calculate(x: int, y: int) -> int:
    return x + y

# ❌ Type error detected
result = calculate("hello", "world")  # Error: Expected int, got str
```

### Ignore when needed

```python
result = legacy_function()  # type: ignore
result = untyped_lib()      # type: ignore[no-untyped-call]
```

__Configuration:__ See `pyrightconfig.json`

---

## 🧪 Pytest - Testing

Pytest is Python's most popular testing framework.

### Project structure

```text
tests/
├── conftest.py          # Shared fixtures
├── test_module1.py
└── test_module2.py
```

### Basic test

```python
def test_addition():
    assert 1 + 1 == 2

def test_string():
    text = "hello"
    assert text.upper() == "HELLO"
```

### Parametrized tests

```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_double(input, expected):
    assert input * 2 == expected
```

### Pytest Commands

```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest -x                 # Stop on first failure
pytest -k "test_name"     # Run tests matching pattern
pytest tests/test_file.py::test_function  # Run specific test
```

__Configuration:__ See `[tool.pytest.ini_options]` in `pyproject.toml`

---

## 📊 Coverage

Coverage measures what percentage of your code is executed by tests.

### Coverage Commands

```bash
pytest --cov                           # Run tests with coverage
pytest --cov --cov-report=term-missing # Show missing lines
pytest --cov --cov-report=html         # Generate HTML report
```

### Example output

```text
Name                Stmts   Miss  Cover   Missing
-------------------------------------------------
src/module1.py         45      3    93%   12-14
src/module2.py         67      8    88%   34, 56-62
-------------------------------------------------
TOTAL                 112     11    90%
```

### Exclude from coverage

```python
if DEBUG:  # pragma: no cover
    print("Debug info")
```

__Configuration:__ See `[tool.coverage]` in `pyproject.toml`

__Target:__ Minimum 80% coverage (configured in `fail_under`)

---

## 🪝 Pre-commit - Git Hooks

Pre-commit automatically runs checks before each commit.

### Workflow

```bash
git commit
    ↓
Pre-commit runs automatically
    ↓
✅ All checks pass → Commit created
❌ Checks fail → Fix issues and retry
```

### Pre-commit Commands

```bash
pre-commit install                # Install hooks
pre-commit run --all-files        # Run on all files
pre-commit autoupdate             # Update hook versions
git commit --no-verify            # Bypass hooks (use sparingly!)
```

### Active hooks

- `ruff` - Linting with auto-fix
- `ruff-format` - Code formatting
- `pyright` - Type checking
- Basic checks (trailing whitespace, YAML syntax, etc.)

__Configuration:__ See `.pre-commit-config.yaml`

---

## 🎬 Development Workflow

### Daily workflow

```bash
# 1. Create branch
git checkout -b feature/my-feature

# 2. Develop
# Edit files...

# 3. Run tests
pytest --cov

# 4. Commit (pre-commit runs automatically)
git add .
git commit -m "feat: add new feature"

# 5. Push
git push origin feature/my-feature
```

### Before PR

```bash
# Full checks
ruff check . --fix
ruff format .
pyright
pytest --cov --cov-report=term-missing
```

### All-in-one command

```bash
ruff check . --fix && ruff format . && pyright && pytest --cov
```

---

## 📚 Quick Reference

### Essential commands

```bash
# Linting & Formatting
ruff check .                    # Check
ruff check . --fix              # Fix
ruff format .                   # Format

# Type Checking
pyright                         # Check types

# Testing
pytest                          # Run tests
pytest -v                       # Verbose
pytest --cov                    # With coverage
pytest --cov --cov-report=html  # HTML report

# Pre-commit
pre-commit run --all-files      # Run all hooks
pre-commit autoupdate           # Update versions
```

### Documentation

- __Ruff__: <https://docs.astral.sh/ruff/>
- __Pyright__: <https://microsoft.github.io/pyright/>
- __Pytest__: <https://docs.pytest.org/>
- __Coverage__: <https://coverage.readthedocs.io/>
- __Pre-commit__: <https://pre-commit.com/>

---

### Quality standards

- ✅ Code coverage ≥ 80%
- ✅ All tests pass
- ✅ Type hints complete (Pyright strict mode)
- ✅ Code formatted with Ruff
- ✅ Pre-commit hooks pass

---

## Git Workflow: Rebase and Squash

### Prerequisites

Make sure your main branch is up to date:

```bash
git checkout main
git pull
```

### Workflow Steps

#### 1. Switch to your feature branch

```bash
git checkout your-feature-branch
```

#### 2. Rebase on main

```bash
git rebase main
```

This replays your commits on top of the latest main branch.

#### 3. Squash your commits (interactive rebase)

```bash
git rebase -i main
```

An editor will open showing your commits. To squash them:

- Keep `pick` on the first commit
- Change `pick` to `squash` (or `s`) on all other commits you want to merge

Example:

```shell
pick abc1234 First commit
squash def5678 Second commit
squash ghi9012 Third commit
```

Save and close the editor. A new editor will open for you to write the final commit message.

#### 4. Push your changes

Since you've rewritten history, you need to force push:

```bash
git push --force-with-lease
```

Or if that doesn't work:

```bash
git push -f
```

__Note:__ Use `--force-with-lease` instead of `-f` as it's safer (checks no one else has pushed in the meantime).

#### 5. Merge via Pull Request on GitHub

Once your branch is pushed:

1. Go to your repository on GitHub
2. Click on "Pull requests" tab
3. Click "New pull request"
4. Select your feature branch to merge into main
5. Review the changes and click "Create pull request"
6. Once approved, click "Merge pull request" on GitHub

## 📝 License

[Your license here]
