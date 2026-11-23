"""El comando «evaluar»: una batería de ejercicios hecha con un modelo de IA.

El modelo recibe el texto del documento (que ya está en la ficha .md) y
devuelve los ejercicios en Markdown: preguntas de tipo test con alternativas
reales, preguntas de desarrollo y problemas de cálculo, con sus soluciones.

Si no hay modelo disponible, se genera la **versión extractiva**, que busca
definiciones y apartados en el texto. Es mucho más pobre, y el documento lo
dice.
"""

from __future__ import annotations

import random
import re
from dataclasses import replace
from pathlib import Path

from .documentos import Seccion, escribir_documento
from .errores import ErrorIA
from .ficha import Ficha
from .markdown import a_secciones

#: Máximo de preguntas de cada tipo en la versión extractiva.
MAXIMO_POR_TIPO = 6

#: Mínimo de preguntas que se piden a la batería: un examen corto no evalúa.
MINIMO_PREGUNTAS = 10

#: Un examen sienta mejor si cada vez sale distinto: temperatura alta para que
#: el modelo se mueva y no repita el mismo enunciado en dos pasadas.
TEMPERATURA_EXAMEN = 0.8

#: Enfoques que se le pueden pedir al modelo, para que varíe cada examen.
ENFOQUES = (
    "pregunta sobre todo conceptos y definiciones",
    "pregunta sobre todo la aplicación práctica de lo que se explica",
    "pone el acento en comparar y relacionar ideas del tema",
    "plantea casos y ejemplos numéricos sacados del contenido",
    "insiste en los errores típicos y en el porqué de cada cosa",
    "pregunta de forma directa, con enunciados cortos y concretos",
)

#: Palabras que suelen anunciar una definición.
MARCAS_DE_DEFINICION = (
    "se define", "se denomina", "consiste en", "servirá", "significa",
    "se entiende por", "se conoce como", "definición", "definicion",
)

#: Palabras que anuncian un cálculo o un ejemplo numérico.
MARCAS_DE_CALCULO = (
    "ejemplo", "ejercicios", "calcula", "calcular", "resuelve", "resolver",
    "aplicación", "aplicacion", "demostración", "demostracion", "práctica", "practica",
)

#: Número de líneas del contexto que se cita antes de cada pregunta.
LINEAS_DE_CONTEXTO = 3

#: Expresiones regulares que se consideran «fórmulas».
RE_FORMULA = re.compile(r"[A-Za-z]\s*=\s*[^.\n]{2,40}")

#: Las instrucciones que se le dan al modelo.
SISTEMA = (
    "Eres un profesor que prepara exámenes de informática para estudiantes de "
    "1º de DAM. Escribes en español y en el idioma del documento original. "
    "Respondes SOLO con el contenido pedido, en Markdown, sin comentarios "
    "sobre lo que haces. No escribas frases como «Aquí tienes...»: "
    "empieza directamente por el contenido."
)


def _definiciones(texto: str) -> list[str]:
    """Las frases del texto que parecen definiciones.

    Solo se aceptan frases con una forma de definición clara («se define»,
    «consiste en»…). Antes se buscaba también «es» y «son», que aparecen en
    casi todas las frases en castellano y convertían el ejercicio en un
    churro de frases cualesquiera.
    """
    encontradas: list[str] = []
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not (30 < len(limpia) < 220):
            continue
        if limpia.startswith(("|", "-", "*", "#", "•")):
            continue
        minuscula = limpia.lower()
        if any(marca in minuscula for marca in MARCAS_DE_DEFINICION):
            encontradas.append(limpia)
        if len(encontradas) >= MAXIMO_POR_TIPO * 2:
            break
    return encontradas


def _apartados(texto: str) -> list[str]:
    """Los títulos de los apartados del documento."""
    from .resumen import _detectar_apartados

    apartados = [titulo for titulo, _ in _detectar_apartados(texto)]
    return [a for a in apartados if len(a) > 3][: MAXIMO_POR_TIPO * 2]


def _contexto(texto: str, frase: str) -> list[str]:
    """Las líneas de alrededor de una frase, para darla como contexto."""
    lineas = texto.splitlines()
    for indice, linea in enumerate(lineas):
        if linea.strip() == frase:
            inicio = max(0, indice - LINEAS_DE_CONTEXTO)
            return [l.strip() for l in lineas[inicio : indice + 1] if l.strip()]
    return []


