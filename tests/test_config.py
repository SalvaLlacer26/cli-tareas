"""Pruebas de la configuración: el fichero no se fía de nadie.

Cada prueba escribe su propio acciones.json en una carpeta temporal: nunca
tocan las carpetas reales del alumno.
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

CARPETA_VALIDA = {
    "clave": "bbdd",
    "etiqueta": "Bases de dades",
    "destino": "~/Documents/Bases de dades",
    "patrones": ["sql", "entitats"],
}


def escribir(tmp_path: Path, datos: object) -> Path:
    """Escribe un acciones.json y devuelve su ruta."""
    ruta = tmp_path / "acciones.json"
    if isinstance(datos, str):
        ruta.write_text(datos, encoding="utf-8")
    else:
        ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


def completo(acciones=None, carpetas=None) -> dict:
    return {
        "version": 1,
        "acciones": acciones if acciones is not None else [ACCION_VALIDA],
        "carpetas": carpetas if carpetas is not None else [CARPETA_VALIDA],
    }


# ------------------------------------------------------------ camino feliz


def test_una_accion_valida_se_carga(tmp_path: Path) -> None:
    ruta = escribir(tmp_path, completo())
    configuracion = cargar(ruta)
    assert len(configuracion.acciones) == 1
    assert configuracion.acciones[0]["nombre"] == "ordenar-descargas"


def test_una_carpeta_valida_se_carga(tmp_path: Path) -> None:
    ruta = escribir(tmp_path, completo())
    configuracion = cargar(ruta)
    assert len(configuracion.carpetas) == 1
    assert configuracion.carpetas[0].clave == "bbdd"
    assert configuracion.carpetas[0].etiqueta == "Bases de dades"


def test_el_destino_se_expande(tmp_path: Path) -> None:
    ruta = escribir(tmp_path, completo())
    configuracion = cargar(ruta)
    assert not str(configuracion.carpetas[0].destino).startswith("~")


# ------------------------------------------------------------ casos feos


def test_fichero_que_no_existe_dice_cual_falta(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as error:
        cargar(tmp_path / "no-existe.json")
    assert "No encuentro" in str(error.value)
    assert error.value.codigo_salida == 3


def test_json_roto_dice_linea_y_columna(tmp_path: Path) -> None:
    ruta = escribir(tmp_path, "{ esto no es json")
    with pytest.raises(ConfigError) as error:
        cargar(ruta)
    assert "no es JSON válido" in str(error.value)
    assert "línea" in str(error.value)


def test_version_desconocida_se_avisa(tmp_path: Path) -> None:
    ruta = escribir(tmp_path, {**completo(), "version": 7})
    with pytest.raises(ConfigError) as error:
        cargar(ruta)
    assert "version" in str(error.value)


def test_tipo_inexistente_dice_que_tipos_hay(tmp_path: Path) -> None:
    rota = {**ACCION_VALIDA, "tipo": "mober"}
    ruta = escribir(tmp_path, completo(acciones=[rota]))
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert error.value.accion == "ordenar-descargas"
    assert error.value.campo == "tipo"
    assert "mover" in str(error.value)


def test_nombre_repetido_se_avisa(tmp_path: Path) -> None:
    ruta = escribir(tmp_path, completo(acciones=[ACCION_VALIDA, ACCION_VALIDA]))
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert error.value.campo == "nombre"
    assert "repetido" in str(error.value)


def test_regex_rota_se_avisa(tmp_path: Path) -> None:
    rota = {**ACCION_VALIDA, "filtro": {"patron": "*.tmp"}}
    ruta = escribir(tmp_path, completo(acciones=[rota]))
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert error.value.campo == "filtro.patron"


def test_mover_sin_destino_se_avisa(tmp_path: Path) -> None:
    sin_destino = {k: v for k, v in ACCION_VALIDA.items() if k != "destino"}
    ruta = escribir(tmp_path, completo(acciones=[sin_destino]))
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert error.value.campo == "destino"


def test_una_accion_no_puede_desactivar_la_confirmacion(tmp_path: Path) -> None:
    """Borrar siempre pregunta: poner «confirmar»: false es un error."""
    peligrosa = {**ACCION_VALIDA, "tipo": "borrar", "destino": None, "confirmar": False}
    ruta = escribir(tmp_path, completo(acciones=[peligrosa]))
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert error.value.campo == "confirmar"


def test_un_campo_desconocido_se_avisa(tmp_path: Path) -> None:
    """Escribir «patron» fuera de «filtro» haría la acción sobre todo."""
    equivocada = {**ACCION_VALIDA, "patron": ".*"}
    ruta = escribir(tmp_path, completo(acciones=[equivocada]))
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert "claves" in str(error.value)


def test_plantilla_con_barra_se_avisa(tmp_path: Path) -> None:
    mala = {**ACCION_VALIDA, "tipo": "renombrar", "plantilla": "sub/{n}.txt"}
    ruta = escribir(tmp_path, completo(acciones=[mala]))
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert error.value.campo == "plantilla"


def test_hueco_que_no_existe_se_avisa(tmp_path: Path) -> None:
    """«{fechae}» es un error de dedo que solo aparece al renombrar."""
    mala = {**ACCION_VALIDA, "tipo": "renombrar", "plantilla": "{fechae:%Y}.pdf"}
    ruta = escribir(tmp_path, completo(acciones=[mala]))
    with pytest.raises(AccionNoValida) as error:
        cargar(ruta)
    assert "fechae" in str(error.value)


def test_una_carpeta_sin_destino_se_avisa(tmp_path: Path) -> None:
    sin_destino = {k: v for k, v in CARPETA_VALIDA.items() if k != "destino"}
    ruta = escribir(tmp_path, completo(carpetas=[sin_destino]))
    with pytest.raises(ConfigError) as error:
        cargar(ruta)
    assert "destino" in str(error.value)


def test_un_patron_de_carpeta_roto_se_avisa(tmp_path: Path) -> None:
    rota = {**CARPETA_VALIDA, "patrones": ["*.txt"]}
    ruta = escribir(tmp_path, completo(carpetas=[rota]))
    with pytest.raises(ConfigError) as error:
        cargar(ruta)
    assert "expresión regular" in str(error.value)


def test_una_carpeta_repetida_se_avisa(tmp_path: Path) -> None:
    ruta = escribir(tmp_path, completo(carpetas=[CARPETA_VALIDA, CARPETA_VALIDA]))
    with pytest.raises(ConfigError) as error:
        cargar(ruta)
    assert "repetida" in str(error.value)


def test_filtro_nulo_no_revienta(tmp_path: Path) -> None:
    """«filtro»: null es legal: la acción toca todos los ficheros."""
    con_null = {**ACCION_VALIDA, "filtro": None}
    ruta = escribir(tmp_path, completo(acciones=[con_null]))
    assert len(cargar(ruta).acciones) == 1


def test_json_con_bom_de_windows_se_lee(tmp_path: Path) -> None:
    """El Bloc de notas de Windows guarda con BOM: el JSON es válido."""
    ruta = tmp_path / "acciones.json"
    ruta.write_bytes(
        b"\xef\xbb\xbf" + json.dumps(completo(), ensure_ascii=False).encode("utf-8")
    )
    assert len(cargar(ruta).acciones) == 1


def test_una_accion_hereda_el_destino_de_su_carpeta(tmp_path: Path) -> None:
    """«carpeta»: la acción no repite el destino, lo hereda."""
    heredada = {
        "nombre": "apuntes-bbdd",
        "descripcion": "Mueve los apuntes de BBDD",
        "tipo": "mover",
        "carpeta": "bbdd",
    }
    ruta = escribir(tmp_path, completo(acciones=[heredada]))
    configuracion = cargar(ruta)
    accion = configuracion.acciones[0]
    assert accion["destino"].endswith("Bases de dades")
    assert "sql" in accion["filtro"]["patron"]
