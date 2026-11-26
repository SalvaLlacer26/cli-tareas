"""El comando «evaluar»: una batería de ejercicios a partir del documento.

Se saca del contenido que ya hay en la ficha .md. El tipo de ejercicio depende
de lo que se ha detectado en el texto:

- **Tipo test**: preguntas de opción múltiple sobre las definiciones y los
  conceptos que aparecen en el documento.
- **Desarrollo**: preguntas abiertas sobre los apartados del documento.
- **Cálculo**: problemas con los números y las fórmulas que aparecen.

Las respuestas se dejan en blanco: el alumno las tiene que hacer. Al final
va la solución, para autocorregirse.
"""

from __future__ import annotations

import re
from pathlib import Path

from .documentos import Seccion, escribir_documento
from .ficha import Ficha
from .resumen import _base, _detectar_apartados, _limpiar

#: Máximo de preguntas de cada tipo.
MAXIMO_POR_TIPO = 6

#: Palabras que suelen anunciar una definición.
MARCAS_DE_DEFINICION = (
    "es", "son", "se define", "se denomina", "consiste en", "servirá",
    "significa", "se entiende por", "se conoce como", "definición", "definicion",
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


def _definiciones(texto: str) -> list[str]:
    """Las frases del texto que parecen definiciones."""
    encontradas: list[str] = []
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not (25 < len(limpia) < 220):
            continue
        if limpia.startswith(("|", "-", "*", "#")):
            continue
        minuscula = limpia.lower()
        if any(marca in minuscula for marca in MARCAS_DE_DEFINICION):
            encontradas.append(limpia)
        if len(encontradas) >= MAXIMO_POR_TIPO * 2:
            break
    return encontradas


def _apartados(texto: str) -> list[str]:
    """Los títulos de los apartados del documento."""
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


def construir_secciones(ficha: Ficha) -> list[Seccion]:
    """Las secciones de la batería de ejercicios."""
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

    # ---------------------------------------------------------- tipo test
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

    # ---------------------------------------------------------- desarrollo
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

    # ----------------------------------------------------------- cálculo
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

    # ----------------------------------------------------------- soluciones
    lineas_solucion: list[str] = []
    for numero, definicion in enumerate(definiciones[:MAXIMO_POR_TIPO], start=1):
        lineas_solucion.append(f"{numero}. {definicion}")
    if not lineas_solucion:
        lineas_solucion.append(
            "Las soluciones de desarrollo y de cálculo están en el documento original."
        )
    secciones.append(Seccion("Soluciones (comprueba tu trabajo)", lineas_solucion))

    return secciones


def escribir_evaluacion(ficha: Ficha, carpeta: Path, formato: str = "") -> Path:
    """Escribe el fichero de ejercicios en la carpeta «ejercicios»."""
    titulo = f"Ejercicios · {ficha.nombre_original}"
    destino = carpeta / "ejercicios"
    nombre = f"{_base(ficha.nombre_original)}_test{formato}"
    return escribir_documento(destino / nombre, titulo, construir_secciones(ficha))
