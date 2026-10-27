"""Clases que saben hacer una cosa cada una.

La clase base Accion define lo que toda acción sabe hacer (ejecutar sobre una
lista de ficheros) y cada subclase (Mover, Copiar, Renombrar, Borrar) solo
implementa lo suyo (aplicar a un fichero). La fábrica Accion.desde_config
devuelve la clase que toca a partir del diccionario del JSON, así que el
motor no necesita un if/elif por tipo: añadir un tipo es escribir una
subclase más.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .errores import AccionNoValida

#: Estados posibles de un fichero tras pasar por una acción.
HECHO = "hecho"
SIMULADO = "simulado"
SALTADO = "saltado"


@dataclass
class Resultado:
    """Qué le pasó a un fichero: de dónde vino, a dónde iba y en qué estado."""

    origen: Path
    destino: Path | None
    estado: str


def destino_libre(destino: Path) -> Path:
    """Devuelve un destino que no existe, añadiendo « (1)», « (2)»… si hace falta.

    Nunca sobrescribimos un fichero: si el destino ya existe, se busca el
    siguiente número libre.
    """
    libre = destino
    numero = 1
    while libre.exists():
        libre = destino.with_name(f"{destino.stem} ({numero}){destino.suffix}")
        numero += 1
    return libre


class Accion(ABC):
    """Base de todas las acciones."""

    #: Identificador del tipo, tal y como aparece en acciones.json.
    tipo = ""

    #: Si es True, la acción es destructiva y pide confirmación.
    destructiva = False

    #: Registro de subclases: cada una se apunta sola al crearse.
    _registro: dict[str, type[Accion]] = {}

    def __init__(self, config: dict) -> None:
        self.nombre = config["nombre"]
        self.descripcion = config["descripcion"]
        self.config = config

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls.tipo:
            Accion._registro[cls.tipo] = cls

    @staticmethod
    def desde_config(config: dict) -> Accion:
        """Fábrica: del diccionario del JSON a la clase que lo ejecuta."""
        clase = Accion._registro.get(config.get("tipo", ""))
        if clase is None:
            raise AccionNoValida(
                config.get("nombre", "?"), "tipo", "no hay ninguna clase para ese tipo"
            )
        return clase(config)

    def ejecutar(self, ficheros: list[Path], simular: bool) -> list[Resultado]:
        """Aplica la acción a cada fichero y devuelve el informe."""
        return [self.aplicar(fichero, numero, simular) for numero, fichero in enumerate(ficheros, start=1)]

    @abstractmethod
    def aplicar(self, fichero: Path, numero: int, simular: bool) -> Resultado:
        """Aplica la acción a un solo fichero. La implementa cada subclase."""

    def _ruta(self, valor: str) -> Path:
        """Convierte una ruta del JSON en Path, expandiendo ~."""
        return Path(valor).expanduser()


class Mover(Accion):
    """Mueve ficheros de una carpeta a otra."""

    tipo = "mover"

    def aplicar(self, fichero: Path, numero: int, simular: bool) -> Resultado:
        destino = self._ruta(self.config["destino"]) / fichero.name
        destino = destino_libre(destino)
        if not simular:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(fichero), str(destino))
        return Resultado(fichero, destino, SIMULADO if simular else HECHO)


class Copiar(Accion):
    """Copia ficheros a otra carpeta y deja el original donde estaba."""

    tipo = "copiar"

    def aplicar(self, fichero: Path, numero: int, simular: bool) -> Resultado:
        destino = self._ruta(self.config["destino"]) / fichero.name
        destino = destino_libre(destino)
        if not simular:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(fichero), str(destino))
        return Resultado(fichero, destino, SIMULADO if simular else HECHO)


class Renombrar(Accion):
    """Renombra ficheros en su sitio con una plantilla."""

    tipo = "renombrar"

    def aplicar(self, fichero: Path, numero: int, simular: bool) -> Resultado:
        fecha = datetime.fromtimestamp(fichero.stat().st_mtime)
        nuevo = self.config["plantilla"].format(
            fecha=fecha,
            n=numero,
            ext=fichero.suffix.lower(),
            nombre=fichero.stem,
        )
        if nuevo == fichero.name:
            return Resultado(fichero, None, SALTADO)
        destino = destino_libre(fichero.with_name(nuevo))
        if not simular:
            fichero.rename(destino)
        return Resultado(fichero, destino, SIMULADO if simular else HECHO)


class Borrar(Accion):
    """Borra ficheros. Siempre pide confirmación salvo que se pase --si."""

    tipo = "borrar"
    destructiva = True

    def aplicar(self, fichero: Path, numero: int, simular: bool) -> Resultado:
        if not simular:
            fichero.unlink()
        return Resultado(fichero, None, SIMULADO if simular else HECHO)
