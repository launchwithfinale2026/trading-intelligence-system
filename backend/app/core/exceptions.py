"""Domain-level exceptions.

Raised by the service layer, translated to HTTP responses by the exception
handlers registered in main.py. Keeping these framework-agnostic means the
service layer has no FastAPI import and can be unit-tested in isolation.
"""


class DomainError(Exception):
    """Base class for all domain errors."""


class NotFoundError(DomainError):
    """The requested entity does not exist."""


class ConflictError(DomainError):
    """The request conflicts with existing state (e.g. duplicate username)."""


class ForbiddenError(DomainError):
    """The requester is not allowed to access this entity."""


class UnauthorizedError(DomainError):
    """The requester's credentials are missing or invalid."""
