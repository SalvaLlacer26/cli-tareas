"""Pruebas de la conversión de Markdown a secciones del documento."""

from __future__ import annotations

from tareas.markdown import a_secciones, limpiar_texto


def test_los_encabezados_de_segundo_nivel_se_apartan() -> None:
    markdown = "## Primer apartado\n\nTexto.\n\n## Segundo apartado\n\nMás texto.\n"
    secciones = a_secciones(markdown)
    assert [s.titulo for s in secciones] == ["Primer apartado", "Segundo apartado"]
    assert secciones[0].lineas == ["Texto."]


def test_el_titulo_principal_se_ignora() -> None:
    markdown = "# Resumen del tema\n\n## Apartado\n\nTexto.\n"
    secciones = a_secciones(markdown)
    assert all(s.titulo != "Resumen del tema" for s in secciones)


def test_el_tercer_nivel_es_un_subapartado() -> None:
    markdown = "## Apartado\n\n### Subapartado\n\nTexto.\n"
    secciones = a_secciones(markdown)
    assert secciones[1].titulo == "Subapartado"
    assert secciones[1].nivel == 2


def test_las_listas_se_convierten_en_vinetas() -> None:
    markdown = "## Apartado\n\n- Primero\n- Segundo\n"
    secciones = a_secciones(markdown)
    assert secciones[0].lineas == ["• Primero", "• Segundo"]


def test_las_listas_numeradas_tambien() -> None:
    markdown = "## Apartado\n\n1. Primero\n2. Segundo\n"
    secciones = a_secciones(markdown)
    assert secciones[0].lineas == ["• Primero", "• Segundo"]


def test_las_tablas_se_convierten_en_filas_con_tabuladores() -> None:
    markdown = (
        "## Apartado\n\n"
        "| Sistema | Base |\n"
        "|---|---|\n"
        "| Binario | 2 |\n"
        "| Octal | 8 |\n"
    )
    secciones = a_secciones(markdown)
    assert "Sistema\tBase" in secciones[0].lineas
    assert "Binario\t2" in secciones[0].lineas
    assert "Octal\t8" in secciones[0].lineas


def test_las_negritas_se_quitan_del_texto() -> None:
    markdown = "## Apartado\n\nEl tema **importante** es SQL.\n"
    secciones = a_secciones(markdown)
    assert secciones[0].lineas == ["El tema importante es SQL."]


def test_las_marcas_de_codigo_se_quitan() -> None:
    assert limpiar_texto("usa `SELECT` aquí") == "usa SELECT aquí"


def test_un_markdown_vacio_devuelve_una_seccion() -> None:
    secciones = a_secciones("")
    assert len(secciones) == 1
