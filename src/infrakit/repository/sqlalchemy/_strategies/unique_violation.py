"""Strategy for handling SQLAlchemy unique constraint violations."""

import re
from typing import cast

from sqlalchemy.exc import IntegrityError
from typing_extensions import override

from infrakit._internal.mapper import MappingStrategy
from infrakit.repository.exceptions import DatabaseError, EntityAlreadyExistsError


class SqlAlchemyUniqueViolationStrategy(MappingStrategy):
    """Handle PostgreSQL unique constraint violations (sqlstate 23505).

    Maps primary key violations to EntityAlreadyExistsError.
    Other unique constraints are not mapped (raised as-is).
    """

    @override
    def can_handle(self, error: Exception) -> bool:
        """Check if error is a SQLAlchemy IntegrityError with sqlstate 23505."""
        if not isinstance(error, IntegrityError):
            return False

        sqlstate = getattr(error.orig, "sqlstate", None)
        return sqlstate == "23505"

    @override
    def map(
        self,
        error: Exception,
        entity_type: str | None,
        entity_id: str | None,
    ) -> DatabaseError:
        """Map to EntityAlreadyExistsError if it's a primary key violation.

        Args:
            error: The IntegrityError to map (guaranteed by can_handle())
            entity_type: The entity type name for error messages
            entity_id: The entity ID for error messages
        """
        # Safe cast: can_handle() already verified it's an IntegrityError
        integrity_error = cast("IntegrityError", error)

        if self._is_primary_key_violation(integrity_error):
            return EntityAlreadyExistsError(entity_type or "Entity", entity_id or "unknown")

        # If it's not a PK, let the original error pass through
        # (may be a UNIQUE constraint on another field)
        raise error

    @staticmethod
    def _is_primary_key_violation(error: IntegrityError) -> bool:
        """Check if the unique violation is specifically on a primary key.

        PostgreSQL names primary key constraints with the suffix '_pkey'.

        Args:
            error: SQLAlchemy IntegrityError (error.orig contains the driver exception)
        """
        message_str = str(error.orig)
        match = re.search(r'violates unique constraint "([^"]+)"', message_str)

        if match:
            constraint_name = match.group(1)
            return constraint_name.endswith("_pkey")

        return False
