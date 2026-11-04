"""Pruebas de la capa de IA.

Ninguna de estas pruebas sale a la red: la llamada al servidor se simula.
"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from tareas.errores import ErrorIA
from tareas.ia import (
    MODELO_POR_DEFECTO,
    ConfiguracionIA,
    _endpoint,
    _extraer_texto,
    configuracion,
    disponible,
    leer_dotenv,
    motivo_de_no_disponible,
    pedir,
)


class RespuestaFalsa:
    """Simula la respuesta de urllib."""

    def __init__(self, datos: dict) -> None:
        self._cuerpo = json.dumps(datos).encode("utf-8")

    def read(self) -> bytes:
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ------------------------------------------------------------- el .env


def test_leer_dotenv_ignora_comentarios_y_comillas(tmp_path: Path) -> None:
    ruta = tmp_path / ".env"
    ruta.write_text(
        "# un comentario\n"
        "CLAVE=valor\n"
        "OTRA=\"con comillas\"\n"
        "SIN_IGUALES\n"
        "ESPACIOS = con espacios \n",
        encoding="utf-8",
    )

    valores = leer_dotenv(ruta)

    assert valores["CLAVE"] == "valor"
    assert valores["OTRA"] == "con comillas"
    assert "SIN_IGUALES" not in valores
    assert valores["ESPACIOS"] == "con espacios"


def test_leer_dotenv_de_un_fichero_que_no_existe() -> None:
    assert leer_dotenv(Path("/no/existe/.env")) == {}


def test_sin_configuracion_no_hay_modelo() -> None:
    config = configuracion()
    assert config.url == ""
    assert config.clave == ""
    assert disponible() is False
    assert "TAREAS_IA_URL" in motivo_de_no_disponible()


def test_con_clave_pero_sin_url_el_motivo_es_el_url() -> None:
    import tareas.ia as ia

    original = ia.configuracion
    try:
        ia.configuracion = lambda: ConfiguracionIA(clave="abc")
        assert "TAREAS_IA_URL" in motivo_de_no_disponible()
    finally:
        ia.configuracion = original


def test_el_modelo_por_defecto_se_pone_si_no_se_indica() -> None:
    config = ConfiguracionIA(url="https://x/v1", clave="k")
    assert config.modelo == MODELO_POR_DEFECTO


# ----------------------------------------------------------- la URL


def test_la_url_se_construye_con_v1() -> None:
    config = ConfiguracionIA(url="https://servidor/v1", clave="k")
    assert _endpoint(config, "chat/completions") == "https://servidor/v1/chat/completions"


def test_la_url_se_construye_sin_v1() -> None:
    config = ConfiguracionIA(url="https://servidor", clave="k")
    assert _endpoint(config, "chat/completions") == "https://servidor/v1/chat/completions"


# ------------------------------------------------------- la respuesta


def test_se_extrae_el_texto_de_una_respuesta_de_chat() -> None:
    datos = {"choices": [{"message": {"content": "  Hola  "}}]}
    assert _extraer_texto(datos) == "Hola"


def test_se_extrae_el_texto_de_una_respuesta_con_partes() -> None:
    datos = {"choices": [{"message": {"content": [{"text": "Hola "}, {"text": "mundo"}]}}]}
    assert _extraer_texto(datos) == "Hola mundo"


def test_una_respuesta_vacia_da_error() -> None:
    with pytest.raises(ErrorIA):
        _extraer_texto({"choices": [{"message": {"content": ""}}]})


# --------------------------------------------------------- la llamada


def test_pedir_devuelve_el_texto_del_modelo(monkeypatch, configuracion_ia) -> None:
    import urllib.request

    capturado = {}

    def falso_urlopen(peticion, timeout=None, context=None):
        capturado["url"] = peticion.full_url
        capturado["cuerpo"] = json.loads(peticion.data.decode("utf-8"))
        return RespuestaFalsa({"choices": [{"message": {"content": "El resumen"}}]})

    monkeypatch.setattr(urllib.request, "urlopen", falso_urlopen)

    respuesta = pedir("sistema", "usuario")

    assert respuesta == "El resumen"
    assert capturado["url"].endswith("/chat/completions")
    assert capturado["cuerpo"]["model"] == "modelo-de-prueba"
    assert capturado["cuerpo"]["messages"][0]["role"] == "system"


def test_un_error_del_servidor_da_un_mensaje_claro(monkeypatch, configuracion_ia) -> None:
    import urllib.request

    def falla(peticion, timeout=None, context=None):
        raise urllib.error.HTTPError("url", 500, "error", {}, io.BytesIO(b""))

    monkeypatch.setattr(urllib.request, "urlopen", falla)

    with pytest.raises(ErrorIA) as error:
        pedir("sistema", "usuario")
    assert "500" in str(error.value)


def test_sin_red_da_un_mensaje_claro(monkeypatch, configuracion_ia) -> None:
    import urllib.request

    def falla(peticion, timeout=None, context=None):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(urllib.request, "urlopen", falla)

    with pytest.raises(ErrorIA) as error:
        pedir("sistema", "usuario")
    assert "servidor de modelos" in str(error.value)


def test_una_respuesta_que_no_es_json_da_error(monkeypatch, configuracion_ia) -> None:
    import urllib.request

    class Raro:
        def read(self):
            return b"esto no es json"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Raro())

    with pytest.raises(ErrorIA) as error:
        pedir("sistema", "usuario")
    assert "JSON" in str(error.value)


def test_sin_clave_no_se_intenta_conectar() -> None:
    with pytest.raises(ErrorIA) as error:
        pedir("sistema", "usuario")
    assert "no se puede usar el modelo" in str(error.value)


def test_un_error_momentaneo_se_reintenta(monkeypatch, configuracion_ia) -> None:
    """Un 503 del servidor no puede acabar el intento: se reintenta."""
    import urllib.error

    import urllib.request

    intentos = []

    def falso(peticion, timeout=None, context=None):
        intentos.append(1)
        if len(intentos) < 3:
            raise urllib.error.HTTPError("url", 503, "saturado", {}, io.BytesIO(b""))
        return RespuestaFalsa({"choices": [{"message": {"content": "Ya funciona"}}]})

    monkeypatch.setattr(urllib.request, "urlopen", falso)

    assert pedir("sistema", "usuario") == "Ya funciona"
    assert len(intentos) == 3, "dos reintentos antes de que funcione"


def test_un_error_que_no_se_reintenta_falla_seguito(monkeypatch, configuracion_ia) -> None:
    """Un 401 no se reintenta: la clave está mal y hay que decirlo."""
    import urllib.error

    import urllib.request

    intentos = []

    def falso(peticion, timeout=None, context=None):
        intentos.append(1)
        raise urllib.error.HTTPError("url", 401, "no autorizado", {}, io.BytesIO(b""))

    monkeypatch.setattr(urllib.request, "urlopen", falso)

    with pytest.raises(ErrorIA) as error:
        pedir("sistema", "usuario")
    assert "401" in str(error.value)
    assert len(intentos) == 1
