from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Callable

from backend.config import get_settings
from backend.models import CasoPrueba, Pregunta, RespuestaAlumno
from backend.sandbox.policy import (
    clasificar_error,
    validar_fragmento,
    validar_programa,
)
from backend.sandbox.runner_docker import ejecutar_codigo_interno_docker
from backend.sandbox.runner_subprocess import ejecutar_codigo_interno
from backend.template_engine import ensamblar_codigo

settings = get_settings()
SandboxRunner = Callable[[str, int, int], dict[str, object]]
BATCH_RESULTS_MARKER = "__TFG_BATCH_RESULTS__="


@dataclass
class ResultadoPregunta:
    pregunta_id: int
    tipo: str
    estado: str
    nota: float | None
    tests_ok: int | None = None
    tests_total: int | None = None
    error_type: str | None = None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "pregunta_id": self.pregunta_id,
            "tipo": self.tipo,
            "estado": self.estado,
            "nota": self.nota,
            "tests_ok": self.tests_ok,
            "tests_total": self.tests_total,
            "error_type": self.error_type,
        }


def get_runner() -> SandboxRunner:
    return (
        ejecutar_codigo_interno_docker
        if settings.sandbox_use_docker
        else ejecutar_codigo_interno
    )


def validate_compilable_code(codigo: str) -> tuple[bool, str]:
    try:
        compile(codigo, "<codigo-alumno>", "exec")
    except SyntaxError as exc:
        linea = f" (línea {exc.lineno})" if exc.lineno is not None else ""
        return False, f"SyntaxError{linea}: {exc.msg}"
    return True, ""


def build_batch_runner_code(codigo_base: str, casos: list[CasoPrueba]) -> str:
    tests_literal = repr([caso.codigo_test for caso in casos])
    return f"""
__tfg_student_code__ = {codigo_base!r}
__tfg_tests__ = {tests_literal}
__tfg_results__ = []

def __tfg_make_capture__():
    __tfg_chunks__ = []

    def __tfg_print__(*args, **kwargs):
        __tfg_sep__ = kwargs.get("sep", " ")
        __tfg_end__ = kwargs.get("end", "\\n")
        __tfg_text__ = __tfg_sep__.join(str(arg) for arg in args) + __tfg_end__
        __tfg_chunks__.append(__tfg_text__)

    return __tfg_chunks__, __tfg_print__

for __tfg_test_code__ in __tfg_tests__:
    __tfg_namespace__ = {{}}
    __tfg_chunks__, __tfg_print__ = __tfg_make_capture__()
    __tfg_namespace__["print"] = __tfg_print__

    try:
        exec(__tfg_student_code__, __tfg_namespace__, __tfg_namespace__)
        exec(__tfg_test_code__, __tfg_namespace__, __tfg_namespace__)
        __tfg_results__.append({{
            "stdout": "".join(__tfg_chunks__),
            "stderr": "",
            "returncode": 0,
        }})
    except Exception as __tfg_exc__:
        __tfg_results__.append({{
            "stdout": "".join(__tfg_chunks__),
            "stderr": f"{{type(__tfg_exc__).__name__}}: {{__tfg_exc__}}",
            "returncode": 1,
        }})

print({BATCH_RESULTS_MARKER!r} + repr(__tfg_results__))
""".strip()


def parse_batch_results(stdout: str) -> list[dict[str, object]] | None:
    marker_position = stdout.rfind(BATCH_RESULTS_MARKER)
    if marker_position == -1:
        return None
    payload = stdout[marker_position + len(BATCH_RESULTS_MARKER) :].strip()
    if not payload:
        return None
    try:
        parsed = ast.literal_eval(payload)
    except (SyntaxError, ValueError):
        return None
    return parsed if isinstance(parsed, list) else None


def resultado_error(
    pregunta: Pregunta,
    casos: list[CasoPrueba],
    error_type: str,
) -> ResultadoPregunta:
    return ResultadoPregunta(
        pregunta_id=pregunta.id,
        tipo=pregunta.tipo,
        estado="corregida",
        nota=0.0,
        tests_ok=0,
        tests_total=len(casos),
        error_type=error_type,
    )