def construir_secciones_extractivas(ficha: Ficha) -> list[Seccion]:
    """La versión sin IA: busca definiciones y apartados en el texto."""
    from .resumen import _limpiar

    texto = _limpiar(ficha.contenido)
    if not texto:
        return [
            Seccion(
                "Aviso",
                ["No se ha podido extraer texto de este documento, "
                 "así que no se pueden preparar ejercicios."],
            )
        ]

    secciones: list[Seccion] = []

    definiciones = _definiciones(texto)
    random.shuffle(definiciones)  # cada pasada, un examen algo distinto
    lineas_test: list[str] = []
    for numero, definicion in enumerate(definiciones[:MAXIMO_POR_TIPO], start=1):
        contexto = _contexto(texto, definicion)
        if contexto:
            lineas_test.append(f"Contexto: {contexto[-1]}")
            lineas_test.append("")
        lineas_test.append(
            f"{numero}. {definicion}\n"
            f"   a) ..............................................\n"
            f"   b) ..............................................\n"
            f"   c) ..............................................\n"
            f"   d) ..............................................\n"
            f"   Respuesta: ______\n"
        )
    if lineas_test:
        secciones.append(Seccion("Tipo test", lineas_test))

    apartados = _apartados(texto)
    random.shuffle(apartados)
    lineas_desarrollo: list[str] = []
    for numero, apartado in enumerate(apartados[:MAXIMO_POR_TIPO], start=1):
        lineas_desarrollo.append(
            f"{numero}. Explica con tus palabras lo que trata el apartado "
            f"«{apartado}» y da un ejemplo.\n"
            f"   Respuesta:\n"
            f"   ................................................................\n"
            f"   ................................................................\n"
            f"   ................................................................\n\n"
        )
    if lineas_desarrollo:
        secciones.append(Seccion("Preguntas de desarrollo", lineas_desarrollo))

    calculos = [l.strip() for l in texto.splitlines() if RE_FORMULA.search(l) and len(l.strip()) > 12]
    random.shuffle(calculos)
    lineas_calculo: list[str] = []
    for numero, calculo in enumerate(calculos[:MAXIMO_POR_TIPO], start=1):
        lineas_calculo.append(
            f"{numero}. {calculo}\n"
            f"   Resuelve el apartado anterior dejando el procedimiento.\n"
            f"   Respuesta:\n"
            f"   ................................................................\n"
            f"   ................................................................\n\n"
        )
    if not lineas_calculo and apartados:
        lineas_calculo.append(
            "1. Repasa los ejemplos numéricos del documento y rehazlos sin mirar.\n"
            "   Respuesta:\n"
            "   ................................................................\n\n"
        )
    if lineas_calculo:
        secciones.append(Seccion("Cálculo y problemas", lineas_calculo))

    if not secciones:
        secciones.append(
            Seccion(
                "Aviso",
                ["El documento es demasiado corto o no tiene apartados "
                 "con los que preparar ejercicios."],
            )
        )

    lineas_solucion = [
        f"{numero}. {definicion}"
        for numero, definicion in enumerate(definiciones[:MAXIMO_POR_TIPO], start=1)
    ]
    if not lineas_solucion:
        lineas_solucion = ["Las soluciones están en el documento original."]
    secciones.append(Seccion("Soluciones (comprueba tu trabajo)", lineas_solucion))

    return secciones


def resumen_previo(carpeta: Path, nombre: str) -> str:
    """Los apuntes que ya generó «resumir» para este documento, si los hay.

    `resumir` escribe ahora apuntes completos desde cero (no un resumen) y los
    guarda en «resumenes/…_resumido» por compatibilidad; ese texto, más rico
    que el documento, es el mejor contexto para preparar el examen.
    """
    from .contenido import extraer
    from .nombres import separar_extension

    base = separar_extension(nombre)[0]
    carpeta_resumenes = Path(carpeta) / "resumenes"
    if not carpeta_resumenes.is_dir():
        return ""

    for ruta in sorted(carpeta_resumenes.glob(f"{base}_resumido.*")):
        contenido = extraer(ruta)
        if contenido.analizable and contenido.texto.strip():
            return contenido.texto[:12000]
    return ""


