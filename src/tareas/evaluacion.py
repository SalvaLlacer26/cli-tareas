"""El comando «evaluar»: una batería de ejercicios hecha con un modelo de IA.

El modelo recibe el texto del documento (que ya está en la ficha .md) y
devuelve los ejercicios en Markdown: preguntas de tipo test con alternativas
reales, preguntas de desarrollo y problemas de cálculo, con sus soluciones.

Si no hay modelo disponible, se genera la **versión extractiva**, que busca
definiciones y apartados en el texto. Es mucho más pobre, y el documento lo
dice.
"""

from __future__ import annotations

import re
from pathlib import Path

from .documentos import Seccion, escribir_documento
from .errores import ErrorIA
from .ficha import Ficha
from .markdown import a_secciones

#: Máximo de preguntas de cada tipo en la versión extractiva.
MAXIMO_POR_TIPO = 6

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
    """El resumen que ya se hizo de este documento, si lo hay.

    Si se ha ejecutado «tareas resumir» antes, ese resumen (que puede llevar
    información completada con internet) es el mejor contexto para preparar
    los ejercicios: está más developed que el documento original.
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


def pedir_ejercicios(ficha: Ficha, contexto_extra: str = "") -> tuple[list[Seccion], list[Fuente]]:
    """Le pide al modelo una batería de ejercicios y la convierte en secciones."""
    from .ia import pedir_con_busqueda

    contenido = ficha.contenido.strip()[:12000]
    if not contenido:
        raise ErrorIA("el documento no tiene texto con el que preparar ejercicios")

    peticion = (
        f"Prepara una batería de ejercicios sobre este documento de apuntes.\n\n"
        f"Primero entiende de qué va el documento: no todos los temas admiten el "
        f"mismo tipo de ejercicio. Un tema de teoría (definiciones, conceptos, "
        f"historia, terminología) NO debe llevar ejercicios de cálculo; un tema de "
        f"cálculos (fórmulas, conversiones, números) sí, y quizá solo de eso. "
        f"Decide la mezcla según el contenido y dilo en una línea al principio, "
        f"con el motivo.\n\n"
        f"Reglas:\n"
        f"- Apartados con encabezados de segundo nivel (##): «Tipo test», "
        f"«Preguntas de desarrollo» y «Cálculo y problemas». Incluye solo los que "
        f"tengan sentido para este documento y explica cuáles has dejado fuera.\n"
        f"- En el tipo test, cada pregunta tiene CUATRO alternativas reales (no "
        f"líneas de puntos), una sola correcta, y la respuesta correcta marcada al "
        f"final de la pregunta entre corchetes, por ejemplo [b)].\n"
        f"- Entre 5 y 8 preguntas de tipo test, entre 3 y 5 de desarrollo y entre "
        f"2 y 4 de cálculo, según lo que dé el documento.\n"
        f"- Las preguntas de desarrollo y de cálculo llevan espacio para responder "
        f"y el enunciado completo.\n"
        f"- Al final, un apartado «## Soluciones» con la solución de cada pregunta "
        f"de tipo test y con las pautas de las de desarrollo.\n"
        f"- Solo contenido del documento. No inventes datos.\n"
        f"- Escribe en el idioma del documento.\n"
    )

    if contexto_extra:
        peticion += (
            f"\nEste es un resumen más desarrollado del mismo documento (puede "
            f"incluir información completada con internet). Úsalo como contexto "
            f"para las preguntas, pero comprueba que sea coherente con el "
            f"documento:\n\n"
            f"--- RESUMEN DEL DOCUMENTO ---\n{contexto_extra}\n"
        )

    peticion += (
        f"\nSi el documento es demasiado escueto o está muy sintetizado, o si te "
        f"falta alguna definición para poder preguntar algo, escribe una línea con "
        f"la forma [[BUSCAR: consulta]] y termina tu turno: se buscará esa "
        f"información en internet y te la devolveré.\n\n"
        f"--- DOCUMENTO ---\n{contenido}"
    )

    respuesta, fuentes = pedir_con_busqueda(SISTEMA, peticion)
    secciones = a_secciones(respuesta, titulo="Ejercicios")
    if not secciones or not any(s.lineas for s in secciones):
        raise ErrorIA("el modelo ha contestado pero sin contenido")
    return secciones, fuentes


def construir_secciones(
    ficha: Ficha, con_ia: bool = True, contexto_extra: str = ""
) -> tuple[list[Seccion], str, list[Fuente]]:
    """Las secciones de la batería, una nota y las fuentes usadas."""
    if con_ia:
        try:
            secciones, fuentes = pedir_ejercicios(ficha, contexto_extra)
            nota = "Generado con inteligencia artificial."
            if contexto_extra:
                nota += " Se ha usado el resumen ya hecho de este documento como contexto."
            if fuentes:
                nota += (
                    f" El documento era demasiado escueto, así que se ha completado "
                    f"con información de {len(fuentes)} fuente(s) de internet."
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
    from .resumen import _base

    contexto = resumen_previo(Path(carpeta), ficha.nombre_original)
    secciones, nota, fuentes = construir_secciones(ficha, con_ia=True, contexto_extra=contexto)
    titulo = f"Ejercicios · {ficha.nombre_original}"
    bloques = [Seccion("", [nota], nivel=1), *secciones]

    if fuentes:
        lineas = [f"• {fuente.titulo} — {fuente.url}" for fuente in fuentes]
        bloques.append(Seccion("Fuentes consultadas", lineas))

    destino = carpeta / "ejercicios"
    nombre = f"{_base(ficha.nombre_original)}_test{formato or formato_preferido()}"
    return escribir_documento(destino / nombre, titulo, bloques)
