"""Interfaz de línea de órdenes: aquí solo hay órdenes, opciones y salida.

Este módulo habla con la persona. No mueve ficheros: llama al analizador, al
organizador o a los generadores de documentos, y se limita a contarles lo que
ha pasado. Los errores previsibles se capturan aquí y se convierten en un
mensaje y un código de salida, nunca en una traza.

Todos los comandos admiten la carpeta sobre la que trabajar como argumento.
Si no se pone, se trabaja sobre la carpeta en la que está la terminal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from tareas import __version__
from tareas.analizador import CARPETA_FICHAS, analizar
from tareas.comandos import ANIO, AVISO_LEGAL, AUTOR, COMANDOS, CURSO
from tareas.config import cargar
from tareas.documentos import formato_preferido
from tareas.errores import TareasError
from tareas.evaluacion import escribir_evaluacion
from tareas.motor import Motor
from tareas.organizador import deshacer, organizar
from tareas.resumen import buscar_ficha, escribir_resumen

app = typer.Typer(
    help="tareas: organiza tus apuntes por asignatura desde la terminal.",
    no_args_is_help=True,
    add_completion=False,
)

consola = Console()
consola_err = Console(stderr=True)


def carpeta_de_trabajo(carpeta: Path | None) -> Path:
    """La carpeta sobre la que se trabaja.

    Si no se indica ninguna, se usa la carpeta en la que está la terminal.
    """
    if carpeta is None:
        return Path.cwd()
    return carpeta.expanduser()


def error_legible(exc: Exception) -> str:
    """Prepara un mensaje de error para Rich, escapando el marcado."""
    return escape(str(exc))


@app.callback()
def principal(
    ctx: typer.Context,
    config: Annotated[
        Path,
        typer.Option("--config", help="Ruta del fichero de configuración."),
    ] = Path("acciones.json"),
) -> None:
    """Guarda la ruta de la configuración para que la usen las demás órdenes."""
    ctx.obj = config


@app.command(name="analizar")
def analizar_cmd(
    ctx: typer.Context,
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta que hay que analizar (por defecto, la actual)."),
    ] = None,
) -> None:
    """Analiza una carpeta y prepara las fichas para poder organizarla."""
    try:
        configuracion = cargar(ctx.obj)
        destino = carpeta_de_trabajo(carpeta)
        resultado = analizar(destino, configuracion.carpetas)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    tabla = Table(title=f"Análisis de {escape(str(destino))}")
    tabla.add_column("Archivo")
    tabla.add_column("Estado")
    tabla.add_column("Asignatura")
    tabla.add_column("Carpeta de destino")

    for fila in resultado.filas:
        estado = fila.estado
        if estado == "formato invalido":
            estado = f"[red]{estado}[/red]"
        elif estado == "sin clasificar":
            estado = f"[yellow]{estado}[/yellow]"
        destino_texto = _corta(fila.destino) or "—"
        tabla.add_row(
            escape(fila.nombre_original),
            estado,
            escape(fila.asignatura),
            escape(destino_texto),
        )

    if resultado.filas:
        consola.print(tabla)
    else:
        consola.print("No hay ningún fichero en la carpeta.")

    if resultado.renombrados:
        consola.print(
            f"[yellow]Se han renombrado {len(resultado.renombrados)} fichero(s) "
            "para que se puedan tratar bien.[/yellow]"
        )
        for antes, despues in resultado.renombrados:
            consola.print(f"  {escape(antes)}  ->  {escape(despues)}")

    consola.print(
        f"Fichas creadas: {resultado.fichas} en «{CARPETA_FICHAS}» · "
        f"{resultado.analizables} analizables · "
        f"{resultado.sin_clasificar} sin clasificar · "
        f"{resultado.invalidos} con formato inválido"
    )

    typer.confirm(
        "¿Confirmas que el análisis se ha ejecutado correctamente?",
        abort=True,
    )
    consola.print("[green]Análisis confirmado.[/green]")


@app.command(name="organizar")
def organizar_cmd(
    ctx: typer.Context,
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta que hay que organizar (por defecto, la actual)."),
    ] = None,
) -> None:
    """Mueve cada documento a la carpeta de su asignatura."""
    try:
        cargar(ctx.obj)
        destino = carpeta_de_trabajo(carpeta)
        resultado = organizar(destino)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    if not resultado.movimientos:
        consola.print("No hay ningún documento que mover.")

    tabla = Table(title=f"Documentos movidos a {escape(str(destino))}")
    tabla.add_column("Documento")
    tabla.add_column("Carpeta de destino")
    for movimiento in resultado.movimientos:
        tabla.add_row(escape(movimiento.nombre_original), escape(movimiento.destino))
    if resultado.movimientos:
        consola.print(tabla)

    if resultado.por_carpeta:
        consola.print("Resumen por carpeta:")
        for carpeta_destino, cantidad in sorted(resultado.por_carpeta.items()):
            consola.print(f"  {escape(carpeta_destino)}: {cantidad} documento(s)")

    consola.print(f"Total: {resultado.total} documento(s) movido(s).")

    if resultado.sin_ficha:
        consola.print(
            f"[yellow]{len(resultado.sin_ficha)} documento(s) se han quedado sin mover "
            "porque su formato no se puede analizar.[/yellow]"
        )


@app.command(name="deshacer")
def deshacer_cmd(
    ctx: typer.Context,
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta donde se deshace (por defecto, la actual)."),
    ] = None,
) -> None:
    """Devuelve los documentos a su carpeta de origen, con su nombre original."""
    try:
        configuracion = cargar(ctx.obj)
        destino = carpeta_de_trabajo(carpeta)
        resultado = deshacer(destino, configuracion.carpetas)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    if not resultado.movimientos:
        consola.print("No hay ningún documento que devolver.")

    tabla = Table(title=f"Documentos devueltos a {escape(str(destino))}")
    tabla.add_column("Documento")
    tabla.add_column("Carpeta de origen")
    for movimiento in resultado.movimientos:
        tabla.add_row(escape(movimiento.nombre_original), escape(movimiento.destino))
    if resultado.movimientos:
        consola.print(tabla)

    consola.print(f"Total: {resultado.total} documento(s) devuelto(s).")
    consola.print(f"[dim]Las fichas de «{CARPETA_FICHAS}» se conservan.[/dim]")


@app.command()
def resumir(
    ctx: typer.Context,
    archivo: Annotated[
        str,
        typer.Argument(help="Nombre del archivo del que se hace el resumen."),
    ],
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta donde está el archivo (por defecto, la actual)."),
    ] = None,
) -> None:
    """Crea un resumen del archivo indicado en la carpeta «resumenes»."""
    try:
        configuracion = cargar(ctx.obj)
        destino = carpeta_de_trabajo(carpeta)
        ficha = buscar_ficha(destino, archivo, configuracion.carpetas)
        ruta = escribir_resumen(ficha, destino, formato_preferido())
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    consola.print(f"[green]Resumen creado:[/green] {escape(str(ruta))}")


@app.command()
def evaluar(
    ctx: typer.Context,
    archivo: Annotated[
        str,
        typer.Argument(help="Nombre del archivo sobre el que se hacen los ejercicios."),
    ],
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta donde está el archivo (por defecto, la actual)."),
    ] = None,
) -> None:
    """Crea una batería de ejercicios sobre el archivo, en la carpeta «ejercicios»."""
    try:
        configuracion = cargar(ctx.obj)
        destino = carpeta_de_trabajo(carpeta)
        ficha = buscar_ficha(destino, archivo, configuracion.carpetas)
        ruta = escribir_evaluacion(ficha, destino, formato_preferido())
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    consola.print(f"[green]Ejercicios creados:[/green] {escape(str(ruta))}")


@app.command(name="validar")
def validar_cmd(ctx: typer.Context) -> None:
    """Comprueba el fichero de configuración y dice exactamente qué campo falla."""
    try:
        configuracion = cargar(ctx.obj)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    consola.print(
        f"[green]✔ {len(configuracion.acciones)} acción(es) y "
        f"{len(configuracion.carpetas)} carpeta(s) válidas.[/green]"
    )


@app.command(name="ejecutar")
def ejecutar_cmd(
    ctx: typer.Context,
    nombre: Annotated[
        str,
        typer.Argument(help="Nombre de la acción (mira la lista con: tareas comandos)."),
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
    """Ejecuta una acción de las definidas en el fichero de configuración."""
    try:
        motor = Motor(cargar(ctx.obj).acciones)
        accion = motor.acciones.get(nombre)
        if accion is not None and accion.destructiva and not simular and not si:
            typer.confirm(f"«{escape(nombre)}» va a modificar ficheros. ¿Seguro?", abort=True)
        resultados = motor.ejecutar(nombre, carpeta_de_trabajo(carpeta) if carpeta else None, simular)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    _pintar_resultados(nombre, resultados, simular)


def _pintar_resultados(nombre: str, resultados: list, simular: bool) -> None:
    """Pinta la tabla de resultados y el resumen de la ejecución."""
    titulo = f"{escape(nombre)} (SIMULACIÓN: no se ha tocado nada)" if simular else escape(nombre)
    tabla = Table(title=titulo)
    tabla.add_column("Fichero")
    tabla.add_column("Destino")
    tabla.add_column("Estado")

    errores = 0
    for resultado in resultados:
        destino = escape(str(resultado.destino)) if resultado.destino else "—"
        estado = resultado.estado
        if resultado.estado == "error":
            estado = f"[red]error: {escape(resultado.error or '')}[/red]"
            errores += 1
        tabla.add_row(escape(resultado.origen.name), destino, estado)

    if resultados:
        consola.print(tabla)
    else:
        consola.print(f"La acción «{escape(nombre)}» no ha encontrado ningún fichero.")

    hechos = sum(1 for r in resultados if r.estado == "hecho")
    simulados = sum(1 for r in resultados if r.estado == "simulado")
    saltados = sum(1 for r in resultados if r.estado == "saltado")
    consola.print(
        f"{len(resultados)} fichero(s) · {hechos} hecho(s) · {simulados} simulado(s) "
        f"· {saltados} saltado(s) · {errores} error(es)"
    )
    if simular:
        consola.print("Para hacerlo de verdad, repite la orden sin --simular.")
    if errores:
        raise typer.Exit(code=1)


@app.command(name="comandos")
def comandos() -> None:
    """Muestra todos los comandos de la herramienta y para qué sirven."""
    consola.print(f"[bold]tareas[/bold] {__version__}")
    consola.print("[dim]Tu propia herramienta de terminal: organiza tus apuntes por asignatura.[/dim]")
    consola.print()

    for ficha in COMANDOS:
        consola.print(f"[bold cyan]{ficha.nombre}[/bold cyan]")
        consola.print(f"  [bold]Uso:[/bold] {escape(ficha.uso)}")
        for linea in _envolver(ficha.para_que):
            consola.print(f"  {escape(linea)}")
        if ficha.ejemplo:
            consola.print(f"  [dim]Ejemplo: {escape(ficha.ejemplo)}[/dim]")
        consola.print()

    consola.print(f"[bold]Creado por[/bold] {AUTOR}")
    consola.print(f"[bold]Curso[/bold] {CURSO} · [bold]Año[/bold] {ANIO}")
    consola.print(f"[dim]{AVISO_LEGAL}[/dim]")


def _corta(ruta: str) -> str:
    """Acorta una ruta quitando el directorio personal, que ocupa mucho."""
    if not ruta:
        return ""
    try:
        return "~/" + str(Path(ruta).resolve().relative_to(Path.home()))
    except (ValueError, OSError, RuntimeError):
        return ruta


def _envolver(texto: str, ancho: int = 78) -> list[str]:
    """Parte un texto en líneas de un anchoaproximado."""
    palabras = texto.split()
    lineas: list[str] = []
    actual = ""
    for palabra in palabras:
        if actual and len(actual) + 1 + len(palabra) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}".strip()
    if actual:
        lineas.append(actual)
    return lineas
