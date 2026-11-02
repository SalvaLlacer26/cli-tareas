"""El comando «analizar»: leer la carpeta, renombrar lo que estorba y hacer fichas.

En tres pasos:

1. Se recorre la carpeta y se extrae el contenido de cada fichero. Lo que no
   se puede leer (un `.deb`, una imagen) se marca como «formato invalido».
2. Se renombran los ficheros con nombres incompatibles (con tildes, espacios
   o caracteres raros) para que las herramientas los traten bien. El nombre
   original se guarda en la ficha, así que luego se puede restituir.
3. Se escribe una ficha .md por documento en la carpeta oculta «md», con los
   datos que hacen falta para clasificar y para resumir.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import ficha as fichas
from .clasificador import Carpeta, clasificar
from .contenido import extraer
from .errores import TareasError
from .nombres import compatible, sin_conflicto

#: Carpeta donde se guardan las fichas .md.
CARPETA_FICHAS = "md"


@dataclass
class Fila:
    """Una fila de la tabla que ve el usuario."""

    nombre_original: str
    nombre_compatible: str
    asignatura: str
    destino: str
    estado: str
    motivo: str = ""


@dataclass
class ResultadoAnalisis:
    """Lo que ha hecho el análisis de una carpeta."""

    filas: list[Fila]
    renombrados: list[tuple[str, str]]
    fichas: int
    invalidos: int
    sin_clasificar: int

    @property
    def analizables(self) -> int:
        return len(self.filas) - self.invalidos


def analizar(
    carpeta: Path,
    carpetas: list[Carpeta],
    destino_base: Path | None = None,
) -> ResultadoAnalisis:
    """Analiza una carpeta: renombra, extrae, clasifica y escribe las fichas.

    No toca nada fuera de la carpeta que se le pasa.
    """
    carpeta = Path(carpeta).expanduser()
    if not carpeta.is_dir():
        raise TareasError(f"La carpeta «{carpeta}» no existe o no es una carpeta.")

    try:
        entradas = sorted(carpeta.iterdir(), key=lambda p: p.name.lower())
    except OSError as exc:
        raise TareasError(f"No puedo leer la carpeta «{carpeta}»: {exc.strerror or exc}.") from exc

    # Se analizan todos los ficheros de la carpeta, incluidos los .md: las
    # fichas que genera este comando viven en la subcarpeta «md», que no se
    # recorre porque es una carpeta.
    documentos = [e for e in entradas if e.is_file()]
    directorio_fichas = carpeta / CARPETA_FICHAS

    filas: list[Fila] = []
    renombrados: list[tuple[str, str]] = []
    invalidos = 0
    sin_clasificar = 0

    for documento in documentos:
        contenido = extraer(documento)
        nombre_original = documento.name

        nombre_compatible = compatible(nombre_original)
        if nombre_compatible != nombre_original:
            destino = sin_conflicto(carpeta, nombre_compatible)
            try:
                documento.rename(destino)
            except OSError as exc:
                raise TareasError(
                    f"No puedo renombrar «{nombre_original}»: {exc.strerror or exc}."
                ) from exc
            renombrados.append((nombre_original, destino.name))
            documento = destino
            nombre_compatible = destino.name

        ficha = fichas.Ficha(
            nombre_original=nombre_original,
            nombre_compatible=nombre_compatible,
            formato=contenido.formato,
        )

        try:
            ficha.tamano = documento.stat().st_size
        except OSError:
            ficha.tamano = 0
        ficha.origen = str(carpeta)
        ficha.analizado = fichas.ahora()

        if not contenido.analizable:
            invalidos += 1
            ficha.estado = fichas.FORMATO_INVALIDO
            ficha.motivo = contenido.motivo
            ficha.asignatura = "formato invalido"
            ficha.carpeta = ""
            ficha.destino = ""
        else:
            ficha.paginas = contenido.paginas
            ficha.contenido = contenido.texto
            diagnostico = clasificar(carpetas, nombre_original, contenido.texto)
            ficha.estado = diagnostico.estado
            ficha.motivo = diagnostico.motivo
            if diagnostico.carpeta is not None:
                ficha.asignatura = diagnostico.carpeta.etiqueta
                ficha.carpeta = diagnostico.carpeta.clave
                destino_carpeta = diagnostico.carpeta.destino
                if destino_base is not None:
                    destino_carpeta = destino_base / diagnostico.carpeta.clave
                ficha.destino = str(destino_carpeta)
            if diagnostico.estado == fichas.SIN_CLASIFICAR:
                sin_clasificar += 1

        fichas.escribir(ficha, directorio_fichas / f"{nombre_compatible}.md")

        filas.append(
            Fila(
                nombre_original=nombre_original,
                nombre_compatible=nombre_compatible,
                asignatura=ficha.asignatura or "sin clasificar",
                destino=ficha.destino,
                estado=ficha.estado,
                motivo=ficha.motivo,
            )
        )

    return ResultadoAnalisis(
        filas=filas,
        renombrados=renombrados,
        fichas=len(filas),
        invalidos=invalidos,
        sin_clasificar=sin_clasificar,
    )


def ocultar_carpeta(carpeta: Path) -> None:
    """Intenta que la carpeta de las fichas no se vea.

    En Windows se marca con el atributo de «oculto». En Linux y macOS una
    carpeta solo se esconde si el nombre empieza por un punto, y aquí el
    nombre es el que el usuario ha pedido («md»), así que se deja visible.
    """
    import sys

    if sys.platform != "win32":
        return
    try:
        import ctypes

        atributos = ctypes.windll.kernel32.GetFileAttributesW(str(carpeta))
        if atributos != -1:
            ctypes.windll.kernel32.SetFileAttributesW(str(carpeta), atributos | 2)
    except Exception:  # noqa: BLE001 - esconder la carpeta es un extra, no un requisito
        return
