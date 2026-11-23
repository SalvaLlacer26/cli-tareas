"""El comando «resumir»: apuntes completos del tema que acota un documento.

El documento NO se resume ni se copia. Solo sirve para dos cosas:

1. **Delimitar el tema**: qué tema trata y **hasta dónde llega** (por ejemplo,
   «componentes de un PC, pero solo hasta los microprocesadores»). Esa acotación
   es la que define el examen que hay que poder aprobar.
2. Los datos del encabezado y del pie del documento generado (nombre, unidad,
   asignatura).

Con esa acotación, el modelo **escribe apuntes completos desde cero**,
investigando la teoría en internet, con la riqueza necesaria para aprobar un
examen del tema acotado. El contenido del documento original no se usa.

Si no hay modelo disponible —sin clave, sin red, servidor caído— la CLI lo
explica en una línea y guarda una **extracción del documento** con fuentes
buscadas en internet, avisando de que no son los apuntes de verdad.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .busqueda import Fuente
from .documentos import Seccion, escribir_documento
from .errores import DocumentoNoEncontrado, ErrorIA
from .ficha import Ficha
from .markdown import a_secciones

#: Máximo de líneas por apartado en la versión extractiva (sin IA).
MAXIMO_LINEAS_POR_SECCION = 25

#: Máximo de apartados en la versión extractiva.
MAXIMO_SECCIONES = 12

#: Cuánto documento se le enseña al modelo para delimitar: el principio dice de
#: qué va el tema; el final dice dónde se queda.
DELIMITAR_INICIO = 5000
DELIMITAR_FINAL = 1500

#: Palabras que delatan un apartado de un documento de apuntes.
MARCAS_DE_SECCION = (
    "índice", "indice", "contenido", "introducción", "introduccion", "resumen",
    "objetivos", "contenidos", "ejercicios", "actividades", "casos prácticos",
    "practica", "bibliografía", "bibliografia", "conclusiones", "anexos",
)

#: El modelo que delimita: ni investiga ni escribe, solo mira y clasifica.
SISTEMA_DELIMITAR = (
    "Analizas documentos de clase de ciclos formativos de informática y dices "
    "qué tratan y hasta dónde llegan. Respondes SOLO con un objeto JSON válido, "
    "sin explicaciones ni marcas de código."
)

#: El modelo que escribe los apuntes.
SISTEMA_APUNTES = (
    "Eres profesor de un ciclo formativo de informática y escribes el manual de "
    "la asignatura. Escribes apuntes COMPLETOS que permiten aprobar un examen "
    "sin abrir ningún otro libro: definiciones exactas, funcionamiento, "
    "ejemplos, tablas comparativas y trucos de examen. No haces resúmenes ni "
    "dices «el documento habla de»: desarrollas el tema de verdad. Respondes "
    "SOLO con el contenido, en Markdown, sin preámbulos ni comentarios sobre lo "
    "que haces."
)


@dataclass
class Alcance:
    """Qué tema trata el documento y hasta dónde llega dentro de él."""

    tema: str
    nivel: str = ""
    #: Subtemas que el documento trata (o roza): el rango de los apuntes.
    cubre: list[str] = field(default_factory=list)
    #: Partes habituales del tema que el documento NO llega a tratar.
    fuera: list[str] = field(default_factory=list)
    idioma: str = ""
    #: De dónde sale la acotación: «modelo» o «documento» (aproximada).
    origen: str = "modelo"


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


# ---------------------------------------------------------------- delimitar


def _fragmento_para_delimitar(ficha: Ficha) -> str:
    """El principio y el final del documento: dicen de qué va y dónde acaba."""
    contenido = _limpiar(ficha.contenido)
    if len(contenido) <= DELIMITAR_INICIO + DELIMITAR_FINAL:
        return contenido
    return (
        contenido[:DELIMITAR_INICIO]
        + "\n\n[…]\n\n"
        + contenido[-DELIMITAR_FINAL:]
    )


def _extraer_objeto_json(texto: str) -> dict | None:
    """El primer objeto JSON que haya en un texto, o None si no hay ninguno.

    Los modelos suelen envolver el JSON en marcas de código o añadir una frase
    antes; se busca la primera llave y se intenta leer hasta la última.
    """
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio == -1 or fin <= inicio:
        return None
    try:
        datos = json.loads(texto[inicio : fin + 1])
    except json.JSONDecodeError:
        return None
    return datos if isinstance(datos, dict) else None


def _lista(texto: str) -> list[str]:
    """Convierte lo que sea en una lista de frases limpias y sin vacíos."""
    if isinstance(texto, str):
        partes = re.split(r"[;\n•·]|,(?=\s*(?:y|and|i)\s)", texto)
    elif isinstance(texto, list):
        partes = [str(parte) for parte in texto]
    else:
        partes = []
    return [parte.strip(" -,·.") for parte in partes if parte and parte.strip(" -,·.")]


def parsear_alcance(texto: str, ficha: Ficha) -> Alcance:
    """El JSON de la delimitación convertido en un `Alcance`.

    Si el JSON no aparece o no dice el tema, se aproxima lo que se puede desde
    el propio documento; nunca se lanza: una delimitación imperfecta da mejores
    apuntes que ninguna.
    """
    datos = _extraer_objeto_json(texto)
    alcance = alcance_desde_documento(ficha)
    if not datos:
        return alcance

    tema = str(datos.get("tema") or "").strip()
    if tema:
        alcance.tema = tema
    nivel = str(datos.get("nivel") or "").strip()
    if nivel:
        alcance.nivel = nivel
    cubre = _lista(datos.get("cubre"))
    if cubre:
        alcance.cubre = cubre
    fuera = _lista(datos.get("fuera") or datos.get("no_cubre"))
    if fuera:
        alcance.fuera = fuera
    alcance.idioma = str(datos.get("idioma") or "").strip() or alcance.idioma
    alcance.origen = "modelo"
    return alcance


def alcance_desde_documento(ficha: Ficha) -> Alcance:
    """La acotación aproximada que se puede sacar del documento sin IA.

    El tema sale del primer título que signifique algo (se saltan líneas que
    son solo «UD1.», «Tema 3»…); como subtemas se ponen los apartados que
    detecta el propio parser. Sin modelo no hay forma de saber dónde termina el
    tema, así que el rango «fuera» queda vacío.
    """
    RE_MARCADOR_UNIDAD = re.compile(
        r"^(?:ud|unitat|unidad|tema|bloque|cap[ií]tulo|parte)\s*\.?\s*\d+\.?$",
        re.IGNORECASE,
    )

    lineas = [linea.strip() for linea in (ficha.contenido or "").splitlines() if linea.strip()]

    tema = ""
    for linea in lineas:
        # Se saltan líneas que son solo el marcador de unidad («UD1.», «Tema 2»).
        if RE_MARCADOR_UNIDAD.match(linea):
            continue
        sin_unidad = re.sub(
            r"^(?:ud|unitat|unidad|tema|bloque|cap[ií]tulo|parte)\s*\.?\s*\d+\.?\s*[-–:]?\s*",
            "",
            linea,
            flags=re.IGNORECASE,
        ).strip()
        tema = sin_unidad or linea
        if tema:
            break

    if not tema:
        tema = _base(ficha.nombre_original).replace("_", " ").strip()

    apartados = _detectar_apartados(_limpiar(ficha.contenido))
    cubre = [
        titulo
        for titulo, _ in apartados
        if titulo.lower() not in MARCAS_DE_SECCION and not RE_MARCADOR_UNIDAD.match(titulo)
    ]
    return Alcance(
        tema=tema or "el tema del documento",
        cubre=cubre[:MAXIMO_SECCIONES],
        origen="documento",
    )


def delimitar_tema(ficha: Ficha) -> Alcance:
    """Fase 1: el documento se mira SOLO para saber el tema y su rango.

    El modelo ve el principio y el final del documento y devuelve un JSON con
    el tema, el nivel, lo que cubre, lo que no llega a tratar y el idioma. Con
    eso se escriben después los apuntes; aquí no se busca nada en internet.
    """
    from .ia import pedir

    fragmento = _fragmento_para_delimitar(ficha)
    if not fragmento and not ficha.nombre_original:
        raise ErrorIA("el documento no tiene ni texto ni nombre para delimitar el tema")

    peticion = (
        "Un alumno tiene este documento de clase. NO lo resumas: solo quiero "
        "saber QUÉ TRATA y HASTA DÓNDE LLEGA, para escribir después unos apuntes "
        "que cubran exactamente ese rango.\n\n"
        "Contesta SOLO con un objeto JSON con estas claves:\n"
        '  "tema": el tema general (p. ej. «Componentes de un PC»),\n'
        '  "nivel": el curso o nivel que aparenta (p. ej. «1º DAM»);\n'
        '  "cubre": lista de los subtemas que el documento desarrolla o trata, '
        "en el orden en que aparecen;\n"
        '  "fuera": partes de ese mismo tema general que el documento NO llega a '
        "tratar, o solo roza (si habla de componentes de un PC y se queda en los "
        "microprocesadores, aquí irían «la memoria», «la gráfica», «el "
        "almacenamiento»...);\n"
        '  "idioma": el idioma del documento («es», «ca», ...).\n\n'
        "Si dudas entre dos temas, quédate con el más concreto.\n\n"
        f"--- DOCUMENTO (principio y final) ---\n{fragmento}"
    )

    respuesta = pedir(SISTEMA_DELIMITAR, peticion, temperatura=0.1)
    alcance = parsear_alcance(respuesta, ficha)
    if not alcance.cubre:
        raise ErrorIA("el modelo no ha sabido delimitar el tema del documento")
    return alcance


# ---------------------------------------------------------------- generar


def _peticion_apuntes(alcance: Alcance) -> str:
    """La petición de la fase 2: apuntes completos del rango, sin documento."""
    cubre = "\n".join(f"- {subtema}" for subtema in alcance.cubre) or "- Todo el tema."
    fuera = (
        "\n".join(f"- {subtema}" for subtema in alcance.fuera)
        or "- (Sin indicación: no te pases del nivel de un primer curso.)"
    )
    idioma = alcance.idioma or "el idioma del tema"
    nivel = f", de nivel {alcance.nivel}" if alcance.nivel else ""

    return (
        f"Escribe unos APUNTES COMPLETOS{nivel} sobre «{alcance.tema}».\n\n"
        f"No tienes ningún documento delante y esto NO es un resumen de nada: "
        f"tú eres el autor del manual. Escribe la teoría desde cero, con la "
        f"profundidad de un libro de texto breve, de forma que un alumno apruebe "
        f"un examen de este tema sin abrir ningún otro material.\n\n"
        f"EL RANGO es exactamente este. Se escribe de:\n{cubre}\n\n"
        f"Se PARA antes de (fuera del examen, no lo desarrolles; si lo mencionas, "
        f"es solo una línea del estilo «esto se ve en el siguiente tema»):\n{fuera}\n\n"
        f"1) INVESTIGA antes de escribir. No inventes: por cada concepto "
        f"importante escribe una línea con la forma [[BUSCAR: consulta]] (una "
        f"por concepto, varias en el mismo turno) y termina tu turno; te "
        f"devolveré fuentes de internet —enciclopedia y web— para que uses las "
        f"mejores.\n\n"
        f"2) ESCRIBE los apuntes, en {idioma}:\n"
        f"- Empieza con un apartado «## Qué hay que saber de este tema»: 8-12 "
        f"cosas que hay que tener claras antes de nada.\n"
        f"- Después, un apartado «##» por cada punto del rango, en orden. En "
        f"cada uno: definición exacta, cómo funciona por dentro, para qué sirve, "
        f"un ejemplo concreto, una tabla o lista comparativa si el tema se "
        f"presta, y un «En el examen» con lo que suelen preguntar y la trampa "
        f"habitual.\n"
        f"- Nada de «existe tal cosa»: explica nombres, números, unidades y "
        f"relaciones entre las cosas. Un apunte que no se pueda preguntar no es "
        f"un apunte.\n"
        f"- Termina con «## Ideas clave» (10-15 para memorizar) y «## Preguntas "
        f"típicas de examen» (8-10 preguntas con su respuesta razonada en 2-4 "
        f"líneas).\n"
        f"- La extensión la marca el tema, no tú: no recortes por ahorrar."
    )


def generar_apuntes(alcance: Alcance) -> tuple[list[Seccion], list[Fuente]]:
    """Fase 2: apuntes completos del tema acotado, investigando en internet.

    No recibe el documento: el contenido sale del conocimiento del modelo y de
    la investigación. Devuelve las secciones ya convertidas y las fuentes.
    """
    from .ia import pedir_con_busqueda

    respuesta, fuentes = pedir_con_busqueda(
        SISTEMA_APUNTES, _peticion_apuntes(alcance), maximo_consultas=6
    )
    secciones = a_secciones(respuesta, titulo="Qué hay que saber de este tema")
    if not secciones or not any(s.lineas for s in secciones):
        raise ErrorIA("el modelo ha contestado pero sin contenido")
    return secciones, fuentes


# ------------------------------------------------------------------ salida


def construir_secciones_extractivas(ficha: Ficha) -> list[Seccion]:
    """La versión sin IA: una extracción del documento, no unos apuntes.

    Sin modelo no se pueden escribir apuntes desde cero; se guarda lo que hay,
    avisando en una nota de que esto no son los apuntes.
    """
    contenido = _limpiar(ficha.contenido)
    if not contenido:
        return [
            Seccion(
                "Aviso",
                ["No se ha podido extraer texto de este documento, y sin modelo "
                 "de IA no se pueden escribir apuntes desde cero."],
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

    notas = [
        "Estos NO son los apuntes: se han generado sin inteligencia artificial "
        "porque no había modelo disponible, y sin modelo no se pueden escribir "
        "apuntes completos desde cero. Aquí está el texto del documento original.",
    ]
    if recortado:
        notas.append("Además, viene recortado: solo las primeras líneas de cada apartado.")
    secciones.append(Seccion("Nota", notas))
    return secciones


def consulta_del_documento(ficha: Ficha) -> str:
    """Una consulta de búsqueda sobre el tema, para cuando no hay modelo."""
    alcance = alcance_desde_documento(ficha)
    return alcance.tema


def ampliacion_sin_modelo(ficha: Ficha) -> tuple[list[Seccion], list[Fuente]]:
    """Sin modelo al menos se buscan fuentes de internet sobre el tema.

    No sustituye a los apuntes, pero un documento con las fuentes de la teoría
    sirve para empezar, y dice claramente lo que es.
    """
    from .busqueda import buscar

    consulta = consulta_del_documento(ficha)
    if not consulta:
        return [], []

    fuentes = buscar(consulta, limite=3)
    if not fuentes:
        return [], []

    secciones = []
    for fuente in fuentes:
        lineas = [f"Fuente: {fuente.url}", ""]
        lineas.extend(fuente.fragmento.splitlines()[:40])
        secciones.append(Seccion(fuente.titulo, lineas))
    return secciones, fuentes


def construir_apuntes(
    ficha: Ficha, con_ia: bool = True
) -> tuple[list[Seccion], str, list[Fuente]]:
    """Las secciones de los apuntes, la nota del encabezado y las fuentes.

    Con IA: delimitar el tema desde el documento y escribir apuntes completos
    del rango, investigando. Si cualquier fase falla, se cae a la extracción
    del documento con fuentes, avisando. Sin IA: extracción + fuentes.
    """
    if con_ia:
        aproximado = ""
        try:
            alcance = delimitar_tema(ficha)
        except ErrorIA as exc:
            alcance = alcance_desde_documento(ficha)
            aproximado = f" No he podido delimitar el tema con el modelo ({exc}); lo he aproximado desde el documento."

        if alcance.origen == "modelo":
            rango = ", ".join(alcance.cubre[:6])
            nota = (
                f"Apuntes escritos desde cero sobre «{alcance.tema}» "
                f"(rango: {rango}), sin copiar el documento original."
            )
        else:
            rango = ", ".join(alcance.cubre[:6]) or alcance.tema
            nota = (
                f"Apuntes escritos desde cero sobre «{alcance.tema}» "
                f"(rango aproximado: {rango}), sin copiar el documento original."
            )
            nota += aproximado or " La acotación del rango es aproximada."

        try:
            secciones, fuentes = generar_apuntes(alcance)
            if fuentes:
                nota += f" La teoría se ha investigado en internet: {len(fuentes)} fuente(s) citadas al final."
            else:
                nota += " No se ha encontrado información en internet; solo conocimiento del modelo."
            return secciones, nota, fuentes
        except ErrorIA as exc:
            nota = f"Sin apuntes de IA: {exc}."
            secciones = construir_secciones_extractivas(ficha)
            try:
                ampliacion, fuentes = ampliacion_sin_modelo(ficha)
            except Exception:  # noqa: BLE001 - la ampliación es un extra
                ampliacion, fuentes = [], []
            if ampliacion:
                nota += " Se han adjuntado fuentes de internet sobre el tema."
                secciones = [*secciones, *ampliacion]
            return secciones, nota, fuentes

    nota = "Sin apuntes de IA: no hay modelo configurado."
    secciones = construir_secciones_extractivas(ficha)
    try:
        ampliacion, fuentes = ampliacion_sin_modelo(ficha)
    except Exception:  # noqa: BLE001 - la ampliación es un extra
        ampliacion, fuentes = [], []
    if ampliacion:
        nota += " Se han adjuntado fuentes de internet sobre el tema."
        secciones = [*secciones, *ampliacion]
    return secciones, nota, fuentes


def escribir_resumen(ficha: Ficha, carpeta: Path, formato: str = "") -> Path:
    """Escribe los apuntes en la carpeta «resumenes».

    Se mantiene el nombre del comando y del fichero generado («resumir»,
    «_resumido») para no romper `evaluar`, que usa este documento como
    contexto; el contenido, eso sí, ya no es un resumen.
    """
    from .documentos import formato_preferido

    secciones, nota, fuentes = construir_apuntes(ficha, con_ia=True)
    titulo = f"Apuntes · {ficha.nombre_original}"
    bloques = [Seccion("", [nota], nivel=1), *secciones]

    if fuentes:
        lineas = []
        for fuente in fuentes:
            lineas.append(f"• {fuente.titulo} — {fuente.url}")
        bloques.append(Seccion("Fuentes consultadas", lineas))

    destino = carpeta / "resumenes"
    nombre = f"{_base(ficha.nombre_original)}_resumido{formato or formato_preferido()}"
    return escribir_documento(
        destino / nombre,
        titulo,
        bloques,
        unidad=unidad_del_documento(ficha),
        asignatura=ficha.asignatura,
    )


def _base(nombre: str) -> str:
    """El nombre del fichero sin la extensión."""
    from .nombres import separar_extension

    return separar_extension(nombre)[0]


#: Las formas en que una unidad puede estar escrita en el nombre del fichero
#: o en las primeras líneas del documento: «UD1.», «Tema 3», «Unitat 2»…
RE_UNIDAD = re.compile(
    r"\b((?:ud|unitat|unidad|tema|bloque|cap[ií]tulo|parte)\s*\.?\s*\d+)\b",
    re.IGNORECASE,
)


def unidad_del_documento(ficha: Ficha) -> str:
    """La unidad a la que parece pertenecer el documento, si se ve clara.

    Se busca en el nombre del fichero y en las primeras líneas del contenido,
    que es donde los apuntes suelen llevar «UD1.» o «Tema 3». El resultado va
    en el encabezado de los documentos generados, con la asignatura al lado.
    """
    candidatos = [ficha.nombre_original, " ".join(ficha.contenido.splitlines()[:3])]
    for texto in candidatos:
        encontrada = RE_UNIDAD.search(texto)
        if encontrada:
            return encontrada.group(1).strip().rstrip(".")
    return ""


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
