"""El comando «resumir»: un resumen del documento hecho con un modelo de IA.

El modelo recibe el texto que ya se extrajo en el análisis (está en la ficha
.md, así que no hay que volver a abrir el PDF) y devuelve un resumen
organizado en Markdown. Ese Markdown se convierte en las secciones del
documento final.

Si no hay modelo disponible —no hay clave, no hay red, el servidor falla— la
CLI lo explica en una línea y genera la **versión extractiva**: las primeras
líneas de cada apartado. No es lo mismo, pero es algo, y el documento dice
claramente que se ha hecho sin IA.
"""

from __future__ import annotations

from pathlib import Path

from .busqueda import Fuente
from .documentos import Seccion, escribir_documento
from .errores import DocumentoNoEncontrado, ErrorIA
from .ficha import Ficha
from .markdown import a_secciones

#: Máximo de líneas por apartado en la versión extractiva.
MAXIMO_LINEAS_POR_SECCION = 25

#: Máximo de apartados en la versión extractiva.
MAXIMO_SECCIONES = 12

#: Cuántos caracteres del documento se le envían al modelo.
MAXIMO_CARACTERES = 12000

#: Palabras que delatan un apartado de un documento de apuntes.
MARCAS_DE_SECCION = (
    "índice", "indice", "contenido", "introducción", "introduccion", "resumen",
    "objetivos", "contenidos", "ejercicios", "actividades", "casos prácticos",
    "practica", "bibliografía", "bibliografia", "conclusiones", "anexos",
)

#: Las instrucciones que se le dan al modelo.
SISTEMA = (
    "Eres un profesor que prepara material de estudio para estudiantes de "
    "informática. Escribes en español y en el idioma del documento original. "
    "Respondes SOLO con el contenido pedido, en Markdown, sin comentarios "
    "sobre lo que haces y sin rodeos. No escribas frases como «Aquí tienes...»: "
    "empieza directamente por el contenido."
)


def _limpiar(texto: str) -> str:
    """Quita líneas en blanco de más y espacios sobrantes."""
    lineas = [linea.rstrip() for linea in texto.splitlines()]
    salida: list[str] = []
    anterior_vacia = False
    for linea in lineas:
        vacia = not linea.strip()
        if vacia and anterior_vacia:
            continue
        salida.append(linea)
        anterior_vacia = vacia
    return "\n".join(salida).strip()


def _detectar_apartados(texto: str) -> list[tuple[str, str]]:
    """Trocea el texto en apartados, con su título."""
    lineas = texto.splitlines()
    apartados: list[tuple[str, str]] = []
    titulo_actual = "Contenido"
    cuerpo: list[str] = []

    for linea in lineas:
        es_titulo = (
            2 < len(linea) < 90
            and not linea.endswith((".", ",", ";", ":"))
            and (linea.isupper() or linea.istitle() or linea.strip().lower() in MARCAS_DE_SECCION)
            and not linea.startswith((" ", "\t", "-", "*", "|"))
        )
        if es_titulo:
            if cuerpo:
                apartados.append((titulo_actual, "\n".join(cuerpo)))
            titulo_actual = linea.strip()
            cuerpo = []
        else:
            cuerpo.append(linea)

    if cuerpo:
        apartados.append((titulo_actual, "\n".join(cuerpo)))

    return apartados