def _variacion() -> str:
    """Una consigna al azar, para que dos exámenes del mismo tema no se parezcan.

    Se le echa a la petición de cada ejecución: cambia el foco y el número de
    preguntas, de modo que la batería salga siempre distinta.
    """
    enfoque = random.choice(ENFOQUES)
    extra = random.randint(0, 4)
    return (
        f"Enfoque de ESTE examen (distinto al de otras veces): {enfoque}. "
        f"Redondea la batería hasta {MINIMO_PREGUNTAS + extra} preguntas en total, "
        f"si el documento da para tanto."
    )


def pedir_ejercicios(
    ficha: Ficha, contexto_extra: str = ""
) -> tuple[list[Seccion], list[Fuente]]:
    """Le pide al modelo una batería de ejercicios y la convierte en secciones."""
    from .ia import pedir_con_busqueda

    contenido = ficha.contenido.strip()[:12000]
    if not contenido:
        raise ErrorIA("el documento no tiene texto con el que preparar ejercicios")

    peticion = (
        f"Prepara un EXAMEN sobre el TEMA al que apuntan estos apuntes. **El "
        f"documento NO es la fuente: es solo la referencia que dice de qué trata "
        f"el tema.** El examen se hace sobre la teoría real del tema, no sobre "
        f"detalles concretos del PDF.\n\n"
        f"{_variacion()}\n\n"
        f"1) INVESTIGA antes de preguntar. Un examen justo se contesta con la "
        f"teoría del tema, no con lo que pone literalmente en el PDF. Para cada "
        f"concepto que vayas a preguntar, pide su teoría en internet: escribe una "
        f"línea con la forma [[BUSCAR: consulta]] por concepto y termina tu turno; "
        f"te devolveré varias fuentes (enciclopedia y web) para que elijas las "
        f"mejores. Puedes pedir varias búsquedas en el mismo turno.\n\n"
        f"2) Primero entiende de qué va el tema: no todos admiten el mismo tipo de "
        f"ejercicio. Un tema de teoría (definiciones, conceptos, historia, "
        f"terminología) NO debe llevar ejercicios de cálculo; un tema de cálculos "
        f"(fórmulas, conversiones, números) sí, y quizá solo de eso. Decide la "
        f"mezcla según el tema y dilo en una línea al principio, con el motivo.\n\n"
        f"Reglas:\n"
        f"- Apartados con encabezados de segundo nivel (##): «Tipo test», "
        f"«Preguntas de desarrollo» y «Cálculo y problemas». Incluye solo los que "
        f"tengan sentido para este tema y explica cuáles has dejado fuera.\n"
        f"- En el tipo test, cada pregunta tiene CUATRO alternativas reales (no "
        f"líneas de puntos) y una sola correcta. NO escribas la respuesta "
        f"correcta junto a la pregunta ni detrás de las alternativas: las "
        f"respuestas van ÚNICAMENTE en el apartado «Soluciones», al final del "
        f"documento.\n"
        f"- MÍNIMO {MINIMO_PREGUNTAS} preguntas en total. Reparte entre «Entre 5 y 8» "
        f"de tipo test, «3 a 6» de desarrollo y «2 a 5» de cálculo; si el tema no "
        f"da para las tres clases, echa más de las que sí tenga sentido, pero sin "
        f"bajar de {MINIMO_PREGUNTAS} entre todas.\n"
        f"- Separa cada pregunta de la siguiente con una línea en blanco, y deja "
        f"las cuatro alternativas de cada pregunta de tipo test sin línea en blanco "
        f"entre ellas (forman un solo bloque).\n"
        f"- Las preguntas de desarrollo y de cálculo llevan espacio para responder "
        f"y el enunciado completo.\n"
        f"- Al final, un apartado «## Soluciones» con la solución de cada pregunta "
        f"de tipo test y con las pautas de las de desarrollo.\n"
        f"- Pregunta la TEORÍA del tema (la que has encontrado al investigar), de "
        f"forma que un alumno que haya estudiado esa teoría pueda aprobar. No "
        f"preguntes cosas que solo se saben por el PDF.\n"
        f"- Escribe en el idioma del documento.\n"
    )

    if contexto_extra:
        peticion += (
            f"\nEstos son los APUNTES del mismo tema (los escribió antes la IA, "
            f"investigando la teoría en internet). El examen debe poder responderse "
            f"estudiándolos: alíñate con su contenido y usa los mismos conceptos y "
            f"términos:\n\n"
            f"--- APUNTES DEL TEMA ---\n{contexto_extra}\n"
        )

    peticion += (
        f"\nRecuerda: INVESTIGA primero con [[BUSCAR: consulta]] (una por concepto) "
        f"y termina tu turno hasta tener la teoría; solo entonces escribe el "
        f"examen.\n\n"
        f"--- APUNTES (referencia del tema) ---\n{contenido}"
    )

    respuesta, fuentes = pedir_con_busqueda(
        SISTEMA, peticion, temperatura=TEMPERATURA_EXAMEN, maximo_consultas=6
    )
    secciones = a_secciones(respuesta, titulo="Ejercicios")
    if not secciones or not any(s.lineas for s in secciones):
        raise ErrorIA("el modelo ha contestado pero sin contenido")
    return secciones, fuentes


