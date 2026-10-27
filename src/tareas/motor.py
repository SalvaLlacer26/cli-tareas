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
        """Devuelve los ficheros de la carpeta que cumplen TODOS los filtros."""
        extensiones = {e.lower() for e in filtro.get("extensiones", [])}
        patron = re.compile(filtro["patron"]) if filtro.get("patron") else None
        dias = filtro.get("mas_antiguo_que_dias")
        megabytes = filtro.get("mayor_que_mb")
        ahora = time.time()

        elegidos: list[Path] = []
        for fichero in sorted(carpeta.iterdir(), key=lambda p: p.name.lower()):
            if not fichero.is_file():
                continue
            if extensiones and fichero.suffix.lower() not in extensiones:
                continue
            if patron and not patron.search(fichero.name):
                continue
            if dias is not None:
                if ahora - fichero.stat().st_mtime < dias * 86400:
                    continue
            if megabytes is not None:
                if fichero.stat().st_size < megabytes * 1024 * 1024:
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
        destino = destino.expanduser()

        if not destino.is_dir():
            raise TareasError(f"La carpeta «{destino}» no existe o no es una carpeta.")

        ficheros = self.seleccionar(destino, accion.config.get("filtro", {}))
        return accion.ejecutar(ficheros, simular)
