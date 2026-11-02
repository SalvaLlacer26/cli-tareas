"""Lectura y validación del fichero de configuración.

El fichero se llama `acciones.json` y vive en la carpeta de la persona (o en
la del usuario, si lo quiere usar desde cualquier sitio). Este módulo lo
desconfía: comprueba el fichero entero ANTES de que se toque un solo
fichero, y cuando algo falla el mensaje dice qué campo está mal.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_config_dir

from .clasificador import Carpeta, cargar_carpetas
from .errores import AccionNoValida, ConfigError

#: Nombre del fichero de configuración.
ARCHIVO = "acciones.json"

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

#: Campos que se admiten en una acción.
CLAVES_ACCION = (
    "nombre", "descripcion", "tipo", "carpeta", "origen", "filtro", "destino",
    "plantilla", "confirmar",
)

#: Huecos que la plantilla de renombrar puede usar.
HUECOS_PLANTILLA = ("fecha", "n", "ext", "nombre")

#: Formato obligatorio del campo «nombre».
RE_NOMBRE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass
class Configuracion:
    """Todo lo que se lee del fichero de configuración."""

    acciones: list[dict] = field(default_factory=list)
    carpetas: list[Carpeta] = field(default_factory=list)
    ruta: Path | None = None

    def carpeta_por_clave(self, clave: str) -> Carpeta | None:
        for carpeta in self.carpetas:
            if carpeta.clave == clave:
                return carpeta
        return None


def ruta_de_usuario() -> Path:
    """El fichero de configuración de la persona.

    - Linux/macOS: ``~/.config/tareas/acciones.json``
    - Windows: ``%APPDATA%\\tareas\\acciones.json``
    """
    return Path(user_config_dir("tareas")) / ARCHIVO


def cargar(ruta: Path) -> Configuracion:
    """Lee y valida el fichero de configuración."""
    ruta = Path(ruta).expanduser()
    if not ruta.is_file():
        propia = ruta_de_usuario()
        if propia.is_file() and ruta.name == ARCHIVO:
            ruta = propia
        else:
            raise ConfigError(
                f"No encuentro «{ruta}». Crea {ARCHIVO}, usa --config RUTA para otro fichero, "
                f"o pon uno en «{propia}» para usarlo desde cualquier carpeta."
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
        # La lista puede estar vacía: las órdenes de analizar, organizar,
        # deshacer, resumir y evaluar trabajan con las «carpetas». Pero avisa,
        # porque el mínimo del proyecto son tres acciones propias.
        acciones = []

    carpetas = cargar_carpetas(datos) if "carpetas" in datos else []
    por_clave = {c.clave: c for c in carpetas}

    vistas: set[str] = set()
    validadas = [
        _validar_accion(accion, posicion, vistas, por_clave)
        for posicion, accion in enumerate(acciones, start=1)
    ]

    return Configuracion(acciones=validadas, carpetas=carpetas, ruta=ruta)


def _validar_accion(
    accion: object,
    posicion: int,
    vistas: set[str],
    por_clave: dict[str, Carpeta],
) -> dict:
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

    accion = _heredar_de_carpeta(nombre, accion, por_clave)

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


def _heredar_de_carpeta(nombre: str, accion: dict, por_clave: dict[str, Carpeta]) -> dict:
    """Si la acción apunta a una carpeta, hereda su destino y sus patrones."""
    clave = accion.get("carpeta")
    if clave is None:
        return accion

    if not isinstance(clave, str) or not clave.strip():
        raise AccionNoValida(nombre, "carpeta", "tiene que ser el nombre de una carpeta")

    carpeta = por_clave.get(clave)
    if carpeta is None:
        raise AccionNoValida(
            nombre, "carpeta", f"«{clave}» no está en la lista «carpetas» del fichero de acciones"
        )

    heredada = dict(accion)
    if not heredada.get("destino"):
        heredada["destino"] = str(carpeta.destino)

    filtro = dict(heredada.get("filtro") or {})
    if not filtro.get("patron"):
        alternativas = [carpeta.clave, *carpeta.patrones]
        filtro["patron"] = "(?:" + "|".join(alternativas) + ")"
    heredada["filtro"] = filtro

    return heredada


def _validar_plantilla(nombre: str, plantilla: object) -> None:
    """Comprueba que la plantilla solo usa huecos que el motor conoce."""
    if not isinstance(plantilla, str) or not plantilla.strip():
        raise AccionNoValida(nombre, "plantilla", "debe ser un texto no vacío")

    if "/" in plantilla or "\\" in plantilla:
        raise AccionNoValida(
            nombre, "plantilla", "no puede contener barras: el nombre nuevo tiene que ser un solo fichero"
        )

    from datetime import datetime

    valores = {"fecha": datetime(2026, 1, 1), "n": 1, "ext": ".pdf", "nombre": "fichero"}
    try:
        resultado = plantilla.format(**valores)
    except KeyError as exc:
        hueco = str(exc).split("'")[1] if "'" in str(exc) else exc
        raise AccionNoValida(
            nombre, "plantilla", f"usa el hueco «{hueco}», que no existe"
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
            raise AccionNoValida(nombre, "filtro.patron", f"expresión regular rota: {exc}") from exc

    for campo in ("mas_antiguo_que_dias", "mayor_que_mb"):
        valor = filtro.get(campo)
        if valor is None:
            continue
        if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
            raise AccionNoValida(nombre, f"filtro.{campo}", "debe ser un número entero de 0 o más")
