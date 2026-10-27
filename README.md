# tareas

Mi herramienta de línea de órdenes para automatizar tareas repetitivas con ficheros.

`tareas` lee un fichero de configuración (`acciones.json`) donde **yo** describo qué
acciones hace, y las ejecuta sobre mis ficheros reales. Añadir una acción nueva es
editar un JSON, no tocar código.

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

Para desarrollar (recarga los cambios al instante):

```bash
uv sync
uv run tareas --help
uv run pytest
```

## Uso

```bash
tareas --help                              # ayuda general
tareas version                             # versión instalada
tareas listar [CARPETA]                    # tabla: nombre, tipo, tamaño, fecha
tareas acciones                            # acciones definidas en acciones.json
tareas validar                             # comprueba acciones.json (código 3 si falla)
tareas ejecutar NOMBRE [CARPETA] --simular # enseña qué haría, sin tocar nada
tareas ejecutar NOMBRE [CARPETA] --si      # lo ejecuta sin preguntar
tareas --config RUTA ...                   # otro fichero de acciones
```

Códigos de salida: **0** bien · **1** fallo al ejecutar · **2** error de uso · **3** configuración inválida.

## Spec (versión 1 · 2026-10-27)

1. **Problema:** cada semana pierdo tiempo ordenando la carpeta de descargas: PDFs
   de seis asignaturas mezclados con instaladores, comprimidos y capturas, y nunca
   sé cuál va a su carpeta.
2. **Para quién:** para mí y para mi compañero de clase, que tiene los mismos seis
   apuntes de 1º DAM.
3. **Cómo se usa:** `tareas ORDEN [CARPETA] [opciones]` desde cualquier terminal.
4. **Órdenes de la semana 1:** `tareas --help`, `tareas version`, `tareas listar [CARPETA]`.
5. **Órdenes previstas:** `tareas acciones`, `tareas validar`, `tareas ejecutar NOMBRE --simular`.
6. **Mis acciones:** repartir apuntes por asignatura (6), separar instaladores,
   renombrar capturas con su fecha, borrar temporales viejos, copiar una copia de
   seguridad de los apuntes.
7. **Nunca hará:** borrar sin preguntar ni tocar ficheros fuera de la carpeta que le
   indique. Antes de tocar nada, `--simular`.
8. **Plataformas:** Linux primero; también Windows y macOS (pathlib, `encoding="utf-8"`,
   nada de `shell=True`).
9. **Códigos de salida:** 0 bien · 1 fallo al ejecutar · 2 uso incorrecto · 3 configuración inválida.
10. **Instalación:** `uv tool install --editable .`

## Esquema de acciones.json

`acciones.json` es la parte que escribo yo. El código solo trae el motor que lo
interpreta. Referencia completa de campos en [`docs/adr/0001-configuracion-externa.md`](docs/adr/0001-configuracion-externa.md).

### Raíz

| Campo | Obligatorio | Tipo | Qué hace |
|---|---|---|---|
| `version` | sí | entero | Versión del esquema. Si cambia el formato, sube a 2. |
| `acciones` | sí | lista | Las acciones. Vacía = error de configuración. |

### Cada acción

| Campo | Obligatorio | Tipo | Qué hace |
|---|---|---|---|
| `nombre` | sí | texto | Lo que escribes en `tareas ejecutar NOMBRE`. Único, en minúsculas y con guiones. |
| `descripcion` | sí | texto | Lo que enseña `tareas acciones`. Una frase para alguien que no eres tú. |
| `tipo` | sí | `mover` \| `copiar` \| `renombrar` \| `borrar` | Qué clase de acción es. |
| `origen` | no | ruta | Carpeta por defecto si no pasas CARPETA en la orden. Admite `~`. |
| `filtro` | no | objeto | Qué ficheros le afectan (ver más abajo). Sin filtro = todos. |
| `destino` | `mover`/`copiar` | ruta | A dónde van. Si no existe, se crea al ejecutar de verdad. |
| `plantilla` | `renombrar` | texto | El nombre nuevo (ver huecos más abajo). |
| `confirmar` | `borrar` | booleano | `true` pide confirmación antes de actuar, salvo que pases `--si`. Las acciones de tipo `borrar` siempre piden confirmación: no se puede desactivar. |

### Filtros (dentro de `filtro`)

Si pones varios, el fichero tiene que cumplirlos **todos**.

