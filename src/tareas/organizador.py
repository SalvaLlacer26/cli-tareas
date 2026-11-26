"""El organizador: reparte una carpeta en las carpetas de asignatura y la devuelve.

Son dos operaciones inversas:

- ``organizar``: mira cada fichero de la carpeta de descargas, decide a qué
  asignatura pertenece y lo mueve allí **renombrándolo** a un formato que el
  CLI entiende (prefijo de la clave + nombre limpio). Si el nombre no dice
  nada, se mira el resumen de texto que va al lado; si tampoco, el fichero va
  a la carpeta de respaldo.

- ``desorganizar``: deshace lo anterior, devolviendo los ficheros a la
  carpeta de descargas con su nombre original (que se recupera del manifiesto).

Las dos son reversibles porque el manifiesto recuerda de dónde salió cada
fichero.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .acciones import ERROR, HECHO, SIMULADO, Resultado, destino_libre
from .carpetas import Carpeta, clasificar
from .errores import TareasError
from .manifiesto import Manifiesto
from .nombres import normalizar

#: Extensión del resumen de texto que va al lado de un documento.
EXTENSION_RESUMEN = ".md"

#: Cuántos caracteres de un resumen se leen. Es un fichero de texto pequeño,
#: pero no hace falta leerlo entero para clasificar.
MAXIMO_RESUMEN = 20000


def _leer_resumen(carpeta: Path, base: str) -> str | None:
    """Lee el resumen que va al lado del fichero, si lo hay."""
    resumen = carpeta / f"{base}{EXTENSION_RESUMEN}"
    if not resumen.is_file():
        return None
    try:
        texto = resumen.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    return texto[:MAXIMO_RESUMEN]


def _es_resumen_suelto(carpeta: Path, fichero: Path) -> bool:
    """Si este .md es el resumen de otro fichero, no se organiza por su cuenta."""
    if fichero.suffix.lower() != EXTENSION_RESUMEN:
        return False
    return any(
        otro.stem == fichero.stem and otro.suffix.lower() != EXTENSION_RESUMEN
        for otro in carpeta.iterdir()
        if otro.is_file()
    )


class Organizador:
    """Reparte los ficheros de una carpeta entre las carpetas de asignatura."""

    def __init__(self, carpetas: list[Carpeta], manifiesto: Manifiesto | None = None) -> None:
        self.carpetas = carpetas
        self.manifiesto = manifiesto if manifiesto is not None else Manifiesto()

    def organizar(self, origen: Path, simular: bool) -> list[Resultado]:
        """Clasifica y renombra todo lo que hay en «origen»."""
        origen = origen.expanduser()
        if not origen.is_dir():
            raise TareasError(f"La carpeta «{origen}» no existe o no es una carpeta.")

        try:
            entradas = sorted(origen.iterdir(), key=lambda p: p.name.lower())
        except OSError as exc:
            raise TareasError(
                f"No puedo leer la carpeta «{origen}»: {exc.strerror or exc}."
            ) from exc

        resultados: list[Resultado] = []
        for fichero in entradas:
            if not fichero.is_file():
                continue
            if _es_resumen_suelto(origen, fichero):
                # Es el resumen de otro fichero: se moverá con él.
                continue
            resultados.extend(self._organizar_fichero(origen, fichero, simular))

        if not simular:
            self.manifiesto.guardar()
        return resultados

    def _organizar_fichero(self, origen: Path, fichero: Path, simular: bool) -> list[Resultado]:
        """Clasifica un fichero (y su resumen, si tiene) y los mueve."""
        resumen = _leer_resumen(origen, fichero.stem)
        carpeta = clasificar(self.carpetas, fichero.name, resumen)

        nombre_nuevo = normalizar(fichero.name, carpeta.clave)
        destino = destino_libre(carpeta.destino / nombre_nuevo)

        resultados = [self._mover(fichero, destino, simular)]
        if not resultados[0].estado == ERROR:
            self.manifiesto.registrar(destino, fichero.name)

        # El resumen de texto viaja con su documento.
        if resumen is not None:
            resumen_origen = origen / f"{fichero.stem}{EXTENSION_RESUMEN}"
            resumen_destino = destino.with_name(f"{destino.stem}{EXTENSION_RESUMEN}")
            resultados.append(self._mover(resumen_origen, resumen_destino, simular))
            if not resultados[-1].estado == ERROR:
                self.manifiesto.registrar(resumen_destino, resumen_origen.name)

        return resultados

    @staticmethod
    def _mover(origen: Path, destino: Path, simular: bool) -> Resultado:
        if simular:
            return Resultado(origen, destino, SIMULADO)
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(origen), str(destino))
        except OSError as exc:
            return Resultado(origen, None, ERROR, exc.strerror or str(exc))
        return Resultado(origen, destino, HECHO)


class Desorganizador:
    """Devuelve los ficheros clasificados a la carpeta de descargas."""

    def __init__(self, carpetas: list[Carpeta], manifiesto: Manifiesto | None = None) -> None:
        self.carpetas = carpetas
        self.manifiesto = manifiesto if manifiesto is not None else Manifiesto()

    def desorganizar(self, destino: Path, simular: bool) -> list[Resultado]:
        """Trae de vuelta todo lo que hay en las carpetas de asignatura."""
        destino = destino.expanduser()
        resultados: list[Resultado] = []

        for carpeta in self.carpetas:
            if not carpeta.destino.is_dir():
                continue
            try:
                entradas = sorted(carpeta.destino.iterdir(), key=lambda p: p.name.lower())
            except OSError as exc:
                raise TareasError(
                    f"No puedo leer la carpeta «{carpeta.destino}»: {exc.strerror or exc}."
                ) from exc

            for fichero in entradas:
                if not fichero.is_file():
                    continue
                resultados.append(self._devolver(fichero, destino, simular))

        if not simular:
            self.manifiesto.guardar()
        return resultados

    def _devolver(self, fichero: Path, destino: Path, simular: bool) -> Resultado:
        """Devuelve un fichero a la carpeta de descargas con su nombre original."""
        original = self.manifiesto.nombre_original(fichero)
        nombre = original if original else fichero.name
        final = destino_libre(destino / nombre)

        if simular:
            return Resultado(fichero, final, SIMULADO)

        try:
            destino.mkdir(parents=True, exist_ok=True)
            shutil.move(str(fichero), str(final))
        except OSError as exc:
            return Resultado(fichero, None, ERROR, exc.strerror or str(exc))

        self.manifiesto.olvidar(fichero)
        return Resultado(fichero, final, HECHO)
