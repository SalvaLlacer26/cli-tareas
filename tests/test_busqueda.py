"""Pruebas de la búsqueda en internet y de la agrupación de documentos."""

from __future__ import annotations

from pathlib import Path

import pytest

from tareas.agrupador import (
    CARPETA_POR_CLASIFICAR,
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


def test_la_web_entra_como_fuente_aunque_la_wikipedia_no_de_nada(monkeypatch) -> None:
    """Si la enciclopedia falla, la búsqueda sigue dando fuentes de la web."""
    import tareas.busqueda as busqueda

    web = Fuente(
        titulo="Documentación de la RAM",
        url="https://docs.example.org/ram",
        fragmento="La RAM es una memoria volátil de acceso aleatorio...",
        origen="web",
    )
    monkeypatch.setattr(busqueda, "_wikipedia", lambda idioma, consulta, limite: [])
    monkeypatch.setattr(busqueda, "_duckduckgo", lambda consulta: [])
    monkeypatch.setattr(busqueda, "_duckduckgo_web", lambda consulta, limite: [web])

    assert buscar("memoria ram") == [web]


def test_la_busqueda_mantiene_al_menos_una_fuente_web(monkeypatch) -> None:
    """Aunque Wikipedia llene el hueco, se reserva sitio para una fuente web."""
    import tareas.busqueda as busqueda

    wiki = [
        Fuente(f"W{i}", f"https://es.wikipedia.org/wiki/W{i}", "x" * 300, "wikipedia-es")
        for i in range(4)
    ]
    web = Fuente("Web", "https://ejemplo.org/guia", "y" * 300, "web")
    monkeypatch.setattr(busqueda, "_wikipedia", lambda idioma, consulta, limite: list(wiki))
    monkeypatch.setattr(busqueda, "_duckduckgo", lambda consulta: [])
    monkeypatch.setattr(busqueda, "_duckduckgo_web", lambda consulta, limite: [web])

    resultado = buscar("memoria", limite=3)
    assert any(f.origen == "web" for f in resultado)


def test_la_web_extrae_titulo_url_y_fragmento(monkeypatch) -> None:
    """Se leen los resultados de DuckDuckGo lite, decodificando su redirección.

    Incluye un resultado patrocinado (publicidad) que debe quedar fuera.
    """
    import tareas.busqueda as busqueda

    pagina = """
      <table>
        <tr class="result-sponsored"><td><a rel="nofollow"
          href="//duckduckgo.com/l/?uddg=https%3A%2F%2Ftienda.example%2Fram&amp;rut=zz"
          class='result-link'>Módulos de RAM baratos - Tienda</a> (Sponsored link -
          <a href="https://duckduckgo.com/help" rel="nofollow" class="result-link">more info</a>)
        </td></tr>
        <tr><td class='result-snippet'>Compra RAM barato aquí, ofertas.</td></tr>
        <tr><td><a rel="nofollow"
          href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.xataka.com%2Fbasics%2Fmemoria-ram&amp;rut=aa"
          class='result-link'>Memoria RAM: qué es y para qué sirve - Xataka</a></td></tr>
        <tr><td class='result-snippet'>Te explicamos qué es la <b>memoria RAM</b>, para
          qué sirve en tu ordenador y cómo saber cuánta tienes instalada.</td></tr>
        <tr><td><a rel="nofollow"
          href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fconcepto.de%2Fmemoria-ram%2F&amp;rut=bb"
          class='result-link'>Memoria RAM - concepto.de</a></td></tr>
        <tr><td class='result-snippet'>La memoria RAM es la memoria principal de un
          ordenador: es volátil y permite el acceso aleatorio a los datos guardados.</td></tr>
      </table>
    """
    monkeypatch.setattr(busqueda, "_pedir_texto", lambda url: pagina)

    fuentes = busqueda._duckduckgo_web("memoria ram", limite=5)
    # El patrocinado (tienda.example) y el enlace de ayuda no entran.
    assert [f.url for f in fuentes] == [
        "https://www.xataka.com/basics/memoria-ram",
        "https://concepto.de/memoria-ram/",
    ]
    assert fuentes[0].titulo == "Memoria RAM: qué es y para qué sirve - Xataka"
    assert fuentes[0].origen == "web"
    assert "memoria RAM" in fuentes[0].fragmento


def test_la_web_sin_pagina_no_rompe(monkeypatch) -> None:
    """Si el buscador no responde o cambia, la búsqueda web no revienta."""
    import tareas.busqueda as busqueda

    monkeypatch.setattr(busqueda, "_pedir_texto", lambda url: None)
    assert busqueda._duckduckgo_web("cualquier cosa", limite=5) == []


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
    assert _nombre_de_carpeta("  ") == CARPETA_POR_CLASIFICAR


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
    assert plan.grupos[0].nombre == CARPETA_POR_CLASIFICAR
    assert sorted(plan.grupos[0].documentos) == ["dos.txt", "uno.txt"]


def test_planear_sin_fichas_avisa(tmp_path: Path) -> None:
    from tareas.errores import TareasError

    with pytest.raises(TareasError) as error:
        planear(tmp_path, usar_ia=False)
    assert "analizar" in str(error.value)


def test_los_formatos_ilegibles_no_se_descartan(tmp_path: Path) -> None:
    """Un .deb (sin texto) entra en el juego y va a «Por clasificar», no se pierde."""
    from tareas import ficha as fichas

    (tmp_path / "md").mkdir()
    for nombre, estado in (("apuntes.txt", fichas.CLASIFICADO), ("programa.deb", fichas.FORMATO_INVALIDO)):
        ficha = fichas.Ficha(
            nombre_original=nombre,
            nombre_compatible=nombre,
            estado=estado,
            formato=".txt" if estado == fichas.CLASIFICADO else ".deb",
            contenido="unas notas" if estado == fichas.CLASIFICADO else "",
        )
        fichas.escribir(ficha, tmp_path / "md" / f"{nombre}.md")

    plan = planear(tmp_path, usar_ia=False)

    por_clasificar = next(g for g in plan.grupos if g.nombre == CARPETA_POR_CLASIFICAR)
    assert "programa.deb" in por_clasificar.documentos
    assert "apuntes.txt" in por_clasificar.documentos


def _con_fichas(tmp_path: Path, nombres: list[str]) -> None:
    from tareas import ficha as fichas

    (tmp_path / "md").mkdir()
    for nombre in nombres:
        fichas.escribir(
            fichas.Ficha(
                nombre_original=nombre,
                nombre_compatible=nombre,
                estado=fichas.CLASIFICADO,
                formato=".txt",
                contenido="un poco de texto para que sea analizable",
            ),
            tmp_path / "md" / f"{nombre}.md",
        )


def test_lo_que_el_modelo_deja_fuera_se_le_vuelve_a_pedir(tmp_path: Path, monkeypatch) -> None:
    """Segunda pasada: lo no colocado en la primera se reintenta con las carpetas ya creadas."""
    from tareas import agrupador as g

    _con_fichas(tmp_path, ["a.txt", "b.txt"])
    llamadas: list[list[str]] = []

    def falsa_agrupacion(documentos, carpetas_conocidas=None):
        nombres = [n for n, _ in documentos]
        llamadas.append(nombres)
        if carpetas_conocidas is None:
            # Primera pasada: el modelo solo coloca «a.txt».
            return [g.Grupo("Uno", ["a.txt"])], []
        # Segunda pasada: coloca lo que quedaba, reutilizando una carpeta.
        return [g.Grupo("Uno", nombres)], []

    monkeypatch.setattr(g, "pedir_agrupacion", falsa_agrupacion)

    plan = g.planear(tmp_path)

    assert len(llamadas) == 2  # hubo una segunda pasada
    assert len(plan.grupos) == 1
    assert sorted(plan.grupos[0].documentos) == ["a.txt", "b.txt"]
    assert not any(grupo.nombre == CARPETA_POR_CLASIFICAR for grupo in plan.grupos)


def test_lo_que_ni_a_la_segunda_va_a_por_clasificar(tmp_path: Path, monkeypatch) -> None:
    """Ningún documento se queda sin carpeta: el sobrante acaba en «Por clasificar»."""
    from tareas import agrupador as g

    _con_fichas(tmp_path, ["a.txt", "fantasma.jpg"])

    def solo_uno(documentos, carpetas_conocidas=None):
        return [g.Grupo("Apuntes", ["a.txt"])], []

    monkeypatch.setattr(g, "pedir_agrupacion", solo_uno)

    plan = g.planear(tmp_path)

    por_clasificar = next(gr for gr in plan.grupos if gr.nombre == CARPETA_POR_CLASIFICAR)
    assert por_clasificar.documentos == ["fantasma.jpg"]


def test_sin_colocar_reconoce_nombres_parecidos() -> None:
    """El modelo puede devolver el nombre sin acento o con guiones: igual cuenta."""
    from tareas import agrupador as g

    documentos = [("Introducció.pdf", "x"), ("Tema 2.docx", "y")]
    grupos = [g.Grupo("Carpeta", ["Introduccio.pdf", "tema-2.docx"])]
    assert g._sin_colocar(documentos, grupos) == []

    # Y lo que de verdad no está, sí se detecta.
    grupos_mal = [g.Grupo("Carpeta", ["Introduccio.pdf"])]
    assert [n for n, _ in g._sin_colocar(documentos, grupos_mal)] == ["Tema 2.docx"]


def test_deshacer_devuelve_lo_que_movo_clasificar(tmp_path: Path) -> None:
    """«deshacer» también revierte los movimientos de «clasificar»."""
    from tareas import agrupador as g
    from tareas import ficha as fichas
    from tareas.organizador import deshacer

    origen = tmp_path / "bajadas"
    destino = tmp_path / "ordenado"
    origen.mkdir()
    (origen / "apuntes.txt").write_text("contenido del documento", encoding="utf-8")
    ficha = fichas.Ficha(
        nombre_original="apuntes.txt",
        nombre_compatible="apuntes.txt",
        estado=fichas.CLASIFICADO,
        formato=".txt",
        origen=str(origen),
    )
    fichas.escribir(ficha, origen / "md" / "apuntes.txt.md")

    plan = g.Plan(
        grupos=[g.Grupo("Apuntes", ["apuntes.txt"])],
        fichas={"apuntes.txt": ficha},
    )
    movidos, errores = g.aplicar(origen, destino, plan)
    assert movidos and not errores
    assert (destino / "Apuntes" / "apuntes.txt").is_file()
    assert not (origen / "apuntes.txt").exists()

    resultado = deshacer(destino)

    assert resultado.total == 1
    assert (origen / "apuntes.txt").is_file()
    assert not (destino / "Apuntes" / "apuntes.txt").exists()
