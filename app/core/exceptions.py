"""
Excepciones propias del dominio de negocio.

Regla del proyecto: los services NUNCA lanzan HTTPException (eso acopla la
capa de negocio a HTTP). Los services lanzan estas excepciones de dominio;
el handler global en main.py las traduce a la respuesta HTTP correcta.
"""


class DomainError(Exception):
    """Excepción base de la que heredan todos los errores de negocio."""
    status_code = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    """El recurso solicitado no existe (ej. una orden, un usuario)."""
    status_code = 404


class ConflictError(DomainError):
    """La operación choca con el estado actual (ej. correo duplicado,
    confirmar una orden ya confirmada)."""
    status_code = 409


class UnauthorizedError(DomainError):
    """Credenciales inválidas o token ausente/expirado."""
    status_code = 401


class ForbiddenError(DomainError):
    """El usuario está autenticado pero no tiene permiso para esta acción
    (ej. intenta ver datos de otra organización)."""
    status_code = 403


class ValidationError(DomainError):
    """Los datos de entrada son válidos en formato pero inválidos en regla
    de negocio (ej. precio negativo)."""
    status_code = 422