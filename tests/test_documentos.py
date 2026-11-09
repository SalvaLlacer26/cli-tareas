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


# ------------------------------------------------- índice, numeración y página


def _xml_de(tmp_path: Path, nombre: str, dentro: str) -> str:
    ruta = escribir_documento(tmp_path / nombre, "Título", SECCIONES)
    with zipfile.ZipFile(ruta) as paquete:
        return paquete.read(dentro).decode("utf-8")


def test_los_apartados_van_numerados_y_hay_indice(tmp_path: Path) -> None:
    contenido = _xml_de(tmp_path, "salida.odt", "content.xml")
    assert "Índice" in contenido
    assert "1. Resumen" in contenido
    assert "2. Detalles" in contenido
    assert 'xlink:href="#seccion2"' in contenido


def test_el_indice_no_sale_con_un_solo_apartado(tmp_path: Path) -> None:
    ruta = escribir_documento(tmp_path / "uno.odt", "Título", [SECCIONES[0]])
    with zipfile.ZipFile(ruta) as paquete:
        contenido = paquete.read("content.xml").decode("utf-8")
    assert "Índice" not in contenido


def test_el_odt_lleva_encabezado_y_pie_con_numero(tmp_path: Path) -> None:
    ruta = escribir_documento(
        tmp_path / "salida.odt",
        "Título",
        SECCIONES,
        unidad="UD1",
        asignatura="Bases de datos",
    )
    with zipfile.ZipFile(ruta) as paquete:
        estilos = paquete.read("styles.xml").decode("utf-8")
    assert "<style:header>" in estilos
    assert "UD1" in estilos
    assert "Bases de datos" in estilos
    assert "<style:footer>" in estilos
    assert "text:page-number" in estilos


def test_la_numeracion_de_segundo_nivel_sigue_al_primero(tmp_path: Path) -> None:
    secciones = [
        Seccion("Uno", ["cosa"]),
        Seccion("Sub de uno", ["cosa"], nivel=2),
        Seccion("Dos", ["cosa"]),
        Seccion("Sub de dos", ["cosa"], nivel=2),
    ]
    ruta = escribir_documento(tmp_path / "niveles.odt", "Título", secciones)
    with zipfile.ZipFile(ruta) as paquete:
        contenido = paquete.read("content.xml").decode("utf-8")
    assert "1.1 Sub de uno" in contenido
    assert "2.1 Sub de dos" in contenido


def test_el_docx_enlaza_el_indice_y_pone_cabecera_y_pie(tmp_path: Path) -> None:
    ruta = escribir_documento(
        tmp_path / "salida.docx",
        "Título",
        SECCIONES,
        unidad="Tema 3",
        asignatura="Sistemes Informàtics",
    )
    with zipfile.ZipFile(ruta) as paquete:
        documento = paquete.read("word/document.xml").decode("utf-8")
        cabecera = paquete.read("word/header1.xml").decode("utf-8")
        pie = paquete.read("word/footer1.xml").decode("utf-8")
    assert 'w:anchor="seccion1"' in documento
    assert "w:bookmarkStart" in documento
    assert "w:headerReference" in documento and "w:footerReference" in documento
    assert "Tema 3" in cabecera and "Sistemes Informàtics" in cabecera
    assert "PAGE" in pie


def test_el_rtf_lleva_encabezado_y_pie(tmp_path: Path) -> None:
    ruta = escribir_documento(
        tmp_path / "salida.rtf",
        "Título",
        SECCIONES,
        unidad="UD2",
        asignatura="Lenguaje de Marcas",
    )
    texto = ruta.read_text(encoding="utf-8")
    assert r"{\header" in texto
    assert "UD2" in texto and "Lenguaje de Marcas" in texto
    assert r"{\footer" in texto
    assert r"\fldinst PAGE" in texto


def test_el_rtf_escapa_las_tildes_para_windows(tmp_path: Path) -> None:
    """El RTF se guarda como cp1252: las tildes van con código, no en UTF-8."""
    ruta = escribir_documento(tmp_path / "salida.rtf", "Título", SECCIONES)
    texto = ruta.read_text(encoding="utf-8")
    assert "á" not in texto, "los bytes UTF-8 crudos se ven de churro en Word"
    assert r"T\'edtulo" in texto
    assert r"P\'e1gina" in texto


def test_la_separacion_entre_parrafos_va_en_los_estilos() -> None:
    """La separación la pone el formato, no espacios metidos a mano."""
    from tareas.documentos import _STYLES_DOCX, _styles_odt

    assert "margin-bottom" in _styles_odt("", "")
    assert 'w:spacing w:after="160"' in _STYLES_DOCX


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
