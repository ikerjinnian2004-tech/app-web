from __future__ import annotations

import argparse
import json
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

RESPUESTAS_ESPERADAS = 4
PROFUNDIDAD_MAXIMA = 12


@dataclass(frozen=True)
class Estado:
    fases: tuple[str, str] = ("idle", "idle")
    reserva: int | None = None
    respuestas: int = 0
    calificacion: int = 0
    cerrada: int = 0
    commits: int = 0


def reemplazar_fase(estado: Estado, solicitud: int, fase: str) -> Estado:
    fases = list(estado.fases)
    fases[solicitud] = fase
    return Estado(
        fases=tuple(fases),
        reserva=estado.reserva,
        respuestas=estado.respuestas,
        calificacion=estado.calificacion,
        cerrada=estado.cerrada,
        commits=estado.commits,
    )


def sucesores(estado: Estado) -> list[tuple[str, Estado]]:
    opciones: list[tuple[str, Estado]] = []
    for solicitud, fase in enumerate(estado.fases):
        if fase == "idle":
            if estado.cerrada:
                opciones.append(
                    (
                        f"r{solicitud}:observa_cierre",
                        reemplazar_fase(estado, solicitud, "done"),
                    )
                )
            elif estado.reserva is None:
                reservado = reemplazar_fase(estado, solicitud, "reserved")
                opciones.append(
                    (
                        f"r{solicitud}:reserva",
                        Estado(
                            fases=reservado.fases,
                            reserva=solicitud,
                            respuestas=estado.respuestas,
                            calificacion=estado.calificacion,
                            cerrada=estado.cerrada,
                            commits=estado.commits,
                        ),
                    )
                )
        elif fase == "reserved" and estado.reserva == solicitud:
            opciones.append(
                (f"r{solicitud}:calcula", reemplazar_fase(estado, solicitud, "ready"))
            )
            fallo = reemplazar_fase(estado, solicitud, "failed")
            opciones.append(
                (
                    f"r{solicitud}:fallo_precommit",
                    Estado(
                        fases=fallo.fases,
                        reserva=None,
                        respuestas=estado.respuestas,
                        calificacion=estado.calificacion,
                        cerrada=estado.cerrada,
                        commits=estado.commits,
                    ),
                )
            )
        elif fase == "ready" and estado.reserva == solicitud:
            final = reemplazar_fase(estado, solicitud, "done")
            opciones.append(
                (
                    f"r{solicitud}:commit_atomico",
                    Estado(
                        fases=final.fases,
                        reserva=None,
                        respuestas=RESPUESTAS_ESPERADAS,
                        calificacion=1,
                        cerrada=1,
                        commits=estado.commits + 1,
                    ),
                )
            )
            fallo = reemplazar_fase(estado, solicitud, "failed")
            opciones.append(
                (
                    f"r{solicitud}:rollback",
                    Estado(
                        fases=fallo.fases,
                        reserva=None,
                        respuestas=estado.respuestas,
                        calificacion=estado.calificacion,
                        cerrada=estado.cerrada,
                        commits=estado.commits,
                    ),
                )
            )
        elif fase == "failed":
            opciones.append(
                (f"r{solicitud}:reintento", reemplazar_fase(estado, solicitud, "idle"))
            )
    return opciones


def invariantes(estado: Estado) -> list[str]:
    errores: list[str] = []
    bundle_vacio = (estado.respuestas, estado.calificacion, estado.cerrada) == (0, 0, 0)
    bundle_final = (
        estado.respuestas,
        estado.calificacion,
        estado.cerrada,
    ) == (RESPUESTAS_ESPERADAS, 1, 1)
    if not (bundle_vacio or bundle_final):
        errores.append("estado persistente parcial")
    if estado.cerrada and not bundle_final:
        errores.append("entrega cerrada sin respuestas y calificacion completas")
    if estado.commits > 1:
        errores.append("mas de una solicitud confirmo")
    if estado.reserva is not None and estado.fases[estado.reserva] not in {
        "reserved",
        "ready",
    }:
        errores.append("reserva sin propietario activo")
    return errores


def explorar() -> dict[str, object]:
    inicial = Estado()
    cola = deque([(inicial, 0, [])])
    visitados = {inicial}
    transiciones = 0
    estados_finales = 0
    while cola:
        estado, profundidad, traza = cola.popleft()
        errores = invariantes(estado)
        if errores:
            return {
                "ok": False,
                "errores": errores,
                "estado": asdict(estado),
                "traza": traza,
                "estados_explorados": len(visitados),
                "transiciones": transiciones,
            }
        if estado.cerrada:
            estados_finales += 1
        if profundidad >= PROFUNDIDAD_MAXIMA:
            continue
        for accion, siguiente in sucesores(estado):
            transiciones += 1
            if siguiente not in visitados:
                visitados.add(siguiente)
                cola.append((siguiente, profundidad + 1, [*traza, accion]))
    return {
        "ok": True,
        "modelo": "exploracion explicita finita de dos solicitudes",
        "profundidad_maxima": PROFUNDIDAD_MAXIMA,
        "estados_explorados": len(visitados),
        "transiciones": transiciones,
        "estados_finales": estados_finales,
        "invariantes": [
            "una entrega cerrada tiene calificacion y respuestas completas",
            "no existen estados persistentes parciales",
            "como maximo una solicitud confirma",
            "rollback y fallo precommit conservan el bundle previo",
            "no queda una reserva sin propietario activo",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    resultado = explorar()
    texto = json.dumps(resultado, ensure_ascii=False, indent=2) + "\n"
    print(texto, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(texto, encoding="utf-8")
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
