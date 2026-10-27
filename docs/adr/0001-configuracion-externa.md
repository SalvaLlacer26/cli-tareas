# ADR-0001: Las acciones viven en acciones.json, no en el código

- Estado: aceptada
- Fecha: 2026-10-27
- Autor/a: Salva Llácer Ivars

## Contexto

Mi herramienta «tareas» automatiza tareas repetitivas con ficheros: repartir los
apuntes de la carpeta de descargas entre las seis carpetas de asignatura, apartar
instaladores, renombrar capturas, borrar temporales viejos y dejar una copia de
seguridad de los apuntes.

Cada persona que la use tendrá carpetas y manías distintas, y yo mismo voy a
querer añadir acciones nuevas cada pocas semanas. Concretamente, mis seis
asignaturas de 1º DAM (Bases de Datos, Entornos de Desarrollo, Lenguaje de
Marcas, Programación, Proyecto Intermodular y Sistemas Informáticos) cambian
de sitio según lo que estoy haciendo, y en el instituto mi compañero de clase
tiene la misma estructura de carpetas pero con otros nombres.

## Decisión

Las acciones se describen en un fichero JSON externo (`acciones.json`) con un
esquema documentado en el README. El código solo contiene el MOTOR que lee,
valida y ejecuta ese fichero. Añadir una acción = editar el JSON.

## Alternativas consideradas

1. **Escribir cada acción como una función en Python.**
   - A favor: es lo más directo y no hay capa de traducción; el depurador entra
     dentro de la acción; el tipo de datos se comprueba solo.
   - En contra: cada cambio exige tocar el código y volver a instalar; quien no
     programa no puede añadir acciones; no se puede validar «antes de ejecutar»
     nada, porque el error aparece cuando ya has movido tres ficheros.

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

- Positivas: añadir una acción no toca el código; el JSON se puede validar antes
  de ejecutar nada; el fichero se puede versionar y compartir; varias personas
  pueden usar el mismo motor con acciones distintas; los errores se detectan
  con un mensaje que dice qué acción y qué campo fallan.
- Negativas: hay que mantener la validación al día cuando el esquema crezca;
  los errores de escritura en el JSON solo se ven al ejecutar `validar`; hay
  una capa de traducción entre el JSON y las clases, y ese coste se paga en
  cada acceso a un campo.
- Qué haré si el esquema cambia: subir `version` a 2 y hacer que `config.py`
  acepte el esquema 1 con un aviso («este fichero es de una versión antigua;
  conviértelo») en vez de romper. Los ficheros de acciones son texto, así que
  siempre se pueden convertir a mano.

## Nota sobre la clasificación por asignatura

La idea con la que empecé era leer el PDF para deducir la asignatura. Al
plantear el esquema vi que no hacía falta: mis seis acciones de apuntes
reconocen la asignatura con `filtro.patron`, o sea, con una expresión regular
sobre el nombre del fichero. Es menos sofisticado que un modelo de lenguaje,
pero es determinista, instantáneo, funciona sin red y —lo más importante— se
puede equivocar de una forma controlada: si el nombre del fichero no dice
nada, el fichero **no se mueve**. Prefiero dejar un PDF en Descargas a mandarlo
a la carpeta equivocada. La clasificación por contenido con IA la reservo para
la semana 3, cuando haya un modo sin red que lo explique.
