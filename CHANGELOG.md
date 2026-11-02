# Changelog

Todas las novedades de `tareas` van aquí. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[versiones semánticas](https://semver.org/lang/es/).

## [No publicado]

## [v2.0.1] — 2026-11-02

### Documentado

- **Las órdenes `resumir` y `evaluar` no funcionan correctamente.** Las dos
  crean el fichero con el formato correcto y lo abren bien, pero el contenido
  que ponen no es el que promete el enunciado:
  - `resumir` **recorta** las primeras 25 líneas de cada apartado. Es una
    extracción, no un resumen: no condensa ni elige lo importante.
  - `evaluar` busca definiciones con marcas como «es» o «son», que aparecen
    en casi todas las frases en castellano, así que las preguntas no preguntan
    nada; las cuatro opciones del tipo test están vacías, y la sección de
    cálculo suele quedar vacía porque depende de que aparezcan fórmulas con
    el formato `X = ...`.

  La causa de fondo es la misma: un resumen de todo el contenido y unos
  ejercicios con sentido necesitan **entender** el documento, y eso lo hace un
  modelo de lenguaje, no unas expresiones regulares. Lo que hay ahora es el
  andamiaje: sabe encontrar el documento, sabe escribir el `.odt`/`.docx` y
  sabe colocar el texto, pero no sabe **qué texto poner**.

  Queda escrito en el README («Limitaciones conocidas») en vez de
  disimularlo. La solución es la capa de IA de la semana 3, que se enchufará
  en el mismo sitio: la función que decide el contenido a partir del texto de
  la ficha.

## [v2.0.0] — 2026-11-02

Reformulación completa de la herramienta. Ahora el trabajo se hace en tres
pasos (`analizar` → `organizar` → `deshacer`), y de los documentos se sacan
resúmenes y ejercicios.

### Añadido

- **`tareas analizar [CARPETA]`**: analiza el contenido de cada documento,
  renombra los que tienen nombres incompatibles y escribe una ficha `.md` por
  documento en la carpeta oculta `md`, con el nombre original, la asignatura
  detectada, la carpeta de destino y el texto extraído. Al final enseña una
  tabla con la clasificación de cada fichero y pide que confirmes que el
  análisis se ha hecho bien.
- **`tareas organizar [CARPETA]`**: reparte los documentos según las fichas y
  les devuelve el nombre original. La ficha viaja con su documento, en la
  carpeta `md` de la asignatura.
- **`tareas deshacer [CARPETA]`**: devuelve los documentos a su carpeta de
  origen con su nombre original. Las fichas se conservan.
- **`tareas resumir 'ARCHIVO' [CARPETA]`**: crea un resumen de diez páginas
  como máximo, sin imágenes y con el texto organizado en apartados, en la
  carpeta `resumenes` y con el nombre `ARCHIVO_resumido`.
- **`tareas evaluar 'ARCHIVO' [CARPETA]`**: crea una batería de ejercicios
  (tipo test, desarrollo y cálculo) en la carpeta `ejercicios` y con el nombre
  `ARCHIVO_test`.
- **`tareas comandos`**: lista todos los comandos, cómo se usan y para qué
  sirven, con el autor, el curso, el año y el aviso legal.
- **La ficha `.md`** es el portador de datos: la leen `organizar`, `deshacer`,
  `resumir` y `evaluar`, así que el documento pesado no se vuelve a abrir.
- **Escritores de documentos** sin dependencias: `.odt` (LibreOffice), `.docx`
  (Word), `.rtf` (WordPad) y `.txt` (Bloc de notas). El formato se elige
  según el sistema operativo. Los `.odt` y los `.docx` son ficheros ZIP con el
  XML dentro, y se generan con la biblioteca estándar.
- **Clasificación por evidencia**: gana la carpeta que aporta más, contando
  que un patrón de varias palabras pesa más que uno corto y que lo que está
  en el título del documento pesa el doble que una mención suelta.
- **Todos los comandos admiten la carpeta como argumento** y, si no se pone,
  trabajan sobre la carpeta en la que está la terminal.

### Corregido

- **Los nombres en NFD no se encontraban.** Un fichero guardado con la «ó» como
  «o» + acento combinante (NFD, como los de macOS) y el nombre tecleado en
  NFC se ven iguales pero no lo son. Ahora todas las comparaciones de nombres
  se normalizan a NFC.
- **`sin_conflicto` devolvía solo el nombre**, así que al mover un documento a
  su carpeta de destino lo dejaba en el directorio desde el que se ejecutaba la
  orden.
- **La ficha se escribía fuera de la carpeta `md`** al renombrar un documento.
- Los `.md` que ya estaban en la carpeta se quedaban sin organizar: ahora se
  analizan y se mueven con el resto.

### Cambiado

- La versión pasa a 2.0.0 porque el cambio de la interfaz es incompatible con
  la anterior: los comandos `version`, `listar` y `acciones` desaparecen y los
  nuevos son `analizar`, `organizar`, `deshacer`, `resumir`, `evaluar` y
  `comandos`. Se mantienen `validar` y `ejecutar` para las acciones genéricas
  del fichero de configuración.

## [v1.2.0] — 2026-11-02

Pequeños arreglos y comodidades después de probar la herramienta con los
ficheros de verdad de la carpeta de descargas.

### Añadido

- **Configuración de usuario**: si no hay un `acciones.json` en la carpeta
  desde la que se lanza la orden, se busca en `~/.config/tareas/acciones.json`
  (o `%APPDATA%\tareas\` en Windows). La herramienta se puede usar desde
  cualquier sitio sin pasar `--config` cada vez.
- **Regla de qué es material de estudio** (`organizador.documentos`): un
  `.tar.xz` con «linux» en el nombre o una foto de una biblioteca ya no acaban
  en la carpeta de Sistemas o de Bases de Datos; van a la de respaldo.
- **5 pruebas nuevas** (68 en total) sobre la regla de documentos y las
  extensiones compuestas.

### Corregido

- `normalizar` mangaba las extensiones compuestas: `archivo.tar.xz` se
  convertía en `archivo-tar.xz` y dejaba de acabar en `.tar.xz`, con lo cual
  la acción `separar-comprimidos` ya no lo encontraba.

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
- **Configuración de usuario**: si no hay un `acciones.json` en la carpeta
  desde la que se lanza la orden, se busca en `~/.config/tareas/acciones.json`
  (o `%APPDATA%\tareas\` en Windows). La herramienta se puede usar desde
  cualquier sitio sin pasar `--config` cada vez.
- **Regla de qué es material de estudio** (`organizador.documentos`): un
  `.tar.xz` con «linux» en el nombre o una foto de una biblioteca ya no acaban
  en la carpeta de Sistemas o de Bases de Datos; van a la de respaldo.

### Corregido

- `normalizar` duplicaba la clave cuando el nombre ya la tenía delante
  (`bbdd_bbdd-nota.pdf`). Ahora normalizar dos veces no cambia nada.
- `normalizar` mangaba las extensiones compuestas: `archivo.tar.xz` se
  convertía en `archivo-tar.xz` y dejaba de acabar en `.tar.xz`, con lo cual
  la acción `separar-comprimidos` ya no lo encontraba.

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

