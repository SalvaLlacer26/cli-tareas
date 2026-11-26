"""Pruebas del examen interactivo: JSON, formulario, corrección y servidor local."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tareas import examenes
from tareas.errores import ErrorIA
from tareas.examenes import Pregunta


# ------------------------------------------------------- leer el JSON modelo


def test_extraer_json_de_una_respuesta_desnuda() -> None:
    assert examenes._extraer_json('[{"a": 1}]') == [{"a": 1}]


def test_extraer_json_envuelto_en_marcas_de_codigo() -> None:
    texto = 'Mira:\n```json\n[{"tipo": "test"}]\n```\n¿vale?'
    assert examenes._extraer_json(texto) == [{"tipo": "test"}]


def test_extraer_json_sin_array_es_un_error() -> None:
    with pytest.raises(ErrorIA):
        examenes._extraer_json("no hay ningún array aquí")


# -------------------------------------------------------- el formulario HTML


PREGUNTAS = [
    Pregunta(1, examenes.TEST, "¿Cuánto es 2+2?", ["3", "4", "5", "6"], "b"),
    Pregunta(2, examenes.DESARROLLO, "Explica la fotosíntesis.", solucion="clorofila"),
    Pregunta(3, examenes.CALCULO, "Calcula el área.", solucion="base por altura"),
]


def test_la_pagina_tiene_radios_para_el_test_y_huecos_para_el_resto() -> None:
    pagina = examenes.construir_pagina("Examen", PREGUNTAS, con_ia=True)
    assert 'name="q1"' in pagina and 'value="b"' in pagina
    assert 'name="q2"' in pagina and "<textarea" in pagina
    assert "Enviar respuestas" in pagina and "fetch" in pagina


def test_la_pagina_escapa_el_html_de_los_enunciados() -> None:
    preguntas = [Pregunta(1, examenes.TEST, "<script>mal</script>", ["a", "b", "c", "d"], "a")]
    pagina = examenes.construir_pagina("Título", preguntas, con_ia=True)
    assert "<script>mal</script>" not in pagina
    assert "&lt;script&gt;" in pagina


# ------------------------------------------------------------ la corrección


def test_el_test_se_corrige_sin_ia_comparando_letras() -> None:
    respuestas = {"q1": "b", "q2": "lo que sea", "q3": "9"}
    pagina = examenes.construir_correccion("Examen", PREGUNTAS, respuestas, con_ia=False)
    assert "CORRECTA" in pagina
    # Con la respuesta mala sale marcado como incorrecta.
    pagina_mala = examenes.construir_correccion("Examen", PREGUNTAS, {"q1": "a"}, con_ia=False)
    assert "INCORRECTA" in pagina_mala


def test_sin_ia_lo_escrito_no_se_autocorrige() -> None:
    pagina = examenes.construir_correccion("Examen", PREGUNTAS, {"q2": "x"}, con_ia=False)
    assert "Sin IA" in pagina


def test_sin_ia_una_respuesta_mala_no_dice_correcta() -> None:
    """Caso feo: responden a medias y no se rellena el examen de «CORRECTA»."""
    pagina = examenes.construir_correccion("Examen", PREGUNTAS, {"q1": "z"}, con_ia=False)
    assert "SIN RESPONDER" not in pagina  # «z» no es ninguna de las letras válidas
    assert "INCORRECTA" in pagina


# ------------------------------------------------------ la batería de prueba


def test_la_bateria_sin_ia_sale_del_texto() -> None:
    from tareas.ficha import Ficha

    ficha = Ficha(
        nombre_original="apuntes.txt",
        contenido="Fotosíntesis\n\nLa fotosíntesis se define como el proceso por "
        "el que las plantas convierten luz en energía química usando la clorofila.",
    )
    preguntas = examenes.bateria_extractiva(ficha)
    assert preguntas
    assert all(p.tipo in (examenes.DESARROLLO, examenes.CALCULO) for p in preguntas)


def test_la_bateria_sin_ia_con_texto_vacio_es_un_error() -> None:
    from tareas.ficha import Ficha

    with pytest.raises(ErrorIA):
        examenes.bateria_extractiva(Ficha(nombre_original="vacio.txt", contenido=""))


def test_pedir_bateria_filtra_las_preguntas_mal_formadas(monkeypatch) -> None:
    """Si el modelo devuelve test sin las cuatro opciones, esas preguntas se tiran."""
    import tareas.ia as ia

    validas = [
        {"tipo": "test", "enunciado": f"Test {n}", "opciones": ["a", "b", "c", "d"], "respuesta": "a"}
        for n in range(1, 7)
    ] + [
        {"tipo": "desarrollo", "enunciado": f"Desarrollo {n}", "solucion": "x"}
        for n in range(1, 4)
    ] + [
        {"tipo": "calculo", "enunciado": "Calcula", "solucion": "y"}
    ]
    validas.insert(3, {"tipo": "test", "enunciado": "Rota", "opciones": ["solo", "dos"], "respuesta": "a"})
    monkeypatch.setattr(ia, "pedir_con_busqueda", lambda *a, **k: (json.dumps(validas), []))
    from tareas.ficha import Ficha

    preguntas = examenes.pedir_bateria(
        Ficha(nombre_original="d.txt", contenido="texto largo " * 20)
    )
    enunciados = [p.enunciado for p in preguntas]
    assert "Rota" not in enunciados  # la malformada se ha caído
    assert len(preguntas) >= 10  # y aun así se llega al mínimo de 10


def test_el_prompt_del_formulario_investiga_y_no_copia_el_pdf(monkeypatch) -> None:
    """El formulario_evaluar se hace sobre la teoría investigada, no el PDF."""
    import tareas.ia as ia
    from tareas.ficha import Ficha

    capturado: dict[str, str] = {}

    def falsa_peticion(sistema, peticion, *a, **k):
        capturado["peticion"] = peticion
        return (
            json.dumps(
                [
                    {
                        "tipo": "test",
                        "enunciado": f"Test {n}",
                        "opciones": ["a", "b", "c", "d"],
                        "respuesta": "a",
                    }
                    for n in range(1, 12)
                ]
            ),
            [],
        )

    monkeypatch.setattr(ia, "pedir_con_busqueda", falsa_peticion)

    examenes.pedir_bateria(Ficha(nombre_original="d.txt", contenido="texto largo " * 20))

    peticion = capturado["peticion"]
    assert "INVESTIGA" in peticion
    assert "referencia del tema" in peticion
    assert "[[BUSCAR: consulta]]" in peticion
    assert "Solo contenido del documento" not in peticion


# ----------------------------------------------------------- el servidor local


def test_el_servidor_local_sirve_la_pagina_y_corrige() -> None:
    """GET a la página y POST de respuestas devuelven HTML, sin salir de la máquina."""
    servidor, url = examenes.crear_servidor("Examen", PREGUNTAS, con_ia=False)
    try:
        with urllib.request.urlopen(url, timeout=5) as respuesta:
            pagina = respuesta.read().decode("utf-8")
        assert "¿Cuánto es 2+2?" in pagina

        peticion = urllib.request.Request(
            url + "corregir",
            data=json.dumps({"respuestas": {"q1": "b"}}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(peticion, timeout=5) as respuesta:
            correccion = respuesta.read().decode("utf-8")
        assert "CORRECTA" in correccion
    finally:
        servidor.shutdown()
        servidor.server_close()
