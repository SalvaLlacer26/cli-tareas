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
documento. El formato del fichero que se crea depende del sistema operativo:

| Sistema | Formato | Programa |
|---|---|---|
| Linux | `.odt` | LibreOffice |
| Windows y macOS | `.docx` | Word |
| Cualquiera | `.rtf` | WordPad |
| Cualquiera | `.txt` | Bloc de notas |

Los `.odt` y los `.docx` se generan con la biblioteca estándar (son ficheros
ZIP con el XML dentro), así que no hace falta instalar nada para escribirlos.

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

## Estructura

```
cli-tareas/
├── pyproject.toml          # [project.scripts] tareas = "tareas.cli:app"
├── README.md
├── .gitignore              # .venv/, __pycache__/, .env
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