| Campo | Tipo | Qué hace |
|---|---|---|
| `extensiones` | lista | Solo esas extensiones, comparadas en minúsculas (`FOTO.JPG` entra en `.jpg`). Se comparan por sufijo del nombre, así que `".tar.gz"` también funciona. |
| `patron` | regex | Expresión regular sobre el nombre del fichero, **sin distinguir mayúsculas**. En JSON la `\` se escribe `\\`. |
| `mas_antiguo_que_dias` | entero | Solo ficheros modificados hace más de N días. |
| `mayor_que_mb` | entero | Solo ficheros de más de N MB. |

El filtro **no baja a las subcarpetas**: solo mira el primer nivel de la carpeta.

### Huecos de `plantilla` (para `renombrar`)

| Hueco | Ejemplo | Qué pone |
|---|---|---|
| `{fecha:%Y-%m-%d}` | `2026-11-03` | Fecha de modificación del fichero, con el formato que quieras. |
| `{n:03}` | `001` | Contador con ceros a la izquierda. |
| `{ext}` | `.jpg` | La extensión original, con punto y en minúsculas. |
| `{nombre}` | `IMG_2041` | El nombre original sin extensión. |

### Mis acciones

| Nombre | Tipo | Qué hace |
|---|---|---|
| `apuntes-bases-dades` | mover | Apuntes de Bases de Datos a su carpeta, según el nombre del fichero. |
| `apuntes-entorns` | mover | Apuntes de Entornos de Desenvolupament a su carpeta. |
| `apuntes-marcs` | mover | Apuntes de Llenguatge de Marques a su carpeta. |
| `apuntes-programacio` | mover | Apuntes de Programació a su carpeta. |
| `apuntes-intermodular` | mover | Apuntes del Projecte Intermodular a su carpeta. |
| `apuntes-sistemes` | mover | Apuntes de Sistemes Informàtics a su carpeta. |
| `separar-instaladores` | mover | Instaladores y paquetes a una subcarpeta aparte. |
| `renombrar-capturas` | renombrar | Capturas y fotos con su fecha: `2026-10-27_001.png`. |
| `limpiar-temporales` | borrar | Ficheros `.tmp` con más de 30 días (pide confirmación). |
| `copiar-copia-apuntes` | copiar | Copia de seguridad de los apuntes en otra carpeta. |

Las seis primeras usan `filtro.patron` para reconocer la asignatura **por el nombre
del fichero**. Es una decisión consciente: si el nombre no dice nada (por ejemplo
`Salva_Llacer.pdf`), el fichero **no se mueve**. Prefiero dejar un archivo en
Descargas a mandarlo a la carpeta equivocada.

## Estructura

```
cli-tareas/
├── pyproject.toml          # [project.scripts] tareas = "tareas.cli:app"
├── README.md
├── .gitignore              # .venv/, __pycache__/, .env
├── .gitattributes          # * text=auto
├── acciones.json           # MIS acciones (lo escribo yo)
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
│   ├── cli.py              # interfaz Typer: órdenes, opciones, salida
│   ├── config.py           # leer y VALIDAR acciones.json
│   ├── motor.py            # clase Motor: ejecuta una Accion sobre una carpeta
│   ├── acciones.py         # clases Accion (mover, renombrar, copiar, borrar…)
│   └── errores.py          # TareasError, ConfigError, AccionNoValida
├── prototipo/              # v0 de un script, ya sustituido por esta CLI
└── pruebas/                # acciones.json de prueba, con rutas en ~/pruebas-tareas
```

## Prototipo

`prototipo/organitza_estudis.py` es la primera versión, un script suelto con
`argparse` que clasificaba PDFs por la materia y leía su `.md` asociado. La idea
siguió viva, pero el esquema de este proyecto es mejor: ahora la clasificación por
asignatura es **una acción declarativa** en `acciones.json`, y el motor hace el
resto. Se queda en el repo como prueba de por dónde empezó la herramienta.

## Seguridad

- `.env` está en `.gitignore` desde el primer commit. Ninguna clave en el repo.
- Las acciones destructivas (`borrar`) piden confirmación salvo `--si`.
- `--simular` no toca el disco: ni mueve, ni copia, ni crea carpetas. Y la
  simulación enseña **exactamente** el mismo destino que la ejecución real,
  incluidos los sufijos « (1)» cuando dos ficheros acabarían con el mismo nombre.
- Nunca se sobrescribe un fichero: si el destino existe, se añade ` (1)`, ` (2)`…
  Ni siquiera a través de un enlace simbólico roto.
- Un fichero que falla no corta la acción: se anota el error, se sigue con los
  demás y el programa sale con código 1.
- Prueba siempre en `~/pruebas-tareas`, nunca sobre tus carpetas reales.
  Con `--config pruebas/acciones-prueba.json` todas las rutas apuntan ahí.

## Multiplataforma

Reglas que sigue el código, para que funcione igual en Linux, Windows y macOS:

- `pathlib.Path` siempre, nunca rutas montadas a mano con `/` o `\`.
- `expanduser()` para las rutas con `~`.
- `encoding="utf-8-sig"` al leer `acciones.json`: acepta los ficheros con BOM
  que guarda el Bloc de notas de Windows.
- `shutil.move` y `shutil.copy2`, nada de `os.system`, `subprocess` ni `shell=True`.
- Colores con Rich, no con códigos ANSI a mano.
- Los nombres que genera `renombrar` se validan contra las reglas de Windows
  (que son las más estrictas): sin `\/:*?"<>|` y sin nombres reservados como
  `CON` o `NUL`.

