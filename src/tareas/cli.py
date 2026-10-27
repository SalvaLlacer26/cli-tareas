"""Interfaz de línea de órdenes: aquí solo hay órdenes, opciones y salida.

Este módulo habla con la persona. No mueve ficheros: llama al motor y se limita
a contarle lo que ha pasado. Los errores previsibles se capturan aquí y se
convierten en un mensaje y un código de salida, nunca en una traza.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from tareas import __version__
from tareas.acciones import HECHO, SALTADO, SIMULADO, Resultado
from tareas.config import cargar
from tareas.errores import TareasError
from tareas.motor import Motor

app = typer.Typer(
    help="tareas: automatiza tareas repetitivas con tus ficheros.",
    no_args_is_help=True,
    add_completion=False,
)

consola = Console()
consola_err = Console(stderr=True)


def tamano_legible(bytes: int) -> str:
    """Convierte bytes en texto: 532 B, 1.2 KB, 3.4 MB…"""
    if bytes < 1024:
        return f"{bytes} B"
    tamano = float(bytes)
    for unidad in ("KB", "MB", "GB", "TB"):
        tamano /= 1024
        if tamano < 1024:
            break
    return f"{tamano:.1f} {unidad}"


@app.callback()
def principal(
    ctx: typer.Context,
    config: Annotated[
        Path,
        typer.Option("--config", help="Ruta del fichero de acciones."),
    ] = Path("acciones.json"),
) -> None:
    """Guarda la ruta de acciones.json para que la usen las demás órdenes."""
    ctx.obj = config


@app.command()
def version() -> None:
    """Muestra la versión instalada."""
    consola.print(f"tareas {__version__}")


@app.command()
def listar(
    carpeta: Annotated[
        Path,
        typer.Argument(help="Carpeta que quieres ver (por defecto, la actual)."),
    ] = Path("."),
) -> None:
    """Lista los ficheros de una carpeta en una tabla."""
    carpeta = carpeta.expanduser()
    if not carpeta.is_dir():
        consola_err.print(
            f"[red]Error:[/red] «{escape(str(carpeta))}» no existe o no es una carpeta."
        )
        raise typer.Exit(code=1)

    elementos = sorted(carpeta.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    if not elementos:
        consola.print(f"La carpeta «{escape(str(carpeta))}» está vacía.")
        return

    tabla = Table(title=f"Contenido de {escape(str(carpeta.resolve()))}")
    tabla.add_column("Nombre")
    tabla.add_column("Tipo")
    tabla.add_column("Tamaño", justify="right")
    tabla.add_column("Modificado")

    for ruta in elementos:
        try:
            datos = ruta.stat()
        except OSError:
            # Enlace roto o sin permisos: lo saltamos sin romper la tabla.
            continue
        es_carpeta = ruta.is_dir()
        tipo = "carpeta" if es_carpeta else (ruta.suffix.lower() or "(sin extensión)")
        tamano = "—" if es_carpeta else tamano_legible(datos.st_size)
        fecha = datetime.fromtimestamp(datos.st_mtime).strftime("%Y-%m-%d %H:%M")
        tabla.add_row(escape(ruta.name), tipo, tamano, fecha)

    consola.print(tabla)


@app.command()
def acciones(ctx: typer.Context) -> None:
    """Lista las acciones definidas en el fichero de configuración."""
    try:
        definiciones = cargar(ctx.obj)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    tabla = Table(title=f"Acciones de {escape(str(Path(ctx.obj).expanduser()))}")
    tabla.add_column("Nombre")
    tabla.add_column("Tipo")
    tabla.add_column("Descripción")

    for definicion in definiciones:
        tabla.add_row(
            escape(definicion["nombre"]),
            escape(definicion["tipo"]),
            escape(definicion["descripcion"]),
        )

    consola.print(tabla)
    consola.print(f"{len(definiciones)} acción(es) definida(s).")


@app.command()
def validar(ctx: typer.Context) -> None:
    """Comprueba el fichero de acciones y dice exactamente qué campo falla."""
    try:
        definiciones = cargar(ctx.obj)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    consola.print(f"[green]✔ {len(definiciones)} acción(es) válida(s).[/green]")


@app.command()
def ejecutar(
    ctx: typer.Context,
    nombre: Annotated[
        str,
        typer.Argument(help="Nombre de la acción (mira la lista con: tareas acciones)."),
    ],
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta sobre la que actuar (si no, la «origen» de la acción)."),
    ] = None,
    simular: Annotated[
        bool,
        typer.Option("--simular", help="Enseña qué haría sin tocar nada."),
    ] = False,
    si: Annotated[
        bool,
        typer.Option("--si", help="No pedir confirmación (para scripts)."),
    ] = False,
) -> None:
    """Ejecuta una acción sobre una carpeta."""
    try:
        motor = Motor(cargar(ctx.obj))
        accion = motor.acciones.get(nombre)
        if accion is not None and accion.destructiva and not simular and not si:
            typer.confirm(f"«{nombre}» borra ficheros. ¿Seguro?", abort=True)
        resultados = motor.ejecutar(nombre, carpeta, simular)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    _pintar_resultados(nombre, resultados, simular)


def _pintar_resultados(nombre: str, resultados: list[Resultado], simular: bool) -> None:
    """Pinta la tabla de resultados y el resumen de la ejecución."""
    titulo = (
        f"{nombre} (SIMULACIÓN: no se ha tocado nada)"
        if simular
        else nombre
    )
    tabla = Table(title=titulo)
    tabla.add_column("Fichero")
    tabla.add_column("Destino")
    tabla.add_column("Estado")

    for resultado in resultados:
        destino = escape(str(resultado.destino)) if resultado.destino else "—"
        tabla.add_row(escape(resultado.origen.name), destino, resultado.estado)

    if resultados:
        consola.print(tabla)
    else:
        consola.print(f"La acción «{nombre}» no ha encontrado ningún fichero.")

    hechos = sum(1 for r in resultados if r.estado == HECHO)
    simulados = sum(1 for r in resultados if r.estado == SIMULADO)
    saltados = sum(1 for r in resultados if r.estado == SALTADO)
    consola.print(
        f"{len(resultados)} fichero(s) · {hechos} hecho(s) · {simulados} simulado(s) · {saltados} saltado(s)"
    )

    if simular:
        consola.print("Para hacerlo de verdad, repite la orden sin --simular.")


if __name__ == "__main__":  # pragma: no cover
    app()
