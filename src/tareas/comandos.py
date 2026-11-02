"""La descripción de cada comando: lo que muestra «tareas comandos».

Cada comando se explica aquí una sola vez, así que la ayuda y el manual
nunca se contradicen. También están los datos del autor, que salen al final.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Quien ha hecho la herramienta.
AUTOR = "Salvador Llácer Ivars"

#: Curso para el que está hecha.
CURSO = "1º DAM"

#: Año de creación.
ANIO = "2026"

#: Aviso legal.
AVISO_LEGAL = f"© {ANIO} {AUTOR}. Todos los derechos reservados."


@dataclass
class FichaComando:
    """Lo que se sabe de un comando."""

    nombre: str
    uso: str
    para_que: str
    ejemplo: str = ""


COMANDOS: list[FichaComando] = [
    FichaComando(
        nombre="analizar",
        uso="tareas analizar [CARPETA]",
        para_que=(
            "Analiza una carpeta y el contenido de cada fichero. Renombra los que "
            "tienen nombres incompatibles (con tildes, espacios o caracteres raros) y "
            "escribe una ficha .md por documento con los datos que hacen falta para "
            "clasificarlo. Muestra una tabla con la asignatura de cada fichero y la "
            "carpeta a la que irá, y pide que confirmes que el análisis se ha hecho bien."
        ),
        ejemplo="tareas analizar ~/Descargas",
    ),
    FichaComando(
        nombre="organizar",
        uso="tareas organizar [CARPETA]",
        para_que=(
            "Mueve cada documento a la carpeta de su asignatura, usando la información "
            "de las fichas .md que dejó «analizar». Al moverlo le devuelve el nombre "
            "original. Muestra un resumen de los ficheros movidos y de las carpetas de "
            "destino."
        ),
        ejemplo="tareas organizar ~/Descargas",
    ),
    FichaComando(
        nombre="deshacer",
        uso="tareas deshacer [CARPETA]",
        para_que=(
            "Deshace lo que hizo «organizar»: devuelve los documentos a su carpeta de "
            "origen con su nombre original. La carpeta oculta «md» con las fichas del "
            "análisis se conserva, para poder volver a organizar sin analizar otra vez."
        ),
        ejemplo="tareas deshacer ~/Descargas",
    ),
    FichaComando(
        nombre="resumir",
        uso="tareas resumir 'NOMBRE_DE_ARCHIVO' [CARPETA]",
        para_que=(
            "Crea un documento con un resumen del contenido del archivo indicado, de "
            "como máximo diez páginas, sin imágenes y con el texto organizado en "
            "apartados y tablas. El resumen lo escribe un modelo de IA (el del "
            "centro, con la clave en el .env); si no hay modelo o no hay red, avisa y "
            "hace una versión extractiva. Se guarda en la carpeta «resumenes» con el "
            "nombre del archivo seguido de «_resumido»."
        ),
        ejemplo="tareas resumir 'A21_IntroduccióGit_GitHub.pdf'",
    ),
    FichaComando(
        nombre="evaluar",
        uso="tareas evaluar 'NOMBRE_DE_ARCHIVO' [CARPETA]",
        para_que=(
            "Crea un documento con ejercicios sobre el archivo indicado: preguntas tipo "
            "test con alternativas reales, preguntas de desarrollo y problemas de "
            "cálculo, con sus soluciones. Los prepara un modelo de IA (el del centro, "
            "con la clave en el .env); si no hay modelo o no hay red, avisa y hace una "
            "versión extractiva. Se guarda en la carpeta «ejercicios» con el nombre "
            "del archivo seguido de «_test»."
        ),
        ejemplo="tareas evaluar 'A21_IntroduccióGit_GitHub.pdf'",
    ),
    FichaComando(
        nombre="validar",
        uso="tareas validar",
        para_que=(
            "Comprueba el fichero de configuración antes de hacer nada y dice "
            "exactamente qué campo falla, en qué acción y por qué. Si el fichero "
            "está mal, sale con el código 3."
        ),
        ejemplo="tareas validar",
    ),
    FichaComando(
        nombre="ejecutar",
        uso="tareas ejecutar NOMBRE [CARPETA] [--simular] [--si]",
        para_que=(
            "Ejecuta una de las acciones genéricas del fichero de configuración "
            "(mover, copiar, renombrar o borrar). Con --simular enseña qué haría "
            "sin tocar nada; con --si no pregunta antes de una acción destructiva."
        ),
        ejemplo="tareas ejecutar separar-instaladores ~/Descargas --simular",
    ),
    FichaComando(
        nombre="comandos",
        uso="tareas comandos",
        para_que=(
            "Muestra esta lista: todos los comandos de la herramienta, cómo se usan y "
            "para qué sirven."
        ),
        ejemplo="tareas comandos",
    ),
]
