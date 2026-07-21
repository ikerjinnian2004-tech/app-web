from __future__ import annotations

import argparse
import html
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
ANCHO, ALTO = 1600, 900


@dataclass(frozen=True)
class Caja:
    id: str
    texto: str
    x: int
    y: int
    w: int
    h: int
    estado: str = "ejecutado"


@dataclass(frozen=True)
class Diagrama:
    nombre: str
    titulo: str
    cajas: tuple[Caja, ...]
    enlaces: tuple[tuple[str, str, str], ...]


COLORES = {
    "ejecutado": (219, 245, 238),
    "configurado": (255, 242, 204),
    "no_validado": (254, 226, 226),
    "frontera": (224, 231, 255),
}


DIAGRAMAS = (
    Diagrama(
        "01_arquitectura",
        "Arquitectura final y estado de validacion",
        (
            Caja("browser", "Navegador\nHTML, CSS y JS", 80, 320, 250, 130),
            Caja("api", "API FastAPI", 430, 320, 220, 130),
            Caja(
                "db",
                "SQLite ejecutado\nPostgreSQL configurado",
                780,
                150,
                300,
                130,
                "configurado",
            ),
            Caja("grader", "Motor de evaluacion", 780, 500, 260, 130),
            Caja("worker", "Adaptador Docker", 1140, 500, 220, 130, "configurado"),
            Caja("container", "Contenedor efimero", 1140, 700, 220, 110, "no_validado"),
        ),
        (
            ("browser", "api", "HTTPS / JSON"),
            ("api", "db", "SQLAlchemy"),
            ("api", "grader", "respuestas"),
            ("grader", "worker", "codigo validado"),
            ("worker", "container", "Docker API"),
        ),
    ),
    Diagrama(
        "02_transaccion_envio",
        "Envio final: calculo fuera y persistencia atomica",
        (
            Caja("alumno", "Alumnado", 40, 300, 180, 100),
            Caja("reserva", "A. Reserva breve\nCOMMIT", 270, 300, 210, 100),
            Caja(
                "sandbox", "B. Calculo sandbox\nsin transaccion SQL", 530, 300, 250, 100
            ),
            Caja("begin", "C. BEGIN\nbloqueo y validacion", 830, 300, 230, 100),
            Caja("bundle", "Respuestas + nota\n+ cierre", 1110, 220, 260, 100),
            Caja("commit", "COMMIT", 1410, 220, 150, 100),
            Caja(
                "rollback", "Fallo precommit\nROLLBACK", 1110, 500, 260, 100, "frontera"
            ),
        ),
        (
            ("alumno", "reserva", "solicitud"),
            ("reserva", "sandbox", "token"),
            ("sandbox", "begin", "resultado"),
            ("begin", "bundle", "flush"),
            ("bundle", "commit", "exito"),
            ("begin", "rollback", "excepcion"),
        ),
    ),
    Diagrama(
        "03_modelo_datos",
        "Modelo de datos esencial",
        (
            Caja("usuario", "Usuario", 80, 100, 200, 90),
            Caja("examen", "Examen", 400, 100, 200, 90),
            Caja("version", "Version de examen", 720, 100, 230, 90),
            Caja("entrega", "Entrega", 400, 330, 200, 90),
            Caja("asignada", "Pregunta asignada", 80, 560, 230, 90),
            Caja("respuesta", "Respuesta", 380, 560, 200, 90),
            Caja("nota", "Calificacion", 650, 560, 200, 90),
            Caja("revision", "Revision manual", 920, 560, 220, 90),
            Caja("evento", "Evento", 1180, 330, 180, 90),
            Caja("evidencia", "Evidencia", 1180, 560, 180, 90),
        ),
        (
            ("usuario", "entrega", "realiza"),
            ("examen", "version", "versiona"),
            ("examen", "entrega", "origina"),
            ("entrega", "asignada", "congela"),
            ("entrega", "respuesta", "contiene"),
            ("entrega", "nota", "1 a 1"),
            ("entrega", "revision", "audita"),
            ("entrega", "evento", "registra"),
            ("evento", "evidencia", "adjunta"),
        ),
    ),
    Diagrama(
        "04_limites_confianza",
        "Limites de confianza del sandbox",
        (
            Caja(
                "browser", "Navegador\nNO CONFIABLE", 80, 330, 240, 120, "no_validado"
            ),
            Caja("api", "API", 430, 330, 200, 120),
            Caja("db", "Base de datos", 430, 600, 220, 110),
            Caja("worker", "Trabajador / adaptador", 780, 330, 250, 120, "configurado"),
            Caja(
                "container",
                "Contenedor\nred bloqueada",
                1150,
                330,
                240,
                120,
                "no_validado",
            ),
            Caja("host", "Host dedicado o VM", 1080, 650, 380, 110, "frontera"),
        ),
        (
            ("browser", "api", "entrada validada"),
            ("api", "db", "credencial limitada"),
            ("api", "worker", "contrato interno"),
            ("worker", "container", "opciones fijas"),
            ("container", "host", "frontera runtime"),
        ),
    ),
    Diagrama(
        "05_evidencias_multimedia",
        "Flujo visible de evidencias multimedia",
        (
            Caja("consent", "Consentimiento", 40, 330, 190, 100),
            Caja("auth", "Autorizacion previa", 270, 330, 210, 100),
            Caja("streams", "Flujos activos", 520, 330, 190, 100),
            Caja("event", "Cambio de pestana", 750, 330, 210, 100),
            Caja("clip", "Clip <= 15 s", 1000, 330, 180, 100),
            Caja("validate", "MIME, firma, bytes", 1220, 330, 220, 100),
            Caja("store", "Almacenamiento BLOB", 850, 600, 230, 100),
            Caja("review", "Revision docente\ny log de acceso", 1160, 600, 240, 100),
        ),
        (
            ("consent", "auth", "accion"),
            ("auth", "streams", "permiso"),
            ("streams", "event", "blur"),
            ("event", "clip", "MediaRecorder"),
            ("clip", "validate", "upload"),
            ("validate", "store", "aceptada"),
            ("store", "review", "rol profesor"),
        ),
    ),
)


