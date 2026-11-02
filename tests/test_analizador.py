"""Pruebas del analizador: renombrar, extraer, clasificar y escribir fichas."""

from __future__ import annotations

from pathlib import Path

import pytest

from tareas.analizador import CARPETA_FICHAS, analizar
from tareas.clasificador import Carpeta, cargar_carpetas, clasificar
from tareas.contenido import extraer
from tareas.ficha import CLASIFICADO, FORMATO_INVALIDO, SIN_CLASIFICAR, leer
from tareas.nombres import compatible, es_compatible

CARPETAS = [
    {
        "clave": "bbdd",
        "etiqueta": "Bases de dades",
        "destino": "CARPETAS/bbdd",
        "patrones": ["sql", "bases de dades", "entitats"],
    },
    {
        "clave": "entorns",
        "etiqueta": "Entorns de desenrotllament",
        "destino": "CARPETAS/entorns",
        "patrones": ["git", "github"],
    },
    {
        "clave": "sistemes",
        "etiqueta": "Sistemes informàtics",
        "destino": "CARPETAS/sistemes",
        "patrones": ["sistemes informàtics", "numeració"],
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
    return tmp_path


def montar_carpetas(base: Path):
    datos = {"carpetas": [{**c, "destino": str(base / c["clave"])} for c in CARPETAS]}
    return cargar_carpetas(datos)


# ---------------------------------------------------------------- nombres


def test_un_nombre_sin_acentos_ni_espacios_es_compatible() -> None:
    assert es_compatible("factura-octubre.pdf")
    assert es_compatible("nota_2026.pdf")


def test_un_nombre_con_acentos_no_es_compatible() -> None:
    assert not es_compatible("Pràctica 1. Entitats.pdf")


def test_normalizar_quita_acentos_y_espacios() -> None:
    assert compatible("Pràctica 1. Entitats.pdf") == "Practica-1-Entitats.pdf"


def test_normalizar_no_toca_los_puntos_de_la_extension() -> None:
    assert compatible("nota.pdf") == "nota.pdf"


def test_normalizar_acepta_los_nombres_largos() -> None:
    assert len(compatible("a" * 200 + ".pdf")) < 100


def test_normalizar_no_deja_nombres_vacios() -> None:
    assert compatible("¿¿¿.pdf").strip("-") != ""


# ------------------------------------------------------------- contenido


def test_un_txt_se_lee(base: Path) -> None:
    fichero = base / "nota.txt"
    fichero.write_text("Hola, esto es un texto.", encoding="utf-8")
    contenido = extraer(fichero)
    assert contenido.analizable
    assert "Hola" in contenido.texto


def test_un_formato_raro_no_se_puede_analizar(base: Path) -> None:
    fichero = base / "programa.deb"
    fichero.write_bytes(b"contenido raro")
    contenido = extraer(fichero)
    assert not contenido.analizable
    assert "no se puede analizar" in contenido.motivo


def test_una_imagen_no_se_puede_analizar(base: Path) -> None:
    fichero = base / "foto.png"
    fichero.write_bytes(b"\x89PNG")
    assert not extraer(fichero).analizable


# ---------------------------------------------------------- clasificación


def test_el_nombre_manda_sobre_el_contenido(base: Path) -> None:
    """Si el nombre dice «git», va a entorns aunque dentro hable de SQL."""
    carpetas = montar_carpetas(base)
    diagnostico = clasificar(carpetas, "A21_Git_GitHub.pdf", "Unas tablas SQL")
    assert diagnostico.carpeta.clave == "entorns"


def test_el_contenido_rescata_un_nombre_que_no_dice_nada(base: Path) -> None:
    carpetas = montar_carpetas(base)
    diagnostico = clasificar(carpetas, "Salva_Llacer.pdf", "SISTEMES INFORMÀTICS")
    assert diagnostico.carpeta.clave == "sistemes"


def test_un_termino_de_una_palabra_no_basta_para_clasificar(base: Path) -> None:
    """«ide» dentro de una frase no convierte el documento en Entornos."""
    carpetas = montar_carpetas(base)
    diagnostico = clasificar(carpetas, "manual.pdf", "El conector IDE de la placa")
    assert diagnostico.estado == SIN_CLASIFICAR
    assert diagnostico.carpeta.clave == "sin-clasificar"


def test_una_frase_pondera_mas_que_una_palabra(base: Path) -> None:
    """«projecte intermodular» tiene que ganar a un «github» suelto."""
    carpetas = montar_carpetas(base)
    carpetas[1].patrones = ["git", "github"]
    carpetas.append(
        Carpeta(
            clave="intermodular",
            etiqueta="Projecte intermodular",
            destino=base / "intermodular",
            patrones=["intermodular", "projecte intermodular", "1daw"],
        )
    )

    diagnostico = clasificar(
        carpetas, "Activitat_PRI_01.pdf", "Projecte Intermodular 1DAW. Activitat 01: Github Fork"
    )
    assert diagnostico.carpeta.clave == "intermodular"


# --------------------------------------------------------------- analizar


def test_analizar_renombra_los_nombres_incompatibles(base: Path) -> None:
    carpeta = base / "Descargas"
    carpeta.mkdir()
    (carpeta / "Pràctica 1. Entitats.pdf").write_text("contenido", encoding="utf-8")

    resultado = analizar(carpeta, montar_carpetas(base))

    assert len(resultado.renombrados) == 1
    assert (carpeta / "Practica-1-Entitats.pdf").exists()
    assert not (carpeta / "Pràctica 1. Entitats.pdf").exists()


def test_analizar_no_toca_los_nombres_compatibles(base: Path) -> None:
    carpeta = base / "Descargas"
    carpeta.mkdir()
    (carpeta / "factura.pdf").write_text("contenido", encoding="utf-8")

    resultado = analizar(carpeta, montar_carpetas(base))

    assert resultado.renombrados == []
    assert (carpeta / "factura.pdf").exists()


def test_analizar_escribe_una_ficha_por_documento(base: Path) -> None:
    carpeta = base / "Descargas"
    carpeta.mkdir()
    (carpeta / "nota.txt").write_text(
        "El tema es SQL i les bases de dades", encoding="utf-8"
    )

    analizar(carpeta, montar_carpetas(base))

    # La ficha lleva la extensión del documento para no chocar con otra
    ficha = base / "Descargas" / CARPETA_FICHAS / "nota.txt.md"
    assert ficha.exists()
    datos = leer(ficha)
    assert datos.nombre_original == "nota.txt"
    assert datos.asignatura == "Bases de dades"
    assert datos.estado == CLASIFICADO
    assert "SQL" in datos.contenido


def test_analizar_marca_los_formatos_invalidos(base: Path) -> None:
    carpeta = base / "Descargas"
    carpeta.mkdir()
    (carpeta / "programa.deb").write_bytes(b"raro")

    resultado = analizar(carpeta, montar_carpetas(base))

    assert resultado.invalidos == 1
    assert resultado.filas[0].estado == FORMATO_INVALIDO
    assert resultado.filas[0].asignatura == "formato invalido"


def test_analizar_avisa_de_los_sin_clasificar(base: Path) -> None:
    carpeta = base / "Descargas"
    carpeta.mkdir()
    (carpeta / "misterio.txt").write_text("texto sin ninguna pista", encoding="utf-8")

    resultado = analizar(carpeta, montar_carpetas(base))

    assert resultado.sin_clasificar == 1
    assert resultado.filas[0].estado == SIN_CLASIFICAR


def test_analizar_no_toca_las_subcarpetas(base: Path) -> None:
    carpeta = base / "Descargas"
    (carpeta / "sub").mkdir(parents=True)
    (carpeta / "sub" / "nota.txt").write_text("x", encoding="utf-8")

    resultado = analizar(carpeta, montar_carpetas(base))

    assert resultado.filas == []
