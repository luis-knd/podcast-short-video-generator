class ShortGeneratorError(Exception):
    """Base exception for all errors in the Short Generator application."""

    pass


class DomainError(ShortGeneratorError):
    """Exception raised for errors in the domain layer (e.g., validation)."""

    pass


class InfrastructureError(ShortGeneratorError):
    """Exception raised for errors in the infrastructure layer (e.g., external tool failures)."""

    pass
