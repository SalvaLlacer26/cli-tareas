"""Pruebas de «resumir»: delimitar el rango y escribir apuntes desde cero."""

from __future__ import annotations

from tareas.ficha import Ficha
from tareas.resumen import (
    Alcance,
    alcance_desde_documento,
    construir_apuntes,
    parsear_alcance,
    unidad_del_documento,
)

RESPUESTA_APUNTES = (
    "## Qué hay que saber de este tema\n\n- La CPU ejecuta instrucciones.\n\n"
    "## El microprocesador\n\nLa CPU es el procesador...\n"
)


# ----------------------------------------------------- unidad del encabezado


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


# ------------------------------------------------------ delimitar el alcance


def test_parsear_alcance_de_un_json_del_modelo() -> None:
    ficha = Ficha(nombre_original="componentes.pdf", contenido="CPU, placas base...")
    texto = (
        '```json\n{"tema": "Componentes de un PC", "nivel": "1º DAM", '
        '"cubre": ["tipos de CPU", "zocalos", "microprocesadores"], '
        '"fuera": ["memoria RAM", "grafica", "almacenamiento"], "idioma": "es"}\n```'
    )
    alcance = parsear_alcance(texto, ficha)
    assert alcance.tema == "Componentes de un PC"
    assert alcance.cubre == ["tipos de CPU", "zocalos", "microprocesadores"]
    assert alcance.fuera == ["memoria RAM", "grafica", "almacenamiento"]
    assert alcance.origen == "modelo"


def test_parsear_alcance_roto_aproxima_desde_el_documento() -> None:
    ficha = Ficha(
        nombre_original="componentes.pdf",
        contenido="Componentes de un PC\n\nLa CPU...\n\nEl ventilador...",
    )
    alcance = parsear_alcance("no hay json aquí", ficha)
    assert alcance.origen == "documento"
    assert "Componentes" in alcance.tema


def test_alcance_desde_documento_saca_tema_y_apartados() -> None:
    ficha = Ficha(
        nombre_original="ud1.pdf",
        contenido=(
            "UD1\n\nComponentes de un PC\n\nLA CPU\n\nel texto...\n\n"
            "LA PLACA BASE\n\nmas texto..."
        ),
    )
    alcance = alcance_desde_documento(ficha)
    assert "Componentes" in alcance.tema
    assert "LA CPU" in alcance.cubre or "LA PLACA BASE" in alcance.cubre
    assert alcance.fuera == []  # sin IA no se puede saber dónde termina el tema


# ------------------------------------------------- generar apuntes (fase 2)


def test_los_apuntes_son_desde_cero_y_respetan_el_rango(monkeypatch) -> None:
    """La petición prohíbe el resumen, marca el rango y manda investigar."""
    import tareas.ia as ia
    from tareas.resumen import generar_apuntes

    capturado: dict[str, str] = {}

    def falsa_peticion(sistema, peticion, *a, **k):
        capturado["peticion"] = peticion
        return RESPUESTA_APUNTES, []

    monkeypatch.setattr(ia, "pedir_con_busqueda", falsa_peticion)

    alcance = Alcance(
        tema="Componentes de un PC",
        nivel="1º DAM",
        cubre=["la CPU", "el microprocesador"],
        fuera=["la memoria RAM"],
        idioma="es",
    )
    generar_apuntes(alcance)

    peticion = capturado["peticion"]
    assert "APUNTES COMPLETOS" in peticion
    assert "esto NO es un resumen" in peticion
    assert "Se PARA antes de" in peticion
    assert "la memoria RAM" in peticion
    assert "[[BUSCAR: consulta]]" in peticion
    assert "## Preguntas típicas de examen" in peticion


def test_el_contenido_del_documento_no_llega_a_la_fase_2(monkeypatch) -> None:
    """Invariante del rediseño: los apuntes no se escriben mirando el PDF.

    Si el contenido del documento se colara en la generación, volveríamos a un
    resumen con otro nombre. Aquí se vigila con un centinela.
    """
    import tareas.ia as ia
    from tareas.resumen import construir_apuntes

    centinela = "CENTINELA_NO_DEBE_APARECER_12345"
    ficha = Ficha(nombre_original="ud1.pdf", contenido=f"Componentes\n\n{centinela}")

    peticiones: list[str] = []

    def falsa_peticion(sistema, peticion, *a, **k):
        peticiones.append(peticion)
        return RESPUESTA_APUNTES, []

    def falsa_delimitacion(sistema, peticion, *a, **k):
        peticiones.append(peticion)
        return '{"tema": "Componentes", "cubre": ["la CPU"], "fuera": ["la RAM"]}'

    monkeypatch.setattr(ia, "pedir_con_busqueda", falsa_peticion)
    monkeypatch.setattr(ia, "pedir", falsa_delimitacion)

    construir_apuntes(ficha, con_ia=True)

    assert len(peticiones) == 2  # delimitar + generar
    assert centinela in peticiones[0]  # la delimitación sí mira el documento
    assert centinela not in peticiones[1]  # la generación, nunca


def test_sin_ia_la_version_extractiva_lo_dice_claramente() -> None:
    """Sin modelo no hay apuntes nuevos: la nota debe decir que no lo son."""
    ficha = Ficha(
        nombre_original="ud1.pdf",
        contenido="UD1\nLa CPU\nEl procesador ejecuta instrucciones\n" * 10,
    )
    secciones, nota, _fuentes = construir_apuntes(ficha, con_ia=False)
    assert "NO son los apuntes" in " ".join(
        linea for s in secciones for linea in s.lineas
    )
    assert "no hay modelo configurado" in nota


def test_si_la_generacion_falla_se_ca_a_la_extraction(monkeypatch) -> None:
    """Un fallo del modelo a medio camino no deja el comando sin documento."""
    import tareas.ia as ia
    from tareas.errores import ErrorIA
    from tareas.resumen import construir_apuntes

    def buena_delimitacion(sistema, peticion, *a, **k):
        return '{"tema": "La RAM", "cubre": ["tipos"], "fuera": ["caché"]}'

    def generacion_rota(sistema, peticion, *a, **k):
        raise ErrorIA("el modelo se ha caído")

    monkeypatch.setattr(ia, "pedir", buena_delimitacion)
    monkeypatch.setattr(ia, "pedir_con_busqueda", generacion_rota)

    ficha = Ficha(nombre_original="ud1.pdf", contenido="La RAM\n\nMemoria volatile\n" * 5)
    secciones, nota, _fuentes = construir_apuntes(ficha, con_ia=True)
    assert secciones
    assert "Sin apuntes de IA" in nota
