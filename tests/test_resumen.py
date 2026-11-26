"""Pruebas de «resumir»: la unidad del encabezado y el prompt de investigación."""

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


def test_el_prompt_usa_el_documento_como_referencia_e_investiga(monkeypatch) -> None:
    """El documento solo indica el tema: el resumen se construye investigando.

    Si el prompt vuelve a decir «resume el documento» o «solo lo que esté en el
    texto», el resumen deja de servir para aprobar un examen. Aquí se vigila.
    """
    import tareas.ia as ia
    from tareas.resumen import pedir_resumen

    capturado: dict[str, str] = {}

    def falsa_peticion(sistema, peticion, *a, **k):
        capturado["peticion"] = peticion
        return "## Ideas principales\n\n- RAM\n", []

    monkeypatch.setattr(ia, "pedir_con_busqueda", falsa_peticion)

    ficha = Ficha(nombre_original="UD1 RAM.pdf", contenido="La RAM es la memoria...")
    pedir_resumen(ficha)

    peticion = capturado["peticion"]
    assert "INVESTIGA" in peticion
    assert "No resumas el documento" in peticion
    assert "[[BUSCAR: consulta]]" in peticion
    assert "máximo 10 páginas" not in peticion
    assert "solo lo que esté en el texto" not in peticion
