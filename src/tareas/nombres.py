"""Nombres de fichero: cuáles son compatibles y cómo se arreglan.

Un nombre como «Pràctica 1. Entitats, atributs i valors.pdf» es legal en el
sistema de ficheros, pero da problemas en cuanto lo toca una herramienta:
acentos que se rompen según la codificación, espacios que hay que entrecomillar,
comas, corchetes que parecen etiquetas...

Aquí se decide qué nombres son **compatibles** (se quedan como están) y cómo se
convierten los que no lo son. El nombre original se guarda siempre en la ficha
.md, así que la cuenta atrás es posible: al organizar se restituye.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

#: Caracteres admitidos en un nombre compatible.
COMPATIBLE = re.compile(r"^[A-Za-z0-9._-]+$")

#: Caracteres que se usan para separar palabras en el nombre compatible.
SEPARADOR = "-"

#: Longitud máxima del nombre compatible (sin contar la extensión).
LONGITUD_MAXIMA = 80

#: Nombres que Windows reserva y no admite.
RESERVADOS_WINDOWS = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

#: Caracteres que Windows no admite en un nombre.
INVALIDOS_WINDOWS = '<>:"/\\|?*'

#: Extensiones con dos partes, para no comerse el «.tar» de «archivo.tar.gz».
EXTENSIONES_COMPUESTAS = (
    ".tar.gz", ".tar.xz", ".tar.bz2", ".tar.zst", ".tar.lz", ".tar.lzma",
    ".user.js", ".min.js", ".min.css", ".d.ts",
)


def sin_acentos(texto: str) -> str:
    """Quita los acentos: «Introducció» -> «Introduccio»."""
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def a_nfc(texto: str) -> str:
    """Normaliza un texto a la forma NFC.

    Dos nombres que se ven iguales pueden estar guardados de forma distinta:
    uno con la «ó» como un carácter (NFC) y otro como una «o» con un acento
    combinante (NFD). Es lo que pasa con los ficheros que vienen de macOS o
    de algunos navegadores. Sin normalizar, comparar «Introducció» con lo
    que hay en el disco falla aunque se vean idénticos.
    """
    return unicodedata.normalize("NFC", texto)


def mismo_nombre(uno: str, otro: str) -> bool:
    """Si dos nombres de fichero son el mismo, ignorando la forma Unicode."""
    return a_nfc(uno) == a_nfc(otro)


def separar_extension(nombre: str) -> tuple[str, str]:
    """Separa el nombre de su extensión, teniendo en cuenta las compuestas.

    («archivo.tar.gz») -> («archivo», «.tar.gz»)
    («P1.2. Activitats.pdf») -> («P1.2. Activitats», «.pdf»)
    """
    minuscula = nombre.lower()
    for compuesta in EXTENSIONES_COMPUESTAS:
        if minuscula.endswith(compuesta):
            return nombre[: -len(compuesta)], nombre[-len(compuesta):]

    punto = nombre.rfind(".")
    if punto > 0:
        return nombre[:punto], nombre[punto:]
    return nombre, ""


def es_compatible(nombre: str) -> bool:
    """Si un nombre se puede usar tal cual sin dar problemas.

    Es compatible si solo tiene letras, dígitos, punto, guion y guion bajo; si
    no acaba en punto ni en espacio; si no es un nombre reservado de Windows;
    y si no es demasiado largo.
    """
    base, _ = separar_extension(nombre)
    if not base:
        return False
    if not COMPATIBLE.match(nombre):
        return False
    if nombre != nombre.strip() or nombre.endswith(".") or nombre.endswith(" "):
        return False
    if base.upper() in RESERVADOS_WINDOWS:
        return False
    if any(c in INVALIDOS_WINDOWS for c in nombre):
        return False
    if len(base) > LONGITUD_MAXIMA:
        return False
    return True


def compatible(nombre: str) -> str:
    """Devuelve el nombre compatible de un fichero.

    Si el nombre ya es compatible, se devuelve tal cual. Si no, se quitan los
    acentos, los caracteres problemáticos se cambian por guiones y se recorta
    a una longitud razonable.
    """
    if es_compatible(nombre):
        return nombre

    base, extension = separar_extension(nombre)
    limpio = sin_acentos(base)
    # Un punto en medio del nombre se cambia por un guion: solo la extensión
    # puede llevar punto. Así «P1.2. Activitats.pdf» no se queda con dos
    # puntos dentro, que confunden a más de una herramienta.
    limpio = limpio.replace(".", SEPARADOR)
    limpio = re.sub(r"[^A-Za-z0-9_-]+", SEPARADOR, limpio)
    limpio = re.sub(r"[-]{2,}", SEPARADOR, limpio)
    limpio = limpio.strip(f"{SEPARADOR}_")

    if not limpio:
        limpio = "sin-nombre"
    if len(limpio) > LONGITUD_MAXIMA:
        limpio = limpio[:LONGITUD_MAXIMA].rstrip(f"{SEPARADOR}._")

    return f"{limpio}{extension.lower()}"


def problema_nombre(nombre: str) -> str | None:
    """Devuelve el motivo por el que un nombre no vale, o None si vale.

    Se comprueba contra las reglas de Windows, que son las más estrictas: un
    nombre válido en Linux puede ser inválido en el portátil de un compañero.
    """
    if not nombre.strip():
        return "el nombre no puede quedar vacío"
    if nombre in (".", ".."):
        return "no puede ser «.» ni «..»"
    if any(c in INVALIDOS_WINDOWS for c in nombre):
        return f"no puede llevar ninguno de estos caracteres: {INVALIDOS_WINDOWS}"
    if nombre.split(".")[0].upper() in RESERVADOS_WINDOWS:
        return f"«{nombre.split('.')[0]}» es un nombre que Windows reserva"
    if nombre.endswith(" ") or nombre.endswith("."):
        return "no puede terminar en espacio ni en punto"
    return None


def sin_conflicto(carpeta: Path | str, nombre: str) -> Path:
    """La ruta completa de un nombre que no pisa otro que ya está.

    Si «nota.pdf» ya existe en la carpeta, devuelve «nota (1).pdf» dentro de
    esa misma carpeta.
    """
    destino = Path(carpeta)
    base, extension = separar_extension(nombre)
    candidato = nombre
    numero = 1
    while (destino / candidato).exists():
        candidato = f"{base} ({numero}){extension}"
        numero += 1
    return destino / candidato
