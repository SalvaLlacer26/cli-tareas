"""Pruebas del organizador: clasificar, renombrar y devolver.

La prueba más importante es la última: organizar y desorganizar tienen que
devolver los ficheros exactamente como estaban.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tareas.carpetas import Carpeta, cargar_carpetas, clasificar
from tareas.manifiesto import Manifiesto
from tareas.organizador import Desorganizador, Organizador

CARPETAS_DIC = [
    {
        "clave": "bbdd",
        "etiqueta": "Bases de dades",
        "destino": "CARPETAS/bbdd",
        "patrones": ["sql", "entitats", "atributs"],
    },
    {
        "clave": "entorns",
        "etiqueta": "Entorns de desenrotllament",
        "destino": "CARPETAS/entorns",
        "patrones": ["github", "git"],
    },
    {
        "clave": "sistemes",
        "etiqueta": "Sistemes informàtics",
        "destino": "CARPETAS/sistemes",
        "patrones": ["linux", "numeració"],
    },
    {
        "clave": "sin-clasificar",
        "etiqueta": "Sin clasificar",
        "destino": "CARPETAS/respaldo",
        "patrones": [],
        "respaldo": True,
    },
]


@pytest.fixture
def base(tmp_path: Path) -> Path:
    """Carpeta base de cada prueba: todo lo que se crea vive aquí dentro."""
    return tmp_path


def montar_carpetas(base: Path) -> list[Carpeta]:
    """Construye las carpetas de prueba: cada una en una carpeta con su clave."""
    datos = {
        "carpetas": [
            {**c, "destino": str(base / c["clave"])} for c in CARPETAS_DIC
        ]
    }
    return cargar_carpetas(datos)


def manifiesto_de_prueba(base: Path) -> Manifiesto:
    return Manifiesto(base / "manifiesto.json")


# ------------------------------------------------------------------ nombres


def test_normalizar_quita_acentos_espacios_y_puntos() -> None:
    from tareas.nombres import normalizar

    assert normalizar("Pràctica 1. Entitats, atributs i valors.pdf", "bbdd") == (
        "bbdd_practica-1-entitats-atributs-i-valors.pdf"
    )


def test_normalizar_no_duplica_la_clave() -> None:
    from tareas.nombres import normalizar

    assert normalizar("bbdd_practica.pdf", "bbdd") == "bbdd_practica.pdf"


def test_normalizar_es_idempotente() -> None:
    """Normalizar dos veces no cambia el nombre."""
    from tareas.nombres import normalizar

    una = normalizar("P1.2. Activitats.pdf", "bbdd")
    dos = normalizar(una, "bbdd")
    assert una == dos


# ------------------------------------------------------------ clasificación


def test_la_clasificacion_gana_la_carpeta_con_mas_patrones(base: Path) -> None:
    """«Projecte intermodular» + «github»: gana intermodular, no entorns."""
    carpetas = [
        Carpeta("entorns", "Entorns", base / "e", ["github", "git"]),
        Carpeta("intermodular", "Intermodular", base / "i", ["projecte", "intermodular"]),
    ]
    elegida = clasificar(carpetas, "Activitat_PRI_01", "Projecte Intermodular 1DAW. Github Fork")
    assert elegida.clave == "intermodular"


def test_si_el_nombre_no_dice_nada_se_mira_el_resumen(base: Path) -> None:
    carpetas = montar_carpetas(base)
    elegida = clasificar(carpetas, "Salva_Llacer.pdf", "SISTEMES INFORMÀTICS. Pràctica de numeració")
    assert elegida.clave == "sistemes"


def test_si_no_se_sabe_nada_va_a_la_carpeta_de_respaldo(base: Path) -> None:
    carpetas = montar_carpetas(base)
    elegida = clasificar(carpetas, "fichero_desconocido.pdf", None)
    assert elegida.clave == "sin-clasificar"
    assert elegida.respaldo is True


def test_el_nombre_manda_sobre_el_resumen(base: Path) -> None:
    """Si el nombre dice «git», va a entorns aunque el resumen hable de SQL."""
    carpetas = montar_carpetas(base)
    elegida = clasificar(carpetas, "A21_Git_GitHub.pdf", "Unas tablas SQL y un SELECT")
    assert elegida.clave == "entorns" if any(c.clave == "entorns" for c in carpetas) else True


# --------------------------------------------------------------- organizar


def test_organizar_mueve_el_fichero_a_su_carpeta(base: Path) -> None:
    descargas = base / "Descargas"
    descargas.mkdir(parents=True)
    (descargas / "Pràctica sql.pdf").write_text("x", encoding="utf-8")

    carpetas = montar_carpetas(base)
    resultados = Organizador(carpetas, manifiesto_de_prueba(base)).organizar(descargas, simular=False)

    assert len(resultados) == 1
    assert resultados[0].estado == "hecho"
    assert (base / "bbdd" / "bbdd_practica-sql.pdf").exists()
    assert not (descargas / "Pràctica sql.pdf").exists()


def test_organizar_renombra_a_un_nombre_interpretable(base: Path) -> None:
    """Un nombre con espacios y acentos se convierte en algo legible."""
    descargas = base / "Descargas"
    descargas.mkdir(parents=True)
    (descargas / "Pràctica 1. Entitats.pdf").write_text("x", encoding="utf-8")

    carpetas = montar_carpetas(base)
    Organizador(carpetas, manifiesto_de_prueba(base)).organizar(descargas, simular=False)

    destino = next(
        p
        for c in carpetas
        if c.clave != "sin-clasificar"
        for p in (base / c.clave).rglob("*.pdf")
    )
    assert destino.name == "bbdd_practica-1-entitats.pdf"


def test_un_nombre_que_no_dice_nada_tambien_acaba_interpretable(base: Path) -> None:
    """Si no se sabe de qué asignatura es, el nombre dice al menos eso."""
    descargas = base / "Descargas"
    descargas.mkdir(parents=True)
    (descargas / "P1.2. Activitats.pdf").write_text("x", encoding="utf-8")

    carpetas = montar_carpetas(base)
    Organizador(carpetas, manifiesto_de_prueba(base)).organizar(descargas, simular=False)

    destino = next(
        p
        for c in carpetas
        if c.clave == "sin-clasificar"
        for p in (base / c.clave).rglob("*.pdf")
    )
    assert destino.name == "sin-clasificar_p1-2-activitats.pdf"


def test_organizar_mueve_el_resumen_al_lado_de_su_documento(base: Path) -> None:
    descargas = base / "Descargas"
    descargas.mkdir(parents=True)
    (descargas / "nota.pdf").write_text("x", encoding="utf-8")
    (descargas / "nota.md").write_text("SISTEMES INFORMÀTICS", encoding="utf-8")

    carpetas = montar_carpetas(base)
    Organizador(carpetas, manifiesto_de_prueba(base)).organizar(descargas, simular=False)

    assert (base / "sistemes" / "sistemes_nota.pdf").exists()
    assert (base / "sistemes" / "sistemes_nota.md").exists()
    assert not (descargas / "nota.md").exists(), "el resumen no se organiza por su cuenta"


def test_organizar_en_simulacion_no_toca_el_disco(base: Path) -> None:
    descargas = base / "Descargas"
    descargas.mkdir(parents=True)
    (descargas / "nota.pdf").write_text("x", encoding="utf-8")

    carpetas = montar_carpetas(base)
    resultados = Organizador(carpetas, manifiesto_de_prueba(base)).organizar(descargas, simular=True)

    assert resultados[0].estado == "simulado"
    assert (descargas / "nota.pdf").exists()
    assert not (base / "bbdd").exists()


# ------------------------------------------------------------ desorganizar


def test_el_viaje_de_ida_y_vuelta_deja_los_ficheros_como_estaban(base: Path) -> None:
    """La prueba que más importa: organizar y desorganizar no pierden nada."""
    descargas = base / "Descargas"
    descargas.mkdir(parents=True)
    originales = ["Pràctica 1. Entitats.pdf", "A21_Git_GitHub.pdf", "Salva_Llacer.pdf"]
    for nombre in originales:
        (descargas / nombre).write_text("x", encoding="utf-8")

    carpetas = montar_carpetas(base)
    manifiesto = manifiesto_de_prueba(base)

    Organizador(carpetas, manifiesto).organizar(descargas, simular=False)
    Desorganizador(carpetas, manifiesto).desorganizar(descargas, simular=False)

    assert sorted(p.name for p in descargas.iterdir()) == sorted(originales)


def test_desorganizar_devuelve_los_ficheros_a_la_carpeta_de_descargas(base: Path) -> None:
    descargas = base / "Descargas"
    descargas.mkdir(parents=True)
    (descargas / "nota sql.pdf").write_text("x", encoding="utf-8")

    carpetas = montar_carpetas(base)
    manifiesto = manifiesto_de_prueba(base)

    Organizador(carpetas, manifiesto).organizar(descargas, simular=False)
    Desorganizador(carpetas, manifiesto).desorganizar(descargas, simular=False)

    assert (descargas / "nota sql.pdf").exists()
    assert not (base / "bbdd" / "bbdd_nota-sql.pdf").exists()


def test_sin_manifiesto_los_ficheros_vuelven_con_el_nombre_normalizado(base: Path) -> None:
    """Si el manifiesto se ha perdido, el fichero vuelve igual, pero renombrado."""
    descargas = base / "Descargas"
    descargas.mkdir(parents=True)
    (descargas / "nota sql.pdf").write_text("x", encoding="utf-8")

    carpetas = montar_carpetas(base)
    Organizador(carpetas, manifiesto_de_prueba(base)).organizar(descargas, simular=False)

    otro = Manifiesto(base / "otro.json")
    Desorganizador(carpetas, otro).desorganizar(descargas, simular=False)

    assert (descargas / "bbdd_nota-sql.pdf").exists()


# --------------------------------------------------------------- manifiesto


def test_el_manifiesto_guarda_y_devuelve_el_nombre_original(base: Path) -> None:
    manifiesto = Manifiesto(base / "manifiesto.json")
    destino = base / "bbdd" / "bbdd_nota.pdf"
    manifiesto.registrar(destino, "Nota Original.pdf")
    manifiesto.guardar()

    assert Manifiesto(base / "manifiesto.json").nombre_original(destino) == "Nota Original.pdf"


def test_un_manifiesto_ilegible_no_rompe_nada(base: Path) -> None:
    ruta = base / "manifiesto.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("{ roto", encoding="utf-8")

    manifiesto = Manifiesto(ruta)
    manifiesto.cargar()
    assert manifiesto.entradas == {}


def test_el_manifiesto_usa_utf8(base: Path) -> None:
    manifiesto = Manifiesto(base / "manifiesto.json")
    destino = base / "bbdd" / "bbdd_nota.pdf"
    manifiesto.registrar(destino, "Pràctica de Ñandú.pdf")
    manifiesto.guardar()

    assert "Ñandú" in (base / "manifiesto.json").read_text(encoding="utf-8")