def fuente(
    tamano: int, negrita: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    nombre = "arialbd.ttf" if negrita else "arial.ttf"
    ruta = Path("C:/Windows/Fonts") / nombre
    return (
        ImageFont.truetype(str(ruta), tamano)
        if ruta.exists()
        else ImageFont.load_default()
    )


def centro(caja: Caja) -> tuple[int, int]:
    return caja.x + caja.w // 2, caja.y + caja.h // 2


def extremos(origen: Caja, destino: Caja) -> tuple[tuple[int, int], tuple[int, int]]:
    ox, oy = centro(origen)
    dx, dy = centro(destino)
    if abs(dx - ox) >= abs(dy - oy):
        return (
            (origen.x + origen.w if dx > ox else origen.x, oy),
            (destino.x if dx > ox else destino.x + destino.w, dy),
        )
    return (
        (ox, origen.y + origen.h if dy > oy else origen.y),
        (dx, destino.y if dy > oy else destino.y + destino.h),
    )


def mmd(diagrama: Diagrama) -> str:
    lineas = ["flowchart LR"]
    for caja in diagrama.cajas:
        lineas.append(f'  {caja.id}["{caja.texto.replace(chr(10), "<br/>")}"]')
    for origen, destino, etiqueta in diagrama.enlaces:
        lineas.append(f'  {origen} -->|"{etiqueta}"| {destino}')
    lineas.extend(
        [
            "  classDef ejecutado fill:#dbf5ee,stroke:#0f766e,color:#172033;",
            "  classDef configurado fill:#fff2cc,stroke:#b45309,color:#172033;",
            "  classDef no_validado fill:#fee2e2,stroke:#b42318,color:#172033;",
            "  classDef frontera fill:#e0e7ff,stroke:#4338ca,color:#172033;",
        ]
    )
    for caja in diagrama.cajas:
        lineas.append(f"  class {caja.id} {caja.estado};")
    return "\n".join(lineas) + "\n"


def svg(diagrama: Diagrama) -> str:
    por_id = {caja.id: caja for caja in diagrama.cajas}
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ANCHO}" height="{ALTO}" viewBox="0 0 {ANCHO} {ALTO}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<defs><marker id="flecha" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#475569"/></marker></defs>',
        f'<text x="60" y="65" font-family="Arial" font-size="34" font-weight="700" fill="#172033">{html.escape(diagrama.titulo)}</text>',
    ]
    for origen, destino, _ in diagrama.enlaces:
        inicio, fin = extremos(por_id[origen], por_id[destino])
        partes.append(
            f'<line x1="{inicio[0]}" y1="{inicio[1]}" x2="{fin[0]}" y2="{fin[1]}" stroke="#475569" stroke-width="3" marker-end="url(#flecha)"/>'
        )
    for caja in diagrama.cajas:
        color = "#%02x%02x%02x" % COLORES[caja.estado]
        partes.append(
            f'<rect x="{caja.x}" y="{caja.y}" width="{caja.w}" height="{caja.h}" rx="14" fill="{color}" stroke="#0f172a" stroke-width="2"/>'
        )
        lineas = caja.texto.splitlines()
        for indice, linea in enumerate(lineas):
            y = caja.y + caja.h / 2 + (indice - (len(lineas) - 1) / 2) * 28 + 7
            partes.append(
                f'<text x="{caja.x + caja.w / 2}" y="{y}" text-anchor="middle" font-family="Arial" font-size="21" font-weight="600" fill="#172033">{html.escape(linea)}</text>'
            )
    for indice, (estado, etiqueta) in enumerate(
        (
            ("ejecutado", "Ejecutado"),
            ("configurado", "Configurado"),
            ("no_validado", "No validado"),
            ("frontera", "Frontera"),
        )
    ):
        x = 60 + indice * 260
        color = "#%02x%02x%02x" % COLORES[estado]
        partes.append(
            f'<rect x="{x}" y="835" width="34" height="24" rx="5" fill="{color}" stroke="#0f172a"/>'
        )
        partes.append(
            f'<text x="{x + 44}" y="854" font-family="Arial" font-size="17" fill="#172033">{etiqueta}</text>'
        )
    partes.append("</svg>")
    return "\n".join(partes) + "\n"


