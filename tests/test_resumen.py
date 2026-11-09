"""Pruebas de la extracción de la unidad, que va en el encabezado del documento."""

from __future__ import annotations

from tareas.ficha import Ficha
from tareas.resumen import unidad_del_documento


def test_la_unidad_sale_del_nombre_del_fichero() -> None:
    ficha = Ficha(nombre_original="UD1. Introducción a Git.pdf")
    assert unidad_del_documento(ficha) == "UD1"


def test_la_unidad_puede_estar_en_las_primeras_lineas() -> None:
    ficha = Ficha(
        nombre_original="apuntes.pdf",
        contenido="Tema 3\n\nEl modelo relacional...",
    )
    assert unidad_del_documento(ficha) == "Tema 3"


def test_sin_unidad_clara_no_se_inventa_nada() -> None:
    ficha = Ficha(nombre_original="apuntes-de-clase.pdf", contenido="La Revolución...")
    assert unidad_del_documento(ficha) == ""
