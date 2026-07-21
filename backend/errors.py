from fastapi import HTTPException, status


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def unauthorized(detail: str = "No autenticado.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def forbidden(detail: str = "Operación no permitida.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def not_found(detail: str = "Recurso no encontrado.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def request_timeout(detail: str = "Tiempo de examen agotado.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=detail)


def conflict(detail: str = "El recurso ya existe o ya fue procesado.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def payload_too_large(
    detail: str = "La petición supera el tamaño máximo permitido.",
) -> HTTPException:
    return HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=detail)
