"""Repository-specific exceptions."""


class DatabaseError(Exception):
    """Base exception for all database-related errors."""


class EntityNotFoundError(DatabaseError):
    """Raised when an entity cannot be found by its identifier."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} with id '{entity_id}' not found")


class EntityAlreadyExistsError(DatabaseError):
    """Raised when attempting to create an entity that already exists."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} with id '{entity_id}' already exists")


class EntityModelError(DatabaseError):
    """Raised when the model of an entity does not match with the one instantiated."""


class PaginationParameterError(DatabaseError):
    """Raised when a pagination parameter (limit or offset) is invalid."""

    def __init__(self, parameter_name: str, value: int) -> None:
        self.parameter_name = parameter_name
        self.value = value
        super().__init__(f"{parameter_name} must be non-negative, got {value}")
