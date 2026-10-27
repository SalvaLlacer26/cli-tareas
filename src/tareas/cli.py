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
from tareas.acciones import ERROR, HECHO, SALTADO, SIMULADO, Resultado
from tareas.config import cargar, cargar_config
from tareas.errores import TareasError
from tareas.motor import Motor
from tareas.organizador import Desorganizador, Organizador

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


def ruta_legible(ruta: Path) -> str:
    """Escribe la ruta con «~» en vez del directorio personal: es más corta."""
    try:
        return "~/" + str(ruta.resolve().relative_to(Path.home()))
    except (ValueError, OSError, RuntimeError):
        return str(ruta)


def error_legible(exc: Exception) -> str:
    """Prepara un mensaje de error para Rich, escapando el marcado.

    Los mensajes llevan texto que escribe el usuario (nombres de fichero,
    rutas), y Rich interpretaría sus corchetes como etiquetas.
    """
    return escape(str(exc))



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

    try:
        elementos = sorted(carpeta.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError as exc:
        consola_err.print(
            f"[red]Error:[/red] No puedo leer «{escape(str(carpeta))}»: {escape(str(exc.strerror or exc))}."
        )
        raise typer.Exit(code=1) from exc

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
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
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
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
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
        pide_confirmacion = accion is not None and (
            accion.destructiva or accion.config.get("confirmar") is True
        )
        if pide_confirmacion and not simular and not si:
            typer.confirm(f"«{escape(nombre)}» va a modificar ficheros. ¿Seguro?", abort=True)
        resultados = motor.ejecutar(nombre, carpeta, simular)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    _pintar_resultados(nombre, resultados, simular)


@app.command()
def organizar(
    ctx: typer.Context,
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta que hay que organizar (por defecto, la de descargas del config)."),
    ] = None,
    simular: Annotated[
        bool,
        typer.Option("--simular", help="Enseña qué haría sin tocar nada."),
    ] = False,
    si: Annotated[
        bool,
        typer.Option("--si", help="No pedir confirmación."),
    ] = False,
) -> None:
    """Reparte los ficheros de una carpeta entre las carpetas de asignatura.

    Cada fichero se renombra a un formato que la herramienta entiende
    (prefijo de la asignatura + nombre limpio) y se mueve a su carpeta. Si el
    nombre no dice a qué asignatura pertenece, se mira el resumen de texto
    que va al lado; si tampoco, el fichero va a la carpeta de respaldo.
    """
    try:
        configuracion = cargar_config(ctx.obj)
        if not configuracion.carpetas:
            raise TareasError(
                "El fichero de acciones no tiene la sección «carpetas», así que no hay "
                "nada a lo que organizar. Mira el README para ver cómo se escribe."
            )
        origen = carpeta if carpeta is not None else configuracion.descargas
        if not simular and not si:
            typer.confirm(
                f"«{escape(str(origen))}» se va a vaciar en las carpetas de asignatura. ¿Seguro?",
                abort=True,
            )
        organizador = Organizador(configuracion.carpetas)
        resultados = organizador.organizar(origen, simular)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    _pintar_organizacion("organizar", resultados, simular, ("Fichero", "Carpeta", "Nombre nuevo"))


@app.command()
def desorganizar(
    ctx: typer.Context,
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta donde dejar los ficheros (por defecto, la de descargas del config)."),
    ] = None,
    simular: Annotated[
        bool,
        typer.Option("--simular", help="Enseña qué haría sin tocar nada."),
    ] = False,
    si: Annotated[
        bool,
        typer.Option("--si", help="No pedir confirmación."),
    ] = False,
) -> None:
    """Devuelve a la carpeta de descargas los ficheros ya clasificados.

    Deshace lo que hizo «tareas organizar»: cada fichero vuelve a su sitio
    con el nombre que tenía antes.
    """
    try:
        configuracion = cargar_config(ctx.obj)
        if not configuracion.carpetas:
            raise TareasError(
                "El fichero de acciones no tiene la sección «carpetas», así que no hay "
                "nada que devolver. Mira el README para ver cómo se escribe."
            )
        destino = carpeta if carpeta is not None else configuracion.descargas
        if not simular and not si:
            typer.confirm(
                f"Las carpetas de asignatura se van a vaciar en «{escape(str(destino))}». ¿Seguro?",
                abort=True,
            )
        desorganizador = Desorganizador(configuracion.carpetas)
        resultados = desorganizador.desorganizar(destino, simular)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    _pintar_organizacion("desorganizar", resultados, simular, ("Fichero", "Carpeta", "Nombre original"))