#: Una línea que abre pregunta: «1. …», «2) …».
RE_PREGUNTA = re.compile(r"^\s*\d+[.)]\s")


def separar_preguntas(secciones: list[Seccion]) -> list[Seccion]:
    """Deja una línea en blanco antes de cada pregunta.

    Así la última frase de una pregunta no queda pegada a la siguiente: entre
    un bloque y otro hay una línea en blanco, que todos los formatos (ODT,
    DOCX, RTF y TXT) pintan como un salto de párrafo.
    """
    separadas: list[Seccion] = []
    for seccion in secciones:
        nueva: list[str] = []
        for linea in seccion.lineas:
            es_pregunta = RE_PREGUNTA.match(linea) is not None
            if es_pregunta and nueva and nueva[-1] != "":
                nueva.append("")
            nueva.append(linea)
        separadas.append(replace(seccion, lineas=nueva))
    return separadas


def construir_secciones(
    ficha: Ficha, con_ia: bool = True, contexto_extra: str = ""
) -> tuple[list[Seccion], str, list[Fuente]]:
    """Las secciones de la batería, una nota y las fuentes usadas."""
    if con_ia:
        try:
            secciones, fuentes = pedir_ejercicios(ficha, contexto_extra)
            nota = "Generado con inteligencia artificial."
            if contexto_extra:
                nota += " Se han usado los apuntes ya hechos de este tema como contexto."
            if fuentes:
                nota += (
                    f" La teoría se ha investigado en internet: "
                    f"{len(fuentes)} fuente(s) citadas al final."
                )
            return secciones, nota, fuentes
        except ErrorIA as exc:
            nota = f"Generado sin inteligencia artificial: {exc}"
            return construir_secciones_extractivas(ficha), nota, []
    return (
        construir_secciones_extractivas(ficha),
        "Generado sin inteligencia artificial: no hay modelo configurado.",
        [],
    )


def escribir_evaluacion(ficha: Ficha, carpeta: Path, formato: str = "") -> Path:
    """Escribe el fichero de ejercicios en la carpeta «ejercicios»."""
    from .documentos import formato_preferido
    from .resumen import _base, unidad_del_documento

    contexto = resumen_previo(Path(carpeta), ficha.nombre_original)
    secciones, nota, fuentes = construir_secciones(ficha, con_ia=True, contexto_extra=contexto)
    titulo = f"Ejercicios · {ficha.nombre_original}"
    bloques = [Seccion("", [nota], nivel=1), *separar_preguntas(secciones)]

    if fuentes:
        lineas = [f"• {fuente.titulo} — {fuente.url}" for fuente in fuentes]
        bloques.append(Seccion("Fuentes consultadas", lineas))

    destino = carpeta / "ejercicios"
    nombre = f"{_base(ficha.nombre_original)}_test{formato or formato_preferido()}"
    return escribir_documento(
        destino / nombre,
        titulo,
        bloques,
        unidad=unidad_del_documento(ficha),
        asignatura=ficha.asignatura,
    )
