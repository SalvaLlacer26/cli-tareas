"""Pruebas de la capa de IA con búsqueda: el protocolo de buscar y el bucle."""

from __future__ import annotations

import json
import urllib.error

import pytest

from tareas.errores import ErrorIA
from tareas.ia import buscar_en_la_respuesta, pedir_con_busqueda


class RespuestaFalsa:
    def __init__(self, datos: dict) -> None:
        self._cuerpo = json.dumps(datos).encode("utf-8")

    def read(self) -> bytes:
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _respuesta(texto: str) -> dict:
    return {"choices": [{"message": {"content": texto}}]}


# ------------------------------------------------------- el protocolo


def test_se_detecta_la_peticion_de_busqueda() -> None:
    assert buscar_en_la_respuesta("[[BUSCAR: bases de datos]]") == ["bases de datos"]


def test_se_detecta_con_las_comillas() -> None:
    assert buscar_en_la_respuesta('[[BUSCAR: "modelo relacional"]]') == ["modelo relacional"]


def test_no_detecta_nada_si_no_hay_marcador() -> None:
    assert buscar_en_la_respuesta("Esta es la respuesta final.") == []


def test_no_repete_la_misma_consulta() -> None:
    respuesta = "[[BUSCAR: uno]]\n[[BUSCAR: uno]]"
    assert buscar_en_la_respuesta(respuesta) == ["uno"]


# -------------------------------------------------------- el bucle


def test_sin_peticion_de_busqueda_hace_una_sola_llamada(monkeypatch, configuracion_ia) -> None:
    import urllib.request

    llamadas = []

    def falso(peticion, timeout=None, context=None):
        llamadas.append(json.loads(peticion.data.decode("utf-8")))
        return RespuestaFalsa(_respuesta("## Resumen\n\nEl contenido."))

    monkeypatch.setattr(urllib.request, "urlopen", falso)

    respuesta, fuentes = pedir_con_busqueda("sistema", "usuario")

    assert respuesta == "## Resumen\n\nEl contenido."
    assert fuentes == []
    assert len(llamadas) == 1


def test_con_peticion_de_busqueda_busca_y_vuelve_a_preguntar(monkeypatch, configuracion_ia) -> None:
    import urllib.request

    from tareas.busqueda import Fuente

    respuestas = [
        _respuesta("[[BUSCAR: bases de datos]]"),
        _respuesta("## Resumen\n\nAhora sí, con la información de internet."),
    ]
    llamadas = []

    def falso(peticion, timeout=None, context=None):
        cuerpo = json.loads(peticion.data.decode("utf-8"))
        llamadas.append(cuerpo)
        return RespuestaFalsa(respuestas[len(llamadas) - 1])

    monkeypatch.setattr(urllib.request, "urlopen", falso)

    fuente = Fuente("Base de datos", "https://es.wikipedia.org/wiki/Base_de_datos", "texto")
    monkeypatch.setattr("tareas.busqueda._wikipedia", lambda idioma, consulta, limite: [fuente])
    monkeypatch.setattr("tareas.busqueda._duckduckgo", lambda consulta: [])

    respuesta, fuentes = pedir_con_busqueda("sistema", "usuario")

    assert len(llamadas) == 2, "la segunda llamada lleva los resultados de la búsqueda"
    assert "RESULTADOS DE LA BÚSQUEDA" in llamadas[1]["messages"][-1]["content"]
    assert "https://es.wikipedia.org/wiki/Base_de_datos" in llamadas[1]["messages"][-1]["content"]
    assert fuentes and fuentes[0].url == fuente.url
    assert "Ahora sí" in respuesta


def test_si_la_busqueda_no_da_nada_no_se_insiste(monkeypatch, configuracion_ia) -> None:
    """Sin resultados, no se queda esperando: sigue con lo que tenía."""
    import urllib.request

    llamadas = []

    def falso(peticion, timeout=None, context=None):
        llamadas.append(1)
        return RespuestaFalsa(_respuesta("[[BUSCAR: nada]]"))

    monkeypatch.setattr(urllib.request, "urlopen", falso)
    monkeypatch.setattr("tareas.busqueda._wikipedia", lambda idioma, consulta, limite: [])
    monkeypatch.setattr("tareas.busqueda._duckduckgo", lambda consulta: [])

    respuesta, fuentes = pedir_con_busqueda("sistema", "usuario")

    assert len(llamadas) == 1
    assert fuentes == []


def test_el_numero_de_busquedas_es_limitado(monkeypatch, configuracion_ia) -> None:
    """El modelo no puede pedir búsquedas sin fin."""
    import urllib.request

    llamadas = []

    def falso(peticion, timeout=None, context=None):
        llamadas.append(1)
        return RespuestaFalsa(_respuesta("[[BUSCAR: otra vez]]"))

    monkeypatch.setattr(urllib.request, "urlopen", falso)

    from tareas.busqueda import Fuente

    fuente = Fuente("T", "https://x", "texto largo")
    monkeypatch.setattr("tareas.busqueda._wikipedia", lambda idioma, consulta, limite: [fuente])
    monkeypatch.setattr("tareas.busqueda._duckduckgo", lambda consulta: [])

    pedir_con_busqueda("sistema", "usuario", maximo_consultas=2)

    assert len(llamadas) == 3, "la llamada inicial más dos reintentos"


def test_sin_clave_no_se_intenta_buscar() -> None:
    with pytest.raises(ErrorIA):
        pedir_con_busqueda("sistema", "usuario")
