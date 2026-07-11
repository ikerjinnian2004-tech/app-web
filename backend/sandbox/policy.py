import ast
from textwrap import dedent, indent

FORBIDDEN_CALLS: frozenset[str] = frozenset(
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

FORBIDDEN_ATTRS: frozenset[str] = frozenset(
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

MAX_CODE_LENGTH = 50_000


class SafetyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.reason = ""

    def _block(self, reason: str) -> None:
        if not self.reason:
            self.reason = reason

    def visit_Import(self, node: ast.Import) -> None:
        self._block("No se permiten importaciones en la respuesta.")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._block("No se permiten importaciones en la respuesta.")

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            self._block(f"Llamada no permitida: {node.func.id}.")
        elif (
            isinstance(node.func, ast.Name)
            and node.func.id in {"getattr", "setattr", "delattr"}
            and len(node.args) > 1
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in FORBIDDEN_ATTRS
        ):
            self._block("Acceso de introspección no permitido.")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in FORBIDDEN_ATTRS:
            self._block("Acceso de introspección no permitido.")
        self.generic_visit(node)


def check_static(codigo: str) -> tuple[bool, str]:
    """Valida el fragmento escrito por el alumno antes de ejecutarlo."""
    if len(codigo) > MAX_CODE_LENGTH:
        return False, f"Código demasiado largo: máximo {MAX_CODE_LENGTH} caracteres."

    try:
        fragmento = indent(dedent(f"    {codigo}") or "pass", "    ")
        tree = ast.parse(f"def __respuesta__():\n{fragmento}", mode="exec")
    except SyntaxError as exc:
        return False, f"SyntaxError: {exc.msg}"

    visitor = SafetyVisitor()
    visitor.visit(tree)
    return (False, visitor.reason) if visitor.reason else (True, "")


def check_static_program(codigo: str) -> tuple[bool, str]:
    """Valida un programa completo escrito por el alumno."""
    if len(codigo) > MAX_CODE_LENGTH:
        return False, f"Código demasiado largo: máximo {MAX_CODE_LENGTH} caracteres."

    try:
        tree = ast.parse(codigo, mode="exec")
    except SyntaxError as exc:
        return False, f"SyntaxError: {exc.msg}"

    visitor = SafetyVisitor()
    visitor.visit(tree)
    return (False, visitor.reason) if visitor.reason else (True, "")


def classify_error(returncode: int, stderr: str) -> str:
    """Convierte el resultado del runner en categorías públicas y estables."""
    if returncode == 0:
        return "OK"
    if returncode in (-9, 137):
        return "TIMEOUT"
    if "SyntaxError" in stderr:
        return "SYNTAX_ERROR"
    if "no permitido" in stderr or "no permitida" in stderr or "bloqueado" in stderr:
        return "SECURITY_BLOCKED"
    return "RUNTIME_ERROR"