def corregir_codigo(
    pregunta: Pregunta,
    contenido: str,
    casos: list[CasoPrueba],
) -> ResultadoPregunta:
    if not casos:
        return resultado_error(pregunta, casos, "NO_TESTS")

    if pregunta.tipo == "rellenar_huecos":
        es_seguro, motivo = validar_fragmento(contenido)
    else:
        es_seguro, motivo = validar_programa(contenido)
    if not es_seguro:
        error_type = (
            "SYNTAX_ERROR" if motivo.startswith("SyntaxError") else "SECURITY_BLOCKED"
        )
        return resultado_error(pregunta, casos, error_type)

    if pregunta.tipo == "rellenar_huecos":
        try:
            codigo_base = ensamblar_codigo(pregunta.codigo_plantilla or "", contenido)
        except ValueError:
            return resultado_error(pregunta, casos, "RUNTIME_ERROR")
    else:
        codigo_base = contenido

    compila, motivo_compilacion = validate_compilable_code(codigo_base)
    if not compila:
        return resultado_error(pregunta, casos, "SYNTAX_ERROR")

    ejecucion = get_runner()(
        build_batch_runner_code(codigo_base, casos),
        timeout=settings.sandbox_timeout_seconds,
        max_output=settings.sandbox_max_output_chars,
    )
    if bool(ejecucion.get("timed_out")):
        return resultado_error(pregunta, casos, "TIMEOUT")

    stdout_total = str(ejecucion.get("stdout", ""))
    stderr_total = str(ejecucion.get("stderr", ""))
    resultados_parseados = parse_batch_results(stdout_total)
    if resultados_parseados is None:
        error_type = clasificar_error(int(ejecucion.get("returncode", 1)), stderr_total)
        return resultado_error(pregunta, casos, error_type)

    peso_total = sum(caso.peso for caso in casos) or 1.0
    peso_ok = 0.0
    primer_error: str | None = None
    tests_ok = 0

    for caso, resultado in zip(casos, resultados_parseados, strict=False):
        stdout = str(resultado.get("stdout", ""))
        stderr = str(resultado.get("stderr", ""))
        returncode = int(resultado.get("returncode", 1))
        error_type = clasificar_error(returncode, stderr)

        if caso.salida_esperada == "":
            passed = returncode == 0
        else:
            passed = returncode == 0 and stdout.strip() == caso.salida_esperada.strip()
            if returncode == 0 and not passed:
                error_type = "WRONG_OUTPUT"

        if passed:
            peso_ok += caso.peso
            tests_ok += 1
        elif primer_error is None:
            primer_error = error_type

    return ResultadoPregunta(
        pregunta_id=pregunta.id,
        tipo=pregunta.tipo,
        estado="corregida",
        nota=round((peso_ok / peso_total) * 10, 2),
        tests_ok=tests_ok,
        tests_total=len(casos),
        error_type=primer_error,
    )


def corregir_tipo_test(pregunta: Pregunta, contenido: str) -> ResultadoPregunta:
    correcto = (pregunta.respuesta_correcta or "").strip()
    nota = 10.0 if contenido.strip() == correcto else 0.0
    return ResultadoPregunta(
        pregunta_id=pregunta.id,
        tipo=pregunta.tipo,
        estado="corregida",
        nota=nota,
        tests_ok=1 if nota == 10.0 else 0,
        tests_total=1,
        error_type=None if nota == 10.0 else "WRONG_OPTION",
    )


def marcar_revision_docente(pregunta: Pregunta) -> ResultadoPregunta:
    return ResultadoPregunta(
        pregunta_id=pregunta.id,
        tipo=pregunta.tipo,
        estado="pendiente_revision",
        nota=None,
    )


def corregir_respuesta(
    pregunta: Pregunta,
    contenido: str,
    casos: list[CasoPrueba],
) -> ResultadoPregunta:
    if pregunta.tipo in {"rellenar_huecos", "corregir_codigo"}:
        return corregir_codigo(pregunta, contenido, casos)
    if pregunta.tipo == "tipo_test":
        return corregir_tipo_test(pregunta, contenido)
    return marcar_revision_docente(pregunta)


def grade_entrega(
    respuestas_alumno: list[RespuestaAlumno],
    preguntas: list[Pregunta],
    casos_por_pregunta: dict[int, list[CasoPrueba]],
) -> dict[str, object]:
    respuestas_por_pregunta = {
        respuesta.pregunta_id: respuesta.contenido for respuesta in respuestas_alumno
    }
    desglose: list[dict[str, object]] = []
    peso_total = 0.0
    nota_ponderada = 0.0
    pendientes = 0

    for pregunta in sorted(preguntas, key=lambda item: item.orden):
        resultado = corregir_respuesta(
            pregunta,
            respuestas_por_pregunta.get(pregunta.id, ""),
            casos_por_pregunta.get(pregunta.id, []),
        )
        desglose.append(resultado.to_public_dict())

        if resultado.estado == "pendiente_revision":
            pendientes += 1
            continue

        peso = float(pregunta.peso)
        peso_total += peso
        nota_ponderada += float(resultado.nota or 0.0) * peso

    nota_global = round(nota_ponderada / peso_total, 2) if peso_total else 0.0
    return {
        "nota_global": nota_global,
        "preguntas_pendientes": pendientes,
        "desglose": desglose,
    }
