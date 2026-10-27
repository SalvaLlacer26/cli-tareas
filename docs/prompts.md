# Prompts clave del proyecto

Cuaderno de bitácora: qué le pedí al agente, qué corregí de lo que propuso y
qué aprendí. Lo escribo yo, no el agente.

---

## 2026-10-27 · Arranque: el problema y el esquema

**Herramienta:** OpenCode 1.18.35 · modelos del centro + `opencode-go`

**Contexto:** la conversación empezó con un script suelto (`prototipo/organitza_estudis.py`)
que ordenaba la carpeta de descargas por asignatura leyendo un `.md` asociado a
cada PDF. Al leer el enunciado del proyecto vi que el esquema de `acciones.json`
resuelve el mismo problema **declarativamente**, sin tocar código.

**Prompt (agente plan):**

> Lee el enunciado del proyecto y mi script prototipo. Quiero un CLI `tareas`
> en Python 3.12 con Typer, src layout, que lea sus acciones de `acciones.json`.
> Explícame qué ficheros crearías y qué clases tendrían. No escribas código.

**Qué corregí del plan:**

- El plan metía la lectura de PDF con `pdftotext` dentro del motor. Lo saqué:
  la lectura de contenido es de la semana 3 (capa IA) y en la semana 2 el
  enunciado solo pide `mover`, `copiar`, `renombrar` y `borrar`.
- Pedí que la clasificación por asignatura se hiciera con `filtro.patron` sobre
  el **nombre** del fichero, no leyendo el PDF. Es determinista, funciona sin
  red y se equivoca de forma controlada: si el nombre no dice nada, el fichero
  no se mueve.

**Qué aprendí:** una expresión regular sobre el nombre del fichero cubre el
80 % de los casos reales y es infinitamente más auditable que un modelo.

---

## 2026-10-27 · Interfaz: `version` y `listar`

**Prompt (agente plan):**

> Quiero `src/tareas/cli.py` (app de Typer llamada `app`) y
> `src/tareas/__main__.py` con dos órdenes: `version` y `listar [CARPETA]`.
> No escribas código todavía: dime qué ficheros crearías, qué funciones
> tendría cada uno y cómo tratarías la carpeta inexistente, la vacía, los
> nombres con corchetes y los ficheros que no se pueden leer.

**Criterio de aceptación que escribí:**

- `uv run tareas` sin argumentos muestra la ayuda, en español y sin autocompletado.
- `version` imprime «tareas 0.1.0» leyendo `__version__` del paquete.
- `listar` (por defecto la carpeta actual, acepta `~`) pinta una tabla Rich:
  Nombre, Tipo (extensión o «carpeta»), Tamaño legible, Modificado
  (AAAA-MM-DD HH:MM). Carpetas primero, luego alfabético sin distinguir
  mayúsculas.
- Carpeta inexistente o que no es carpeta: mensaje en stderr, sin traza, código 1.
  Carpeta vacía: aviso en vez de tabla vacía.

**Correcciones que hice al plan:**

1. **Escapar los nombres con `rich.markup.escape`.** El plan inicial pintaba
   `ruta.name` a pelo: un fichero llamado `[borrador].pdf` se comía los
   corchetes y Rich lo interpretaba como marcado. Añadí el escape.
2. **Saltar los ficheros que fallan al `stat()`.** Un enlace roto o un fichero
   sin permisos lanzaba una excepción y rompía la tabla entera. Ahora se
   saltan y la tabla sigue.
3. **`typer.Exit(code=1)` en vez de `sys.exit`.** Lo pedía el criterio: el
   programa tiene que terminar con código 1 sin soltar una traza.

**Funcionó a la primera:** sí. Lo que no funcionó: mi primer `escape()` lo
aplicaba al `str(carpeta)` del título pero no a los nombres de las filas; lo
detecté probando con `touch "[borrador].pdf"`.

**Qué aprendí:** `typer.Exit(code=1)` termina con el código correcto y sin
traza; `Console(stderr=True)` separa el error del resultado, que es lo que
permite redirigir solo lo útil.

---

## 2026-10-27 · Validación: `errores.py` y `config.py`

**Prompt (agente plan):**

> Carga la skill acciones-json y lee @acciones.json. Quiero validar
> acciones.json ANTES de ejecutar nada: `src/tareas/errores.py` con
> TareasError, ConfigError y AccionNoValida; `src/tareas/config.py` con
> `cargar(ruta) -> list[dict]`; y la orden «tareas validar». No toques nada
> todavía: dime qué ficheros crearías y qué casos de error vas a detectar.

