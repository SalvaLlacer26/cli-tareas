"""Interfaz de línea de órdenes: aquí solo hay órdenes, opciones y salida.

Este módulo habla con la persona. No mueve ficheros: llama al analizador, al
organizador o a los generadores de documentos, y se limita a contarles lo que
ha pasado. Los errores previsibles se capturan aquí y se convierten en un
mensaje y un código de salida, nunca en una traza.

Todos los comandos admiten la carpeta sobre la que trabajar como argumento.
Si no se pone, se trabaja sobre la carpeta en la que está la terminal.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from tareas import __version__
from tareas import agrupador
from tareas import examenes
from tareas.analizador import CARPETA_FICHAS, analizar
from tareas.comandos import ANIO, AVISO_LEGAL, AUTOR, COMANDOS, CURSO, SIGUIENTES
from tareas.config import cargar
from tareas.documentos import formato_preferido
from tareas.errores import TareasError
from tareas.evaluacion import escribir_evaluacion
from tareas.ia import ProveedorIA
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

#: Paleta de la herramienta. Colores legibles sobre fondo claro y oscuro, que
#: sirven para separar unos apartados de otros sin cansar la vista.
ACENTO = "bold cyan"       # títulos de tabla y nombres de apartado
NOMBRE = "bold magenta"    # una orden o un dato que destaca
CORRECTO = "green"         # lo que ha salido bien
AVISO = "yellow"           # algo a revisar, sin ser error
ERROR = "red"              # lo que ha fallado
BORDE = "blue"             # el marco de las tablas


def _tabla(titulo: str = "", **extras) -> Table:
    """Una tabla con el estilo de la herramienta: marco redondeado y azules."""
    return Table(
        title=escape(titulo) if titulo else None,
        title_style=ACENTO,
        title_justify="left",
        header_style=f"white on {BORDE}",
        box=box.ROUNDED,
        border_style=BORDE,
        **extras,
    )


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


def simbolo(bonito: str, alternativa: str) -> str:
    """Un símbolo que la consola de este equipo pueda escribir.

    En Windows la consola usa cp1252 por defecto, y ahí no caben algunos
    símbolos como «✔» (U+2714): al imprimirlos, Python revienta con un
    UnicodeEncodeError. Aquí se prueba el símbolo y, si no cabe, se usa el
    texto de siempre. Lo descubrió la CI al fallar en Windows.
    """
    codificacion = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        bonito.encode(codificacion)
    except (UnicodeEncodeError, LookupError):
        return alternativa
    return bonito


def _despues_de(nombre: str) -> None:
    """Cierra cada comando con «¿Qué quieres hacer ahora?».

    Lista, una por línea y con una descripción corta, las acciones que tienen
    sentido justo después del comando que se acaba de terminar. Debajo recuerda
    que «tareas comandos» da la información detallada de todo. «comandos» no se
    cuela entre las sugerencias: solo aparece ahí abajo. Solo en una terminal de
    verdad; en scripts, tuberías y CI el resultado debe salir limpio.
    """
    if not sys.stdout.isatty():
        return
    consola.print()
    consola.print(f"[{ACENTO}]¿Qué quieres hacer ahora?[/{ACENTO}]")
    for siguiente, motivo in SIGUIENTES.get(nombre, []):
        consola.print(f"  [{NOMBRE}]tareas {siguiente}[/]  [dim]{escape(motivo)}[/dim]")
    consola.print()
    consola.print(
        "  Para información más detallada introduce el comando: "
        f"[{NOMBRE}]tareas comandos[/]"
    )


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
        with consola.status(f"Leyendo y analizando «{escape(str(destino))}»…", spinner="dots"):
            resultado = analizar(destino, configuracion.carpetas)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    tabla = _tabla(f"Análisis de {destino}")
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
        f"[bold]Fichas creadas:[/] {resultado.fichas} en «{CARPETA_FICHAS}» · "
        f"[{CORRECTO}]{resultado.analizables} analizables[/] · "
        f"[{AVISO}]{resultado.sin_clasificar} sin clasificar[/] · "
        f"[{ERROR}]{resultado.invalidos} con formato inválido[/]"
    )

    typer.confirm(
        "¿Confirmas que el análisis se ha ejecutado correctamente?",
        abort=True,
    )
    consola.print("[green]Análisis confirmado.[/green]")
    _despues_de("analizar")


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
        with consola.status("Moviendo cada documento a su asignatura…", spinner="dots"):
            resultado = organizar(destino)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    if not resultado.movimientos:
        consola.print("No hay ningún documento que mover.")

    tabla = _tabla(f"Documentos movidos a {destino}")
    tabla.add_column("Documento")
    tabla.add_column("Carpeta de destino")
    for movimiento in resultado.movimientos:
        tabla.add_row(escape(movimiento.nombre_original), escape(movimiento.destino))
    if resultado.movimientos:
        consola.print(tabla)

    if resultado.por_carpeta:
        consola.print(f"[{ACENTO}]Resumen por carpeta:[/]")
        for carpeta_destino, cantidad in sorted(resultado.por_carpeta.items()):
            consola.print(f"  {escape(carpeta_destino)}: [{NOMBRE}]{cantidad}[/] documento(s)")

    consola.print(f"[bold]Total:[/] [{CORRECTO}]{resultado.total}[/] documento(s) movido(s).")

    if resultado.sin_ficha:
        consola.print(
            f"[{AVISO}]{len(resultado.sin_ficha)} documento(s) se han quedado sin mover "
            "porque su formato no se puede analizar.[/]"
        )
    _despues_de("organizar")


@app.command(name="deshacer")
def deshacer_cmd(
    ctx: typer.Context,
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta donde se deshace (por defecto, la actual)."),
    ] = None,
) -> None:
    """Devuelve los documentos a su origen: deshace «organizar» y «clasificar»."""
    try:
        configuracion = cargar(ctx.obj)
        destino = carpeta_de_trabajo(carpeta)
        with consola.status("Devolviendo los documentos a su carpeta de origen…", spinner="dots"):
            resultado = deshacer(destino, configuracion.carpetas)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    if not resultado.movimientos:
        consola.print("No hay ningún documento que devolver.")

    tabla = _tabla(f"Documentos devueltos a {destino}")
    tabla.add_column("Documento")
    tabla.add_column("Carpeta de origen")
    for movimiento in resultado.movimientos:
        tabla.add_row(escape(movimiento.nombre_original), escape(movimiento.destino))
    if resultado.movimientos:
        consola.print(tabla)

    consola.print(f"[bold]Total:[/] [{CORRECTO}]{resultado.total}[/] documento(s) devuelto(s).")
    consola.print(f"[dim]Las fichas de «{CARPETA_FICHAS}» se conservan.[/dim]")
    _despues_de("deshacer")


@app.command()
def resumir(
    ctx: typer.Context,
    archivo: Annotated[
        str,
        typer.Argument(help="Archivo que acota el tema (se usa solo como referencia)."),
    ],
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta donde está el archivo (por defecto, la actual)."),
    ] = None,
) -> None:
    """Delimita el tema del archivo y escribe apuntes completos en «resumenes».

    El archivo solo sirve para saber de qué tema va y hasta dónde llega; los
    apuntes se escriben desde cero, investigando la teoría en internet.
    """
    try:
        configuracion = cargar(ctx.obj)
        destino = carpeta_de_trabajo(carpeta)
        ficha = buscar_ficha(destino, archivo, configuracion.carpetas)
        if ProveedorIA.desde_configuracion().disponible:
            aviso = (
                f"Escribiendo apuntes de «{escape(archivo)}» con el modelo: "
                "delimitando el tema e investigando; puede tardar unos minutos…"
            )
        else:
            aviso = f"Sin modelo configurado: extracción de «{escape(archivo)}» sin IA."
        with consola.status(aviso, spinner="dots"):
            ruta = escribir_resumen(ficha, destino, formato_preferido())
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    consola.print(f"[green]Apuntes creados:[/green] {escape(str(ruta))}")
    _despues_de("resumir")


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
        if ProveedorIA.desde_configuracion().disponible:
            aviso = f"Preparando ejercicios de «{escape(archivo)}» con el modelo: puede tardar unos minutos…"
        else:
            aviso = f"Sin modelo configurado: preparando ejercicios de «{escape(archivo)}» sin IA."
        with consola.status(aviso, spinner="dots"):
            ruta = escribir_evaluacion(ficha, destino, formato_preferido())
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    consola.print(f"[green]Ejercicios creados:[/green] {escape(str(ruta))}")
    _despues_de("evaluar")


@app.command(name="formulario_evaluar")
def formulario_evaluar(
    ctx: typer.Context,
    archivo: Annotated[
        str,
        typer.Argument(help="Nombre del archivo sobre el que se hacen los ejercicios."),
    ],
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta donde está el archivo (por defecto, la actual)."),
    ] = None,
    abrir: Annotated[
        bool,
        typer.Option("--abrir/--no-abrir", help="Abrir el navegador automáticamente."),
    ] = True,
) -> None:
    """(En pruebas) Examen interactivo en el navegador que corrige la IA.

    Prepara los mismos ejercicios que «evaluar» pero en un formulario HTML:
    tipo test con botones de opción y preguntas escritas con su hueco. Al
    enviar, se corrige el tipo test y la IA revisa lo escrito. El servidor
    solo escucha en tu propio equipo; pulsa Enter aquí para cerrarlo.
    """
    try:
        configuracion = cargar(ctx.obj)
        destino = carpeta_de_trabajo(carpeta)
        ficha = buscar_ficha(destino, archivo, configuracion.carpetas)
        from .evaluacion import resumen_previo

        contexto = resumen_previo(destino, ficha.nombre_original)
        proveedor = ProveedorIA.desde_configuracion()
        con_ia = proveedor.disponible
        aviso = (
            f"Preparando el examen interactivo de «{escape(archivo)}» con el modelo…"
            if con_ia
            else f"Sin modelo: preparando un examen sencillo de «{escape(archivo)}»."
        )
        with consola.status(aviso, spinner="dots"):
            try:
                preguntas = examenes.pedir_bateria(ficha, contexto)
            except TareasError:
                con_ia = False
                preguntas = examenes.bateria_extractiva(ficha)

        titulo = f"Ejercicios · {ficha.nombre_original}"
        servidor, url = examenes.crear_servidor(titulo, preguntas, con_ia)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    consola.print(f"[green]Examen listo:[/green] {len(preguntas)} pregunta(s).")
    if abrir and examenes.abrir_navegador(url):
        consola.print(f"Se ha abierto el navegador en [bold]{escape(url)}[/bold].")
    else:
        consola.print(f"Abre en el navegador esta dirección: [bold]{escape(url)}[/bold]")
    consola.print("[dim]Responde y pulsa «Enviar respuestas». Aquí abajo, Enter para cerrar.[/dim]")
    try:
        with consola.status("Examen abierto, esperando tus respuestas…", spinner="dots"):
            input()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        servidor.shutdown()
        servidor.server_close()
    consola.print("Examen cerrado.")
    _despues_de("formulario_evaluar")


@app.command()
def version() -> None:
    """Muestra la versión instalada."""
    with consola.status("Mostrando la versión…"):
        consola.print(f"[{ACENTO}]tareas[/] [bold]{__version__}[/bold]")
    _despues_de("version")


def _tamano_legible(pixels: int) -> str:
    """Un tamaño en bytes, dicho como lo diría una persona: «1,2 MB»."""
    for unidad in ("B", "KB", "MB", "GB"):
        if pixels < 1024 or unidad == "GB":
            if unidad == "B":
                return f"{pixels} {unidad}"
            return f"{pixels / 1024:.1f} {unidad}"
        pixels /= 1024
    return f"{pixels:.1f} GB"


@app.command()
def listar(
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta que se lista (por defecto, la actual)."),
    ] = None,
    json_salida: Annotated[
        bool,
        typer.Option("--json", help="Salida en JSON, para otros programas."),
    ] = False,
) -> None:
    """Lista los ficheros de una carpeta: nombre, tipo, tamaño y fecha."""
    destino = carpeta_de_trabajo(carpeta)
    if not destino.is_dir():
        consola_err.print(
            f"[red]Error:[/red] No existe la carpeta «{escape(str(destino))}»."
        )
        raise typer.Exit(code=1)

    with consola.status(f"Leyendo «{escape(str(destino))}»…"):
        entradas = [
            ruta for ruta in sorted(destino.iterdir(), key=lambda p: p.name.lower())
            if not ruta.name.startswith(".")
        ]

    if json_salida:
        # stdout limpio: sin colores ni tablas, solo JSON para quien pipee.
        datos = []
        for ruta in entradas:
            info = ruta.stat()
            datos.append({
                "nombre": ruta.name,
                "tipo": (
                    "carpeta"
                    if ruta.is_dir()
                    else (ruta.suffix.lower().lstrip(".") or "sin extensión")
                ),
                "tamano": info.st_size,
                "modificado": datetime.fromtimestamp(info.st_mtime).isoformat(
                    timespec="seconds"
                ),
            })
        typer.echo(json.dumps(datos, ensure_ascii=False, indent=2))
        return

    tabla = _tabla(f"Contenido de {destino}")
    tabla.add_column("Fichero")
    tabla.add_column("Tipo")
    tabla.add_column("Tamaño", justify="right")
    tabla.add_column("Modificado")
    for ruta in entradas:
        info = ruta.stat()
        tipo = (
            "carpeta"
            if ruta.is_dir()
            else (ruta.suffix.lower().lstrip(".") or "sin extensión")
        )
        tabla.add_row(
            escape(ruta.name),
            tipo,
            "—" if ruta.is_dir() else _tamano_legible(info.st_size),
            datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d %H:%M"),
        )
    if entradas:
        consola.print(tabla)
    else:
        consola.print(f"La carpeta «{escape(str(destino))}» está vacía.")
    _despues_de("listar")


@app.command()
def acciones(ctx: typer.Context) -> None:
    """Lista las acciones del fichero de configuración con su descripción."""
    try:
        configuracion = cargar(ctx.obj)
        with consola.status("Leyendo las acciones de la configuración…"):
            motor = Motor(configuracion.acciones)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    tabla = _tabla("Acciones del fichero de configuración")
    tabla.add_column("Acción")
    tabla.add_column("Tipo")
    tabla.add_column("Pide confirmación")
    tabla.add_column("Descripción")
    for accion in motor.acciones.values():
        tabla.add_row(
            escape(accion.nombre),
            escape(accion.tipo),
            "sí" if accion.destructiva else "no",
            escape(accion.descripcion),
        )
    if motor.acciones:
        consola.print(tabla)
    else:
        consola.print("El fichero de configuración no tiene ninguna acción.")

    if configuracion.carpetas:
        carpetas = ", ".join(
            str(carpeta.etiqueta or carpeta.clave)
            for carpeta in configuracion.carpetas
        )
        consola.print(f"[dim]Carpetas (asignaturas): {escape(carpetas)}[/dim]")
    _despues_de("acciones")


@app.command(name="validar")
def validar_cmd(ctx: typer.Context) -> None:
    """Comprueba el fichero de configuración y dice exactamente qué campo falla."""
    try:
        with consola.status("Comprobando el fichero de configuración…"):
            configuracion = cargar(ctx.obj)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    consola.print(
        f"[green]{simbolo('✔', 'OK')} {len(configuracion.acciones)} acción(es) y "
        f"{len(configuracion.carpetas)} carpeta(s) válidas.[/green]"
    )
    _despues_de("validar")


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
        with consola.status(
            f"«{escape(nombre)}» trabajando…" + (" (simulación)" if simular else ""),
            spinner="dots",
        ):
            resultados = motor.ejecutar(
                nombre, carpeta_de_trabajo(carpeta) if carpeta else None, simular
            )
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    _pintar_resultados(nombre, resultados, simular)
    _despues_de("ejecutar")


def _pintar_resultados(nombre: str, resultados: list, simular: bool) -> None:
    """Pinta la tabla de resultados y el resumen de la ejecución."""
    titulo = f"{nombre} (SIMULACIÓN: no se ha tocado nada)" if simular else nombre
    tabla = _tabla(titulo)
    tabla.add_column("Fichero")
    tabla.add_column("Destino")
    tabla.add_column("Estado")

    errores = 0
    for resultado in resultados:
        destino = escape(str(resultado.destino)) if resultado.destino else "—"
        estado = resultado.estado
        if resultado.estado == "error":
            estado = f"[{ERROR}]error: {escape(resultado.error or '')}[/]"
            errores += 1
        elif resultado.estado in ("hecho", "simulado"):
            estado = f"[{CORRECTO}]{estado}[/]"
        tabla.add_row(escape(resultado.origen.name), destino, estado)

    if resultados:
        consola.print(tabla)
    else:
        consola.print(f"La acción «{escape(nombre)}» no ha encontrado ningún fichero.")

    hechos = sum(1 for r in resultados if r.estado == "hecho")
    simulados = sum(1 for r in resultados if r.estado == "simulado")
    saltados = sum(1 for r in resultados if r.estado == "saltado")
    consola.print(
        f"[dim]{len(resultados)} fichero(s)[/dim] · "
        f"[{CORRECTO}]{hechos} hecho(s)[/] · "
        f"[cyan]{simulados} simulado(s)[/] · "
        f"[dim]{saltados} saltado(s)[/] · "
        f"[{ERROR}]{errores} error(es)[/]"
    )
    if simular:
        consola.print(f"[{AVISO}]Para hacerlo de verdad, repite la orden sin --simular.[/]")
    if errores:
        raise typer.Exit(code=1)


@app.command(name="clasificar")
def clasificar_cmd(
    ctx: typer.Context,
    destino: Annotated[
        Path,
        typer.Option("--destino", help="Ruta donde se crea el grupo de carpetas."),
    ],
    carpeta: Annotated[
        Path | None,
        typer.Argument(help="Carpeta con los documentos analizados (por defecto, la actual)."),
    ] = None,
) -> None:
    """Crea las carpetas según el contenido de los documentos y los mueve dentro.

    A diferencia de «organizar», que usa las asignaturas de la configuración,
    aquí las carpetas las decide la IA mirando lo que dicen los documentos.
    """
    try:
        cargar(ctx.obj)
        origen = carpeta_de_trabajo(carpeta)
        with consola.status(
            "Pidiendo al modelo que agrupe los documentos por su contenido: puede tardar unos minutos…",
            spinner="dots",
        ):
            plan = agrupador.planear(origen, usar_ia=True)
    except TareasError as exc:
        consola_err.print(f"[red]Error:[/red] {error_legible(exc)}")
        raise typer.Exit(code=exc.codigo_salida) from exc

    if plan.aviso:
        consola.print(f"[{AVISO}]{escape(plan.aviso)}[/]")

    tabla = _tabla(f"Carpetas que se van a crear en {destino.expanduser()}")
    tabla.add_column("Carpeta")
    tabla.add_column("Documentos")
    tabla.add_column("Cantidad", justify="right")
    for grupo in plan.grupos:
        tabla.add_row(escape(grupo.nombre), escape(", ".join(grupo.documentos[:3])), str(len(grupo.documentos)))
    consola.print(tabla)

    if not typer.confirm("¿Quieres crear esas carpetas y mover los documentos?"):
        raise typer.Exit(code=1)

    with consola.status("Creando las carpetas y moviendo los documentos…", spinner="dots"):
        movidos, errores = agrupador.aplicar(origen, destino, plan)

    consola.print(f"[bold]Total:[/] [{CORRECTO}]{len(movidos)}[/] documento(s) movido(s).")
    for movimiento in movidos:
        consola.print(f"  {escape(movimiento)}")

    sin_sitio = [
        grupo
        for grupo in plan.grupos
        if grupo.nombre == agrupador.CARPETA_POR_CLASIFICAR
    ]
    for grupo in sin_sitio:
        consola.print(
            f"[{AVISO}]{len(grupo.documentos)} documento(s) no se han podido "
            f"clasificar y están en la carpeta «{agrupador.CARPETA_POR_CLASIFICAR}»:[/]"
        )
        for nombre in grupo.documentos:
            consola.print(f"  [{AVISO}]· {escape(nombre)}[/]")

    for error in errores:
        consola_err.print(f"[{AVISO}]{escape(error)}[/]")

    if plan.fuentes:
        consola.print(f"[dim]Fuentes consultadas: {len(plan.fuentes)}[/dim]")

    if errores:
        raise typer.Exit(code=1)
    _despues_de("clasificar")


@app.command(name="comandos")
def comandos() -> None:
    """Muestra todos los comandos de la herramienta y para qué sirven."""
    consola.print(f"[{ACENTO}]tareas[/] [bold]{__version__}[/bold]")
    consola.print("[dim]Tu propia herramienta de terminal: organiza tus apuntes por asignatura.[/dim]")
    consola.print()

    for ficha in COMANDOS:
        consola.print(f"[{ACENTO}]{ficha.nombre}[/]")
        consola.print(f"  [{NOMBRE}]Uso:[/] {escape(ficha.uso)}")
        for linea in _envolver(ficha.para_que):
            consola.print(f"  {escape(linea)}")
        if ficha.ejemplo:
            consola.print(f"  [dim]Ejemplo:[/] [dim]{escape(ficha.ejemplo)}[/dim]")
        consola.print()

    consola.print(f"[{NOMBRE}]Creado por[/] {escape(AUTOR)}")
    consola.print(f"[{NOMBRE}]Curso[/] {escape(CURSO)} · [{NOMBRE}]Año[/] {escape(ANIO)}")
    consola.print(f"[dim]{escape(AVISO_LEGAL)}[/dim]")
    _despues_de("comandos")


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