def construir_secciones_extractivas(ficha: Ficha) -> list[Seccion]:
    """La versión sin IA: las primeras líneas de cada apartado.

    Es una extracción, no un resumen. Se usa cuando no hay modelo, y el
    documento avisa de ello.
    """
    contenido = _limpiar(ficha.contenido)
    if not contenido:
        return [
            Seccion(
                "Aviso",
                ["No se ha podido extraer texto de este documento, "
                 "así que no hay nada que resumir."],
            )
        ]

    apartados = _detectar_apartados(contenido) or [("Contenido", contenido)]

    secciones: list[Seccion] = []
    recortado = False
    for titulo, cuerpo in apartados[:MAXIMO_SECCIONES]:
        lineas = [linea for linea in cuerpo.splitlines() if linea.strip()]
        if len(lineas) > MAXIMO_LINEAS_POR_SECCION:
            lineas = lineas[:MAXIMO_LINEAS_POR_SECCION]
            recortado = True
        secciones.append(Seccion(titulo.strip() or "Contenido", lineas))

    if len(apartados) > MAXIMO_SECCIONES:
        recortado = True

    if recortado:
        secciones.append(
            Seccion(
                "Nota",
                [
                    "Este resumen se ha hecho SIN inteligencia artificial, porque no "
                    "había modelo disponible: es una extracción del principio de cada "
                    "apartado, no un resumen de verdad.",
                ],
            )
        )

    return secciones


def pedir_resumen(ficha: Ficha) -> tuple[list[Seccion], list[Fuente]]:
    """Le pide al modelo un resumen y lo convierte en secciones.

    Si el documento es demasiado escueto, el modelo pide una búsqueda con
    ``[[BUSCAR: consulta]]`` y la herramienta se la devuelve ya hecha.
    """
    from .ia import pedir_con_busqueda

    contenido = ficha.contenido.strip()[:MAXIMO_CARACTERES]
    if not contenido:
        raise ErrorIA("el documento no tiene texto que resumir")

    peticion = (
        f"Resume este documento de apuntes.\n\n"
        f"Reglas:\n"
        f"- Un resumen de máximo 10 páginas, sin imágenes.\n"
        f"- Empieza con un apartado «Ideas principales» con entre 5 y 10 puntos "
        f"con los conceptos que de verdad hay que saberse.\n"
        f"- Después, un apartado por cada tema del documento, con el contenido "
        f"esencial y, si ayuda, una tabla.\n"
        f"- Usa encabezados de segundo nivel (##) para los apartados.\n"
        f"- No inventes nada: solo lo que esté en el texto.\n"
        f"- Escribe en el idioma del documento.\n\n"
        f"Si el documento es demasiado escueto o está muy sintetizado (por ejemplo, "
        f"solo tiene un índice y títulos, o es un PDF de diapositivas con muy poco "
        f"texto), te falta información para hacer un buen resumen. En ese caso, "
        f"escribe una línea con la forma [[BUSCAR: consulta]] y termina tu turno: "
        f"se buscará esa información en internet y te la devolveré para que la uses. "
        f"Pide una búsqueda por concepto, no por el documento entero.\n\n"
        f"--- DOCUMENTO ---\n{contenido}"
    )

    respuesta, fuentes = pedir_con_busqueda(SISTEMA, peticion)
    secciones = a_secciones(respuesta, titulo="Ideas principales")
    if not secciones or not any(s.lineas for s in secciones):
        raise ErrorIA("el modelo ha contestado pero sin contenido")
    return secciones, fuentes


def consulta_del_documento(contenido: str) -> str:
    """Una consulta de búsqueda sacada del propio documento.

    Se usan las primeras palabras, que suelen ser el título. Si el título
    lleva el nombre del autor o el nombre del curso, «buscar» los va
    acortando hasta que algo encaja.
    """
    palabras = " ".join(contenido.split())[:200].split()
    return " ".join(palabras[:12])


def ampliacion_sin_modelo(ficha: Ficha) -> tuple[list[Seccion], list[Fuente]]:
    """Busca en internet lo que trata el documento, aunque no haya modelo.

    Si el servidor de modelos no está (o da error), al menos se pueden buscar
    las fuentes y añadirlas al documento, marcadas como lo que son. Es mejor
    que un resumen vacío, y deja claro que no lo ha hecho el modelo.
    """
    from .busqueda import buscar

    consulta = consulta_del_documento(ficha.contenido)
    if not consulta:
        return [], []

    fuentes = buscar(consulta, limite=2)
    if not fuentes:
        return [], []

    secciones = []
    for fuente in fuentes:
        lineas = [f"Fuente: {fuente.url}", ""]
        lineas.extend(fuente.fragmento.splitlines()[:40])
        secciones.append(Seccion(fuente.titulo, lineas))
    return secciones, fuentes