**Correcciones que hice al plan:**

- El plan solo miraba los campos obligatorios. Le pedí que comprobara también
  el **formato** del `nombre` (minúsculas y guiones), que el `patron` compila y
  que la `plantilla` solo usa huecos que el motor conoce. Con eso, un
  `{fechae:...}` mal escrito se detecta al validar y no al renombrar.
- Pedí que una acción de tipo `borrar` no pudiera llevar `confirmar: false`.
  Es una decisión de seguridad, no de estilo: el enunciado pide que borrar
  pida confirmación.

**Casos feos que probé yo** (ninguno puede acabar en traza):

| Caso | Lo que dice |
|---|---|
| Coma de más | «no es JSON válido: línea X, columna Y» |
| `"tipo": "mober"` | «Acción «x», campo «tipo»: «mober» no existe; usa uno de: …» |
| Nombre repetido | «Acción «x», campo «nombre»: está repetido» |
| Regex rota | «Acción «x», campo «filtro.patron»: expresión regular rota: …» |
| Fichero inexistente | «No encuentro «nada.json»…» |
| Hueco inexistente en la plantilla | «Acción «x», campo «plantilla»: usa el hueco «fechae»…» |

**Qué aprendí:** un mensaje de error que dice *qué acción* y *qué campo* vale
mucho más que «error de configuración»: el primero se arregla en diez segundos.

---

## 2026-10-27 · El motor y las acciones en clases

**Prompt (agente build):**

> Carga la skill acciones-json. Crea `src/tareas/acciones.py` y
> `src/tareas/motor.py`:
> 1. `acciones.py`: dataclass `Resultado(origen, destino, estado: hecho | simulado | saltado)`;
>    clase base abstracta `Accion` con `ejecutar(ficheros, simular)` y
>    `aplicar(fichero, n, simular)` abstracto; fábrica `Accion.desde_config(dict)`
>    con un registro de subclases (nada de if/elif por tipo); subclases `Mover`,
>    `Copiar`, `Renombrar` y `Borrar` (destructiva = True).
> 2. `motor.py`: clase `Motor(acciones)` con `seleccionar(carpeta, filtro)` y
>    `ejecutar(nombre, carpeta, simular) -> list[Resultado]`. Sin carpeta, usa
>    «origen». Acción o carpeta inexistente → TareasError con mensaje humano.
>    Con `simular=True` no se toca NADA del disco (ni `mkdir`). Nunca sobrescribir:
>    sufijo « (1)».
> No toques `cli.py` y NO ejecutes ninguna acción: las pruebo yo.

**Lo que el revisor me señaló después y corregí:**

1. **`destino_libre` en simulación.** La función mira el disco para ver si el
   destino existe. En simulación el primer fichero todavía no está en el
   destino, así que dos ficheros que se renombran al mismo nombre **no** se
   detectan como colisión: los dos simulados apuntarían al mismo destino.
   Lo dejé anotado como mejora en el README en vez de complicar el código, y
   es una de las preguntas que me hará el profesor en la defensa.
2. **`Renombrar` y el contador `{n}`.** `{n:03}` se reinicia en cada ejecución
   de la acción, así que renombrar dos veces seguidas genera `001` otra vez. Es
   el comportamiento que pide el enunciado, pero conviene saberlo.
3. **Tildes al renombrar.** `fichero.suffix.lower()` y `stem` conservan las
   tildes; el problema no era ahí, sino en la tabla de Rich, que las
   interpretaba como marcado. Ya estaba resuelto con `escape`.

**Qué aprendí:** el patrón de registro (`__init_subclass__` apunta cada
subclase en un diccionario) hace que el motor no sepa nada de los tipos: para
añadir uno nuevo se escribe la clase y ya está.

---

## 2026-10-27 · La interfaz completa: `acciones` y `ejecutar`

**Prompt (agente build):**