def png(diagrama: Diagrama, ruta: Path) -> None:
    imagen = Image.new("RGB", (ANCHO, ALTO), "#f8fafc")
    dibujo = ImageDraw.Draw(imagen)
    dibujo.text((60, 35), diagrama.titulo, fill="#172033", font=fuente(34, True))
    por_id = {caja.id: caja for caja in diagrama.cajas}
    for origen, destino, _ in diagrama.enlaces:
        inicio, fin = extremos(por_id[origen], por_id[destino])
        dibujo.line((*inicio, *fin), fill="#475569", width=4)
    for caja in diagrama.cajas:
        dibujo.rounded_rectangle(
            (caja.x, caja.y, caja.x + caja.w, caja.y + caja.h),
            radius=14,
            fill=COLORES[caja.estado],
            outline="#0f172a",
            width=3,
        )
        dibujo.multiline_text(
            centro(caja),
            caja.texto,
            anchor="mm",
            align="center",
            spacing=8,
            fill="#172033",
            font=fuente(21, True),
        )
    for indice, (estado, etiqueta) in enumerate(
        (
            ("ejecutado", "Ejecutado"),
            ("configurado", "Configurado"),
            ("no_validado", "No validado"),
            ("frontera", "Frontera"),
        )
    ):
        x = 60 + indice * 260
        dibujo.rounded_rectangle(
            (x, 835, x + 34, 859),
            radius=5,
            fill=COLORES[estado],
            outline="#0f172a",
            width=2,
        )
        dibujo.text(
            (x + 44, 847), etiqueta, anchor="lm", fill="#172033", font=fuente(17)
        )
    imagen.save(ruta, dpi=(150, 150))


def pdf(diagrama: Diagrama, ruta: Path) -> None:
    pagina = landscape(A4)
    escala = min(pagina[0] / ANCHO, pagina[1] / ALTO)
    lienzo = canvas.Canvas(str(ruta), pagesize=pagina)
    lienzo.scale(escala, escala)
    lienzo.setFillColorRGB(0.973, 0.98, 0.988)
    lienzo.rect(0, 0, ANCHO, ALTO, fill=1, stroke=0)
    lienzo.setFillColorRGB(0.09, 0.125, 0.2)
    lienzo.setFont("Helvetica-Bold", 34)
    lienzo.drawString(60, ALTO - 65, diagrama.titulo)
    por_id = {caja.id: caja for caja in diagrama.cajas}
    for origen, destino, _ in diagrama.enlaces:
        inicio, fin = extremos(por_id[origen], por_id[destino])
        inicio_pdf = (inicio[0], ALTO - inicio[1])
        fin_pdf = (fin[0], ALTO - fin[1])
        lienzo.setStrokeColorRGB(0.28, 0.33, 0.41)
        lienzo.setLineWidth(3)
        lienzo.line(*inicio_pdf, *fin_pdf)
    for caja in diagrama.cajas:
        r, g, b = (valor / 255 for valor in COLORES[caja.estado])
        lienzo.setFillColorRGB(r, g, b)
        lienzo.setStrokeColorRGB(0.06, 0.09, 0.16)
        lienzo.roundRect(caja.x, ALTO - caja.y - caja.h, caja.w, caja.h, 14, fill=1)
        lienzo.setFillColorRGB(0.09, 0.125, 0.2)
        lienzo.setFont("Helvetica-Bold", 21)
        lineas = caja.texto.splitlines()
        for indice, linea in enumerate(lineas):
            y = ALTO - caja.y - caja.h / 2 + (len(lineas) - 1) * 14 - indice * 28 - 7
            lienzo.drawCentredString(caja.x + caja.w / 2, y, linea)
    for indice, (estado, etiqueta) in enumerate(
        (
            ("ejecutado", "Ejecutado"),
            ("configurado", "Configurado"),
            ("no_validado", "No validado"),
            ("frontera", "Frontera"),
        )
    ):
        x = 60 + indice * 260
        r, g, b = (valor / 255 for valor in COLORES[estado])
        lienzo.setFillColorRGB(r, g, b)
        lienzo.roundRect(x, 41, 34, 24, 5, fill=1)
        lienzo.setFillColorRGB(0.09, 0.125, 0.2)
        lienzo.setFont("Helvetica", 17)
        lienzo.drawString(x + 44, 47, etiqueta)
    lienzo.save()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "figuras_simplificadas",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for diagrama in DIAGRAMAS:
        (args.output / f"{diagrama.nombre}.mmd").write_text(
            mmd(diagrama), encoding="utf-8"
        )
        (args.output / f"{diagrama.nombre}.svg").write_text(
            svg(diagrama), encoding="utf-8"
        )
        png(diagrama, args.output / f"{diagrama.nombre}.png")
        pdf(diagrama, args.output / f"{diagrama.nombre}.pdf")
        print(f"Generado: {diagrama.nombre} (.mmd, .svg, .png, .pdf)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
