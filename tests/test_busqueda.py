"""Pruebas de la búsqueda en internet y de la agrupación de documentos."""

from __future__ import annotations

from pathlib import Path

import pytest

from tareas.agrupador import (
    CARPETA_SIN_CLASIFICAR,
    Grupo,
    _nombre_de_carpeta,
    leer_agrupacion,
    planear,
)
from tareas.busqueda import Fuente, buscar, como_texto


# ------------------------------------------------------------- búsqueda


def test_una_consulta_vacia_no_busca() -> None:
    assert buscar("") == []
    assert buscar("   ") == []


def test_buscar_devuelve_fuentes_con_titulo_url_y_texto(monkeypatch) -> None:
    """La búsqueda se simula: las pruebas no salen a internet."""
    import tareas.busqueda as busqueda

    fuente = Fuente(
        titulo="Base de datos",
        url="https://es.wikipedia.org/wiki/Base_de_datos",
        fragmento="Una base de datos es…",
        origen="wikipedia-es",
    )
    monkeypatch.setattr(busqueda, "_wikipedia", lambda idioma, consulta, limite: [fuente])
    monkeypatch.setattr(busqueda, "_duckduckgo", lambda consulta: [])

    assert buscar("bases de datos") == [fuente]


def test_buscar_no_devuelve_la_misma_fuente_dos_veces(monkeypatch) -> None:
    import tareas.busqueda as busqueda

    fuente = Fuente("T", "https://x", "texto largo")
    monkeypatch.setattr(busqueda, "_wikipedia", lambda idioma, consulta, limite: [fuente])
    monkeypatch.setattr(busqueda, "_duckduckgo", lambda consulta: [fuente])

    assert len(buscar("algo")) == 1


def test_sin_red_la_busqueda_devuelve_una_lista_vacia(monkeypatch) -> None:
    """Si no hay red, no se rompe: simplemente no hay resultados."""
    import urllib.request

    import tareas.busqueda as busqueda

    def falla(*args, **kwargs):
        raise urllib.error.URLError("sin red")

    monkeypatch.setattr(urllib.request, "urlopen", falla)
    assert buscar("bases de datos") == []


def test_las_fuentes_se_pasan_al_modelo_en_texto() -> None:
    fuentes = [
        Fuente("Título", "https://x/1", "Fragmento uno"),
        Fuente("Otro", "https://x/2", "Fragmento dos"),
    ]
    texto = como_texto(fuentes)
    assert "[1] Título" in texto
    assert "https://x/1" in texto
    assert "Fragmento dos" in texto


def test_sin_fuentes_el_texto_vacio() -> None:
    assert como_texto([]) == ""


# ------------------------------------------------------------ agrupación


def test_se_lee_una_respuesta_con_tres_carpetas() -> None:
    respuesta = (
        "[Recetas]\n"
        "- bizcocho.txt\n"
        "- tortilla.txt\n\n"
        "[Historia]\n"
        "- roma.txt\n\n"
        "[Hardware]\n"
        "- placa.txt\n"
    )
    grupos = leer_agrupacion(respuesta)

    assert [g.nombre for g in grupos] == ["Recetas", "Historia", "Hardware"]
    assert grupos[0].documentos == ["bizcocho.txt", "tortilla.txt"]


def test_una_carpeta_sin_documentos_no_se_acepta() -> None:
    grupos = leer_agrupacion("[Vacía]\n\n[Con algo]\n- algo.txt\n")
    assert [g.nombre for g in grupos] == ["Con algo"]


def test_los_nombres_de_carpeta_se_limpian() -> None:
    """Un nombre con caracteres que Windows no admite se limpia."""
    assert "/" not in _nombre_de_carpeta("Recetas/Cocina")
    assert _nombre_de_carpeta("  ") == CARPETA_SIN_CLASIFICAR


def test_el_plan_sin_ia_mete_todo_en_una_carpeta(tmp_path: Path) -> None:
    """Sin modelo, el plan de reserva es una sola carpeta."""
    from tareas import ficha as fichas

    (tmp_path / "md").mkdir()
    for nombre in ("uno.txt", "dos.txt"):
        ficha = fichas.Ficha(
            nombre_original=nombre,
            nombre_compatible=nombre,
            estado=fichas.CLASIFICADO,
            contenido="algo",
        )
        fichas.escribir(ficha, tmp_path / "md" / f"{nombre}.md")

    plan = planear(tmp_path, usar_ia=False)

    assert len(plan.grupos) == 1
    assert plan.grupos[0].nombre == CARPETA_SIN_CLASIFICAR
    assert sorted(plan.grupos[0].documentos) == ["dos.txt", "uno.txt"]


def test_planear_sin_fichas_avisa(tmp_path: Path) -> None:
    from tareas.errores import TareasError

    with pytest.raises(TareasError) as error:
        planear(tmp_path, usar_ia=False)
    assert "analizar" in str(error.value)


def test_planear_sin_documentos_analizables_avisa(tmp_path: Path) -> None:
    from tareas import ficha as fichas
    from tareas.errores import TareasError

    (tmp_path / "md").mkdir()
    ficha = fichas.Ficha(
        nombre_original="programa.deb",
        nombre_compatible="programa.deb",
        estado=fichas.FORMATO_INVALIDO,
    )
    fichas.escribir(ficha, tmp_path / "md" / "programa.deb.md")

    with pytest.raises(TareasError) as error:
        planear(tmp_path, usar_ia=False)
    assert "analizable" in str(error.value)