> Amplía SOLO @src/tareas/cli.py (Typer + Rich). Ya existen `config.cargar`,
> `Motor` y las `Accion`.
> 1. Opción global `--config RUTA` en `@app.callback` (por defecto
>    ./acciones.json), guardada en `ctx.obj`.
> 2. «tareas acciones»: tabla Rich con nombre, tipo y descripción.
> 3. «tareas ejecutar NOMBRE [CARPETA] --simular --si»:
>    - `--simular`: tabla «fichero → destino» con estado «simulado», sin tocar nada;
>    - acción destructiva sin `--simular` ni `--si` → `typer.confirm(..., abort=True)`;
>    - resumen final: N hechos, N simulados, N saltados; si ningún fichero
>      cumple el filtro, dilo.
> 4. Códigos de salida: 0 bien · 1 TareasError · 2 uso (Typer) · 3 ConfigError.
>    Nunca un traceback ante errores previsibles: mensaje en rojo y
>    `typer.Exit(e.codigo_salida)`.
> No toques `acciones.py` ni `motor.py`. Termina con: `uv run tareas --help`

**Correcciones que hice al plan:**

- Pedí que el error de configuración (código 3) se capturara **también** en
  `tareas acciones`, no solo en `validar`. Si el JSON está roto, la orden que
  lo lee tiene que fallar con 3, no con 1.
- Pedí que `ejecutar` capturara `TareasError` **una sola vez**, alrededor del
  bloque completo, en vez de repetir el `try/except` en cada sitio.

**Lo que me costó un rato:** el `try/except` que envuelve a la confirmación
interactiva. Si `typer.confirm` lanza `Abort` dentro del `try`, el `except
TareasError` no lo captura (no es una `TareasError`), pero el mensaje de
aborto se mezcla con el mío. Lo comprobé contestando «no» y viendo que no se
borra nada y que el código de salida es distinto de 0.

---

## 2026-10-27 · El esquema de `acciones.json` y mis 11 acciones

Esta parte la escribí yo, sin IA, como pide el enunciado («tu
`acciones.json` lo escribes tú, sin IA»).

**Prompt (agente build, vía el comando `/nueva-accion`):**

> /nueva-accion apuntes-programacio "mueve los apuntes de Programación a su
> carpeta, reconociendo la asignatura por el nombre del fichero"

**Qué corregí de lo que propuso el agente:**

- El patrón que propuso era demasiado amplio: `programa` también aparece dentro
  de palabras que no son apuntes de Programación. Lo acoté a
  `(python|java|programa|algorit|pseudocodi|funcions|bucles|llistes|c\+\+)`.
- Faltaba el flag `(?i)` al principio de todos los patrones: sin él,
  `IntroduccióGit` y `introducciogit` se comportarían distinto.
- Quité un `\b` (límite de palabra) que proponía el agente: en un nombre de
  fichero con acentos y espacios los límites de palabra en Python se
  comportan de forma poco intuitiva con `\w` y la ñ, así que prefiero
  subcadenas distintivas.

**Ideas de mis 11 acciones:** las seis de apuntes (una por asignatura), separar
instaladores, separar comprimidos, renombrar capturas con su fecha, borrar
temporales viejos y copiar una copia de seguridad de los apuntes.

**Qué aprendí:** una acción de `mover` con `filtro.extensiones` y
`filtro.patron` es un «buscador con destino». Encadenarlas (primero separar
instaladores, luego repartir apuntes) es lo que da a la herramienta el
comportamiento de «combinables» que pide la rúbrica.

---

## 2026-10-27 · Revisión con @revisor: 10 fallos reales

Antes de dar el proyecto por bueno, lancé el subagente revisor sobre
`src/tareas/`. No se quedó en comentarios de estilo: encontró diez fallos
reales, y casi todos eran **excepciones sin capturar que llegaban al usuario
como una traza de Python**. Eso es justo lo que la rúbrica penaliza.

**Prompt:**

> @revisor revisa @src/tareas/

**Lo que señaló, y lo que hice:**

1. **`UnicodeDecodeError` al leer `acciones.json`.** `read_text(encoding="utf-8")`
   solo captura `OSError`, y `UnicodeDecodeError` es un `ValueError`. Si el
   JSON estaba en latin-1 (el «ANSI» de Windows), el usuario veía una traza.
   Ahora se lee con `utf-8-sig` y se avisa: «no está guardado en UTF-8».
   De paso, `utf-8-sig` también arregla el **BOM** del Bloc de notas de
   Windows, que hacía que un JSON perfectamente válido pareciera roto.
2. **`AttributeError` con `"filtro": null`.** La validación aceptaba un filtro
   nulo, pero `config.get("filtro", {})` devuelve `None` cuando la clave
   **existe** con valor `null` (el valor por defecto solo se aplica si falta
   la clave). Arreglado con `or {}`.
3. **`TypeError` con `"origen": 123`.** `origen` no se validaba en absoluto y
   el motor hacía `Path(origen)`. Ahora `config.py` comprueba que sea un texto.
