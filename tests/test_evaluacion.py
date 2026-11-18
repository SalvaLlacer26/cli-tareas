"""Pruebas de la batería de ejercicios de «evaluar» (el prompt, sobre todo)."""

from __future__ import annotations

from tareas import evaluacion
from tareas.documentos import Seccion
from tareas.ficha import Ficha


def test_separar_preguntas_deja_una_linea_en_blanco_entre_preguntas() -> None:
    """Entre la última frase de una pregunta y la siguiente hay una línea en blanco."""
    secciones = [
        Seccion(
            "Tipo test",
            [
                "1. ¿Primera?",
                "a) uno",
                "b) dos",
                "2. ¿Segunda?",
                "a) tres",
            ],
        )
    ]
    (separada,) = evaluacion.separar_preguntas(secciones)
    # No se corta entre la pregunta y sus alternativas, pero sí antes de la 2.
    assert separada.lineas == [
        "1. ¿Primera?",
        "a) uno",
        "b) dos",
        "",
        "2. ¿Segunda?",
        "a) tres",
    ]


def test_separar_preguntas_no_pone_blanco_al_empezar() -> None:
    (separada,) = evaluacion.separar_preguntas([Seccion("X", ["1. Una", "2. Dos"])])
    assert separada.lineas[0] == "1. Una"


def test_el_prompt_no_pide_la_respuesta_dentro_de_la_pregunta(monkeypatch) -> None:
    """La respuesta correcta solo va al final, en «Soluciones», no en el enunciado.

    Marca de la casa: si se escribe «[b)]» junto a la pregunta, el examen deja
    de servir para practicar. Aquí se vigila que el prompt no vuelva a pedirlo.
    """
    import tareas.ia as ia

    capturado: dict[str, str] = {}

    def falsa_peticion(sistema, peticion, *a, **k):
        capturado["peticion"] = peticion
        return "## Tipo test\n\n1. ¿Un ejemplo?\n   a) Uno\n   b) Dos\n", []

    monkeypatch.setattr(ia, "pedir_con_busqueda", falsa_peticion)

    ficha = Ficha(nombre_original="apuntes.txt", contenido="El agua hierve a 100 grados.")
    evaluacion.pedir_ejercicios(ficha)

    peticion = capturado["peticion"]
    assert "[b)]" not in peticion
    assert "entre corchetes" not in peticion
    assert "ÚNICAMENTE en el apartado «Soluciones»" in peticion


def test_el_prompt_del_examen_investiga_y_no_copia_el_pdf(monkeypatch) -> None:
    """El examen se hace sobre la teoría investigada, no copiando el documento."""
    import tareas.ia as ia

    capturado: dict[str, str] = {}

    def falsa_peticion(sistema, peticion, *a, **k):
        capturado["peticion"] = peticion
        return "## Tipo test\n\n1. ¿Un ejemplo?\n   a) Uno\n   b) Dos\n", []

    monkeypatch.setattr(ia, "pedir_con_busqueda", falsa_peticion)

    ficha = Ficha(nombre_original="apuntes.txt", contenido="El agua hierve a 100 grados.")
    evaluacion.pedir_ejercicios(ficha)

    peticion = capturado["peticion"]
    assert "INVESTIGA" in peticion
    assert "NO es la fuente" in peticion
    assert "[[BUSCAR: consulta]]" in peticion
    assert "Solo contenido del documento" not in peticion
