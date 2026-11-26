"""Las carpetas de destino: qué asignatura es cada una y cómo se reconoce.

Una «carpeta» es una asignatura (o la carpeta de respaldo donde va lo que no se
ha podido clasificar). Cada una tiene:

- ``clave``: identificador corto que se pone delante del nombre del fichero
  («bbdd», «sistemes»…). Es lo que hace que el nombre sea interpretable.
- ``etiqueta``: el nombre que ve la persona («Bases de dades»).
- ``destino``: la carpeta donde van los ficheros.
- ``patrones``: palabras o expresiones que señalan esa asignatura.

La clasificación **puntúa**: gana la carpeta con más patrones que aparecen,
no la primera que coincide. Así «Projecte Intermodular 1DAW», que contiene
«projecte» (intermodular) y «github» (entornos), acaba en intermodular y no
en entornos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .errores import CarpetaNoValida


@dataclass
class Carpeta:
    """Una carpeta de destino con sus patrones de reconocimiento."""

    clave: str
    etiqueta: str
    destino: Path
    patrones: list[str] = field(default_factory=list)
    respaldo: bool = False

    def puntua(self, texto: str) -> int:
        """Cuántos de sus patrones aparecen en el texto.

        La clave cuenta siempre: un fichero que ya empieza por «bbdd_» es
        interpretable aunque su nombre no diga nada más.
        """
        if not texto:
            return 0
        puntos = 0
        if re.search(re.escape(self.clave), texto, re.IGNORECASE):
            puntos += 1
        for patron in self.patrones:
            try:
                if re.search(patron, texto, re.IGNORECASE):
                    puntos += 1
            except re.error:
                # Un patrón roto se ignora aquí; config.py lo avisa antes.
                continue
        return puntos

    def coincide(self, texto: str) -> bool:
        """Si esta carpeta reconoce el texto."""
        return self.puntua(texto) > 0


def cargar_carpetas(datos: dict) -> list[Carpeta]:
    """Construye las carpetas a partir de la sección «carpetas» del config.

    Devuelve también la carpeta de respaldo, que es la que recibe lo que no se
    ha podido clasificar. Si no hay ninguna marcada como respaldo, se usa la
    primera que no tenga patrones.
    """
    secciones = datos.get("carpetas")
    if not isinstance(secciones, list) or not secciones:
        raise CarpetaNoValida("carpetas", "falta la lista de carpetas o está vacía")

    carpetas: list[Carpeta] = []
    claves: set[str] = set()
    for seccion in secciones:
        if not isinstance(seccion, dict):
            raise CarpetaNoValida("carpetas", "cada carpeta debe ser un objeto")
        clave = seccion.get("clave")
        if not isinstance(clave, str) or not clave.strip():
            raise CarpetaNoValida("carpetas", "cada carpeta necesita una «clave»")
        if clave in claves:
            raise CarpetaNoValida(clave, "clave", "está repetida")
        claves.add(clave)
        etiqueta = seccion.get("etiqueta", clave)
        destino = seccion.get("destino")
        if not isinstance(destino, str) or not destino.strip():
            raise CarpetaNoValida(clave, "destino", "es obligatorio y tiene que ser una ruta")
        patrones = seccion.get("patrones", [])
        if not isinstance(patrones, list) or not all(isinstance(p, str) for p in patrones):
            raise CarpetaNoValida(clave, "patrones", "tiene que ser una lista de textos")
        carpetas.append(
            Carpeta(
                clave=clave,
                etiqueta=str(etiqueta),
                destino=Path(destino).expanduser(),
                patrones=list(patrones),
                respaldo=bool(seccion.get("respaldo", False)),
            )
        )

    if not any(c.respaldo for c in carpetas):
        sin_patrones = [c for c in carpetas if not c.patrones]
        if sin_patrones:
            sin_patrones[0].respaldo = True

    return carpetas


def de_respaldo(carpetas: list[Carpeta]) -> Carpeta | None:
    """La carpeta donde va lo que no se ha podido clasificar."""
    for carpeta in carpetas:
        if carpeta.respaldo:
            return carpeta
    return None


def mejor_carpeta(carpetas: list[Carpeta], texto: str) -> Carpeta | None:
    """La carpeta que mejor reconoce el texto, o None si ninguna.

    Gana la que más patrones acierta. Si dos empatan, gana la primera del
    fichero de configuración: el orden lo pone el usuario.
    """
    mejor: Carpeta | None = None
    mejor_puntos = 0
    for carpeta in carpetas:
        if carpeta.respaldo:
            continue
        puntos = carpeta.puntua(texto)
        if puntos > mejor_puntos:
            mejor = carpeta
            mejor_puntos = puntos
    return mejor


def clasificar(carpetas: list[Carpeta], nombre: str, resumen: str | None = None) -> Carpeta:
    """Decide en qué carpeta va un fichero.

    Primero se mira el nombre. Si el nombre no dice nada (que es justo el caso
    «no interpretable»), se mira el resumen de texto que va al lado, que es
    mucho más barato de leer que el PDF original. Si tampoco hay nada, el
    fichero va a la carpeta de respaldo.
    """
    por_nombre = mejor_carpeta(carpetas, nombre)
    if por_nombre is not None:
        return por_nombre

    if resumen:
        por_resumen = mejor_carpeta(carpetas, resumen)
        if por_resumen is not None:
            return por_resumen

    respaldo = de_respaldo(carpetas)
    if respaldo is None:
        raise CarpetaNoValida("carpetas", "no hay ninguna carpeta de respaldo para lo que no se sepa clasificar")
    return respaldo
