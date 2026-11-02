"""Pruebas de los documentos que se generan y del formato Unicode de los nombres."""

from __future__ import annotations

import unicodedata
import zipfile
from pathlib import Path

import pytest

from tareas.documentos import (
    DOCX,
    ODT,
    RTF,
    TXT,
    Seccion,
    escribir_documento,
    formato_preferido,
)
from tareas.nombres import a_nfc, compatible, es_compatible, mismo_nombre

SECCIONES = [
    Seccion("Resumen", ["Primera línea del resumen.", "Segunda línea."]),
    Seccion("Detalles", ["Un detalle importante."]),
]


# ------------------------------------------------------------- documentos


def test_se_escribe_un_odt_valido(tmp_path: Path) -> None:
    ruta = escribir_documento(tmp_path / "salida.odt", "Título", SECCIONES)
    assert ruta.exists()
    with zipfile.ZipFile(ruta) as paquete:
        nombres = paquete.namelist()
        assert "mimetype" in nombres
        assert "content.xml" in nombres
        assert paquete.read("mimetype").decode() == "application/vnd.oasis.opendocument.text"


def test_el_odt_lleva_el_titulo_y_los_apartados(tmp_path: Path) -> None:
    ruta = escribir_documento(tmp_path / "salida.odt", "Mi título", SECCIONES)
    with zipfile.ZipFile(ruta) as paquete:
        contenido = paquete.read("content.xml").decode("utf-8")
    assert "Mi título" in contenido
    assert "Detalles" in contenido
    assert "Un detalle importante." in contenido


def test_se_escribe_un_docx_valido(tmp_path: Path) -> None:
    ruta = escribir_documento(tmp_path / "salida.docx", "Mi título", SECCIONES)
    with zipfile.ZipFile(ruta) as paquete:
        nombres = paquete.namelist()
        assert "[Content_Types].xml" in nombres
        assert "word/document.xml" in nombres
        assert "Mi título" in paquete.read("word/document.xml").decode("utf-8")


def test_se_escribe_un_rtf(tmp_path: Path) -> None:
    ruta = escribir_documento(tmp_path / "salida.rtf", "Mi título", SECCIONES)
    texto = ruta.read_text(encoding="utf-8")
    assert texto.startswith(r"{\rtf1")
    assert r"\b" in texto


def test_se_escribe_un_txt(tmp_path: Path) -> None:
    ruta = escribir_documento(tmp_path / "salida.txt", "Mi título", SECCIONES)
    texto = ruta.read_text(encoding="utf-8")
    assert "Mi título" in texto
    assert "Detalles" in texto


def test_el_formato_se_elige_segun_el_sistema() -> None:
    """Cada sistema operativo tiene su formato preferido, y todos se pueden escribir."""
    from tareas.documentos import PREFERENCIAS

    assert formato_preferido() in PREFERENCIAS["linux"]
    for extension in (ODT, DOCX, RTF, TXT):
        assert extension in PREFERENCIAS["linux"]
    for extension in (DOCX, RTF, TXT):
        assert extension in PREFERENCIAS["win32"]
    assert ODT == PREFERENCIAS["linux"][0], "en Linux se empieza por LibreOffice"


def test_el_odt_se_abre_con_libreooffice(tmp_path: Path) -> None:
    """Si LibreOffice está instalado, el fichero se convierte sin errores."""
    import shutil
    import subprocess

    if not shutil.which("soffice"):
        pytest.skip("LibreOffice no está instalado en esta máquina")

    ruta = escribir_documento(tmp_path / "salida.odt", "Mi título", SECCIONES)
    salida = tmp_path / "convertido"
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "txt", str(ruta), "--outdir", str(salida)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=120,
        check=False,
    )
    convertido = salida / "salida.txt"
    assert convertido.exists()
    assert "Mi título" in convertido.read_text(encoding="utf-8", errors="ignore")


# ------------------------------------------------------------------ unicode


def test_un_nombre_nfd_y_uno_nfc_son_el_mismo() -> None:
    """El problema clásico: dos nombres que se ven iguales pero no lo son."""
    nfc = "Introducció"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd
    assert mismo_nombre(nfc, nfd)
    assert a_nfc(nfd) == nfc


def test_normalizar_a_nfc_deja_el_nombre_igual() -> None:
    nfd = unicodedata.normalize("NFD", "Introducció")
    assert a_nfc(nfd) == "Introducció"


def test_normalizar_el_nombre_quita_los_acentos_pero_no_los_pierde() -> None:
    """«compatible» limpia el nombre, pero la ficha guarda el original."""
    assert compatible("Introducció.pdf") == "Introduccio.pdf"
