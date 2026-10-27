"""Pruebas de la orden «tareas validar» y de la lectura de acciones.json.

Cada prueba escribe su propio acciones.json en una carpeta temporal: nunca
toca las carpetas reales del alumno.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tareas.config import cargar
from tareas.errores import AccionNoValida, ConfigError

ACCION_VALIDA = {
    "nombre": "ordenar-descargas",
    "descripcion": "Mueve los PDF a una carpeta",
    "tipo": "mover",
    "origen": "~/Descargas",
    "filtro": {"extensiones": [".pdf"]},
    "destino": "~/Documentos/PDF",
}


def escribir(tmp_path: Path, datos: object) -> Path:
    """Escribe un acciones.json y devuelve su ruta."""
    ruta = tmp_path / "acciones.json"
    if isinstance(datos, str):
        ruta.write_text(datos, encoding="utf-8")
    else:
        ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


def test_una_accion_valida_se_carga(tmp_path: Path) -> None:
    ruta = escribir(tmp_path, {"version": 1, "acciones": [ACCION_VALIDA]})
    acciones = cargar(ruta)
    assert len(acciones) == 1
    assert acciones[0]["nombre"] == "ordenar-descargas"


def test_una_accion_valida_no_pide_nada(tmp_path: Path) -> None:
    """El camino feliz: si el fichero es correcto, cargar() no protesta."""
    ruta = escribir(tmp_path, {"version": 1, "acciones": [ACCION_VALIDA]})
    assert cargar(ruta) == [ACCION_VALIDA]


def test_fichero_que_no_existe_dice_cual_falta(tmp_path: Path) -> None:
    ruta = tmp_path / "no-existe.json"
    with pytest.raises(ConfigError) as error:
        cargar(ruta)
    assert "No encuentro" in str(error.value)
    assert error.value.codigo_salida == 3


def test_json_roto_dice_linea_y_columna(tmp_path: Path) -> None:
    ruta = escribir(tmp_path, "{ esto no es json")
    with pytest.raises(ConfigError) as error:
        cargar(ruta)
    assert "no es JSON válido" in str(error.value)
    assert "línea" in str(error.value)


def test_tipo_inexistente_dice_que_tipos_hay(tmp_path: Path) -> None:
    ruta = escribir(tmp_path, {"version": 1, "acciones": [{**ACCION_VALIDA, "tipo": "mober"}]})
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert error.value.accion == "ordenar-descargas"
    assert error.value.campo == "tipo"
    assert "mover" in str(error.value)


def test_nombre_repetido_se_avisa(tmp_path: Path) -> None:
    ruta = escribir(tmp_path, {"version": 1, "acciones": [ACCION_VALIDA, ACCION_VALIDA]})
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert error.value.campo == "nombre"
    assert "repetido" in str(error.value)


def test_regex_rota_se_avisa(tmp_path: Path) -> None:
    rota = {**ACCION_VALIDA, "filtro": {"patron": "*.tmp"}}
    ruta = escribir(tmp_path, {"version": 1, "acciones": [rota]})
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert error.value.campo == "filtro.patron"


def test_mover_sin_destino_se_avisa(tmp_path: Path) -> None:
    sin_destino = {k: v for k, v in ACCION_VALIDA.items() if k != "destino"}
    ruta = escribir(tmp_path, {"version": 1, "acciones": [sin_destino]})
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert error.value.campo == "destino"


def test_una_accion_no_puede_desactivar_la_confirmacion(tmp_path: Path) -> None:
    """Borrar siempre pregunta: poner «confirmar»: false es un error."""
    peligrosa = {**ACCION_VALIDA, "tipo": "borrar", "destino": None, "confirmar": False}
    ruta = escribir(tmp_path, {"version": 1, "acciones": [peligrosa]})
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert error.value.campo == "confirmar"


def test_un_campo_desconocido_se_avisa(tmp_path: Path) -> None:
    """Escribir «patron» fuera de «filtro» haría la acción sobre todo."""
    equivocada = {**ACCION_VALIDA, "patron": ".*"}
    ruta = escribir(tmp_path, {"version": 1, "acciones": [equivocada]})
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert "claves" in str(error.value)


def test_plantilla_con_barra_se_avisa(tmp_path: Path) -> None:
    """Un nombre nuevo no puede ser una ruta."""
    mala = {**ACCION_VALIDA, "tipo": "renombrar", "plantilla": "sub/{n}.txt"}
    ruta = escribir(tmp_path, {"version": 1, "acciones": [mala]})
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert error.value.campo == "plantilla"


def test_hueco_que_no_existe_se_avisa(tmp_path: Path) -> None:
    """«{fechae}» es un error de dedo que solo aparece al renombrar."""
    mala = {**ACCION_VALIDA, "tipo": "renombrar", "plantilla": "{fechae:%Y}.pdf"}
    ruta = escribir(tmp_path, {"version": 1, "acciones": [mala]})
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert "fechae" in str(error.value)


def test_filtro_nulo_no_revienta(tmp_path: Path) -> None:
    """«filtro»: null es legal: la acción toca todos los ficheros."""
    con_null = {**ACCION_VALIDA, "filtro": None}
    ruta = escribir(tmp_path, {"version": 1, "acciones": [con_null]})
    assert len(cargar(ruta)) == 1


def test_json_con_bom_de_windows_se_lee(tmp_path: Path) -> None:
    """El Bloc de notas de Windows guarda con BOM: el JSON es válido."""
    ruta = tmp_path / "acciones.json"
    ruta.write_bytes(
        b"\xef\xbb\xbf" + json.dumps({"version": 1, "acciones": [ACCION_VALIDA]}).encode("utf-8")
    )
    assert len(cargar(ruta)) == 1