4. **`ValueError: Invalid name` con `"plantilla": "sub/{n}.txt"`.** La
   plantilla pasaba la validación y reventaba al renombrar, porque el nombre
   nuevo no puede ser una ruta. Ahora la plantilla no puede llevar barras.
5. **`MarkupError` de Rich.** Los mensajes de error metían texto del usuario
   sin escapar, así que un fichero llamado `[/].pdf` hacía que Rich protestara
   con un `MarkupError` en vez de decir qué pasaba. Ahora todo lo que viene
   del usuario pasa por `escape()`.
6. **`PermissionError` al leer la carpeta.** `listar` lo controlaba, pero el
   motor no: una carpeta sin permisos lancía la traza.
7. **`FileNotFoundError` en `stat()`.** Si el fichero se borra entre el
   `iterdir()` y el `stat()` —cosa normal en `~/Baixades` mientras descargas
   algo— la acción reventaba. Ahora se salta ese fichero.
8. **`OSError` al mover, copiar, renombrar o borrar.** Destino sin permiso,
   fichero bloqueado en Windows, disco lleno. Y lo peor: como `ejecutar` era
   una comprensión de listas, **un solo fallo abortaba la acción entera**,
   dejando los ficheros anteriores ya movidos y sin tabla de resultados. Ahora
   cada fichero se captura por separado, se anota el error y se sigue; el
   programa sale con código 1 al final.
9. **`RuntimeError` de `expanduser()`** si no se puede resolver `~`.
10. **La simulación mentía.** `destino_libre` decide mirando el disco, y en
    simulación el disco no cambia: dos ficheros que se renombraban al mismo
    nombre **mostraban el mismo destino**, cuando de verdad el segundo habría
    acabado en « (1)». Justo al revés de lo que sirve una simulación. Ahora la
    acción lleva un conjunto de nombres ya reservados, así que la simulación
    enseña exactamente los destinos reales.

**Unos más que también arreglé:**

- **La extensión `.tar.gz` nunca entraba.** `Path("informe.tar.gz").suffix` es
  `".gz"`, así que mi propia acción `separar-comprimidos` pedía `".tar.gz"` y
  `".tar.xz"` y esos ficheros jamás se habrían movido. Ahora se comparan las
  extensiones por sufijo del **nombre**, no con `Path.suffix`.
- **La regex no distinguía mayúsculas, pero las extensiones sí.** Era
  incoherente: `factura.PDF` entraba en `.pdf` pero `Informe.pdf` no entraba
  en el patrón `informe`. Ahora el motor compila el patrón con
  `re.IGNORECASE` y he quitado el `(?i)` de los seis patrones del JSON, que
  era redundante.
- **Un campo desconocido en una acción pasaba desapercibido.** Si escribías
  `"patron"` en vez de dentro de `"filtro"`, la validación lo aceptaba y la
  acción se aplicaba a **todos** los ficheros de la carpeta. Con `tipo:
  "borrar"` eso es borrar de más. Ahora hay una lista blanca de campos por
  acción.
- **`confirmar` era un campo muerto.** La documentación lo describía, pero el código solo miraba `destructiva`. Ahora una acción con `"confirmar": true` también pregunta.
- **Los enlaces simbólicos rotos.** `destino.exists()` sigue los enlaces, así
  que un enlace roto en el destino devolvía `False` y `shutil.copy2`
  escribía **a través** del enlace, machacando el fichero al que apuntaba
  (que puede estar en cualquier sitio). Ahora `destino_libre` cuenta los
  enlaces rotos como destino ocupado.
- **Nombres que Windows no admite.** `CON.txt`, `LPT1.txt` o un nombre con
  `:` son válidos en Linux y reventan en el portátil de un compañero. Ahora
  `config.py` los rechaza con un mensaje claro.

**Lo que el revisor se equivocó en:** dijo que el código de salida de una
acción inexistente debería ser 2 (error de uso). No es así: el enunciado dice
que «acción desconocida» es un 1 (fallo al ejecutar), y el 2 lo pone Typer
solo cuando el uso de la orden es incorrecto.

**Qué aprendí:** un programa que borra ficheros no puede fiarse ni de los
ficheros ni del disco. Casi todos los fallos que encontró el revisor eran de
la misma familia: una excepción de la que nadie se encarga. Y la simulación
debe ser **fiel**: si enseña un destino que luego no se usa, deja de servir
para lo único que sirve.