def construir_secciones(
    ficha: Ficha, con_ia: bool = True
) -> tuple[list[Seccion], str, list[Fuente]]:
    """Las secciones del resumen, una nota y las fuentes usadas."""
    if con_ia:
        try:
            secciones, fuentes = pedir_resumen(ficha)
            nota = "Generado con inteligencia artificial."
            if fuentes:
                nota += (
                    f" El documento era demasiado escueto, así que se ha completado "
                    f"con información de {len(fuentes)} fuente(s) de internet."
                )
            return secciones, nota, fuentes
        except ErrorIA as exc:
            nota = f"Generado sin inteligencia artificial: {exc}."
            secciones = construir_secciones_extractivas(ficha)
            try:
                ampliacion, fuentes = ampliacion_sin_modelo(ficha)
            except Exception:  # noqa: BLE001 - la ampliación es un extra
                ampliacion, fuentes = [], []
            if ampliacion:
                nota += (
                    " Aun así, se han buscado fuentes en internet sobre el tema "
                    "del documento; están abajo sin resumir."
                )
                secciones = [*secciones, *ampliacion]
            return secciones, nota, fuentes
    return (
        construir_secciones_extractivas(ficha),
        "Generado sin inteligencia artificial: no hay modelo configurado.",
        [],
    )


def escribir_resumen(ficha: Ficha, carpeta: Path, formato: str = "") -> Path:
    """Escribe el fichero del resumen en la carpeta «resumenes»."""
    from .documentos import formato_preferido

    secciones, nota, fuentes = construir_secciones(ficha, con_ia=True)
    titulo = f"Resumen · {ficha.nombre_original}"
    bloques = [Seccion("", [nota], nivel=1), *secciones]

    if fuentes:
        lineas = []
        for fuente in fuentes:
            lineas.append(f"• {fuente.titulo} — {fuente.url}")
        bloques.append(Seccion("Fuentes consultadas", lineas))

    destino = carpeta / "resumenes"
    nombre = f"{_base(ficha.nombre_original)}_resumido{formato or formato_preferido()}"
    return escribir_documento(destino / nombre, titulo, bloques)



def _base(nombre: str) -> str:
    """El nombre del fichero sin la extensión."""
    from .nombres import separar_extension

    return separar_extension(nombre)[0]


def buscar_ficha(carpeta: Path, nombre: str, carpetas: list | None = None) -> Ficha:
    """Busca la ficha de un documento por su nombre.

    Se acepta el nombre original o el compatible, con o sin extensión. Las
    comparaciones ignoran la forma Unicode: un fichero guardado en NFD y el
    nombre tecleado en NFC se ven iguales pero no lo son.
    """
    from . import ficha as fichas
    from .nombres import a_nfc, mismo_nombre
    from .organizador import _buscar_fichas

    carpeta = Path(carpeta).expanduser()
    objetivo = a_nfc(nombre)
    candidatos = [objetivo]
    if not Path(nombre).suffix:
        candidatos += [f"{objetivo}.pdf", f"{objetivo}.docx", f"{objetivo}.odt", f"{objetivo}.txt"]

    for ruta in _buscar_fichas(carpeta, carpetas):
        ficha = fichas.leer(ruta)
        if not ficha.nombre_original and not ficha.nombre_compatible:
            continue
        if a_nfc(ficha.nombre_original) in candidatos or a_nfc(ficha.nombre_compatible) in candidatos:
            return ficha
        base_original = _base(ficha.nombre_original)
        base_compatible = _base(ficha.nombre_compatible)
        if mismo_nombre(base_original, objetivo) or mismo_nombre(base_compatible, objetivo):
            return ficha

    raise DocumentoNoEncontrado(
        f"No encuentro la ficha de «{nombre}» en «{carpeta}». "
        "Ejecuta primero «tareas analizar» en esa carpeta."
    )
