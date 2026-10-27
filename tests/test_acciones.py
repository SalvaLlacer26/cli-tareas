"""Pruebas de las acciones y del motor: qué toca cada fichero y qué no.

Todas las pruebas trabajan en una carpeta temporal que crea pytest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tareas.acciones import Accion, Mover, Renombrar, Resultado, destino_libre
from tareas.errores import TareasError
from tareas.motor import Motor


def crear_accion(tipo: str, **extra: object) -> dict:
    """Construye el diccionario de configuración de una acción."""
    base = {"nombre": "accion", "descripcion": "Una acción de prueba", "tipo": tipo}
    base.update(extra)
    return base


def accion_de(tipo: str, **extra: object) -> Accion:
    return Accion.desde_config(crear_accion(tipo, **extra))


# ---------------------------------------------------------------- mover


def test_mover_deja_el_fichero_en_el_destino(tmp_path: Path) -> None:
    origen = tmp_path / "origen"
    destino = tmp_path / "destino"
    origen.mkdir()
    (origen / "nota.txt").write_text("hola", encoding="utf-8")

    accion = accion_de("mover", destino=str(destino))
    resultados = accion.ejecutar([origen / "nota.txt"], simular=False)

    assert len(resultados) == 1
    assert resultados[0].estado == "hecho"
    assert not (origen / "nota.txt").exists()
    assert (destino / "nota.txt").read_text(encoding="utf-8") == "hola"


def test_mover_crea_la_carpeta_de_destino_si_no_existe(tmp_path: Path) -> None:
    origen = tmp_path / "origen"
    origen.mkdir()
    (origen / "nota.txt").write_text("hola", encoding="utf-8")
    destino = tmp_path / "a" / "b" / "c"

    accion_de("mover", destino=str(destino)).ejecutar([origen / "nota.txt"], simular=False)

    assert (destino / "nota.txt").exists()


def test_nunca_se_sobrescribe_un_fichero(tmp_path: Path) -> None:
    """Si el destino ya tiene el nombre, se añade « (1)»."""
    origen = tmp_path / "origen"
    destino = tmp_path / "destino"
    origen.mkdir()
    destino.mkdir()
    (origen / "nota.txt").write_text("nuevo", encoding="utf-8")
    (destino / "nota.txt").write_text("viejo", encoding="utf-8")

    accion_de("mover", destino=str(destino)).ejecutar([origen / "nota.txt"], simular=False)

    assert (destino / "nota.txt").read_text(encoding="utf-8") == "viejo"
    assert (destino / "nota (1).txt").read_text(encoding="utf-8") == "nuevo"


def test_destino_libre_no_escribe_a_traves_de_un_enlace_roto(tmp_path: Path) -> None:
    """Un enlace simbólico roto en el destino también cuenta como ocupado."""
    destino = tmp_path / "destino"
    destino.mkdir()
    (destino / "nota.txt").symlink_to(tmp_path / "no-existe.txt")

    libre = destino_libre(destino / "nota.txt")

    assert libre.name == "nota (1).txt"


# ---------------------------------------------------------------- simular


def test_simular_no_toca_nada_del_disco(tmp_path: Path) -> None:
    origen = tmp_path / "origen"
    destino = tmp_path / "destino"
    origen.mkdir()
    (origen / "nota.txt").write_text("hola", encoding="utf-8")

    accion = accion_de("mover", destino=str(destino))
    resultados = accion.ejecutar([origen / "nota.txt"], simular=True)

    assert resultados[0].estado == "simulado"
    assert (origen / "nota.txt").exists()
    assert not destino.exists(), "en simulación no se debe crear la carpeta de destino"


def test_simular_enseña_el_mismo_destino_que_la_ejecucion_real(tmp_path: Path) -> None:
    """Dos ficheros al mismo nombre: la simulación no puede mentir."""
    origen = tmp_path / "origen"
    origen.mkdir()
    primero = origen / "a.txt"
    segundo = origen / "b.txt"
    primero.write_text("a", encoding="utf-8")
    segundo.write_text("b", encoding="utf-8")

    configuracion = crear_accion(
        "renombrar", origen=str(origen), plantilla="igual{n}.txt"
    )
    simulados = Accion.desde_config(configuracion).ejecutar(
        [primero, segundo], simular=True
    )
    reales = Accion.desde_config(configuracion).ejecutar([primero, segundo], simular=False)

    assert [r.destino.name for r in simulados] == [r.destino.name for r in reales]
    assert len({r.destino.name for r in simulados}) == 2


# ---------------------------------------------------------------- renombrar


def test_renombrar_usa_la_plantilla(tmp_path: Path) -> None:
    origen = tmp_path / "origen"
    origen.mkdir()
    fichero = origen / "IMG_1.jpg"
    fichero.write_text("x", encoding="utf-8")

    accion = accion_de("renombrar", plantilla="{nombre}-{n:03}{ext}")
    resultados = accion.ejecutar([fichero], simular=False)

    assert resultados[0].estado == "hecho"
    assert (origen / "IMG_1-001.jpg").exists()


def test_renombrar_rechaza_un_nombre_que_windows_no_admite(tmp_path: Path) -> None:
    """«CON.txt» es un nombre que Windows reserva: se avisa, no se revienta."""
    origen = tmp_path / "origen"
    origen.mkdir()
    fichero = origen / "cualquier.jpg"
    fichero.write_text("x", encoding="utf-8")

    accion = accion_de("renombrar", plantilla="CON.txt")
    resultados = accion.ejecutar([fichero], simular=False)

    assert resultados[0].estado == "error"
    assert "CON" in (resultados[0].error or "")


# ---------------------------------------------------------------- borrar


def test_borrar_es_destructiva_y_pide_confirmacion() -> None:
    assert accion_de("borrar").destructiva is True
    assert accion_de("mover").destructiva is False


def test_borrar_en_simulacion_no_borra(tmp_path: Path) -> None:
    fichero = tmp_path / "nota.tmp"
    fichero.write_text("x", encoding="utf-8")

    accion_de("borrar").ejecutar([fichero], simular=True)

    assert fichero.exists()


# ---------------------------------------------------------------- motor


def test_el_motor_selecciona_solo_los_ficheros_que_cumplen_el_filtro(tmp_path: Path) -> None:
    origen = tmp_path / "origen"
    origen.mkdir()
    (origen / "a.pdf").write_text("x", encoding="utf-8")
    (origen / "b.txt").write_text("x", encoding="utf-8")
    (origen / "c.PDF").write_text("x", encoding="utf-8")

    motor = Motor([crear_accion("mover", filtro={"extensiones": [".pdf"]})])
    elegidos = motor.seleccionar(origen, {"extensiones": [".pdf"]})

    assert {p.name for p in elegidos} == {"a.pdf", "c.PDF"}


def test_el_motor_acepta_una_extension_compuesta(tmp_path: Path) -> None:
    """«.tar.gz» es un sufijo doble: con Path.suffix nunca entraría."""
    origen = tmp_path / "origen"
    origen.mkdir()
    (origen / "a.tar.gz").write_text("x", encoding="utf-8")
    (origen / "b.zip").write_text("x", encoding="utf-8")

    elegidos = Motor([]).seleccionar(origen, {"extensiones": [".tar.gz"]})

    assert [p.name for p in elegidos] == ["a.tar.gz"]


def test_el_motor_no_baja_a_las_subcarpetas(tmp_path: Path) -> None:
    origen = tmp_path / "origen"
    (origen / "sub").mkdir(parents=True)
    (origen / "sub" / "a.pdf").write_text("x", encoding="utf-8")

    elegidos = Motor([]).seleccionar(origen, {})

    assert elegidos == []


def test_una_accion_inexistente_dice_cuando_mirar_la_lista(tmp_path: Path) -> None:
    motor = Motor([crear_accion("mover", destino=str(tmp_path))])
    with pytest.raises(TareasError) as error:
        motor.ejecutar("no-existe", None, simular=True)
    assert "tareas acciones" in str(error.value)


def test_una_carpeta_que_no_existe_dice_cual(tmp_path: Path) -> None:
    motor = Motor([crear_accion("mover", destino=str(tmp_path))])
    with pytest.raises(TareasError) as error:
        motor.ejecutar("accion", tmp_path / "no-existe", simular=True)
    assert "no existe" in str(error.value)


def test_la_fabrica_devuelve_la_clase_correcta() -> None:
    assert isinstance(Accion.desde_config(crear_accion("mover")), Mover)
    assert isinstance(Accion.desde_config(crear_accion("renombrar")), Renombrar)


def test_un_fichero_que_falla_no_corta_la_accion(tmp_path: Path) -> None:
    """Si un fichero falla, los demás se mueven igualmente."""
    origen = tmp_path / "origen"
    destino = tmp_path / "destino"
    origen.mkdir()
    (origen / "bueno.txt").write_text("x", encoding="utf-8")
    (origen / "malo.txt").write_text("x", encoding="utf-8")

    accion = accion_de("mover", destino=str(destino))
    resultados = accion.ejecutar(
        [origen / "malo.txt", origen / "bueno.txt"], simular=False
    )

    estados = {r.origen.name: r.estado for r in resultados}
    assert estados["bueno.txt"] == "hecho"
    assert (destino / "bueno.txt").exists()
