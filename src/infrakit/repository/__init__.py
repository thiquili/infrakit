"""Repository pattern implementations.

Provides a unified interface for data access across different storage backends.
"""

from infrakit.repository.exceptions import (
    DatabaseError,
    EntityAlreadyExistsError,
    EntityModelError,
    EntityNotFoundError,
    PaginationParameterError,
)

# Implementations
from infrakit.repository.memory import InMemory
from infrakit.repository.protocols import Repository
from infrakit.repository.sqlalchemy import SqlAlchemy

__all__ = [  # noqa: RUF022
    # Core
    "Repository",
    # Exceptions
    "DatabaseError",
    "EntityAlreadyExistsError",
    "EntityModelError",
    "EntityNotFoundError",
    "PaginationParameterError",
    # Implementations
    "InMemory",
    "SqlAlchemy",
]
