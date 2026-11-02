# tareas

**Tu propia herramienta de terminal: organiza tus apuntes por asignatura.**

`tareas` lee una carpeta, analiza el contenido de cada documento, decide de qué
asignatura es cada uno y lo mueve a su carpeta. Todo está descrito en un
fichero de configuración (`acciones.json`) que escribes tú, así que añadir una
asignatura no es tocar código.

Creada por **Salvador Llácer Ivars** · 1º DAM · 2026

## Instalación

Necesitas [uv](https://astral.sh/uv) (que ya trae Python 3.12):

```bash
uv python install 3.12
uv tool install --editable .
```

Para instalarla desde el repo, sin clonarlo:

```bash
uv tool install git+https://github.com/SalvaLlacer26/cli-tareas
```

### Configuración de usuario

Por defecto, `acciones.json` se busca en la carpeta desde la que lanzas la
orden. Si quieres usarlo desde cualquier sitio:

```bash
mkdir -p ~/.config/tareas
cp acciones.json ~/.config/tareas/acciones.json
```

(En Windows la ruta es `%APPDATA%\tareas\`.)

## Los comandos

`tareas comandos` te los explica todos. Resumen:

| Comando | Qué hace |
|---|---|
| `tareas analizar [CARPETA]` | Analiza la carpeta y el contenido de cada fichero, renombra los que tienen nombres incompatibles y escribe una ficha `.md` por documento con los datos para clasificarlo. Muestra una tabla con la asignatura de cada fichero y pide que confirmes el análisis. |
| `tareas organizar [CARPETA]` | Mueve cada documento a la carpeta de su asignatura usando las fichas, y le devuelve el nombre original. Muestra un resumen. |
| `tareas deshacer [CARPETA]` | Deshace lo anterior: devuelve los documentos a su carpeta de origen con su nombre original. Las fichas se conservan. |
| `tareas resumir 'ARCHIVO' [CARPETA]` | Crea un resumen del archivo (10 páginas como máximo, sin imágenes, organizado en apartados) en la carpeta `resumenes`, con el nombre `ARCHIVO_resumido`. |
| `tareas evaluar 'ARCHIVO' [CARPETA]` | Crea una batería de ejercicios (tipo test, desarrollo y cálculo) en la carpeta `ejercicios`, con el nombre `ARCHIVO_test`. |
| `tareas comandos` | Lista todos los comandos, cómo se usan y para qué sirven. |
| `tareas validar` | Comprueba el fichero de configuración y dice qué campo falla. |
| `tareas ejecutar NOMBRE [CARPETA]` | Ejecuta una de las acciones del fichero de configuración. |

**Todos aceptan la carpeta como argumento.** Si no la pones, se trabaja sobre
la carpeta en la que estás en la terminal:

```bash
cd ~/Descargas
tareas analizar        # trabaja en ~/Descargas
tareas organizar       # y en ~/Descargas también
```

## El ciclo completo

```bash
cd ~/Descargas

tareas analizar        # lee, renombra lo que estorba y hace las fichas
tareas organizar       # reparte por asignatura y devuelve los nombres
tareas deshacer        # si te has equivocado, todo vuelve a su sitio
```

### 1 · `analizar`

Por cada documento:

1. **Se extrae el texto.** Los PDF se leen con `pdftotext` (solo las
   primeras páginas, así que un PDF de 300 páginas no se carga entero); los
   `.docx` y los de OpenOffice se leen descomprimiendo el ZIP; los de texto,
   directamente. Lo que no se puede leer (un `.deb`, una imagen, un PDF
   escaneado) se marca como **formato invalido**.
2. **Se renombra** si el nombre no es compatible. Un nombre con tildes,
   espacios o caracteres raros se limpia (`Pràctica 1. Entitats.pdf` →
   `Practica-1-Entitats.pdf`). El nombre original se guarda en la ficha, así
   que luego se devuelve.
3. **Se clasifica** por el nombre del fichero y, si el nombre no dice nada,
   por su contenido. Gana la carpeta con más evidencia, contando que un
   patrón de varias palabras pesa más que uno corto, y que lo que está en el
   título del documento pesa el doble que una mención suelta.
4. **Se escribe una ficha** `.md` en la carpeta oculta `md`, con el nombre
   original, la asignatura detectada, la carpeta de destino y el texto
   extraído.

Al final se muestra la tabla y te pide que confirmes:

```
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Archivo          ┃ Estado        ┃ Asignatura       ┃ Carpeta de destino  ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ Actividad_CSS.pdf│ clasificado   │ Llenguatge de…   │ ~/Documents/Llengu… │
│ Salva_Llacer.pdf │ clasificado   │ Sistemes info…   │ ~/Documents/Siste…  │
│ foto.png         │ formato inval… │ formato invalido │ —                    │
└───────────────────┴───────────────┴──────────────────┴──────────────────────┘
Fichas creadas: 27 en «md» · 27 analizables · 1 sin clasificar · 0 con formato inválido
```

### 2 · `organizar`

Lee las fichas, mueve cada documento a la carpeta de su asignatura **y le
devuelve el nombre original** (el renombrado era solo para trabajar cómodo) y
lleva la ficha con él, en la carpeta `md` de la asignatura.

### 3 · `deshacer`

Devuelve los documentos a su carpeta de origen, con su nombre original. Las
fichas vuelven a la carpeta `md` de origen: el análisis se conserva y se puede
volver a organizar sin analizar otra vez.

### 4 · `resumir` y `evaluar`

Trabajan sobre lo que ya hay en la ficha, así que no vuelven a abrir el
documento. **El resumen y los ejercicios los escribe un modelo de IA**: el
texto del documento se le envía al modelo del centro y vuelve ya resumido, con
apartados, negritas y tablas.

El formato del fichero que se crea depende del sistema operativo:

| Sistema | Formato | Programa |
|---|---|---|
| Linux | `.odt` | LibreOffice |
| Windows y macOS | `.docx` | Word |
| Cualquiera | `.rtf` | WordPad |
| Cualquiera | `.txt` | Bloc de notas |

Los `.odt` y los `.docx` se generan con la biblioteca estándar (son ficheros
ZIP con el XML dentro), así que no hace falta instalar nada para escribirlos.

#### Configurar el modelo

La clave **nunca** va en el repo. Se copia el fichero de ejemplo y se rellena:

```bash
cp .env.example .env
```

```bash
TAREAS_IA_URL=https://ia.simarro/llmapi/v1
TAREAS_IA_KEY=la-clave-del-profesor
TAREAS_MODELO=Qwen38-DualSpark-low
TAREAS_IA_CA=~/.config/opencode/ca-simarro.crt
```

| Variable | Para qué |
|---|---|
| `TAREAS_IA_URL` | Dirección del servidor. Debe acabar en `/v1`. |
| `TAREAS_IA_KEY` | La clave del modelo. |
| `TAREAS_MODELO` | Qué modelo usar. Si se deja vacío, el de por defecto. |
| `TAREAS_IA_CA` | Certificado propio del servidor, si lo tiene (en el centro, hace falta). |
| `TAREAS_IA_TIMEOUT` | Segundos de espera. Por defecto 600, porque los modelos del centro tardan. |

El fichero `.env` se busca en la carpeta desde la que se lanza la orden y en
`~/.config/tareas/.env`. Las variables de entorno del sistema tienen prioridad.

#### Sin red o sin clave

Si no hay modelo (no hay clave, no hay red, el servidor falla), la CLI **no
se rompe**: lo explica en una línea y genera la versión extractiva, que corta
las primeras 25 líneas de cada apartado. El documento lleva una nota dizendo
que se ha hecho sin IA, para que nadie se tome por bueno un resumen que no lo
es.

#### Privacidad

Al resumir o evaluar, **el texto del documento sale del equipo** y va al
servidor que tengas configurado. Con la configuración por defecto va a
`ia.simarro`, que es un servidor de tu instituto. Si prefieres que no salga
nada, usa un Ollama en local:

```bash
TAREAS_IA_URL=http://localhost:11434/v1
TAREAS_IA_KEY=ollama
TAREAS_MODELO=llama3.2
```


## Esquema de acciones.json

### Raíz

| Campo | Obligatorio | Tipo | Qué hace |
|---|---|---|---|
| `version` | sí | entero | Versión del esquema. |
| `acciones` | sí | lista | Las acciones genéricas. Puede estar vacía. |
| `carpetas` | no | lista | Las asignaturas: dónde va cada una y cómo se reconoce. |

### `carpetas`: las asignaturas

| Campo | Obligatorio | Tipo | Qué hace |
|---|---|---|---|
| `clave` | sí | texto | Identificador corto de la asignatura (`bbdd`, `sistemes`). |
| `etiqueta` | no | texto | El nombre que ve la persona. |
| `destino` | sí | ruta | La carpeta donde van los ficheros. Admite `~`. |
| `patrones` | no | lista | Palabras o expresiones que la señalan. Se **cuentan** y se ponderan: una frase pesa más que una palabra suelta. |
| `respaldo` | no | booleano | `true` en la carpeta que recibe lo que no se ha podido clasificar. |

### `acciones`

| Campo | Obligatorio | Tipo | Qué hace |
|---|---|---|---|
| `nombre` | sí | texto | Lo que escribes en `tareas ejecutar NOMBRE`. |
| `descripcion` | sí | texto | Lo que enseña `tareas acciones`. |
| `tipo` | sí | `mover` \| `copiar` \| `renombrar` \| `borrar` | Qué clase de acción es. |
| `carpeta` | no | texto | Clave de una carpeta: la acción hereda su `destino` y sus `patrones`. |
| `origen` | no | ruta | Carpeta por defecto. Admite `~`. |
| `filtro` | no | objeto | `extensiones`, `patron`, `mas_antiguo_que_dias`, `mayor_que_mb`. |
| `destino` | `mover`/`copiar` | ruta | A dónde van. |
| `plantilla` | `renombrar` | texto | El nombre nuevo: `{fecha:%Y-%m-%d}`, `{n:03}`, `{ext}`, `{nombre}`. |
| `confirmar` | `borrar` | booleano | Las acciones que borran siempre preguntan. |

## Limitaciones conocidas

Las ocho órdenes están implementadas y funcionan. Queda una cosa que conviene
saber:

### Los resúmenes y los ejercicios tardan

Con los modelos del centro, resumir un documento de unas 30 páginas tarda
**entre 1 y 4 minutos**. No es un fallo: el modelo del centro es lento con
documentos largos y la red del instituto tampoco ayuda. Para archivos sueltos
va bien.

Si quieres que vaya más rápido, usa un modelo más ligero
(`Qwen38-DualSpark-low`) o recorta el documento antes de resumirlo.

### `tareas resumir` y `tareas evaluar` necesitan un modelo

Sin `TAREAS_IA_KEY` (o sin red) estas dos órdenes **no pueden hacer su
trabajo**: avisan y generan una versión extractiva, que corta el principio de
cada apartado. El documento lleva una nota que lo dice. Es el modo sin red:
las otras seis órdenes siguen funcionando igual.

### El resumen extractivo es una extracción, no un resumen

Cuando el resumen lo hace la IA, es un resumen de verdad. Cuando cae al
respaldo extractivo, lo que sale son las primeras 25 líneas de cada apartado:
es una extracción, y el documento lo indica. Lo que **no** hace ninguna de las
dos versiones es inventar contenido que no esté en el documento.

## Estructura


```
cli-tareas/
├── pyproject.toml          # [project.scripts] tareas = "tareas.cli:app"
├── README.md
├── .gitignore              # .venv/, __pycache__/, .env
├── .env.example            # cómo configurar el modelo de IA (sin claves)
├── .gitattributes          # * text=auto
├── acciones.json           # la configuración: asignaturas y acciones
├── docs/
│   ├── adr/0001-configuracion-externa.md
│   └── prompts.md
├── opencode.json           # permisos de mi agente
├── AGENTS.md               # normas del proyecto para el agente
├── .opencode/
│   ├── skills/acciones-json/SKILL.md
│   ├── commands/nueva-accion.md
│   └── agents/revisor.md
├── src/tareas/
│   ├── __init__.py         # __version__
│   ├── __main__.py         # python -m tareas
│   ├── cli.py              # interfaz Typer: las órdenes
│   ├── comandos.py         # la ficha de cada orden (para «tareas comandos»)
│   ├── config.py           # leer y VALIDAR acciones.json
│   ├── analizador.py       # analizar: renombrar, extraer, clasificar, fichas
│   ├── clasificador.py     # qué asignatura es cada documento
│   ├── contenido.py        # extraer texto de PDF, DOCX, ODT, TXT…
│   ├── ficha.py            # el formato de la ficha .md
│   ├── nombres.py          # qué nombres son compatibles y cómo se limpian
│   ├── organizador.py      # organizar y deshacer
│   ├── documentos.py       # escribir .odt, .docx, .rtf y .txt
│   ├── ia.py               # la capa de IA: cliente del servidor de modelos
│   ├── markdown.py         # de la respuesta en Markdown a las secciones
│   ├── resumen.py          # el resumen
│   ├── evaluacion.py       # los ejercicios
│   ├── acciones.py         # clases Accion (mover, copiar, renombrar, borrar)
│   ├── motor.py            # el motor de las acciones genéricas
│   └── errores.py          # TareasError, ConfigError, AccionNoValida
└── tests/                  # 83 pruebas
```

## Multiplataforma

- `pathlib.Path` siempre, `expanduser()` para las rutas con `~`, y
  `encoding="utf-8"` en todas las lecturas y escrituras.
- Los nombres se comparan **normalizados a NFC**: un fichero guardado en NFD
  (como los de macOS) y el nombre tecleado en NFC se ven iguales pero no lo
  son, y sin normalizar la herramienta no los encontraría.
- Los nombres que genera `renombrar` se validan contra las reglas de Windows,
  que son las más estrictas.
- Los `.odt` y los `.docx` se escriben con la biblioteca estándar.

## Seguridad

- `.env` está en `.gitignore` desde el primer commit. Ninguna clave en el repo.
- Las acciones que borran piden confirmación salvo `--si`.
- `tareas ejecutar` admite `--simular`, que enseña qué haría sin tocar nada.
- Prueba siempre en `~/pruebas-tareas`, nunca sobre tus carpetas reales.
  Con `--config pruebas/acciones-prueba.json` todas las rutas apuntan ahí.
