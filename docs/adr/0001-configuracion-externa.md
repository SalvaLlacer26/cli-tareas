# ADR-0001: Las acciones viven en acciones.json, no en el código

- Estado: aceptada
- Fecha: 2026-11-02
- Autor/a: Salvador Llácer Ivars

## Contexto

Mi herramienta «tareas» organiza mis apuntes: lee una carpeta de descargas,
analiza el contenido de cada documento, decide de qué asignatura es cada uno y
lo mueve a su carpeta. Cada persona que la use tendrá carpetas y manías
distintas, y yo mismo voy a querer añadir asignaturas nuevas cada pocas
semanas.

Concretamente, mis seis asignaturas de 1º DAM (Bases de Datos, Entornos de
Desarrollo, Lenguaje de Marcas, Programación, Proyecto Intermodular y
Sistemas Informáticos) están en carpetas con estos nombres en mi equipo, pero
mi compañero de clase tiene las mismas con otros nombres. Y dentro de seis
meses yo tendré más asignaturas, o las mismas con otros nombres.

## Decisión

Las acciones y las asignaturas se describen en un fichero JSON externo
(`acciones.json`) con un esquema documentado en el README. El código solo
contiene el MOTOR que lee, valida y ejecuta ese fichero.

Concretamente, la sección `carpetas` describe las asignaturas: su clave, su
carpeta de destino y los patrones que las reconocen. La sección `acciones`
describe las acciones genéricas (mover, copiar, renombrar, borrar), y una
acción puede apuntar a una carpeta con `«carpeta»: «bbdd»` para heredar su
destino y sus patrones, de forma que la asignatura se escribe una sola vez.

Añadir una asignatura = añadir una entrada al JSON. Añadir una acción = lo
mismo.

## Alternativas consideradas

1. **Escribir cada acción como una función en Python.**
   - A favor: es lo más directo y no hay capa de traducción; el depurador entra
     dentro de la acción; el tipo de datos se comprueba solo.
   - En contra: cada cambio exige tocar el código y volver a instalar; quien no
     programa no puede añadir acciones; no se puede validar nada «antes de
     ejecutar», porque el error aparece cuando ya has movido tres ficheros.

2. **Usar YAML o TOML en vez de JSON.**
   - A favor: YAML admite comentarios, que-help para documentar el fichero, y
     TOML es más legible para listas de cadenas.
   - En contra: YAML no viene en la biblioteca estándar (dependencia extra) y su
     indentación es una fuente clásica de errores silenciosos. TOML, en cambio,
     no permite repetir claves, así que no encaja con un esquema de «acciones»
     donde quiero poder validar nombres duplicados con un mensaje propio.

3. **Dejar las acciones en un fichero de shell o un Makefile.**
   - A favor: no hace falta programar nada; cada acción es una orden del sistema.
   - En contra: no es multiplataforma (el curso exige Linux, Windows y macOS),
     y no hay forma de validar antes de ejecutar.

## Consecuencias

- Positivas: añadir una acción o una asignatura no toca el código; el JSON se
  puede validar antes de ejecutar nada; el fichero se puede versionar y
  compartir; varias personas pueden usar el mismo motor con configuraciones
  distintas; los errores se detectan con un mensaje que dice qué acción y qué
  campo fallan.
- Negativas: hay que mantener la validación al día cuando el esquema crezca;
  los errores de escritura en el JSON solo se ven al ejecutar `validar`; hay
  una capa de traducción entre el JSON y las clases, y ese coste se paga en
  cada acceso a un campo.
- Qué haré si el esquema cambia: subir `version` a 2 y hacer que `config.py`
  acepte el esquema 1 con un aviso («este fichero es de una versión antigua;
  conviértelo») en vez de romper. Los ficheros de acciones son texto, así que
  siempre se pueden convertir a mano.

## Nota sobre la clasificación por asignatura

La idea con la que empecé era leer el PDF entero para deducir la asignatura.
Al plantear el esquema vi que no hacía falta: las asignaturas se reconocen con
`patrones`, o sea, con expresiones regulares sobre el nombre del fichero y
sobre el texto extraído. Es menos sofisticado que un modelo de lenguaje, pero
es determinista, instantáneo, funciona sin red y —lo más importante— se puede
equivocar de una forma controlada: si no hay evidencia suficiente, el fichero
**no se mueve** y va a la carpeta de respaldo. Prefiero dejar un PDF en
Descargas a mandarlo a la carpeta equivocada.

Cuando hay empate o evidencia repartida, no gana «la primera que coincide»:
gana la carpeta que aporta más evidencia, contando que un patrón de varias
palabras («projecte intermodular») pesa más que uno corto («git») y que lo que
aparece en el título del documento pesa el doble que una mención suelta a
mitad del texto.

La clasificación por contenido **con un modelo de lenguaje** es la capa de la
semana 3, y se enchufará en el mismo sitio: el punto único donde se decide la
asignatura de un documento.
