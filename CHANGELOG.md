# Changelog

Todas las novedades de `tareas` van aquí. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[versiones semánticas](https://semver.org/lang/es/).

## [No publicado]

## [v1.1.0] — 2026-10-27

Ahora la herramienta **organiza la carpeta de descargas entera con una orden**
y sabe **deshacerlo** con otra. Y renombra los ficheros a un formato que la
propia herramienta entiende.

### Añadido

- **`tareas organizar [CARPETA] --simular`**: reparte todo lo que hay en la
  carpeta de descargas entre las carpetas de asignatura. Decide la asignatura
  por el nombre del fichero; si el nombre no dice nada, mira el resumen de
  texto que va al lado (`.md`), que es mucho más barato de leer que el PDF; y
  si tampoco hay resumen, lo manda a la carpeta de respaldo.
- **`tareas desorganizar [CARPETA] --simular`**: deshace lo anterior y devuelve
  los ficheros a la carpeta de descargas **con su nombre original**, gracias al
  manifiesto que recuerda de dónde salió cada uno.
- **Nombres canónicos**: `Pràctica 1. Entitats, atributs i valors.pdf` pasa a
  llamarse `bbdd_practica-1-entitats-atributs-i-valors.pdf`. El prefijo es la
  clave de la asignatura, así que el nombre **sí dice de qué es el fichero** y
  las acciones con patrón lo reconocen sin tocar nada.
- **Sección `carpetas` en `acciones.json`**: las asignaturas se describen una
  sola vez (clave, etiqueta, destino y patrones) y las acciones que apuntan a
  ellas heredan su destino y sus patrones. Añadir una asignatura es añadir una
  entrada, sin tocar código.
- **Clasificación por puntuación**: gana la carpeta con **más** patrones que
  aparecen, no la primera que coincide. «Projecte Intermodular 1DAW» va a
  intermodular aunque también mentione «github».
- **Manifiesto** en la carpeta de estado del usuario (`platformdirs` la calcula
  bien en Linux, Windows y macOS), que hace que el viaje de ida y vuelta no
  pierda ni un nombre.
- **16 pruebas nuevas** (63 en total) sobre la normalización de nombres, la
  clasificación, el ciclo completo de ida y vuelta y el manifiesto.

### Corregido

- `normalizar` duplicaba la clave cuando el nombre ya la tenía delante
  (`bbdd_bbdd-nota.pdf`). Ahora normalizar dos veces no cambia nada.

## [v1.0.0] — 2026-10-27

Primera versión estable. La herramienta se instala con una orden, valida su
configuración antes de tocar nada y no deja pasar un solo error previsto como
una traza de Python.

### Añadido

- **`tareas --help`**, `tareas version` y `tareas listar [CARPETA]`, con tabla
  Rich de nombre, tipo, tamaño y fecha. Las carpetas van primero y luego se
  ordenan alfabéticamente sin distinguir mayúsculas.
- **`tareas acciones`**: tabla con el nombre, el tipo y la descripción de cada
  acción del fichero de configuración.
- **`tareas validar`**: comprueba el fichero de acciones y dice qué acción y
  qué campo fallan. Sale con código 3 si el fichero está mal.
- **`tareas ejecutar NOMBRE [CARPETA] --simular --si`**: ejecuta una acción.
  Con `--simular` enseña qué haría sin tocar nada; con `--si` no pregunta antes
  de una acción destructiva.
- **Opción global `--config RUTA`** para usar otro fichero de acciones.
- **Fichero `acciones.json`** con 11 acciones propias: seis reparten los
  apuntes por asignatura, dos apartan instaladores y comprimidos, una
  renombra las capturas con su fecha, una borra los temporales viejos y otra
  deja una copia de seguridad.
- **Configuración externa**: añadir una acción es editar un JSON, no tocar
  código. Documentado en el README y justificado en el ADR-0001.
- **Excepciones propias** (`TareasError`, `ConfigError`, `AccionNoValida`) para
  que ningún error previsto llegue al usuario como una traza de Python.
- **Códigos de salida**: 0 bien · 1 fallo al ejecutar · 2 error de uso ·
  3 configuración inválida.
- **Multiempaquetado**: `pathlib`, `expanduser()`, `encoding="utf-8-sig"`,
  `shutil` en vez de `shell=True`, y colores con Rich.
- **Configuración del agente**: `opencode.json` con los permisos, `AGENTS.md`
  con las normas, la skill `acciones-json`, el comando `/nueva-accion` y el
  subagente `@revisor`.
- **Pruebas** con pytest: 45 pruebas que cubren el camino feliz y los casos
  feos, ejecutadas también en GitHub Actions sobre Ubuntu, Windows y macOS.

### Corregido

- Diez fallos que llegaban al usuario como una traza de Python: JSON en
  latin-1 o con BOM de Windows, `filtro` nulo, `origen` no textual, plantilla
  con barras, nombres con corchetes de Rich, permisos de carpeta, ficheros que
  desaparecen a mitad de la ejecución y errores al mover, copiar o borrar.
- La simulación mentía: dos ficheros que acaban con el mismo nombre
  mostraban el mismo destino, cuando de verdad el segundo habría acabado en
  « (1)». Ahora la simulación enseña los mismos destinos que la ejecución real.
- Las extensiones se comparan por sufijo del nombre: «.tar.gz» ya funciona.
- El patrón ya no distingue mayúsculas, como las extensiones.
- `destino_libre` no escribe a través de un enlace simbólico roto.
- Los nombres que genera `renombrar` se validan contra las reglas de Windows.

[No publicado]: https://github.com/SalvaLlacer26/cli-tareas/compare/v1.0.0...HEAD
[v1.0.0]: https://github.com/SalvaLlacer26/cli-tareas/releases/tag/v1.0.0

