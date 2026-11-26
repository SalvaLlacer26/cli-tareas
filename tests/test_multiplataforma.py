"""Pruebas de multiplataforma: la salida tiene que poder escribirse en Windows.

En Windows la consola usa cp1252 por defecto. Si la herramienta imprime un
carácter que no cabe ahí (como «✔», U+2714), Python revienta con un
UnicodeEncodeError. Lo descubrió la CI al fallar en windows-latest.

La regla: **ningún carácter que llegue a la consola puede salirse de
cp1252**, salvo los que pasan por el helper `simbolo()`, que comprueba la
codificación antes de usarlos.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

import pytest

from typer.testing import CliRunner

from tareas.cli import app

runner = CliRunner()

#: La codificación que usa Windows en su consola por defecto.
CODIFICACION_WINDOWS = "cp1252"

#: Las llamadas al helper: su primer argumento sí puede ser exótico.
RE_SIMBOLO = re.compile(r"(simbolo\(\s*['\"])[^'\"]*(['\"])")


def _fuentes() -> list[pathlib.Path]:
    raiz = pathlib.Path(__file__).resolve().parent.parent / "src" / "tareas"
    return sorted(raiz.glob("*.py"))


def _codigo_imprimible(texto: str) -> str:
    """El código sin comentarios ni docstrings: lo único que puede imprimirse."""
    arbol = ast.parse(texto)
    for nodo in ast.walk(arbol):
        if isinstance(
            nodo, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            cuerpo = nodo.body
            if (
                cuerpo
                and isinstance(cuerpo[0], ast.Expr)
                and isinstance(cuerpo[0].value, ast.Constant)
                and isinstance(cuerpo[0].value.value, str)
            ):
                nodo.body = cuerpo[1:]
    return ast.unparse(arbol)


def test_ningun_caracter_de_la_consola_se_sale_de_cp1252() -> None:
    """Ningún texto que se imprima puede tener un carácter que no quepa en cp1252."""
    prototipos: list[tuple[str, str, str]] = []

    for fichero in _fuentes():
        texto = fichero.read_text(encoding="utf-8")
        # Se tapan los argumentos del helper: esos sí están vigilados.
        texto = RE_SIMBOLO.sub(r"\1\2", texto)

        for linea in _codigo_imprimible(texto).splitlines():
            for caracter in linea:
                if caracter in "\n\r\t":
                    continue
                try:
                    caracter.encode(CODIFICACION_WINDOWS)
                except UnicodeEncodeError:
                    prototipos.append((fichero.name, caracter, linea.strip()[:60]))
                    break

    if prototipos:
        detalle = "\n".join(
            f"  {nombre}  {caracter!r} ({hex(ord(caracter))})  ->  {linea}"
            for nombre, caracter, linea in prototipos[:10]
        )
        pytest.fail(
            "Estos caracteres no se pueden escribir en la consola de Windows "
            f"(cp1252):\n{detalle}\n"
            "Usa el helper «simbolo()» para los que no quepan."
        )


def test_el_simbolo_usa_el_texto_alterno_si_no_cabe(monkeypatch) -> None:
    from tareas import cli

    monkeypatch.setattr(cli.sys, "stdout", type("Falso", (), {"encoding": "cp1252"})())
    assert cli.simbolo("✔", "OK") == "OK"


def test_el_simbolo_se_mantiene_si_cabe(monkeypatch) -> None:
    from tareas import cli

    monkeypatch.setattr(cli.sys, "stdout", type("Falso", (), {"encoding": "utf-8"})())
    assert cli.simbolo("✔", "OK") == "✔"


def test_la_salida_se_puede_escribir_en_la_consola_actual(tmp_path: pathlib.Path) -> None:
    """Lo que se imprime tiene que caber en la consola donde se está."""
    datos = {
        "version": 1,
        "acciones": [],
        "carpetas": [
            {
                "clave": "bbdd",
                "etiqueta": "Bases de dades",
                "destino": str(tmp_path / "bbdd"),
                "patrones": ["sql"],
            }
        ],
    }
    ruta = tmp_path / "acciones.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")

    resultado = runner.invoke(app, ["--config", str(ruta), "validar"])
    assert resultado.exit_code == 0

    codificacion = getattr(sys.stdout, "encoding", None) or "utf-8"
    for caracter in resultado.output:
        try:
            caracter.encode(codificacion)
        except UnicodeEncodeError:
            pytest.fail(
                f"la salida trae {caracter!r}, que no cabe en {codificacion}"
            )
