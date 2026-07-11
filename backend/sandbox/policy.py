import ast
from textwrap import dedent, indent

LLAMADAS_PROHIBIDAS: frozenset[str] = frozenset(
    {
        "__import__",
        "compile",
        "eval",
        "exec",
        "globals",
        "input",
        "locals",
        "open",
        "vars",
    }
)

ATRIBUTOS_PROHIBIDOS: frozenset[str] = frozenset(
    {
        "__bases__",
        "__builtins__",
        "__class__",
        "__closure__",
        "__code__",
        "__globals__",
        "__mro__",
        "__subclasses__",
    }
)

LONGITUD_MAXIMA_CODIGO = 50_000


class VisitanteSeguridad(ast.NodeVisitor):
    def __init__(self) -> None:
        self.reason = ""

    def _bloquear(self, motivo: str) -> None:
        if not self.reason:
            self.reason = motivo

    def visit_Import(self, node: ast.Import) -> None:
        self._bloquear("No se permiten importaciones en la respuesta.")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._bloquear("No se permiten importaciones en la respuesta.")

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in LLAMADAS_PROHIBIDAS:
            self._bloquear(f"Llamada no permitida: {node.func.id}.")
        elif (
            isinstance(node.func, ast.Name)
            and node.func.id in {"getattr", "setattr", "delattr"}
            and len(node.args) > 1
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in ATRIBUTOS_PROHIBIDOS
        ):
            self._bloquear("Acceso de introspección no permitido.")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in ATRIBUTOS_PROHIBIDOS:
            self._bloquear("Acceso de introspección no permitido.")
        self.generic_visit(node)


def validar_fragmento(codigo: str) -> tuple[bool, str]:
    if len(codigo) > LONGITUD_MAXIMA_CODIGO:
        return False, (
            f"Código demasiado largo: máximo {LONGITUD_MAXIMA_CODIGO} caracteres."
        )

    try:
        fragmento = indent(dedent(f"    {codigo}") or "pass", "    ")
        tree = ast.parse(f"def __respuesta__():\n{fragmento}", mode="exec")
    except SyntaxError as exc:
        return False, f"SyntaxError: {exc.msg}"

    visitante = VisitanteSeguridad()
    visitante.visit(tree)
    return (False, visitante.reason) if visitante.reason else (True, "")


def validar_programa(codigo: str) -> tuple[bool, str]:
    if len(codigo) > LONGITUD_MAXIMA_CODIGO:
        return False, (
            f"Código demasiado largo: máximo {LONGITUD_MAXIMA_CODIGO} caracteres."
        )

    try:
        tree = ast.parse(codigo, mode="exec")
    except SyntaxError as exc:
        return False, f"SyntaxError: {exc.msg}"

    visitante = VisitanteSeguridad()
    visitante.visit(tree)
    return (False, visitante.reason) if visitante.reason else (True, "")


def clasificar_error(codigo_retorno: int, stderr: str) -> str:
    if codigo_retorno == 0:
        return "OK"
    if codigo_retorno in (-9, 137):
        return "TIMEOUT"
    if "SyntaxError" in stderr:
        return "SYNTAX_ERROR"
    if "no permitido" in stderr or "no permitida" in stderr or "bloqueado" in stderr:
        return "SECURITY_BLOCKED"
    return "RUNTIME_ERROR"


# Compatibilidad para consumidores de la API anterior del sandbox.
FORBIDDEN_CALLS = LLAMADAS_PROHIBIDAS
FORBIDDEN_ATTRS = ATRIBUTOS_PROHIBIDOS
MAX_CODE_LENGTH = LONGITUD_MAXIMA_CODIGO
SafetyVisitor = VisitanteSeguridad
check_static = validar_fragmento
check_static_program = validar_programa
classify_error = clasificar_error
