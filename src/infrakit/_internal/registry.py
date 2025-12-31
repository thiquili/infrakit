"""Reusable strategy registry for exception mapping."""

import logging

from infrakit._internal.mapper import MappingStrategy
from infrakit.repository.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """Registry of mapping strategies.

    Strategies are tried in registration order until one successfully
    maps the error.
    """

    def __init__(self) -> None:
        self._strategies: list[MappingStrategy] = []

    def register(self, strategy: MappingStrategy) -> None:
        """Register a new mapping strategy.

        Args:
            strategy: The strategy to register
        """
        self._strategies.append(strategy)

    def map(
        self,
        error: Exception,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> DatabaseError:
        """Try to map the error using registered strategies.

        Args:
            error: The infrastructure exception
            entity_type: Optional entity type name
            entity_id: Optional entity ID

        Returns:
            The mapped domain exception (always returns a DatabaseError).
            If no strategy can handle the error, returns a generic DatabaseError.
        """
        for strategy in self._strategies:
            if strategy.can_handle(error):
                try:
                    return strategy.map(error, entity_type, entity_id)
                except Exception:  # noqa: BLE001
                    # Intentionally catching all exceptions to try next strategy
                    logger.debug(
                        "Strategy %s failed to map, try the next strategy.",
                        strategy.__name__,
                        exc_info=True,
                    )
                    continue

        # No strategy was able to map, raise DatabaseError
        return DatabaseError(
            f"Database error during operation on {entity_type or 'unknown entity'}: {error}"
        )
