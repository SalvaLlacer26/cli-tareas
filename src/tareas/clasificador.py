"""Decidir de qué asignatura es un documento.

Se usan dos señales y se cuentan, no se aplica «la primera que coincida»:

1. El **nombre** del fichero: si dice «A21_IntroduccióGit_GitHub.pdf», es de
   Entornos de Desarrollo.
2. El **contenido**: si el nombre no dice nada, el texto del documento suele
   decirlo («SISTEMES INFORMÀTICS» en la primera página).

Gana la carpeta con más aciertos. Si no hay ninguna, el documento queda
«sin clasificar»; si el formato no se puede leer, «formato invalido».
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .errores import CarpetaNoValida


@dataclass
class Carpeta:
    """Una carpeta de destino: una asignatura, o la de respaldo."""

    clave: str
    etiqueta: str
    destino: Path
    patrones: list[str] = field(default_factory=list)
    respaldo: bool = False

    def puntua(self, texto: str) -> int:
        """Cuánto evidencia aporta este texto para esta carpeta.

        No cuenta solo cuántos patrones aparecen, sino **cuánto pesan**:

        - Un patrón de varias palabras («projecte intermodular») dice mucho más
          que uno corto («git»), y «git» dentro de «github» no cuenta como una
          prueba aparte.
        - Un patrón que aparece en la **cabecera** del documento (el título)
          pesa el doble que uno que sale a mitad del texto: el título dice de
          qué va el documento; una mención suelta puede ser de cualquier cosa.
        """
        if not texto:
            return 0
        puntos = 0
        for patron in self.patrones:
            try:
                encontrada = re.search(patron, texto, re.IGNORECASE)
            except re.error:
                continue
            if not encontrada:
                continue
            peso = peso_de(patron)
            if encontrada.start() < ZONA_TITULO:
                peso *= 2
            puntos += peso
        return puntos

    def coincide(self, texto: str) -> bool:
        return self.puntua(texto) > 0


def peso_de(patron: str) -> int:
    """Cuánto pesa un patrón: las frases largas son pruebas más fuertes."""
    if " " in patron or "-" in patron:
        return 3
    if len(patron) >= 5:
        return 2
    return 1


#: Puntuación mínima para clasificar **por el contenido**. Por el nombre
#: basta con un golpe: el nombre lo ha puesto la persona, no el azar.
MINIMO_POR_CONTENIDO = 2

#: Los primeros caracteres del documento, donde suele estar el título. Un
#: patrón que aparece aquí pesa el doble.
ZONA_TITULO = 120


def cargar_carpetas(datos: dict) -> list[Carpeta]:
    """Construye las carpetas a partir de la sección «carpetas» del config."""
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

        for patron in patrones:
            try:
                re.compile(patron)
            except re.error as exc:
                raise CarpetaNoValida(clave, "patrones", f"«{patron}» no es una expresión regular válida: {exc}") from exc

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


def mejor_carpeta(carpetas: list[Carpeta], texto: str, minimo: int = 1) -> Carpeta | None:
    """La carpeta que mejor reconoce el texto, o None si ninguna.

    Gana la que más evidencia aporta. Si dos empatan, gana la primera del
    fichero de configuración: el orden lo pone el usuario.
    """
    mejor: Carpeta | None = None
    mejor_puntos = 0
    for carpeta in carpetas:
        if carpeta.respaldo:
            continue
        puntos = carpeta.puntua(texto)
        if puntos >= minimo and puntos > mejor_puntos:
            mejor = carpeta
            mejor_puntos = puntos
    return mejor


@dataclass
class Diagnostico:
    """Lo que el clasificador ha deducido de un documento."""

    carpeta: Carpeta | None
    estado: str
    motivo: str = ""
    por_nombre: str = ""
    por_contenido: str = ""


def clasificar(carpetas: list[Carpeta], nombre: str, contenido: str = "") -> Diagnostico:
    """Clasifica un documento por su nombre y su contenido.

    El nombre manda: si el nombre dice «git», el documento es de Entornos
    aunque dentro se mentione SQL. El contenido solo entra cuando el nombre
    no dice nada, que es justo el caso difícil.
    """
    from .ficha import CLASIFICADO, FORMATO_INVALIDO, SIN_CLASIFICAR

    por_nombre = mejor_carpeta(carpetas, nombre)
    if por_nombre is not None:
        return Diagnostico(
            carpeta=por_nombre,
            estado=CLASIFICADO,
            por_nombre=por_nombre.etiqueta,
            por_contenido=por_contenido(carpetas, contenido),
        )

    por_texto = mejor_carpeta(carpetas, contenido, minimo=MINIMO_POR_CONTENIDO)
    if por_texto is not None:
        return Diagnostico(
            carpeta=por_texto,
            estado=CLASIFICADO,
            por_contenido=por_texto.etiqueta,
        )

    respaldo = de_respaldo(carpetas)
    if respaldo is None:
        raise CarpetaNoValida(
            "carpetas", "no hay ninguna carpeta de respaldo para lo que no se sepa clasificar"
        )

    return Diagnostico(
        carpeta=respaldo,
        estado=SIN_CLASIFICAR,
        motivo="ni el nombre ni el contenido indican de qué asignatura es",
        por_contenido=por_contenido(carpetas, contenido),
    )


def por_contenido(carpetas: list[Carpeta], contenido: str) -> str:
    """La carpeta que mejor encaja con el contenido (para mostrarla)."""
    if not contenido:
        return ""
    encontrada = mejor_carpeta(carpetas, contenido)
    return encontrada.etiqueta if encontrada else ""


def formato_invalido(motivo: str) -> Diagnostico:
    """El diagnóstico de un documento cuyo formato no se puede leer."""
    from .ficha import FORMATO_INVALIDO

    return Diagnostico(carpeta=None, estado=FORMATO_INVALIDO, motivo=motivo)
