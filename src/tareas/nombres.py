"""Normalización de nombres: convertir cualquier nombre en uno interpretable.

El CLI reconoce los ficheros por su nombre. Un nombre como
«Pràctica 1. Entitats, atributs i valors.pdf» es perfectamente válido en el
sistema de ficheros, pero es horroroso para comparar, para escribir en una
terminal y para que un patrón lo encuentre.

Aquí se convierte ese nombre en una forma canónica:

    Pràctica 1. Entitats, atributs i valors.pdf
    -> bbdd_practica-1-entitats-atributs-i-valors.pdf

El prefijo es la clave de la carpeta donde va el fichero, así que a partir de
ahí el nombre **sí** dice a qué asignatura pertenece. Y como el prefijo
contiene la clave, los patrones de esa carpeta lo encuentran solos.
"""

from __future__ import annotations

import re
import unicodedata

#: Caracteres que se conservan tal cual dentro de un nombre canónico.
PERMITIDOS = re.compile(r"[^a-z0-9]+")

#: Separador entre la clave de la carpeta y el nombre del fichero.
SEPARADOR = "_"

#: Extensiones con dos partes. Sin esta lista, «archivo.tar.xz» se convertiría
#: en «archivo-tar.xz» y dejaría de acabar en «.tar.xz», con lo cual las
#: acciones que filtran por esa extensión no lo encontrarían.
EXTENSIONES_COMPUESTAS = (
    ".tar.gz", ".tar.xz", ".tar.bz2", ".tar.zst", ".tar.lz", ".tar.lzma",
    ".user.js", ".min.js", ".min.css", ".d.ts",
)


def separar_extension(nombre: str) -> tuple[str, str]:
    """Separa el nombre de su extensión, teniendo en cuenta las compuestas.

    («archivo.tar.xz») -> («archivo», «.tar.xz»)
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



def sin_acentos(texto: str) -> str:
    """Quita los acentos: «Introducció» -> «Introduccio»."""
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def slug(texto: str) -> str:
    """Convierte un texto en un nombre corto y sin sorpresas.

    «Pràctica 1. Entitats, atributs i valors» -> «practica-1-entitats-atributs-i-valors»

    Se quitan los acentos, todo lo que no sean letras o números se cambia por
    un guion, y los guiones repetidos se colapsan en uno solo.
    """
    limpio = sin_acentos(texto).lower()
    slug_ = PERMITIDOS.sub("-", limpio)
    return slug_.strip("-")


def normalizar(nombre: str, clave: str) -> str:
    """Devuelve el nombre canónico de un fichero para una carpeta concreta.

    «Pràctica 1. Entitats.pdf» con la clave «bbdd» ->
    «bbdd_practica-1-entitats.pdf»

    Si el nombre ya es canónico (empieza por la clave y el resto es un slug),
    se devuelve tal cual: normalizar dos veces no cambia nada.
    """
    nombre = nombre.strip()
    base, extension = separar_extension(nombre)

    clave_slug = slug(clave) or "sin-clave"

    # Si el nombre ya lleva la clave delante, se quita antes de normalizar el
    # resto: si no, la clave se slugificaría y se acabaría duplicando.
    if base.lower().startswith(clave_slug.lower()):
        resto = base[len(clave_slug):].lstrip(SEPARADOR).lstrip("-")
    else:
        resto = base

    resto_slug = slug(resto) or "sin-nombre"

    return f"{clave_slug}{SEPARADOR}{resto_slug}{extension.lower()}"

