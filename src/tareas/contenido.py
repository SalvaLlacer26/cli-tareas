"""Leer el contenido de un fichero para poder analizarlo.

Se extrae **texto**, nunca imágenes: el objetivo es entender de qué va el
documento, no recrearlo. Los formatos que no se pueden leer (un `.deb`, un
`.png`, un ZIP) se marcan como «formato invalido» en vez de fallar.

Los PDF se leen con `pdftotext` de poppler, que solo lee las primeras páginas
que se le pidan: un PDF de 300 páginas no se carga entero en memoria.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .errores import FormatoNoAnalizable

#: Formatos de los que se puede extraer texto.
FORMATOS_CON_TEXTO = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "doc",
    ".odt": "odt",
    ".ods": "ods",
    ".odp": "odp",
    ".rtf": "rtf",
    ".txt": "txt",
    ".md": "txt",
    ".csv": "txt",
    ".html": "html",
    ".htm": "html",
    ".xml": "xml",
    ".json": "txt",
}

#: Cuántas páginas se leen de un PDF. Suficiente para saber de qué va.
PAGINAS_PDF = 3

#: Cuántos caracteres se guardan del contenido extraído.
MAXIMO_CARACTERES = 40000

#: Tamaño máximo del fichero que se procesa (por encima, no se analiza).
MAXIMO_BYTES = 200 * 1024 * 1024


@dataclass
class Contenido:
    """Lo que se ha podido sacar de un fichero."""

    texto: str = ""
    formato: str = ""
    paginas: int | None = None
    analizable: bool = True
    motivo: str = ""

    @property
    def vacio(self) -> bool:
        return not self.texto.strip()


def es_analizable(ruta: Path) -> bool:
    """Si el formato del fichero se puede analizar."""
    return ruta.suffix.lower() in FORMATOS_CON_TEXTO


def extraer(ruta: Path) -> Contenido:
    """Extrae el texto de un fichero. Nunca lanza por un formato raro."""
    ruta = Path(ruta)
    extension = ruta.suffix.lower()

    if extension not in FORMATOS_CON_TEXTO:
        return Contenido(
            formato=extension or "(sin extensión)",
            analizable=False,
            motivo=f"el formato «{extension or 'desconocido'}» no se puede analizar",
        )

    try:
        tamano = ruta.stat().st_size
    except OSError as exc:
        return Contenido(
            formato=extension,
            analizable=False,
            motivo=f"no se puede leer el fichero: {exc.strerror or exc}",
        )

    if tamano > MAXIMO_BYTES:
        return Contenido(
            formato=extension,
            analizable=False,
            motivo=f"el fichero es demasiado grande ({tamano} bytes)",
        )

    tipo = FORMATOS_CON_TEXTO[extension]
    try:
        if tipo == "pdf":
            return _de_pdf(ruta)
        if tipo in ("docx", "odt", "ods", "odp"):
            return _de_openoffice(ruta, tipo)
        if tipo == "rtf":
            return Contenido(texto=_de_rtf(ruta), formato=extension)
        if tipo == "html":
            return Contenido(texto=_de_html(ruta), formato=extension)
        return Contenido(texto=_de_texto(ruta), formato=extension)
    except OSError as exc:
        return Contenido(
            formato=extension,
            analizable=False,
            motivo=f"no se puede leer el fichero: {exc.strerror or exc}",
        )
    except Exception as exc:  # noqa: BLE001 - ningún fichero puede romper el análisis
        return Contenido(
            formato=extension,
            analizable=False,
            motivo=f"no se ha podido analizar: {exc}",
        )


# ----------------------------------------------------------------- PDF


def _de_pdf(ruta: Path) -> Contenido:
    """Lee las primeras páginas de un PDF con pdftotext."""
    if not shutil.which("pdftotext"):
        return Contenido(
            formato=".pdf",
            analizable=False,
            motivo="falta la herramienta «pdftotext» (paquete poppler-utils)",
        )

    resultado = subprocess.run(
        ["pdftotext", "-f", "1", "-l", str(PAGINAS_PDF), str(ruta), "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        check=False,
    )
    texto = resultado.stdout.decode("utf-8", errors="ignore")
    paginas = _paginas_pdf(ruta)

    if not texto.strip():
        return Contenido(
            texto="",
            formato=".pdf",
            paginas=paginas,
            analizable=False,
            motivo="el PDF no tiene texto (puede ser escaneado como imagen)",
        )

    return Contenido(texto=texto[:MAXIMO_CARACTERES], formato=".pdf", paginas=paginas)


def _paginas_pdf(ruta: Path) -> int | None:
    """Cuántas páginas tiene el PDF, si se puede saber."""
    if not shutil.which("pdfinfo"):
        return None
    resultado = subprocess.run(
        ["pdfinfo", str(ruta)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=False,
    )
    salida = resultado.stdout.decode("utf-8", errors="ignore")
    encontrada = re.search(r"^Pages:\s+(\d+)", salida, re.MULTILINE)
    return int(encontrada.group(1)) if encontrada else None


# ------------------------------------------------- OpenOffice y Word


def _de_openoffice(ruta: Path, tipo: str) -> Contenido:
    """Extrae el texto de un .docx, .odt, .ods u .odp.

    Todos son ficheros ZIP con el texto dentro: en un .docx está en
    word/document.xml y en los de OpenOffice en content.xml.
    """
    with zipfile.ZipFile(ruta) as paquete:
        if tipo == "docx":
            miembros = [n for n in paquete.namelist() if n.endswith("document.xml")]
        else:
            miembros = [n for n in paquete.namelist() if n.endswith("content.xml")]

        if not miembros:
            return Contenido(
                formato=ruta.suffix.lower(),
                analizable=False,
                motivo="el fichero no tiene el XML del texto dentro",
            )

        xml = paquete.read(miembros[0]).decode("utf-8", errors="ignore")

    texto = _xml_a_texto(xml)
    if not texto.strip():
        return Contenido(
            texto="",
            formato=ruta.suffix.lower(),
            analizable=False,
            motivo="el documento está vacío",
        )
    return Contenido(texto=texto[:MAXIMO_CARACTERES], formato=ruta.suffix.lower())


def _xml_a_texto(xml: str) -> str:
    """Convierte el XML de un documento en texto plano, respetando los párrafos."""
    sin_etiquetas = re.sub(r"</(w:p|text:p|paragraph)>", "\n", xml)
    sin_etiquetas = re.sub(r"<w:tab[^>]*/>", "\t", sin_etiquetas)
    sin_etiquetas = re.sub(r"<w:br[^>]*/>", "\n", sin_etiquetas)
    sin_etiquetas = re.sub(r"<[^>]+>", "", sin_etiquetas)

    import html

    texto = html.unescape(sin_etiquetas)
    lineas = [linea.strip() for linea in texto.splitlines()]
    return "\n".join(linea for linea in lineas if linea)


# ---------------------------------------------------------------- otros


def _de_texto(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8", errors="ignore")[:MAXIMO_CARACTERES]


def _de_html(ruta: Path) -> str:
    import html

    crudo = ruta.read_text(encoding="utf-8", errors="ignore")
    limpio = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", crudo, flags=re.S | re.I)
    limpio = re.sub(r"<[^>]+>", " ", limpio)
    return html.unescape(limpio)[:MAXIMO_CARACTERES]


def _de_rtf(ruta: Path) -> str:
    """El RTF es texto con comandos entre llaves: se quitan y ya."""
    crudo = ruta.read_text(encoding="utf-8", errors="ignore")
    limpio = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", crudo)
    limpio = limpio.replace("{", "").replace("}", "")
    return limpio[:MAXIMO_CARACTERES]
