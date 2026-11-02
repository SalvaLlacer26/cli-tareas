"""El comando «organizar» y el comando «deshacer».

«organizar» lee las fichas .md de la carpeta oculta «md», y mueve cada
documento a la carpeta de su asignatura. Al moverlo **devuelve el nombre
original**: el renombrado que hizo «analizar» era solo para trabajar cómodo,
así que el fichero acaba en su destino con el nombre que tenía.

«deshacer» hace lo contrario: devuelve los documentos a la carpeta de origen
con su nombre original. La carpeta de fichas se conserva, porque es el
historial del análisis.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import ficha as fichas
from .errores import TareasError
from .nombres import sin_conflicto

#: Carpeta donde se guardan las fichas .md.
CARPETA_FICHAS = "md"


@dataclass
class Movimiento:
    """Un fichero que se ha movido."""

    nombre_original: str
    origen: str
    destino: str
    estado: str = "movido"


@dataclass
class ResultadoOrganizacion:
    """Lo que ha hecho una organización o una deshacedura."""

    movimientos: list[Movimiento] = field(default_factory=list)
    por_carpeta: dict[str, int] = field(default_factory=dict)
    sin_ficha: list[str] = field(default_factory=list)
    ya_organizado: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.movimientos)


def _fichas_de(carpeta: Path) -> list[Path]:
    """Las fichas .md de la carpeta «md»."""
    directorio = carpeta / CARPETA_FICHAS
    if not directorio.is_dir():
        return []
    return sorted(directorio.glob("*.md"), key=lambda p: p.name.lower())


def _buscar_fichas(carpeta: Path, carpetas: list | None = None) -> list[Path]:
    """Busca las fichas en la carpeta «md» y en las de sus subcarpetas.

    Después de «organizar» las fichas están en la carpeta «md» de cada
    asignatura, que es hermana de la carpeta de origen y no está dentro de
    ella. Por eso se buscan también en las carpetas de destino que declara la
    configuración: así «deshacer» funciona se ejecute desde donde se ejecute.
    """
    candidatas: list[Path] = [carpeta]
    candidatas += sorted(
        (d for d in carpeta.rglob(CARPETA_FICHAS) if d.is_dir()), key=lambda p: str(p)
    )
    for definicion in carpetas or []:
        candidatas.append(definicion.destino)
        candidatas += sorted(
            (d for d in definicion.destino.rglob(CARPETA_FICHAS) if d.is_dir()),
            key=lambda p: str(p),
        )

    encontradas: list[Path] = []
    vistos: set[Path] = set()
    for base in candidatas:
        directorio = base / CARPETA_FICHAS
        if directorio in vistos or not directorio.is_dir():
            continue
        vistos.add(directorio)
        for ruta in sorted(directorio.glob("*.md"), key=lambda p: p.name.lower()):
            if ruta not in encontradas:
                encontradas.append(ruta)
    return encontradas


def organizar(carpeta: Path) -> ResultadoOrganizacion:
    """Reparte los documentos de una carpeta según sus fichas."""
    carpeta = Path(carpeta).expanduser()
    if not carpeta.is_dir():
        raise TareasError(f"La carpeta «{carpeta}» no existe o no es una carpeta.")

    resultado = ResultadoOrganizacion()
    fichas_encontradas = _fichas_de(carpeta)
    if not fichas_encontradas:
        raise TareasError(
            f"No hay fichas en «{carpeta / CARPETA_FICHAS}». "
            "Ejecuta primero «tareas analizar» en esta carpeta."
        )

    for ruta_ficha in fichas_encontradas:
        ficha = fichas.leer(ruta_ficha)

        if ficha.estado == fichas.FORMATO_INVALIDO:
            resultado.sin_ficha.append(ficha.nombre_original)
            continue

        origen = carpeta / ficha.nombre_compatible
        if not origen.exists():
            # Ya no está aquí: puede que esté en su carpeta de destino.
            resultado.ya_organizado.append(ficha.nombre_original)
            continue

        destino_carpeta = Path(ficha.destino) if ficha.destino else None
        if destino_carpeta is None or not ficha.carpeta:
            resultado.sin_ficha.append(ficha.nombre_original)
            continue

        destino_carpeta.mkdir(parents=True, exist_ok=True)
        destino = destino_carpeta / ficha.nombre_original
        destino = sin_conflicto(destino_carpeta, ficha.nombre_original)

        try:
            shutil.move(str(origen), str(destino))
        except OSError as exc:
            raise TareasError(
                f"No puedo mover «{ficha.nombre_original}» a «{destino_carpeta}»: "
                f"{exc.strerror or exc}."
            ) from exc

        # La ficha viaja con su documento, en la carpeta oculta del destino.
        destino_fichas = destino_carpeta / CARPETA_FICHAS
        destino_fichas.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(ruta_ficha), str(destino_fichas / ruta_ficha.name))
        except OSError:
            pass

        resultado.movimientos.append(
            Movimiento(
                nombre_original=ficha.nombre_original,
                origen=str(origen),
                destino=str(destino),
            )
        )
        resultado.por_carpeta[ficha.carpeta] = resultado.por_carpeta.get(ficha.carpeta, 0) + 1

    return resultado


def deshacer(carpeta: Path, carpetas: list | None = None) -> ResultadoOrganizacion:
    """Devuelve los documentos a su carpeta de origen.

    La carpeta de fichas no se borra: sus ficheros vuelven a la carpeta «md»
    de la carpeta de origen, así que el análisis se conserva y se puede volver
    a organizar sin analizar otra vez.
    """
    carpeta = Path(carpeta).expanduser()
    if not carpeta.is_dir():
        raise TareasError(f"La carpeta «{carpeta}» no existe o no es una carpeta.")

    resultado = ResultadoOrganizacion()
    rutas_fichas = _buscar_fichas(carpeta, carpetas)
    if not rutas_fichas:
        raise TareasError(
            f"No hay fichas en «{carpeta}». No se puede deshacer nada aquí."
        )

    for ruta_ficha in rutas_fichas:
        ficha = fichas.leer(ruta_ficha)
        if not ficha.destino:
            continue

        origen = Path(ficha.destino) / ficha.nombre_original
        if not origen.exists():
            resultado.ya_organizado.append(ficha.nombre_original)
            continue

        destino_carpeta = Path(ficha.origen) if ficha.origen else carpeta
        destino_carpeta.mkdir(parents=True, exist_ok=True)
        destino = sin_conflicto(destino_carpeta, ficha.nombre_original)

        try:
            shutil.move(str(origen), str(destino))
        except OSError as exc:
            raise TareasError(
                f"No puedo devolver «{ficha.nombre_original}» a «{destino_carpeta}»: "
                f"{exc.strerror or exc}."
            ) from exc

        # La ficha se conserva: vuelve a la carpeta «md» de la carpeta de origen.
        destino_fichas = destino_carpeta / CARPETA_FICHAS
        destino_fichas.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(ruta_ficha), str(destino_fichas / ruta_ficha.name))
        except OSError:
            pass

        resultado.movimientos.append(
            Movimiento(
                nombre_original=ficha.nombre_original,
                origen=str(origen),
                destino=str(destino),
                estado="devuelto",
            )
        )
        etiqueta = ficha.carpeta or "origen"
        resultado.por_carpeta[etiqueta] = resultado.por_carpeta.get(etiqueta, 0) + 1

    return resultado
