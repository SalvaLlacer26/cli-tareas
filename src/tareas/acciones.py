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

from .config import problema_nombre
from .errores import AccionNoValida, TareasError

#: Estados posibles de un fichero tras pasar por una acción.
HECHO = "hecho"
SIMULADO = "simulado"
SALTADO = "saltado"
ERROR = "error"


@dataclass
class Resultado:
    """Qué le pasó a un fichero: de dónde vino, a dónde iba y en qué estado."""

    origen: Path
    destino: Path | None
    estado: str
    error: str | None = None


def destino_libre(destino: Path, reservados: set[Path] | None = None) -> Path:
    """Devuelve un destino que no existe, añadiendo « (1)», « (2)»… si hace falta.

    Nunca sobrescribimos un fichero: si el destino ya existe, se busca el
    siguiente número libre. Los enlaces simbólicos rotos también cuentan como
    destino ocupado, porque escribir a través de ellos machacaría el fichero
    al que apuntan.

    «reservados» son los nombres ya asignados en esta misma ejecución. Sin
    ellos, una simulación enseñaría el mismo destino para dos ficheros, que
    no es lo que va a pasar de verdad.
    """
    ocupados = reservados or set()
    libre = destino
    numero = 1
    while libre.exists() or libre.is_symlink() or libre in ocupados:
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
        self._reservados: set[Path] = set()

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
        """Aplica la acción a cada fichero y devuelve el informe.

        Un fichero que falla no corta la acción: se anota el error y se sigue
        con el siguiente. Perder el trabajo ya hecho sería peor que un error.
        """
        self._reservados = set()
        return [self.aplicar(fichero, numero, simular) for numero, fichero in enumerate(ficheros, start=1)]

    @abstractmethod
    def aplicar(self, fichero: Path, numero: int, simular: bool) -> Resultado:
        """Aplica la acción a un solo fichero. La implementa cada subclase."""

    def _ruta(self, valor: str) -> Path:
        """Convierte una ruta del JSON en Path, expandiendo ~."""
        try:
            return Path(valor).expanduser()
        except RuntimeError as exc:
            raise TareasError(
                "No sé dónde está tu carpeta personal: el sistema no ha podido resolver «~»."
            ) from exc

    def _error(self, fichero: Path, exc: OSError) -> Resultado:
        """Construye el resultado de un fichero que no se ha podido tocar."""
        motivo = exc.strerror or str(exc)
        return Resultado(fichero, None, ERROR, motivo)


class Mover(Accion):
    """Mueve ficheros de una carpeta a otra."""

    tipo = "mover"

    def aplicar(self, fichero: Path, numero: int, simular: bool) -> Resultado:
        destino = destino_libre(self._ruta(self.config["destino"]) / fichero.name, self._reservados)
        self._reservados.add(destino)
        if not simular:
            try:
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(fichero), str(destino))
            except OSError as exc:
                return self._error(fichero, exc)
        return Resultado(fichero, destino, SIMULADO if simular else HECHO)


class Copiar(Accion):
    """Copia ficheros a otra carpeta y deja el original donde estaba."""

    tipo = "copiar"

    def aplicar(self, fichero: Path, numero: int, simular: bool) -> Resultado:
        destino = destino_libre(self._ruta(self.config["destino"]) / fichero.name, self._reservados)
        self._reservados.add(destino)
        if not simular:
            try:
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(fichero), str(destino))
            except OSError as exc:
                return self._error(fichero, exc)
        return Resultado(fichero, destino, SIMULADO if simular else HECHO)


class Renombrar(Accion):
    """Renombra ficheros en su sitio con una plantilla."""

    tipo = "renombrar"

    def aplicar(self, fichero: Path, numero: int, simular: bool) -> Resultado:
        try:
            fecha = datetime.fromtimestamp(fichero.stat().st_mtime)
        except OSError as exc:
            return self._error(fichero, exc)

        nuevo = self.config["plantilla"].format(
            fecha=fecha,
            n=numero,
            ext=fichero.suffix.lower(),
            nombre=fichero.stem,
        )
        if nuevo == fichero.name:
            return Resultado(fichero, None, SALTADO)

        problema = problema_nombre(nuevo)
        if problema:
            return Resultado(fichero, None, ERROR, f"«{nuevo}» no vale como nombre: {problema}")

        destino = destino_libre(fichero.with_name(nuevo), self._reservados)
        self._reservados.add(destino)
        if not simular:
            try:
                fichero.rename(destino)
            except OSError as exc:
                return self._error(fichero, exc)
        return Resultado(fichero, destino, SIMULADO if simular else HECHO)


class Borrar(Accion):
    """Borra ficheros. Siempre pide confirmación salvo que se pase --si."""

    tipo = "borrar"
    destructiva = True

    def aplicar(self, fichero: Path, numero: int, simular: bool) -> Resultado:
        if not simular:
            try:
                fichero.unlink()
            except OSError as exc:
                return self._error(fichero, exc)
        return Resultado(fichero, None, SIMULADO if simular else HECHO)
