"""Pruebas de la interfaz: cada orden responde y devuelve el código correcto.

Se llama a la app de Typer con el cliente de pruebas, que captura la salida
y el código de salida sin abrir una terminal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tareas.cli import app

runner = CliRunner()


def plano(texto: str) -> str:
    """Quita los saltos de línea: Rich parte las frases largas al ancho."""
    return " ".join(texto.split())


def escribir_config(tmp_path: Path, extra: dict | None = None) -> Path:
    """Escribe un acciones.json con una acción y una carpeta."""
    datos = {
        "version": 1,
        "acciones": [
            {
                "nombre": "mover-cosas",
                "descripcion": "Mueve ficheros de prueba",
                "tipo": "mover",
                "filtro": {"extensiones": [".pdf"]},
                "destino": str(tmp_path / "destino"),
            }
        ],
        "carpetas": [
            {
                "clave": "bbdd",
                "etiqueta": "Bases de dades",
                "destino": str(tmp_path / "bbdd"),
                "patrones": ["sql", "bases de dades"],
            },
            {
                "clave": "sin-clasificar",
                "etiqueta": "Sin clasificar",
                "destino": str(tmp_path / "respaldo"),
                "patrones": [],
                "respaldo": True,
            },
        ],
    }
    if extra:
        datos.update(extra)
    ruta = tmp_path / "acciones.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


def documento(carpeta: Path, nombre: str, contenido: str = "Unas tablas SQL") -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_text(contenido, encoding="utf-8")
    return carpeta


# ------------------------------------------------------------- comandos


def test_la_ayuda_general_sale_sin_argumentos() -> None:
    resultado = runner.invoke(app, [])
    assert "analizar" in resultado.output
    assert "organizar" in resultado.output


def test_comandos_lista_los_ocho_comandos() -> None:
    resultado = runner.invoke(app, ["comandos"])
    assert resultado.exit_code == 0
    for nombre in ("analizar", "organizar", "deshacer", "resumir", "evaluar", "comandos"):
        assert nombre in resultado.output


def test_comandos_muestra_el_autor_y_el_aviso_legal() -> None:
    resultado = runner.invoke(app, ["comandos"])
    assert "Salvador Llácer Ivars" in resultado.output
    assert "1º DAM" in resultado.output
    assert "2026" in resultado.output
    assert "Todos los derechos reservados" in resultado.output


# ------------------------------------------------------------- analizar


def test_analizar_crea_las_fichas_y_muestra_la_tabla(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path)
    documento(tmp_path / "Descargas", "nota.txt", "SQL i bases de dades")

    resultado = runner.invoke(
        app,
        ["--config", str(ruta), "analizar", str(tmp_path / "Descargas")],
        input="y\n",
    )

    assert resultado.exit_code == 0
    assert "Bases de dades" in plano(resultado.output)
    assert "fichas" in plano(resultado.output).lower()
    assert (tmp_path / "Descargas" / "md" / "nota.txt.md").exists()


def test_analizar_pide_confirmacion(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path)
    documento(tmp_path / "Descargas", "nota.txt")

    resultado = runner.invoke(
        app, ["--config", str(ruta), "analizar", str(tmp_path / "Descargas")], input="n\n"
    )

    assert resultado.exit_code != 0


def test_analizar_usa_la_carpeta_actual_si_no_se_indica(tmp_path: Path, monkeypatch) -> None:
    """Sin argumento, trabaja sobre la carpeta en la que está la terminal."""
    ruta = escribir_config(tmp_path)
    documento(tmp_path / "Descargas", "nota.txt")
    monkeypatch.chdir(tmp_path / "Descargas")

    resultado = runner.invoke(
        app, ["--config", str(ruta), "analizar"], input="y\n"
    )

    assert resultado.exit_code == 0
    assert (tmp_path / "Descargas" / "md" / "nota.txt.md").exists()


def test_analizar_una_carpeta_que_no_existe_da_codigo_1(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path)
    resultado = runner.invoke(
        app, ["--config", str(ruta), "analizar", str(tmp_path / "no-existe")]
    )
    assert resultado.exit_code == 1
    assert "no existe" in plano(resultado.output)


# ------------------------------------------------------------ organizar


def test_organizar_mueve_el_documento_y_devuelve_el_nombre_original(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path)
    documento(tmp_path / "Descargas", "Pràctica SQL.txt", "SQL i bases de dades")

    runner.invoke(
        app, ["--config", str(ruta), "analizar", str(tmp_path / "Descargas")], input="y\n"
    )
    resultado = runner.invoke(
        app, ["--config", str(ruta), "organizar", str(tmp_path / "Descargas")]
    )

    assert resultado.exit_code == 0
    assert (tmp_path / "bbdd" / "Pràctica SQL.txt").exists()
    assert not (tmp_path / "Descargas" / "Pràctica SQL.txt").exists()


def test_organizar_sin_fichas_avisa(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path)
    (tmp_path / "Descargas").mkdir()
    resultado = runner.invoke(
        app, ["--config", str(ruta), "organizar", str(tmp_path / "Descargas")]
    )
    assert resultado.exit_code == 1
    assert "analizar" in plano(resultado.output)


def test_deshacer_devuelve_el_documento(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path)
    documento(tmp_path / "Descargas", "Pràctica SQL.txt", "SQL i bases de dades")

    runner.invoke(
        app, ["--config", str(ruta), "analizar", str(tmp_path / "Descargas")], input="y\n"
    )
    runner.invoke(app, ["--config", str(ruta), "organizar", str(tmp_path / "Descargas")])
    resultado = runner.invoke(
        app, ["--config", str(ruta), "deshacer", str(tmp_path / "Descargas")]
    )

    assert resultado.exit_code == 0
    assert (tmp_path / "Descargas" / "Pràctica SQL.txt").exists()
    assert not (tmp_path / "bbdd" / "Pràctica SQL.txt").exists()


# ------------------------------------------------------- resumir/evaluar


def test_resumir_crea_el_fichero_en_resumenes(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path)
    documento(tmp_path / "Descargas", "nota.txt", "SQL i bases de dades relacionals")

    runner.invoke(
        app, ["--config", str(ruta), "analizar", str(tmp_path / "Descargas")], input="y\n"
    )
    resultado = runner.invoke(
        app, ["--config", str(ruta), "resumir", "nota.txt", str(tmp_path / "Descargas")]
    )

    assert resultado.exit_code == 0
    assert (tmp_path / "Descargas" / "resumenes").is_dir()
    assert len(list((tmp_path / "Descargas" / "resumenes").iterdir())) == 1


def test_resumir_de_un_fichero_que_no_existe_avisa(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path)
    resultado = runner.invoke(
        app, ["--config", str(ruta), "resumir", "nada.pdf", str(tmp_path)]
    )
    assert resultado.exit_code == 1
    assert "No encuentro" in plano(resultado.output)


def test_evaluar_crea_el_fichero_en_ejercicios(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path)
    documento(tmp_path / "Descargas", "nota.txt", "El SQL es un lenguaje de consulta de datos")

    runner.invoke(
        app, ["--config", str(ruta), "analizar", str(tmp_path / "Descargas")], input="y\n"
    )
    resultado = runner.invoke(
        app, ["--config", str(ruta), "evaluar", "nota.txt", str(tmp_path / "Descargas")]
    )

    assert resultado.exit_code == 0
    assert (tmp_path / "Descargas" / "ejercicios").is_dir()


# ------------------------------------------------------ validar/ejecutar


def test_validar_un_config_valido_dice_cuantas_hay(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path)
    resultado = runner.invoke(app, ["--config", str(ruta), "validar"])
    assert resultado.exit_code == 0
    assert "1 acción(es)" in plano(resultado.output)


def test_validar_un_config_roto_da_codigo_3(tmp_path: Path) -> None:
    ruta = tmp_path / "acciones.json"
    ruta.write_text("{ roto", encoding="utf-8")
    resultado = runner.invoke(app, ["--config", str(ruta), "validar"])
    assert resultado.exit_code == 3
    assert "no es JSON válido" in plano(resultado.output)


def test_ejecutar_mueve_un_fichero(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path)
    documento(tmp_path / "Descargas", "nota.pdf")

    resultado = runner.invoke(
        app,
        ["--config", str(ruta), "ejecutar", "mover-cosas", str(tmp_path / "Descargas")],
    )

    assert resultado.exit_code == 0
    assert (tmp_path / "destino" / "nota.pdf").exists()


def test_ejecutar_una_accion_que_no_existe_da_codigo_1(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path)
    resultado = runner.invoke(app, ["--config", str(ruta), "ejecutar", "no-existe"])
    assert resultado.exit_code == 1
