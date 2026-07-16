from __future__ import annotations

import ast
import json
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
from backend.template_engine import assemble_code, count_blanks

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
    casos: list[dict[str, object]] | None = None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "pregunta_id": self.pregunta_id,
            "tipo": self.tipo,
            "estado": self.estado,
            "nota": self.nota,
            "tests_ok": self.tests_ok,
            "tests_total": self.tests_total,
            "error_type": self.error_type,
            "casos": self.casos,
        }


def get_runner() -> SandboxRunner:
    return (
        ejecutar_codigo_interno_docker
        if settings.sandbox_use_docker
        else ejecutar_codigo_interno
    )


def is_compilable_code(code: str) -> tuple[bool, str]:
    try:
        compile(code, "<codigo-alumno>", "exec")
    except SyntaxError as exc:
        line = f" (línea {exc.lineno})" if exc.lineno is not None else ""
        return False, f"SyntaxError{line}: {exc.msg}"
    return True, ""


def build_batch_execution_code(
    base_code: str,
    test_cases: list[CasoPrueba],
    output_limit_per_case: int,
) -> str:
    tests_literal = repr([test_case.codigo_test for test_case in test_cases])
    return f"""
__tfg_student_code__ = {base_code!r}
__tfg_tests__ = {tests_literal}
__tfg_results__ = []
__tfg_output_limit__ = {output_limit_per_case}

def __tfg_make_capture__():
    __tfg_chunks__ = []
    __tfg_size__ = [0]

    def __tfg_print__(*args, **kwargs):
        __tfg_sep__ = kwargs.get("sep", " ")
        __tfg_end__ = kwargs.get("end", "\\n")
        __tfg_text__ = __tfg_sep__.join(str(arg) for arg in args) + __tfg_end__
        __tfg_remaining__ = __tfg_output_limit__ - __tfg_size__[0]
        if __tfg_remaining__ > 0:
            __tfg_piece__ = __tfg_text__[:__tfg_remaining__]
            __tfg_chunks__.append(__tfg_piece__)
            __tfg_size__[0] += len(__tfg_piece__)

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


def parse_batch_results_from_stdout(stdout: str) -> list[dict[str, object]] | None:
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


def build_error_result(
    question: Pregunta,
    test_cases: list[CasoPrueba],
    error_type: str,
) -> ResultadoPregunta:
    return ResultadoPregunta(
        pregunta_id=question.id,
        tipo=question.tipo,
        estado="corregida",
        nota=0.0,
        tests_ok=0,
        tests_total=len(test_cases),
        error_type=error_type,
    )


def parse_blank_answers(answer: str, number_of_blanks: int) -> list[str] | None:
    if number_of_blanks == 1:
        return [answer]
    try:
        parsed = json.loads(answer)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or len(parsed) != number_of_blanks:
        return None
    return parsed if all(isinstance(item, str) for item in parsed) else None


def grade_code_answer(
    question: Pregunta,
    answer: str,
    test_cases: list[CasoPrueba],
    modo_calificacion: str = "parcial_por_tests",
) -> ResultadoPregunta:
    if not test_cases:
        return build_error_result(question, test_cases, "NO_TESTS")

    if question.tipo == "rellenar_huecos":
        blank_answers = parse_blank_answers(
            answer, count_blanks(question.codigo_plantilla or "")
        )
        if blank_answers is None:
            return build_error_result(question, test_cases, "INVALID_ANSWER")
        validations = [validar_fragmento(item) for item in blank_answers]
        is_safe = all(result[0] for result in validations)
        reason = next((result[1] for result in validations if not result[0]), "")
    else:
        blank_answers = []
        is_safe, reason = validar_programa(answer)
    if not is_safe:
        error_type = (
            "SYNTAX_ERROR" if reason.startswith("SyntaxError") else "SECURITY_BLOCKED"
        )
        return build_error_result(question, test_cases, error_type)

    if question.tipo == "rellenar_huecos":
        try:
            base_code = assemble_code(question.codigo_plantilla or "", blank_answers)
        except ValueError:
            return build_error_result(question, test_cases, "RUNTIME_ERROR")
    else:
        base_code = answer

    is_compilable, _ = is_compilable_code(base_code)
    if not is_compilable:
        return build_error_result(question, test_cases, "SYNTAX_ERROR")

    limite_por_caso = max(
        100,
        min(
            1_000,
            settings.sandbox_max_output_chars // (max(len(test_cases), 1) * 2),
        ),
    )
    execution = get_runner()(
        build_batch_execution_code(base_code, test_cases, limite_por_caso),
        timeout=settings.sandbox_timeout_seconds,
        max_output=settings.sandbox_max_output_chars,
    )
    if bool(execution.get("timed_out")):
        return build_error_result(question, test_cases, "TIMEOUT")

    stdout = str(execution.get("stdout", ""))
    stderr = str(execution.get("stderr", ""))
    parsed_results = parse_batch_results_from_stdout(stdout)
    if parsed_results is None:
        error_type = clasificar_error(int(execution.get("returncode", 1)), stderr)
        return build_error_result(question, test_cases, error_type)

    total_weight = sum(test_case.peso for test_case in test_cases) or 1.0
    passed_weight = 0.0
    first_error: str | None = None
    tests_ok = 0
    resultados_casos: list[dict[str, object]] = []

    for indice, test_case in enumerate(test_cases):
        result = (
            parsed_results[indice]
            if indice < len(parsed_results)
            else {"stdout": "", "stderr": "Caso no ejecutado", "returncode": 1}
        )
        case_stdout = str(result.get("stdout", ""))
        case_stderr = str(result.get("stderr", ""))
        returncode = int(result.get("returncode", 1))
        error_type = clasificar_error(returncode, case_stderr)

        if test_case.salida_esperada == "":
            passed = returncode == 0
        else:
            passed = (
                returncode == 0
                and case_stdout.strip() == test_case.salida_esperada.strip()
            )
            if returncode == 0 and not passed:
                error_type = "WRONG_OUTPUT"

        if passed:
            passed_weight += test_case.peso
            tests_ok += 1
        elif first_error is None:
            first_error = error_type
        resultados_casos.append(
            {
                "caso_id": test_case.id,
                "descripcion": test_case.descripcion,
                "visible": test_case.visible,
                "correcto": passed,
                "error_type": None if passed else error_type,
            }
        )

    nota_parcial = (passed_weight / total_weight) * 10
    nota = (
        10.0
        if tests_ok == len(test_cases)
        else 0.0
        if modo_calificacion == "todo_o_nada_por_pregunta"
        else nota_parcial
    )

    return ResultadoPregunta(
        pregunta_id=question.id,
        tipo=question.tipo,
        estado="corregida",
        nota=round(nota, 2),
        tests_ok=tests_ok,
        tests_total=len(test_cases),
        error_type=first_error,
        casos=resultados_casos,
    )


def grade_multiple_choice_answer(question: Pregunta, answer: str) -> ResultadoPregunta:
    correct_answer = (question.respuesta_correcta or "").strip()
    score = 10.0 if answer.strip() == correct_answer else 0.0
    return ResultadoPregunta(
        pregunta_id=question.id,
        tipo=question.tipo,
        estado="corregida",
        nota=score,
        tests_ok=1 if score == 10.0 else 0,
        tests_total=1,
        error_type=None if score == 10.0 else "WRONG_OPTION",
    )


def mark_for_manual_review(question: Pregunta) -> ResultadoPregunta:
    return ResultadoPregunta(
        pregunta_id=question.id,
        tipo=question.tipo,
        estado="pendiente_revision",
        nota=None,
    )


def grade_answer(
    question: Pregunta,
    answer: str,
    test_cases: list[CasoPrueba],
    modo_calificacion: str = "parcial_por_tests",
) -> ResultadoPregunta:
    if question.tipo in {"rellenar_huecos", "corregir_codigo"}:
        return grade_code_answer(
            question,
            answer,
            test_cases,
            modo_calificacion=modo_calificacion,
        )
    if question.tipo == "tipo_test":
        return grade_multiple_choice_answer(question, answer)
    return mark_for_manual_review(question)


def grade_entrega(
    respuestas_alumno: list[RespuestaAlumno],
    preguntas: list[Pregunta],
    casos_por_pregunta: dict[int, list[CasoPrueba]],
    pesos_por_pregunta: dict[int, float] | None = None,
    modo_calificacion: str = "parcial_por_tests",
) -> dict[str, object]:
    answers_by_question = {
        respuesta.pregunta_id: respuesta.contenido for respuesta in respuestas_alumno
    }
    breakdown: list[dict[str, object]] = []
    total_weight = 0.0
    weighted_score = 0.0
    pending_reviews = 0

    for question in sorted(preguntas, key=lambda item: item.orden):
        result = grade_answer(
            question,
            answers_by_question.get(question.id, ""),
            casos_por_pregunta.get(question.id, []),
            modo_calificacion=modo_calificacion,
        )
        weight = float((pesos_por_pregunta or {}).get(question.id, question.peso))
        result_dict = result.to_public_dict()
        result_dict["peso"] = weight
        result_dict["version_pregunta"] = question.version

        if result.estado == "pendiente_revision":
            pending_reviews += 1
            result_dict["contribucion"] = None
            breakdown.append(result_dict)
            continue

        total_weight += weight
        contribution = float(result.nota or 0.0) * weight
        weighted_score += contribution
        result_dict["contribucion"] = round(contribution, 2)
        breakdown.append(result_dict)

    nota_global = round(weighted_score / total_weight, 2) if total_weight else 0.0
    return {
        "nota_global": nota_global,
        "preguntas_pendientes": pending_reviews,
        "desglose": breakdown,
        "peso_evaluado": round(total_weight, 2),
        "suma_ponderada": round(weighted_score, 2),
        "modo_calificacion": modo_calificacion,
    }
