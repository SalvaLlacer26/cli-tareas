"""Configuración de pytest.

Las pruebas **no** pueden llamar a la red: sería gastar tiempo y créditos, y
haría que la suite fallara en un equipo sin conexión. Aquí se anulan las
variables de la IA y se aparta la configuración del usuario, de modo que la
capa de IA se queda siempre en «no disponible» y las pruebas ejercitan el
camino sin IA.

Para probar la capa de IA de verdad hay pruebas marcadas con «@pytest.mark.ia»,
que solo se ejecutan si se piden expresamente:

    uv run pytest -m ia
"""

from __future__ import annotations

import os

import pytest

VARIABLES_IA = (
    "TAREAS_IA_URL",
    "TAREAS_IA_KEY",
    "TAREAS_MODELO",
    "TAREAS_IA_CA",
    "TAREAS_IA_TIMEOUT",
)


@pytest.fixture(autouse=True)
def _sin_red_real(monkeypatch, tmp_path):
    """Deja la IA desactivada en TODAS las pruebas.

    Es automático: así nadie puede añadirse por error una prueba que se
    conecte al servidor de modelos y tarde dos minutos.
    """
    for variable in VARIABLES_IA:
        monkeypatch.delenv(variable, raising=False)

    import tareas.ia as ia

    # La configuración del usuario se aparta: si alguien tiene un .env con
    # una clave real, las pruebas no la ven.
    monkeypatch.setattr(ia, "ruta_de_usuario", lambda: tmp_path / "sin-config")

    # Y se trabaja en una carpeta limpia, sin un .env al lado.
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def configuracion_ia(monkeypatch):
    """Deja la IA «disponible» sin salir a la red: el modelo se simula."""
    import tareas.ia as ia

    monkeypatch.setattr(
        ia,
        "configuracion",
        lambda: ia.ConfiguracionIA(
            url="https://servidor.interno/v1",
            clave="clave-de-prueba",
            modelo="modelo-de-prueba",
        ),
    )
    return ia
