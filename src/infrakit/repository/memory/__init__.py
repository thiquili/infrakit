"""In-memory repository implementation."""

from infrakit.repository.memory.repository import InMemory
from infrakit.repository.memory.session import InMemorySession

__all__ = ["InMemory", "InMemorySession"]
