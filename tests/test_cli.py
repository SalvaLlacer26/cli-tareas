"""Pruebas de la interfaz: la orden responde y devuelve el código correcto.

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



def escribir_config(tmp_path: Path, acciones: list[dict]) -> Path:
    ruta = tmp_path / "acciones.json"
    ruta.write_text(
        json.dumps({"version": 1, "acciones": acciones}, ensure_ascii=False), encoding="utf-8"
    )
    return ruta


def accion_mover(destino: Path, **extra: object) -> dict:
    base = {
        "nombre": "mover-cosas",
        "descripcion": "Mueve ficheros de prueba",
        "tipo": "mover",
        "filtro": {"extensiones": [".pdf"]},
        "destino": str(destino),
    }
    base.update(extra)
    return base


def test_ayuda_general_sale_sin_argumentos() -> None:
    resultado = runner.invoke(app, [])
    assert "Muestra la versión instalada" in resultado.output
    assert "Lista los ficheros" in resultado.output


def test_version_dice_la_version_instalada() -> None:
    from tareas import __version__

    resultado = runner.invoke(app, ["version"])
    assert resultado.exit_code == 0
    assert f"tareas {__version__}" in plano(resultado.output)


def test_listar_una_carpeta_vacia_avisa_en_vez_de_pintar_tabla(tmp_path: Path) -> None:
    resultado = runner.invoke(app, ["listar", str(tmp_path)])
    assert resultado.exit_code == 0
    assert "está vacía" in plano(resultado.output)


def test_listar_una_carpeta_que_no_existe_da_error_y_codigo_1(tmp_path: Path) -> None:
    resultado = runner.invoke(app, ["listar", str(tmp_path / "no-existe")])
    assert resultado.exit_code == 1
    assert "no existe" in plano(resultado.output)


def test_listar_muestra_los_ficheros_con_tamano_y_fecha(tmp_path: Path) -> None:
    (tmp_path / "nota.pdf").write_text("hola", encoding="utf-8")
    resultado = runner.invoke(app, ["listar", str(tmp_path)])
    assert resultado.exit_code == 0
    assert "nota.pdf" in resultado.output
    assert ".pdf" in resultado.output


def test_validar_un_config_valido_dice_cuantas_hay(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path, [accion_mover(tmp_path / "destino")])
    resultado = runner.invoke(app, ["--config", str(ruta), "validar"])
    assert resultado.exit_code == 0
    assert "1 acción(es) válida(s)" in plano(resultado.output)


def test_validar_un_config_roto_da_codigo_3(tmp_path: Path) -> None:
    ruta = tmp_path / "acciones.json"
    ruta.write_text("{ roto", encoding="utf-8")
    resultado = runner.invoke(app, ["--config", str(ruta), "validar"])
    assert resultado.exit_code == 3
    assert "no es JSON válido" in plano(resultado.output)


def test_acciones_lista_las_que_hay(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path, [accion_mover(tmp_path / "destino")])
    resultado = runner.invoke(app, ["--config", str(ruta), "acciones"])
    assert resultado.exit_code == 0
    assert "mover-cosas" in plano(resultado.output)


def test_ejecutar_en_simulacion_no_toca_el_disco(tmp_path: Path) -> None:
    origen = tmp_path / "origen"
    origen.mkdir()
    (origen / "nota.pdf").write_text("hola", encoding="utf-8")
    destino = tmp_path / "destino"
    ruta = escribir_config(tmp_path, [accion_mover(destino)])

    resultado = runner.invoke(
        app, ["--config", str(ruta), "ejecutar", "mover-cosas", str(origen), "--simular"]
    )

    assert resultado.exit_code == 0
    assert "simulado" in plano(resultado.output)
    assert (origen / "nota.pdf").exists()
    assert not destino.exists()


def test_ejecutar_mueve_de_verdad(tmp_path: Path) -> None:
    origen = tmp_path / "origen"
    origen.mkdir()
    (origen / "nota.pdf").write_text("hola", encoding="utf-8")
    destino = tmp_path / "destino"
    ruta = escribir_config(tmp_path, [accion_mover(destino)])

    resultado = runner.invoke(
        app, ["--config", str(ruta), "ejecutar", "mover-cosas", str(origen)]
    )

    assert resultado.exit_code == 0
    assert "hecho" in plano(resultado.output)
    assert (destino / "nota.pdf").exists()
    assert not (origen / "nota.pdf").exists()


def test_una_accion_que_no_existe_da_codigo_1(tmp_path: Path) -> None:
    ruta = escribir_config(tmp_path, [accion_mover(tmp_path / "destino")])
    resultado = runner.invoke(app, ["--config", str(ruta), "ejecutar", "no-existe"])
    assert resultado.exit_code == 1
    assert "tareas acciones" in plano(resultado.output)


def test_borrar_pide_confirmacion_y_no_borra_si_dices_que_no(tmp_path: Path) -> None:
    origen = tmp_path / "origen"
    origen.mkdir()
    (origen / "nota.tmp").write_text("x", encoding="utf-8")
    ruta = escribir_config(
        tmp_path,
        [
            {
                "nombre": "limpiar",
                "descripcion": "Borra temporales",
                "tipo": "borrar",
                "filtro": {"extensiones": [".tmp"]},
                "confirmar": True,
            }
        ],
    )

    resultado = runner.invoke(
        app, ["--config", str(ruta), "ejecutar", "limpiar", str(origen)], input="n\n"
    )

    assert resultado.exit_code != 0
    assert (origen / "nota.tmp").exists()


def test_borrar_con_si_no_pregunta(tmp_path: Path) -> None:
    origen = tmp_path / "origen"
    origen.mkdir()
    (origen / "nota.tmp").write_text("x", encoding="utf-8")
    ruta = escribir_config(
        tmp_path,
        [
            {
                "nombre": "limpiar",
                "descripcion": "Borra temporales",
                "tipo": "borrar",
                "filtro": {"extensiones": [".tmp"]},
                "confirmar": True,
            }
        ],
    )

    resultado = runner.invoke(
        app, ["--config", str(ruta), "ejecutar", "limpiar", str(origen), "--si"]
    )

    assert resultado.exit_code == 0
    assert not (origen / "nota.tmp").exists()


def test_un_nombre_con_corchetes_no_rompe_la_tabla(tmp_path: Path) -> None:
    """Rich interpretaría los corchetes como marcado si no se escapan."""
    origen = tmp_path / "origen"
    origen.mkdir()
    (origen / "[borrador].pdf").write_text("x", encoding="utf-8")
    ruta = escribir_config(tmp_path, [accion_mover(tmp_path / "destino")])

    resultado = runner.invoke(
        app, ["--config", str(ruta), "ejecutar", "mover-cosas", str(origen), "--simular"]
    )

    assert resultado.exit_code == 0
    assert "[borrador].pdf" in plano(resultado.output)
