"""El comando «clasificar»: crear las carpetas según lo que dicen los documentos.

A diferencia de «organizar», que usa las asignaturas que están escritas en
`acciones.json`, aquí **las carpetas las decide la IA** mirando el contenido
de los documentos. Un PDF de recetas de cocina acaba en una carpeta «Recetas»;
un manual de una placa base, en «Hardware»; un tema de historia, en «Historia».

El modelo responde con un formato sencillo que la herramienta entiende:

    [Recetas]
    - receta de tortilla.pdf
    - bizcocho de limón.pdf

    [Hardware]
    - manual de la placa.pdf

Si un documento no encaja en ninguna carpeta, el modelo lo deja en
«Sin clasificar».
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import ficha as fichas
from .busqueda import Fuente
from .errores import TareasError
from .nombres import sin_conflicto

#: La carpeta donde va lo que el modelo no sabe colocar.
CARPETA_SIN_CLASIFICAR = "Sin clasificar"

#: Cuántos caracteres de cada documento se le enseñan al modelo.
MAXIMO_POR_DOCUMENTO = 700

#: El formato de la respuesta: una cabecera de carpeta y sus documentos.
RE_CARPETA = re.compile(r"^\[\s*(.+?)\s*\]\s*$")
RE_DOCUMENTO = re.compile(r"^\s*[-*+]\s+(.+?)\s*$")

#: Cómo se le pide al modelo.
SISTEMA = (
    "Eres un bibliotecario digital: organizas documentos en carpetas por su "
    "contenido. Respondes en español y los nombres de las carpetas van en el "
    "idioma de los documentos."
)


@dataclass
class Grupo:
    """Una carpeta con los documentos que van dentro."""

    nombre: str
    documentos: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """Lo que hay que hacer: los grupos y las fuentes consultadas."""

    grupos: list[Grupo] = field(default_factory=list)
    fichas: dict[str, fichas.Ficha] = field(default_factory=dict)
    fuentes: list[Fuente] = field(default_factory=list)


def _nombre_de_carpeta(nombre: str) -> str:
    """Un nombre de carpeta que se pueda crear en cualquier sistema."""
    limpio = re.sub(r"[\\/:*?\"<>|]+", "-", nombre).strip()
    limpio = re.sub(r"\s+", " ", limpio)
    return limpio[:80] or CARPETA_SIN_CLASIFICAR


def pedir_agrupacion(documentos: list[tuple[str, str]]) -> tuple[list[Grupo], list[Fuente]]:
    """Le pide al modelo que agrupe los documentos en carpetas.

    «documentos» es una lista de (nombre, fragmento de contenido).
    """
    from .ia import pedir_con_busqueda

    if not documentos:
        raise TareasError("No hay ningún documento que clasificar.")

    descripcion = []
    for nombre, fragmento in documentos:
        descripcion.append(f"- {nombre}\n    {fragmento.strip()[:MAXIMO_POR_DOCUMENTO]}")

    peticion = (
        "Agrupa estos documentos en carpetas según su contenido.\n\n"
        "Reglas:\n"
        "- El número de carpetas es el que haga falta: agrupa por el tema de "
        "verdad de cada documento, no por el tipo de fichero.\n"
        "- Los nombres de las carpetas van en el idioma de los documentos.\n"
        "- Un nombre corto y claro: «Recetas», «Hardware», «Historia antigua».\n"
        "- Si un documento no encaja en ninguna carpeta, déjalo en una carpeta "
        f"«{CARPETA_SIN_CLASIFICAR}».\n"
        "- Cada documento va en una sola carpeta.\n\n"
        "Responde SOLO con este formato, sin explicaciones:\n\n"
        "[Nombre de la carpeta]\n"
        "- documento.ext\n"
        "- otro documento.ext\n\n"
        "[Otra carpeta]\n"
        "- otro.ext\n\n"
        "--- DOCUMENTOS ---\n"
        + "\n".join(descripcion)
    )

    respuesta, fuentes = pedir_con_busqueda(SISTEMA, peticion)
    grupos = leer_agrupacion(respuesta)
    if not grupos:
        raise TareasError("el modelo no ha devuelto ningún grupo de carpetas.")
    return grupos, fuentes


def leer_agrupacion(respuesta: str) -> list[Grupo]:
    """Lee la respuesta del modelo y la convierte en grupos."""
    grupos: list[Grupo] = []
    grupo: Grupo | None = None

    for linea in respuesta.splitlines():
        if not linea.strip():
            continue

        carpeta = RE_CARPETA.match(linea)
        if carpeta:
            grupo = Grupo(nombre=_nombre_de_carpeta(carpeta.group(1)))
            grupos.append(grupo)
            continue

        documento = RE_DOCUMENTO.match(linea)
        if documento and grupo is not None:
            grupo.documentos.append(documento.group(1))

    return [g for g in grupos if g.documentos]


def _fichas_de(carpeta: Path) -> list[Path]:
    """Las fichas .md de la carpeta «md»."""
    directorio = carpeta / "md"
    if not directorio.is_dir():
        return []
    return sorted(directorio.glob("*.md"), key=lambda p: p.name.lower())


def _sin_clasificar(documentos: list[str]) -> list[Grupo]:
    """El plan de reserva: una sola carpeta con todo."""
    return [Grupo(nombre=CARPETA_SIN_CLASIFICAR, documentos=list(documentos))]


def planear(carpeta: Path, usar_ia: bool = True) -> Plan:
    """Agrupa los documentos analizados de una carpeta y devuelve el plan."""
    from .errores import ErrorIA

    carpeta = Path(carpeta).expanduser()
    if not carpeta.is_dir():
        raise TareasError(f"La carpeta «{carpeta}» no existe o no es una carpeta.")

    rutas = _fichas_de(carpeta)
    if not rutas:
        raise TareasError(
            f"No hay fichas en «{carpeta / 'md'}». Ejecuta primero «tareas analizar» "
            "en esta carpeta."
        )

    documentos: list[tuple[str, str]] = []
    por_nombre: dict[str, fichas.Ficha] = {}
    for ruta in rutas:
        ficha = fichas.leer(ruta)
        if ficha.estado == fichas.FORMATO_INVALIDO or not ficha.nombre_original:
            continue
        documentos.append((ficha.nombre_original, ficha.contenido))
        por_nombre[ficha.nombre_original] = ficha

    if not documentos:
        raise TareasError("No hay ningún documento analizable en esta carpeta.")

    if not usar_ia:
        return Plan(
            grupos=_sin_clasificar([n for n, _ in documentos]),
            fichas=por_nombre,
        )

    try:
        grupos, fuentes = pedir_agrupacion(documentos)
    except ErrorIA as exc:
        raise TareasError(
            f"No se ha podido usar el modelo ({exc}). "
            "Se usará una sola carpeta con todos los documentos."
        ) from exc

    return Plan(grupos=grupos, fichas=por_nombre, fuentes=fuentes)


def aplicar(carpeta: Path, destino: Path, plan: Plan) -> tuple[list[str], list[str]]:
    """Crea las carpetas en el destino y mueve los documentos dentro.

    Devuelve (movidos, errores). Los nombres originales se respetan y la
    carpeta «md» de fichas viaja con cada documento.
    """
    from .nombres import mismo_nombre

    carpeta = Path(carpeta).expanduser()
    destino = Path(destino).expanduser()
    destino.mkdir(parents=True, exist_ok=True)

    movidos: list[str] = []
    errores: list[str] = []
    fichas_por_nombre = plan.fichas

    for grupo in plan.grupos:
        carpeta_destino = destino / grupo.nombre
        carpeta_destino.mkdir(parents=True, exist_ok=True)

        for nombre in grupo.documentos:
            ficha = fichas_por_nombre.get(nombre)
            if ficha is None:
                ficha = next(
                    (
                        f
                        for clave, f in fichas_por_nombre.items()
                        if mismo_nombre(clave, nombre)
                    ),
                    None,
                )
            if ficha is None:
                errores.append(f"{nombre}: no se encuentra su ficha")
                continue

            origen = carpeta / ficha.nombre_compatible
            if not origen.exists():
                errores.append(f"{ficha.nombre_original}: no se encuentra el fichero")
                continue

            final = sin_conflicto(carpeta_destino, ficha.nombre_original)
            try:
                shutil.move(str(origen), str(final))
            except OSError as exc:
                errores.append(f"{ficha.nombre_original}: {exc.strerror or exc}")
                continue
            movidos.append(f"{ficha.nombre_original} -> {grupo.nombre}/")

            # La ficha viaja con su documento.
            ficha_origen = carpeta / "md" / f"{ficha.nombre_compatible}.md"
            if ficha_origen.is_file():
                destino_fichas = carpeta_destino / "md"
                destino_fichas.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(ficha_origen), str(destino_fichas / ficha_origen.name))
                except OSError:
                    pass

    return movidos, errores
