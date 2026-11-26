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

Ningún documento se queda atrás: si el modelo deja alguno sin colocar se le
vuelve a preguntar una segunda vez con lo que falta, y lo que siga sin sitio
va a una carpeta «Por clasificar» que la CLI enseña en la consola.
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

#: La carpeta donde va lo que ni a la segunda se ha podido colocar.
CARPETA_POR_CLASIFICAR = "Por clasificar"

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
    """Lo que hay que hacer: los grupos, las fichas, las fuentes y un aviso."""

    grupos: list[Grupo] = field(default_factory=list)
    fichas: dict[str, fichas.Ficha] = field(default_factory=dict)
    fuentes: list[Fuente] = field(default_factory=list)
    aviso: str = ""


def _nombre_de_carpeta(nombre: str) -> str:
    """Un nombre de carpeta que se pueda crear en cualquier sistema."""
    limpio = re.sub(r"[\\/:*?\"<>|]+", "-", nombre).strip()
    limpio = re.sub(r"\s+", " ", limpio)
    return limpio[:80] or CARPETA_POR_CLASIFICAR


def pedir_agrupacion(
    documentos: list[tuple[str, str]], carpetas_conocidas: list[str] | None = None
) -> tuple[list[Grupo], list[Fuente]]:
    """Le pide al modelo que agrupe los documentos en carpetas.

    «documentos» es una lista de (nombre, fragmento de contenido). Con
    «carpetas_conocidas» se le dicen las carpetas que ya existen, para que
    las reuse en vez de inventar una parecida.
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
        "- Debes colocar TODOS los documentos, sin dejar ninguno fuera. Si un "
        "documento no se puede leer (una foto, un instalador, un ZIP…), "
        "clasifícalo por su nombre y su tipo de fichero; solo si no hay ni "
        f"una pista, déjalo en la carpeta «{CARPETA_POR_CLASIFICAR}».\n"
        "- Cada documento va en una sola carpeta.\n\n"
    )
    if carpetas_conocidas:
        peticion += (
            "Estas carpetas ya existen; úsalas cuando tenga sentido y crea "
            "otras nuevas solo si hace falta:\n"
            + "\n".join(f"- {nombre}" for nombre in carpetas_conocidas)
            + "\n\n"
        )
    peticion += (
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
    return [Grupo(nombre=CARPETA_POR_CLASIFICAR, documentos=list(documentos))]


def _clave(nombre: str) -> str:
    """La forma comparable de un nombre: compatible, en minúsculas."""
    from .nombres import compatible

    return compatible(Path(nombre).name).lower()


def _sin_colocar(
    documentos: list[tuple[str, str]], grupos: list[Grupo]
) -> list[tuple[str, str]]:
    """Los documentos que el modelo no puso en ninguna carpeta.

    Los nombres que devuelve el modelo no siempre coinciden letra a letra con
    los reales (les quita acentos, cambia espacios por guiones, a veces deja
    fuera la extensión). Se comparan por su forma «compatible» y, si no, por
    el nombre sin extensión, que es lo bastante tolerante para reconocerlos.
    """
    colocadas: set[str] = set()
    for grupo in grupos:
        for puesto in grupo.documentos:
            colocadas.add(_clave(puesto))
            colocadas.add(_clave(Path(puesto).stem))

    restantes: list[tuple[str, str]] = []
    for nombre, fragmento in documentos:
        if _clave(nombre) in colocadas or _clave(Path(nombre).stem) in colocadas:
            continue
        restantes.append((nombre, fragmento))
    return restantes


def _mezclar(grupos: list[Grupo], nuevos: list[Grupo]) -> None:
    """Añade grupos nuevos, juntando los que repiten nombre de carpeta."""
    por_nombre = {grupo.nombre: grupo for grupo in grupos}
    for nuevo in nuevos:
        existente = por_nombre.get(nuevo.nombre)
        if existente is not None:
            existente.documentos.extend(nuevo.documentos)
        else:
            grupos.append(nuevo)
            por_nombre[nuevo.nombre] = nuevo


def _resolver_nombres(grupos: list[Grupo], reales: dict[str, fichas.Ficha]) -> None:
    """Cambia los nombres del modelo por los reales de las fichas.

    El modelo escribe los nombres «sucios» (sin acentos, con guiones, a veces
    sin extensión). Aquí se emparejan con el `nombre_original` de verdad de
    cada ficha, y si un documento aparece en dos carpetas se deja en la primera
    que lo nombró: un documento va en una sola carpeta.
    """
    por_clave = {_clave(nombre): nombre for nombre in reales}
    vistos: set[str] = set()

    for grupo in grupos:
        definitivos: list[str] = []
        for puesto in grupo.documentos:
            real = por_clave.get(_clave(puesto)) or por_clave.get(_clave(Path(puesto).stem))
            if real is None:
                # El modelo se inventó un nombre: ese documento no está en
                # ninguna parte de verdad. Se descarta de aquí; el plan ya lo
                # hará acabar en «Por clasificar».
                continue
            if real in vistos:
                continue
            vistos.add(real)
            definitivos.append(real)
        grupo.documentos = definitivos

    grupos[:] = [grupo for grupo in grupos if grupo.documentos]


def planear(carpeta: Path, usar_ia: bool = True) -> Plan:
    """Agrupa los documentos analizados de una carpeta y devuelve el plan.

    Nada más que dos garantías: todos los ficheros de la carpeta entran en el
    juego (también los que no tienen texto legible, como las fotos, que el
    modelo juzga por el nombre y el tipo) y ninguno se queda sin carpeta: lo
    que no coloque el modelo se le vuelve a preguntar una segunda vez, y lo
    que siga sin sitio va a «Por clasificar».
    """
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
        if not ficha.nombre_original:
            continue
        if ficha.estado == fichas.FORMATO_INVALIDO:
            # Sin texto extraíble (una foto, un .deb, un ZIP): la pista es lo
            # que dice su propio nombre y el tipo de fichero.
            fragmento = (
                f"(sin texto legible; tipo de fichero: {ficha.formato or 'desconocido'})"
            )
        else:
            fragmento = ficha.contenido
        documentos.append((ficha.nombre_original, fragmento))
        por_nombre[ficha.nombre_original] = ficha

    if not documentos:
        raise TareasError("No hay ningún documento analizado en esta carpeta.")

    if not usar_ia:
        return Plan(
            grupos=_sin_clasificar([n for n, _ in documentos]),
            fichas=por_nombre,
            aviso="Sin modelo: todos los documentos van a la carpeta «Por clasificar».",
        )

    try:
        grupos, fuentes = pedir_agrupacion(documentos)
    except ErrorIA as exc:
        return Plan(
            grupos=_sin_clasificar([n for n, _ in documentos]),
            fichas=por_nombre,
            aviso=(
                f"No se ha podido usar el modelo ({exc}); todos los documentos "
                "van a la carpeta «Por clasificar»."
            ),
        )

    # Segunda pasada con lo que el modelo dejó fuera: a veces basta con
    # preguntarle otra vez, ya con las carpetas existentes delante.
    restantes = _sin_colocar(documentos, grupos)
    if restantes:
        try:
            nuevos, fuentes_extra = pedir_agrupacion(
                restantes, carpetas_conocidas=[g.nombre for g in grupos]
            )
        except ErrorIA:
            fuentes_extra = []
        if nuevos:
            _mezclar(grupos, nuevos)
            fuentes.extend(
                fuente for fuente in fuentes_extra if fuente not in fuentes
            )
        restantes = _sin_colocar(documentos, grupos)

    # Los nombres del modelo se convierten en los reales de las fichas, para
    # que «aplicar» mueva el fichero exacto y no uno adivinado.
    _resolver_nombres(grupos, por_nombre)

    if restantes:
        grupos.append(
            Grupo(nombre=CARPETA_POR_CLASIFICAR, documentos=[n for n, _ in restantes])
        )

    return Plan(grupos=grupos, fichas=por_nombre, fuentes=fuentes)


def aplicar(carpeta: Path, destino: Path, plan: Plan) -> tuple[list[str], list[str]]:
    """Crea las carpetas en el destino y mueve los documentos dentro.

    Devuelve (movidos, errores). Los nombres originales se respetan y la
    carpeta «md» de fichas viaja con cada documento.

    Cada ficha que se mueve se **reescribe** dejando apuntado de dónde salió
    (`origen`) y dónde está ahora (`destino`): así `tareas deshacer` puede
    devolver también lo que movió `clasificar`, no solo lo de `organizar`.
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

            # La ficha viaja con su documento y se reescribe para que
            # «deshacer» sepa cómo devolver este movimiento.
            ficha_origen = carpeta / "md" / f"{ficha.nombre_compatible}.md"
            if ficha_origen.is_file():
                destino_fichas = carpeta_destino / "md"
                destino_fichas.mkdir(parents=True, exist_ok=True)
                nueva_ruta = destino_fichas / ficha_origen.name
                try:
                    shutil.move(str(ficha_origen), str(nueva_ruta))
                except OSError:
                    pass
                else:
                    movida = fichas.leer(nueva_ruta)
                    movida.origen = str(carpeta)
                    movida.destino = str(carpeta_destino)
                    movida.carpeta = grupo.nombre
                    fichas.escribir(movida, nueva_ruta)

    return movidos, errores
