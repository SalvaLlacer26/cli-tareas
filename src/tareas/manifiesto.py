"""El manifiesto: acordarse de cómo se llamaba cada fichero.

Cuando `tareas organizar` renombra un fichero para que su nombre sea
interpretable, el nombre original se guarda aquí. Así `tareas desorganizar`
puede devolver los ficheros a la carpeta de descargas **tal como estaban** y
el viaje de ida y vuelta no pierde nada.

El manifiesto se guarda en la carpeta de estado del usuario, que platformdirs
devuelve correcta en Linux, Windows y macOS:

- Linux/macOS: ``~/.local/state/tareas/manifiesto.json``
- Windows: ``%LOCALAPPDATA%\\tareas\\state\\manifiesto.json``
"""

from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_state_dir

from .errores import TareasError

NOMBRE_ARCHIVO = "manifiesto.json"


class Manifiesto:
    """Guarda el nombre original de los ficheros que se han renombrado."""

    def __init__(self, ruta: Path | None = None) -> None:
        self.ruta = ruta if ruta is not None else Path(user_state_dir("tareas")) / NOMBRE_ARCHIVO
        self.entradas: dict[str, str] = {}
        self._cargado = False

    def cargar(self) -> None:
        """Lee el manifiesto del disco. Si no existe, se empieza vacío."""
        if self._cargado:
            return
        self._cargado = True
        if not self.ruta.is_file():
            return
        try:
            datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Un manifiesto ilegible no puede ser motivo para que la herramienta
            # no funcione: se empieza de cero.
            return
        entradas = datos.get("entradas") if isinstance(datos, dict) else None
        if isinstance(entradas, dict):
            self.entradas = {str(k): str(v) for k, v in entradas.items()}

    def registrar(self, destino: Path, nombre_original: str) -> None:
        """Apunta que en «destino» había un fichero que se llamaba así."""
        self.cargar()
        self.entradas[str(destino)] = nombre_original

    def nombre_original(self, destino: Path) -> str | None:
        """Cómo se llamaba el fichero que ahora está en «destino»."""
        self.cargar()
        return self.entradas.get(str(destino))

    def olvidar(self, destino: Path) -> None:
        """Quita una entrada (el fichero ya no está donde estaba)."""
        self.cargar()
        self.entradas.pop(str(destino), None)

    def guardar(self) -> None:
        """Escribe el manifiesto en disco."""
        self.cargar()
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            self.ruta.write_text(
                json.dumps(
                    {"version": 1, "entradas": self.entradas},
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            raise TareasError(
                f"No puedo guardar el manifiesto en «{self.ruta}»: {exc.strerror or exc}."
            ) from exc
