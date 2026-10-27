"""Lectura y validación de acciones.json.

Este módulo desconfía del JSON: comprueba el fichero entero ANTES de que el
motor toque un solo fichero. Cuando algo falla, el mensaje dice qué acción y
qué campo fallan, para que se pueda arreglar en diez segundos.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .errores import AccionNoValida, ConfigError

#: Tipos de acción que el motor sabe ejecutar.
TIPOS = ("mover", "copiar", "renombrar", "borrar")

#: Campos que toda acción tiene que traer.
OBLIGATORIOS = ("nombre", "descripcion", "tipo")

#: Campo que cada tipo necesita además de los obligatorios.
POR_TIPO = {"mover": "destino", "copiar": "destino", "renombrar": "plantilla"}

#: Tipos que borran ficheros: siempre piden confirmación salvo --si.
DESTRUCTIVAS = ("borrar",)

#: Claves que se admiten dentro de «filtro».
CLAVES_FILTRO = ("extensiones", "patron", "mas_antiguo_que_dias", "mayor_que_mb")

#: Campos que se admiten en una acción. Lo que no esté aquí es un error:
#: escribir «patron» fuera de «filtro» haría que la acción se aplicase a todo.
CLAVES_ACCION = ("nombre", "descripcion", "tipo", "origen", "filtro", "destino", "plantilla", "confirmar")

#: Huecos que la plantilla de renombrar puede usar.
HUECOS_PLANTILLA = ("fecha", "n", "ext", "nombre")

#: Caracteres que Windows no admite en un nombre de fichero.
CARACTERES_INVALIDOS = '<>:"/\\|?*'

#: Nombres que Windows reserva y no puede usar.
NOMBRES_RESERVADOS = (
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
)

#: Formato obligatorio del campo «nombre».
RE_NOMBRE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")



def cargar(ruta: Path) -> list[dict]:
    """Lee y valida un fichero de acciones. Devuelve la lista de acciones.

    Lanza ConfigError (código de salida 3) si el fichero no existe, no es JSON
    o no cumple el esquema, y AccionNoValida concrete qué acción y campo
    están mal.
    """
    ruta = ruta.expanduser()
    if not ruta.is_file():
        raise ConfigError(
            f"No encuentro «{ruta}». Crea acciones.json o usa --config RUTA para otro fichero."
        )

    try:
        # utf-8-sig lee igual con BOM que sin BOM: el Bloc de notas de Windows
        # guarda en UTF-8 con BOM y sin él el JSON parecería roto.
        texto = ruta.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ConfigError(
            f"«{ruta.name}» no está guardado en UTF-8. Vuelve a guardarlo con esa codificación."
        ) from exc
    except OSError as exc:
        raise ConfigError(f"No puedo leer «{ruta}»: {exc.strerror or exc}.") from exc

    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"«{ruta.name}» no es JSON válido: línea {exc.lineno}, columna {exc.colno} ({exc.msg})"
        ) from exc

    if not isinstance(datos, dict):
        raise ConfigError(
            f"«{ruta.name}» debe tener un objeto en la raíz con las claves «version» y «acciones»."
        )

    version = datos.get("version")
    if version != 1:
        raise ConfigError(
            f"«{ruta.name}», campo «version»: se espera el número 1 y hay {version!r}. "
            "Esta versión del programa solo entiende el esquema 1."
        )

    acciones = datos.get("acciones")
    if not isinstance(acciones, list):
        raise ConfigError(f"«{ruta.name}», campo «acciones»: falta la lista de acciones.")
    if not acciones:
        raise ConfigError(f"«{ruta.name}», campo «acciones»: la lista está vacía.")

    validadas: list[dict] = []
    vistas: set[str] = set()
    for posicion, accion in enumerate(acciones, start=1):
        validadas.append(_validar_accion(accion, posicion, vistas))

    return validadas


def _validar_accion(accion: object, posicion: int, vistas: set[str]) -> dict:
    """Valida una acción suelta y devuelve el diccionario."""
    if not isinstance(accion, dict):
        raise AccionNoValida(f"nº {posicion}", "accion", "no es un objeto con campos")

    nombre = accion.get("nombre")
    etiqueta = nombre if isinstance(nombre, str) and nombre else f"nº {posicion}"

    for campo in OBLIGATORIOS:
        if not accion.get(campo):
            raise AccionNoValida(etiqueta, campo, "es obligatorio")

    if not isinstance(nombre, str) or not RE_NOMBRE.match(nombre):
        raise AccionNoValida(
            etiqueta,
            "nombre",
            "debe estar en minúsculas y con guiones, sin espacios (p. ej. «ordenar-descargas»)",
        )
    if nombre in vistas:
        raise AccionNoValida(nombre, "nombre", "está repetido")
    vistas.add(nombre)

    desconocidas = set(accion) - set(CLAVES_ACCION)
    if desconocidas:
        raise AccionNoValida(
            nombre,
            "claves",
            f"tiene campos que no existen ({', '.join(sorted(desconocidas))}); "
            f"los válidos son: {', '.join(CLAVES_ACCION)}",
        )

    descripcion = accion["descripcion"]
    if not isinstance(descripcion, str) or not descripcion.strip():
        raise AccionNoValida(nombre, "descripcion", "debe ser un texto que explique qué hace")

    tipo = accion["tipo"]
    if tipo not in TIPOS:
        raise AccionNoValida(
            nombre, "tipo", f"«{tipo}» no existe; usa uno de: {', '.join(TIPOS)}"
        )

    if "origen" in accion and not isinstance(accion["origen"], str):
        raise AccionNoValida(nombre, "origen", "debe ser una ruta (admite ~)")

    extra = POR_TIPO.get(tipo)
    if extra and not accion.get(extra):
        raise AccionNoValida(nombre, extra, f"es obligatorio en acciones de tipo {tipo}")

    if extra == "destino" and not isinstance(accion["destino"], str):
        raise AccionNoValida(nombre, "destino", "debe ser una ruta (admite ~)")

    if extra == "plantilla":
        _validar_plantilla(nombre, accion["plantilla"])

    if tipo in DESTRUCTIVAS and accion.get("confirmar") is False:
        raise AccionNoValida(
            nombre,
            "confirmar",
            "una acción que borra no puede desactivar la confirmación; quita el campo o ponlo a true",
        )

    _validar_filtro(nombre, accion.get("filtro"))

    return accion


def _validar_plantilla(nombre: str, plantilla: object) -> None:
    """Comprueba que la plantilla solo usa huecos que el motor conoce."""
    if not isinstance(plantilla, str) or not plantilla.strip():
        raise AccionNoValida(nombre, "plantilla", "debe ser un texto no vacío")

    separadores = [c for c in ("/", "\\") if c in plantilla]
    if separadores:
        raise AccionNoValida(
            nombre,
            "plantilla",
            "no puede contener barras: el nombre nuevo tiene que ser un solo fichero, "
            "no una ruta",
        )

    valores = {
        "fecha": datetime(2026, 1, 1),
        "n": 1,
        "ext": ".pdf",
        "nombre": "fichero",
    }
    try:
        resultado = plantilla.format(**valores)
    except KeyError as exc:
        hueco = str(exc).split("'")[1] if "'" in str(exc) else exc
        raise AccionNoValida(
            nombre,
            "plantilla",
            f"usa el hueco «{hueco}», que no existe; los huecos válidos son: "
            f"{', '.join(HUECOS_PLANTILLA)}",
        ) from exc
    except (IndexError, ValueError) as exc:
        raise AccionNoValida(nombre, "plantilla", f"el formato no es válido: {exc}") from exc

    if not resultado.strip():
        raise AccionNoValida(nombre, "plantilla", "el nombre nuevo no puede quedar vacío")


def _validar_filtro(nombre: str, filtro: object) -> None:
    """Comprueba que el filtro tiene sentido antes de usarlo sobre el disco."""
    if filtro is None:
        return
    if not isinstance(filtro, dict):
        raise AccionNoValida(nombre, "filtro", "debe ser un objeto con los campos de filtrado")

    desconocidas = set(filtro) - set(CLAVES_FILTRO)
    if desconocidas:
        raise AccionNoValida(
            nombre,
            "filtro",
            f"tiene claves desconocidas ({', '.join(sorted(desconocidas))}); "
            f"las válidas son: {', '.join(CLAVES_FILTRO)}",
        )

    extensiones = filtro.get("extensiones")
    if extensiones is not None:
        if not isinstance(extensiones, list) or not all(isinstance(e, str) for e in extensiones):
            raise AccionNoValida(nombre, "filtro.extensiones", "debe ser una lista de textos")
        if any(not e.startswith(".") for e in extensiones):
            raise AccionNoValida(
                nombre, "filtro.extensiones", "cada extensión debe empezar por punto (p. ej. «.pdf»)"
            )

    patron = filtro.get("patron")
    if patron is not None:
        if not isinstance(patron, str):
            raise AccionNoValida(nombre, "filtro.patron", "debe ser un texto con una expresión regular")
        try:
            re.compile(patron)
        except re.error as exc:
            raise AccionNoValida(
                nombre, "filtro.patron", f"expresión regular rota: {exc}"
            ) from exc

    for campo in ("mas_antiguo_que_dias", "mayor_que_mb"):
        valor = filtro.get(campo)
        if valor is None:
            continue
        if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
            raise AccionNoValida(nombre, f"filtro.{campo}", "debe ser un número entero de 0 o más")


def problema_nombre(nombre: str) -> str | None:
    """Devuelve el motivo por el que un nombre no vale, o None si vale.

    Se comprueba contra las reglas de Windows, que son las más estrictas: un
    nombre válido en Linux puede ser inválido en el portátil de un compañero.
    """
    if not nombre.strip():
        return "el nombre no puede quedar vacío"
    if nombre in (".", ".."):
        return "no puede ser «.» ni «..»"
    if any(c in CARACTERES_INVALIDOS for c in nombre):
        return f"no puede llevar ninguno de estos caracteres: {CARACTERES_INVALIDOS}"
    if nombre.split(".")[0].upper() in NOMBRES_RESERVADOS:
        return f"«{nombre.split('.')[0]}» es un nombre que Windows reserva"
    if nombre.endswith(" ") or nombre.endswith("."):
        return "no puede terminar en espacio ni en punto"
    return None
