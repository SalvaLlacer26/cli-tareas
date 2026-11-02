"""La ficha .md: el fichero donde se guarda todo lo que se sabe de un documento.

`analizar` escribe una ficha por cada documento, dentro de la carpeta oculta
«md». Esa ficha es la que leen después `organizar`, `deshacer`, `resumir` y
`evaluar`: por eso se llama «ficha» y no «nota».

El formato es Markdown legible, con una sección de datos al principio:

    # Ficha de analisis

    ## Datos

    - **Nombre original:** Práctica 1. Entitats.pdf
    - **Nombre compatible:** practica-1-entitats.pdf
    - **Asignatura:** Bases de dades
    ...

    ## Contenido

    <el texto extraído del documento>

Se escribe a mano (sin dependencias) y se lee con un par de expresiones
regulares, porque el formato es estable y lo controlamos nosotros.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

#: Estados posibles de un documento analizado.
CLASIFICADO = "clasificado"
SIN_CLASIFICAR = "sin clasificar"
FORMATO_INVALIDO = "formato invalido"

#: Separador entre los campos de la sección de datos.
CAMPOS = re.compile(r"^-\s+\*\*(.+?):\*\*\s*(.*)$")


@dataclass
class Ficha:
    """Todo lo que se sabe de un documento."""

    nombre_original: str = ""
    nombre_compatible: str = ""
    asignatura: str = ""
    carpeta: str = ""
    destino: str = ""
    origen: str = ""
    estado: str = CLASIFICADO
    formato: str = ""
    tamano: int = 0
    paginas: int | None = None
    motivo: str = ""
    analizado: str = ""
    contenido: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def es_valida(self) -> bool:
        """Si la ficha se puede usar para organizar."""
        return self.estado == CLASIFICADO and bool(self.destino) and bool(self.nombre_compatible)

    def texto(self) -> str:
        """La ficha completa, lista para escribirse en un .md."""
        lineas = [
            "# Ficha de análisis",
            "",
            "Generada por `tareas analizar`. Los datos de esta ficha son los que",
            "usan después `tareas organizar`, `tareas resumir` y `tareas evaluar`.",
            "",
            "## Datos",
            "",
            f"- **Nombre original:** {self.nombre_original}",
            f"- **Nombre compatible:** {self.nombre_compatible}",
            f"- **Asignatura:** {self.asignatura}",
            f"- **Carpeta:** {self.carpeta}",
            f"- **Destino:** {self.destino}",
            f"- **Origen:** {self.origen}",
            f"- **Estado:** {self.estado}",
            f"- **Formato:** {self.formato}",
            f"- **Tamaño:** {self.tamano}",
            f"- **Páginas:** {self.paginas if self.paginas is not None else '-'}",
            f"- **Motivo:** {self.motivo or '-'}",
            f"- **Analizado:** {self.analizado}",
        ]
        for clave, valor in self.extra.items():
            lineas.append(f"- **{clave}:** {valor}")

        lineas += ["", "## Contenido", "", self.contenido.strip() or "(sin contenido extraído)", ""]
        return "\n".join(lineas)


def escribir(ficha: Ficha, ruta: Path) -> Path:
    """Escribe la ficha en un .md."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(ficha.texto(), encoding="utf-8")
    return ruta


def leer(ruta: Path) -> Ficha:
    """Lee una ficha .md y devuelve lo que tiene dentro."""
    ruta = Path(ruta)
    texto = ruta.read_text(encoding="utf-8", errors="ignore")

    ficha = Ficha()

    # Los datos están entre «## Datos» y la siguiente sección.
    seccion_datos = ""
    seccion_contenido = ""
    partes = re.split(r"^##\s+", texto, flags=re.MULTILINE)
    for parte in partes:
        titulo, _, cuerpo = parte.partition("\n")
        titulo = titulo.strip().lower()
        if titulo == "datos":
            seccion_datos = cuerpo
        elif titulo == "contenido":
            seccion_contenido = cuerpo

    for linea in seccion_datos.splitlines():
        encontrada = CAMPOS.match(linea.strip())
        if not encontrada:
            continue
        clave = encontrada.group(1).strip().lower()
        valor = encontrada.group(2).strip()
        _asignar(ficha, clave, valor)

    ficha.contenido = seccion_contenido.strip()
    return ficha


def _asignar(ficha: Ficha, clave: str, valor: str) -> None:
    """Pone un dato de la sección «Datos» en su sitio."""
    if clave == "nombre original":
        ficha.nombre_original = valor
    elif clave == "nombre compatible":
        ficha.nombre_compatible = valor
    elif clave == "asignatura":
        ficha.asignatura = valor
    elif clave == "carpeta":
        ficha.carpeta = valor
    elif clave == "destino":
        ficha.destino = valor
    elif clave == "origen":
        ficha.origen = valor
    elif clave == "estado":
        ficha.estado = valor
    elif clave == "formato":
        ficha.formato = valor
    elif clave == "tamaño":
        try:
            ficha.tamano = int(valor)
        except ValueError:
            ficha.tamano = 0
    elif clave == "páginas":
        try:
            ficha.paginas = int(valor)
        except ValueError:
            ficha.paginas = None
    elif clave == "motivo":
        ficha.motivo = "" if valor == "-" else valor
    elif clave == "analizado":
        ficha.analizado = valor
    else:
        ficha.extra[clave] = valor


def ahora() -> str:
    """La fecha y hora de ahora, en texto."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
