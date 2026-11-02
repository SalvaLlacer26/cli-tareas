"""Convertir una respuesta en Markdown en las secciones de un documento.

El modelo responde en Markdown; el documento final (.odt, .docx, .rtf o .txt)
tiene que tener títulos, negritas, listas y tablas. Este módulo hace esa
traducción sin dependencias: lee los encabezados, las listas y las tablas y
devuelve la lista de secciones que los escritores saben pintar.
"""

from __future__ import annotations

import re

from .documentos import Seccion

#: Una línea de tabla de Markdown: | a | b |
RE_TABLA = re.compile(r"^\s*\|.*\|\s*$")

#: La fila de separación de una tabla: |---|---| (solo guiones y dos puntos).
RE_SEPARADOR = re.compile(r"^\s*\|[\s:|-]+\|\s*$")

#: Un elemento de lista: «- », «* », «+ » o «1. ».
RE_LISTA = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")

#: Un encabezado de Markdown: dos o tres almohadillas.
RE_ENCABEZADO = re.compile(r"^(#{1,6})\s+(.*)$")

#: Las marcas de negrita y cursiva dentro de una línea.
RE_NEGRITA = re.compile(r"\*\*(.+?)\*\*")
RE_CURSIVA = re.compile(r"(?<!\*)\*([^*]+?)\*(?!\*)")


def limpiar_texto(texto: str) -> str:
    """Quita las marcas de Markdown de una línea de texto."""
    limpio = RE_NEGRITA.sub(r"\1", texto)
    limpio = RE_CURSIVA.sub(r"\1", limpio)
    limpio = limpio.replace("`", "")
    return limpio.strip()


def _es_linea_de_tabla(lineas: list[str], indice: int) -> bool:
    """Si la línea forma parte de una tabla."""
    return (
        RE_TABLA.match(lineas[indice]) is not None
        and indice + 1 < len(lineas)
        and RE_SEPARADOR.match(lineas[indice + 1]) is not None
    )


def _tabla_a_texto(lineas: list[str], indice: int) -> tuple[list[str], int]:
    """Convierte una tabla de Markdown en filas con tabuladores."""
    filas: list[str] = []
    cursor = indice
    while cursor < len(lineas) and RE_TABLA.match(lineas[cursor]):
        if not RE_SEPARADOR.match(lineas[cursor]):
            celdas = [celda.strip() for celda in lineas[cursor].strip().strip("|").split("|")]
            filas.append("\t".join(limpiar_texto(celda) for celda in celdas))
        cursor += 1
    return filas, cursor


def a_secciones(markdown: str, titulo: str = "") -> list[Seccion]:
    """Convierte una respuesta en Markdown en secciones para el documento.

    Los encabezados de primer nivel se ignoran (el título lo pone el
    comando). Los de segundo y tercer nivel se convierten en apartados, y el
    de segundo nivel en un subapartado del anterior.
    """
    lineas = markdown.splitlines()
    secciones: list[Seccion] = []
    actual: Seccion | None = None
    titulo_principal = ""

    indice = 0
    while indice < len(lineas):
        linea = lineas[indice]
        indice += 1

        if not linea.strip():
            continue

        # ------------------------------------------------ tabla
        if _es_linea_de_tabla(lineas, indice - 1):
            filas, indice = _tabla_a_texto(lineas, indice - 1)
            if actual is None:
                actual = Seccion(titulo=titulo or titulo_principal or "Contenido", lineas=[])
            actual.lineas.extend(filas)
            actual.lineas.append("")
            continue

        # -------------------------------------------- encabezado
        encabezado = RE_ENCABEZADO.match(linea)
        if encabezado:
            nivel = len(encabezado.group(1))
            texto = limpiar_texto(encabezado.group(2))
            if nivel == 1:
                # El título principal lo pone el comando.
                if not titulo_principal:
                    titulo_principal = texto
                continue
            if actual is not None:
                secciones.append(actual)
            actual = Seccion(titulo=texto, lineas=[], nivel=min(nivel - 1, 2))
            continue

        # ------------------------------------------------- lista
        lista = RE_LISTA.match(linea)
        if lista:
            if actual is None:
                actual = Seccion(titulo=titulo or titulo_principal or "Contenido", lineas=[])
            actual.lineas.append(f"• {limpiar_texto(lista.group(1))}")
            continue

        # ----------------------------------------------- párrafo
        if actual is None:
            actual = Seccion(titulo=titulo or titulo_principal or "Contenido", lineas=[])
        actual.lineas.append(limpiar_texto(linea))

    if actual is not None:
        if actual.lineas or not secciones:
            secciones.append(actual)
    elif not secciones:
        secciones.append(Seccion(titulo=titulo or "Contenido", lineas=[]))

    return secciones

