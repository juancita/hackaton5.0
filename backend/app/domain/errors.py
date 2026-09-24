"""Errores de dominio. La capa HTTP los traduce a códigos de estado."""


class DomainError(Exception):
    pass


class NotFound(DomainError):
    pass


class InvalidInput(DomainError):
    pass


class Conflict(DomainError):
    pass


class RateLimited(DomainError):
    pass
