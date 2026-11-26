"""El motor: elige los ficheros que cumplen el filtro y se los pasa a la acción.

El motor no sabe qué hace cada acción (eso lo sabe cada subclase de Accion) ni
cómo se pinta el resultado (eso lo sabe la CLI). Solo orchestrationa.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from .acciones import Accion, Resultado
from .errores import TareasError


class Motor:
    """Ejecuta acciones sobre carpetas."""

    def __init__(self, acciones: list[dict]) -> None:
        self.acciones = {a["nombre"]: Accion.desde_config(a) for a in acciones}

    @staticmethod
    def seleccionar(carpeta: Path, filtro: dict) -> list[Path]:
        """Devuelve los ficheros de la carpeta que cumplen TODOS los filtros.

        No baja a las subcarpetas: solo mira lo que hay en el primer nivel.
        """
        extensiones = [e.lower() for e in filtro.get("extensiones", [])]
        patron = re.compile(filtro["patron"], re.IGNORECASE) if filtro.get("patron") else None
        dias = filtro.get("mas_antiguo_que_dias")
        megabytes = filtro.get("mayor_que_mb")
        ahora = time.time()

        elegidos: list[Path] = []
        try:
            entradas = sorted(carpeta.iterdir(), key=lambda p: p.name.lower())
        except OSError as exc:
            raise TareasError(
                f"No puedo leer la carpeta «{carpeta}»: {exc.strerror or exc}."
            ) from exc

        for fichero in entradas:
            try:
                if not fichero.is_file():
                    continue
                nombre = fichero.name.lower()
                # Se comparan las extensiones por sufijo del nombre, no con
                # Path.suffix: así «.tar.gz» también funciona, que es un
                # sufijo doble y Path.suffix solo devolvería «.gz».
                if extensiones and not any(nombre.endswith(e) for e in extensiones):
                    continue
                if patron and not patron.search(fichero.name):
                    continue
                datos = fichero.stat()
                if dias is not None and ahora - datos.st_mtime < dias * 86400:
                    continue
                if megabytes is not None and datos.st_size < megabytes * 1024 * 1024:
                    continue
            except OSError:
                # Enlace roto, fichero borrado entre medias o sin permisos:
                # lo saltamos sin romper la acción entera.
                continue
            elegidos.append(fichero)
        return elegidos

    def ejecutar(self, nombre: str, carpeta: Path | None, simular: bool) -> list[Resultado]:
        """Ejecuta la acción indicada sobre la carpeta (o la que diga su «origen»)."""
        accion = self.acciones.get(nombre)
        if accion is None:
            raise TareasError(
                f"No hay ninguna acción «{nombre}». Mira las que hay con: tareas acciones"
            )

        origen = accion.config.get("origen")
        destino = carpeta if carpeta is not None else (Path(origen) if origen else Path("."))
        try:
            destino = destino.expanduser()
        except RuntimeError as exc:
            raise TareasError(
                "No sé dónde está tu carpeta personal: el sistema no ha podido resolver «~»."
            ) from exc

        if not destino.is_dir():
            raise TareasError(f"La carpeta «{destino}» no existe o no es una carpeta.")

        ficheros = self.seleccionar(destino, accion.config.get("filtro") or {})
        return accion.ejecutar(ficheros, simular)
