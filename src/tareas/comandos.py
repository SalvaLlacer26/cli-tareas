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
        nombre="version",
        uso="tareas version",
        para_que="Muestra la versión instalada de la herramienta.",
        ejemplo="tareas version",
    ),
    FichaComando(
        nombre="listar",
        uso="tareas listar [CARPETA] [--json]",
        para_que=(
            "Lista los ficheros de una carpeta con su nombre, tipo, tamaño y fecha "
            "de modificación. Con --json la salida es JSON limpio, sin colores, "
            "para tuberías y otros programas."
        ),
        ejemplo="tareas listar ~/Descargas --json",
    ),
    FichaComando(
        nombre="acciones",
        uso="tareas acciones",
        para_que=(
            "Lista las acciones definidas en el fichero de configuración con su "
            "tipo, si piden confirmación y su descripción, más las carpetas "
            "(asignaturas) declaradas."
        ),
        ejemplo="tareas acciones",
    ),
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
            "Usa el archivo para identificar el tema y crea un resumen de estudio "
            "con el texto organizado en apartados y tablas. Lo escribe un modelo de "
            "IA (el del centro, con la clave en el .env) que INVESTIGA la teoría en "
            "internet (Wikipedia y la web) en lugar de copiar el documento; las "
            "fuentes quedan escritas al final. Si no hay modelo o no hay red, avisa "
            "y hace una versión extractiva. Se guarda en la carpeta «resumenes» con "
            "el nombre del archivo seguido de «_resumido»."
        ),
        ejemplo="tareas resumir 'A21_IntroduccióGit_GitHub.pdf'",
    ),
    FichaComando(
        nombre="evaluar",
        uso="tareas evaluar 'NOMBRE_DE_ARCHIVO' [CARPETA]",
        para_que=(
            "Crea un examen sobre el TEMA del archivo (mínimo 10 preguntas) con sus "
            "soluciones. La IA investiga la teoría del tema en internet y pregunta "
            "sobre ella, no sobre lo que pone en el PDF; decide la mezcla de tipo "
            "test, desarrollo y cálculo (un tema teórico no lleva cálculo) y lo "
            "explica al principio. Si ya se hizo `resumir` de ese tema, se apoya en "
            "él, de forma que estudiar ese resumen sirva para aprobar. Cada pasada "
            "sale distinta. Si no hay modelo o no hay red, avisa y hace una versión "
            "extractiva. Se guarda en la carpeta «ejercicios» con el nombre del "
            "archivo seguido de «_test»."
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
        nombre="clasificar",
        uso="tareas clasificar [CARPETA] --destino RUTA",
        para_que=(
            "Crea en la ruta indicada un grupo de carpetas nuevas, decididas por la "
            "IA según el contenido de los documentos analizados, y mueve dentro cada "
            "documento. Un PDF de recetas acabaría en una carpeta «Recetas» y un "
            "manual de hardware en otra «Hardware». A diferencia de «organizar», que "
            "usa las asignaturas de la configuración, aquí las carpetas las crea la "
            "IA. Necesita un modelo configurado y pide confirmación antes de mover "
            "nada."
        ),
        ejemplo="tareas clasificar --destino ~/Documents/MisTemas",
    ),
    FichaComando(
        nombre="formulario_evaluar",
        uso="tareas formulario_evaluar 'NOMBRE_DE_ARCHIVO' [CARPETA] [--no-abrir]",
        para_que=(
            "EN PRUEBAS. Prepara los mismos ejercicios que «evaluar», pero en "
            "un formulario HTML que abre en el navegador: tipo test con botones "
            "de opción, desarrollo y cálculo con hueco para escribir, y botón "
            "de enviar. Al enviar, corrige el tipo test en local y la IA "
            "corrige lo escrito. El servidor solo escucha en tu propio equipo. "
            "Pulsa Enter en la terminal para cerrar el examen."
        ),
        ejemplo="tareas formulario_evaluar 'A21_IntroduccióGit_GitHub.pdf'",
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

#: Qué se le sugiere a quien acaba de terminar cada comando: la herramienta
#: se cuenta sola con un «¿Qué quieres hacer ahora?» al final de cada orden.
#: Una línea corta por sugerencia. «comandos» nunca se sugiere aquí: se ofrece
#: aparte, al final del bloque, como ayuda detallada.
SIGUIENTES: dict[str, list[tuple[str, str]]] = {
    "analizar": [
        ("organizar", "a colocar cada documento"),
        ("clasificar", "a agrupar por contenido"),
        ("resumir", "de un documento ya analizado"),
    ],
    "organizar": [
        ("resumir", "de lo recién colocado"),
        ("evaluar", "de cualquier documento"),
        ("deshacer", "devolver todo a su sitio"),
    ],
    "deshacer": [
        ("organizar", "volver a colocar"),
        ("analizar", "con otros criterios"),
    ],
    "resumir": [
        ("evaluar", "con el resumen de contexto"),
        ("formulario_evaluar", "el examen en el navegador"),
    ],
    "evaluar": [
        ("formulario_evaluar", "el mismo examen, interactivo"),
    ],
    "formulario_evaluar": [
        ("resumir", "y el documento en papel"),
    ],
    "clasificar": [
        ("resumir", "de lo ya agrupado"),
        ("evaluar", "de un documento con ficha"),
        ("deshacer", "devolver lo clasificado"),
    ],
    "validar": [
        ("acciones", "ver las acciones configuradas"),
        ("ejecutar", "una acción, con --simular"),
    ],
    "ejecutar": [
        ("listar", "ver cómo ha quedado"),
        ("deshacer", "si algo no te convence"),
    ],
    "listar": [
        ("analizar", "esa carpeta"),
    ],
    "acciones": [
        ("ejecutar", "una, probando con --simular"),
    ],
    "version": [
        ("analizar", "empezar a organizar"),
    ],
    "comandos": [
        ("analizar", "el primer paso del ciclo"),
    ],
}