def _pintar_organizacion(
    titulo: str,
    resultados: list[Resultado],
    simular: bool,
    cabeceras: tuple[str, str, str],
) -> None:
    """Pinta la tabla del organizador: fichero, carpeta y nombre final.

    Es más legible que la tabla genérica: aquí lo interesante es a qué carpeta
    va cada fichero y cómo se queda su nombre, no la ruta entera.
    """
    if not resultados:
        consola.print("No hay ningún fichero que organizar.")
        return

    tabla = Table(
        title=f"{escape(titulo)} (SIMULACIÓN: no se ha tocado nada)" if simular else escape(titulo)
    )
    tabla.add_column(cabeceras[0])
    tabla.add_column(cabeceras[1])
    tabla.add_column(cabeceras[2])
    tabla.add_column("Estado")

    errores = 0
    for resultado in resultados:
        carpeta = resultado.destino.parent.name if resultado.destino else "—"
        nombre = resultado.destino.name if resultado.destino else "—"
        estado = resultado.estado
        if resultado.estado == ERROR:
            estado = f"[red]error: {escape(resultado.error or '')}[/red]"
            errores += 1
        tabla.add_row(
            escape(resultado.origen.name),
            escape(carpeta),
            escape(nombre),
            estado,
        )

    consola.print(tabla)
    hechos = sum(1 for r in resultados if r.estado == HECHO)
    simulados = sum(1 for r in resultados if r.estado == SIMULADO)
    saltados = sum(1 for r in resultados if r.estado == SALTADO)
    consola.print(
        f"{len(resultados)} fichero(s) · {hechos} hecho(s) · {simulados} simulado(s) "
        f"· {saltados} saltado(s) · {errores} error(es)"
    )
    if simular:
        consola.print("Para hacerlo de verdad, repite la orden sin --simular.")


def _pintar_resultados(nombre: str, resultados: list[Resultado], simular: bool) -> None:
    """Pinta la tabla de resultados y el resumen de la ejecución."""
    titulo = (
        f"{escape(nombre)} (SIMULACIÓN: no se ha tocado nada)"
        if simular
        else escape(nombre)
    )
    tabla = Table(title=titulo)
    tabla.add_column("Fichero")
    tabla.add_column("Destino")
    tabla.add_column("Estado")

    errores: list[Resultado] = []
    for resultado in resultados:
        if resultado.destino is not None:
            destino = escape(ruta_legible(resultado.destino))
        else:
            destino = "—"
        estado = resultado.estado
        if resultado.estado == ERROR:
            estado = f"[red]error: {escape(resultado.error or '')}[/red]"
            errores.append(resultado)
        tabla.add_row(escape(resultado.origen.name), destino, estado)

    if resultados:
        consola.print(tabla)
    else:
        consola.print(f"La acción «{escape(nombre)}» no ha encontrado ningún fichero.")

    hechos = sum(1 for r in resultados if r.estado == HECHO)
    simulados = sum(1 for r in resultados if r.estado == SIMULADO)
    saltados = sum(1 for r in resultados if r.estado == SALTADO)
    consola.print(
        f"{len(resultados)} fichero(s) · {hechos} hecho(s) · {simulados} simulado(s) "
        f"· {saltados} saltado(s) · {len(errores)} error(es)"
    )

    if simular:
        consola.print("Para hacerlo de verdad, repite la orden sin --simular.")

    if errores:
        raise typer.Exit(code=1)



if __name__ == "__main__":  # pragma: no cover
    app()
