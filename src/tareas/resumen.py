"""El comando «resumir»: un resumen del documento, de 10 páginas como máximo.

El resumen se construye a partir del contenido que ya se extrajo y se guardó
en la ficha .md, así que no hace falta volver a abrir el documento (ni un PDF
de 300 páginas).

Sale **sin imágenes** y con el texto organizado: títulos, apartados y tablas
con tabuladores. Si el documento es largo, se recorta lo que sobra y se dice
dónde se ha recortado, en vez de cortar por sorpresa.
"""

from __future__ import annotations

import re
from pathlib import Path

from .documentos import Seccion, escribir_documento
from .errores import DocumentoNoEncontrado
from .ficha import Ficha

#: Máximo de líneas por sección del resumen.
MAXIMO_LINEAS_POR_SECCION = 25

#: Máximo de secciones del resumen.
MAXIMO_SECCIONES = 12

#: Caracteres máximos de contenido en el resumen.
MAXIMO_CARACTERES = 30000

#: Palabras que delatan un apartado de un documento de apuntes.
MARCAS_DE_SECCION = (
    "índice", "indice", "contenido", "introducción", "introduccion", "resumen",
    "objetivos", "contenidos", "ejercicios", "actividades", "casos prácticos",
    "practica", "bibliografía", "bibliografia", "conclusiones", "anexos",
)


def _limpiar(texto: str) -> str:
    """Quita líneas en blanco de más y espacios sobrantes."""
    lineas = [linea.rstrip() for linea in texto.splitlines()]
    salida: list[str] = []
    anterior_vacia = False
    for linea in lineas:
        vacia = not linea.strip()
        if vacia and anterior_vacia:
            continue
        salida.append(linea)
        anterior_vacia = vacia
    return "\n".join(salida).strip()


def _detectar_apartados(texto: str) -> list[tuple[str, str]]:
    """Trocea el texto en apartados, con su título."""
    lineas = texto.splitlines()
    apartados: list[tuple[str, str]] = []
    titulo_actual = "Contenido"
    cuerpo: list[str] = []

    for linea in lineas:
        es_titulo = (
            2 < len(linea) < 90
            and not linea.endswith((".", ",", ";", ":"))
            and (linea.isupper() or linea.istitle() or linea.strip().lower() in MARCAS_DE_SECCION)
            and not linea.startswith((" ", "\t", "-", "*", "|"))
        )
        if es_titulo:
            if cuerpo:
                apartados.append((titulo_actual, "\n".join(cuerpo)))
            titulo_actual = linea.strip()
            cuerpo = []
        else:
            cuerpo.append(linea)

    if cuerpo:
        apartados.append((titulo_actual, "\n".join(cuerpo)))

    return apartados


def _recortar(lineas: list[str], maximo: int) -> tuple[list[str], bool]:
    """Recorta una lista de líneas y avisa si ha habido que cortar."""
    if len(lineas) <= maximo:
        return lineas, False
    return lineas[:maximo], True


def construir_secciones(ficha: Ficha) -> list[Seccion]:
    """Las secciones del resumen, a partir del contenido de la ficha."""
    contenido = _limpiar(ficha.contenido)
    if not contenido:
        return [
            Seccion(
                "Aviso",
                ["No se ha podido extraer texto de este documento, "
                 "así que no hay nada que resumir."],
            )
        ]

    apartados = _detectar_apartados(contenido) or [("Contenido", contenido)]

    secciones: list[Seccion] = []
    recortado = False

    for titulo, cuerpo in apartados[:MAXIMO_SECCIONES]:
        lineas = [linea for linea in cuerpo.splitlines() if linea.strip()]
        lineas, cortado = _recortar(lineas, MAXIMO_LINEAS_POR_SECCION)
        recortado = recortado or cortado
        secciones.append(Seccion(titulo.strip() or "Contenido", lineas))

    if len(apartados) > MAXIMO_SECCIONES:
        recortado = True

    if recortado:
        secciones.append(
            Seccion(
                "Nota",
                [
                    "El documento es más largo de lo que cabe en un resumen de diez "
                    "páginas, así que se ha recortado. El texto completo sigue en la "
                    "ficha «md» del documento.",
                ],
            )
        )

    return secciones


def resumen_de(ficha: Ficha) -> tuple[str, list[Seccion]]:
    """El título y las secciones del resumen."""
    titulo = f"Resumen · {ficha.nombre_original}"
    return titulo, construir_secciones(ficha)


def escribir_resumen(ficha: Ficha, carpeta: Path, formato: str = "") -> Path:
    """Escribe el fichero del resumen en la carpeta «resumenes»."""
    titulo, secciones = resumen_de(ficha)
    destino = carpeta / "resumenes"
    nombre = f"{_base(ficha.nombre_original)}_resumido{formato}"
    return escribir_documento(destino / nombre, titulo, secciones)


def _base(nombre: str) -> str:
    """El nombre del fichero sin la extensión."""
    from .nombres import separar_extension

    return separar_extension(nombre)[0]


def buscar_ficha(carpeta: Path, nombre: str, carpetas: list | None = None) -> Ficha:
    """Busca la ficha de un documento por su nombre.

    Se acepta el nombre original o el compatible, con o sin extensión. Las
    comparaciones ignoran la forma Unicode: un fichero guardado en NFD y el
    nombre tecleado en NFC se ven iguales pero no lo son.
    """
    from . import ficha as fichas
    from .nombres import a_nfc, mismo_nombre
    from .organizador import _buscar_fichas

    carpeta = Path(carpeta).expanduser()
    objetivo = a_nfc(nombre)
    candidatos = [objetivo]
    if not Path(nombre).suffix:
        candidatos += [f"{objetivo}.pdf", f"{objetivo}.docx", f"{objetivo}.odt", f"{objetivo}.txt"]

    for ruta in _buscar_fichas(carpeta, carpetas):
        ficha = fichas.leer(ruta)
        if not ficha.nombre_original and not ficha.nombre_compatible:
            continue
        if a_nfc(ficha.nombre_original) in candidatos or a_nfc(ficha.nombre_compatible) in candidatos:
            return ficha
        base_original = _base(ficha.nombre_original)
        base_compatible = _base(ficha.nombre_compatible)
        if mismo_nombre(base_original, objetivo) or mismo_nombre(base_compatible, objetivo):
            return ficha

    raise DocumentoNoEncontrado(
        f"No encuentro la ficha de «{nombre}» en «{carpeta}». "
        "Ejecuta primero «tareas analizar» en esa carpeta."
    )
