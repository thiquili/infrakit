"""Base interfaces for exception mapping."""

from abc import ABC, abstractmethod

from infrakit.repository.exceptions import DatabaseError


class MappingStrategy(ABC):
    """Strategy for mapping a specific type of database error.

    Each strategy handles one type of error (e.g., unique violation,
    foreign key violation, etc.) and converts it to the appropriate
    domain exception.
    """

    @abstractmethod
    def can_handle(self, error: Exception) -> bool:
        """Check if this strategy can handle the given error.

        Args:
            error: The infrastructure exception to check

        Returns:
            True if this strategy can handle the error, False otherwise
        """

    @abstractmethod
    def map(
        self,
        error: Exception,
        entity_type: str | None,
        entity_id: str | None,
    ) -> DatabaseError:
        """Map the error to a domain exception.

        Args:
            error: The infrastructure exception
            entity_type: Optional entity type name
            entity_id: Optional entity ID

        Returns:
            The mapped domain exception

        Raises:
            The original exception if mapping fails
        """


class ExceptionMapper(ABC):
    """Base interface for exception mappers.

    Each ORM/database implementation provides its own mapper with its own
    set of mapping strategies.
    """

    @abstractmethod
    def map(
        self,
        error: Exception,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> DatabaseError:
        """Map an infrastructure exception to a domain exception.

        Args:
            error: The infrastructure exception (e.g., SQLAlchemy IntegrityError)
            entity_type: Optional entity type name for better error messages
            entity_id: Optional entity ID for better error messages

        Returns:
            A domain exception

        Raises:
            The original exception if it cannot be mapped
        """
