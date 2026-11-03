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

---

## 2026-10-27 · Organizar y desorganizar la carpeta de descargas

**Petición:** «cuando un archivo tenga un formato de nombre que no sea
interpretable por el CLI, lo cambie y lo adapte para que sí lo sea», más dos
órdenes: una que organice todo lo de la carpeta de descargas y otra que lo
devuelva.

**Prompt (agente plan):**

> Quiero dos órdenes nuevas: `tareas organizar` y `tareas desorganizar`.
> La primera reparte todo lo que hay en la carpeta de descargas entre las
> carpetas de asignatura; la segunda lo devuelve. Al organizar, los nombres
> que no sean interpretables se adaptan a un formato que sí lo sea.

**Lo primero que hice fue mirar los datos, no escribir código.** En la carpeta
de descargas había 13 PDF y, al lado, 13 ficheros `.md` con un resumen del
contenido. Comparé qué.decía el nombre de cada fichero con qué decía su
resumen, y salió esto:

| Fichero | Por el nombre | Por el resumen |
|---|---|---|
| `P1.2. Activitats.pdf` | nada | **bbdd** («Introducció a les BBDD») |
| `Activitat_PRI_01.pdf` | nada | **intermodular** («Projecte Intermodular 1DAW») |
| `Salva_Llacer.pdf` | nada | **sistemes** («SISTEMES INFORMÀTICS») |
| `A22_IntroduccióGit_2.pdf` | entorns | bbdd |

Tres de los cuatro casos que no se entendían por el nombre **se entendían por
el resumen**. Y el resumen son 2 KB de texto, frente a los PDF de varios
megabytes. Esta es justo la optimización que planteé en el principio: leer lo
barato, no lo caro.

**Correcciones que hice al plan:**

1. **La clasificación no puede ser «la primera que coincide».** Al principio
   escribí que gana la primera carpeta cuyo patrón aparece. Al probarlo vi que
   «Projecte Intermodular 1DAW» contiene «projecte» (intermodular) *y*
   «github» (entornos), y se iba a entornos. Lo cambié por **puntuación**: gana
   la carpeta con más patrones que aparecen. Con eso, intermodular gana 2-1.
2. **El `.md` es un respaldo del PDF, no un fichero más.** Si no lo trato
   aparte, se organizaría por su cuenta y acabaría con el nombre canónico
   distinto al de su documento. Ahora se mueve con él.
3. **Hacerlo reversible.** Si solo normalizo los nombres, desorganizar deja
   los ficheros con el nombre canónico y el usuario ha perdido el suyo. Añadí
   un manifiesto que recuerda de dónde salió cada fichero, así que la vuelta
   los devuelve **exactamente** como estaban. Es la diferencia entre una
   herramienta y un trasto.
4. **La clave de la carpeta tiene que contar como patrón.** Si no, el nombre
   nuevo (`bbdd_practica-1-entitats.pdf`) seguiría sin ser interpretable por
   las acciones existentes, y todo el trabajo de normalizar sería inútil.

**Lo que me salió mal:**

- **La normalización no era idempotente.** `normalizar("bbdd_nota.pdf", "bbdd")`
  devolvía `bbdd_bbdd-nota.pdf`, porque slugificaba el nombre entero (y el
  guion bajo se convertía en guion) y luego le añadía la clave otra vez. Lo
  detecté al escribir el test de idempotencia. Arreglo: quitar la clave del
  nombre **antes** de normalizarlo.
- **Un test mío daba por hecho que «P1.2. Activitats.pdf» iba a bbdd**, pero
  sin el resumen no hay forma de saberlo: va a la carpeta de respaldo. El test
  estaba mal, no el código. Lo reescribí para que compruebe las dos cosas.

**Qué aprendí:**

- Un nombre de fichero no es un dato: es una **etiqueta**, y las etiquetas se
  pueden estandarizar. `Pràctica 1. Entitats, atributs i valors.pdf` → prefixo
  de asignatura + nombre limpio. A partir de ahí el nombre dice de qué es el
  fichero, y hasta las expresiones regulares que ya tenía escritas lo
  entienden.
- **La carpeta de asignaturas va en el fichero de configuración, no en el
  código.** Las seis acciones `apuntes-*` heredan de la sección `carpetas`, así
  que la asignatura se escribe una sola vez. Añadir una asignatura nueva es
  añadir una entrada al JSON.
- Lo que no se puede leer de un fichero pequeño, se lee de su resumen. Y lo
  que no se puede saber de ningún sitio, se dice con claridad: la carpeta de
  respaldo.

---

## 2026-11-02 · Reformulación: analizar → organizar → deshacer

**Petición:** cambiar el CLI entero. Seis órdenes: `analizar`, `organizar`,
`deshacer`, `resumir`, `evaluar` y `comandos`. Todas admiten la carpeta como
argumento y, si no se pone, trabajan sobre la de la terminal.

**Lo primero que hice fue mirar los datos de verdad.** En `~/Baixades` había 41
ficheros: PDF con sus `.md` al lado. Y al mirar el contenido de los `.md` se
vio algo que cambió el diseño:

| Fichero | Por el nombre | Por su contenido |
|---|---|---|
| `P1.2. Activitats.pdf` | nada | **bbdd** («Introducció a les BBDD») |
| `Activitat_PRI_01.pdf` | nada | **intermodular** («Projecte Intermodular 1DAW») |
| `Salva_Llacer.pdf` | nada | **sistemes** («SISTEMES INFORMÀTICS») |
| `Ud1. Introducción a las Bases de Datos.pdf` | nada | **bbdd** |
| `Veure este document per ajudar-te en la tasca 4.pdf` | nada | **bbdd** («crear una base de datos en LibreOffice Base») |

Cinco de los que el nombre no explicaba, el contenido sí. Así que `analizar`
**lee el contenido de verdad**, no solo el nombre.

**Decisiones que tomé:**

1. **La ficha .md es el portador de datos.** `analizar` la escribe en la
   carpeta `md`, y `organizar`, `deshacer`, `resumir` y `evaluar` la leen. Así
   el PDF de 300 páginas se abre **una sola vez**, y el resumen se hace sin
   tocarlo. Es la versión buena de la idea del principio.
2. **El renombrado es temporal.** `analizar` limpia los nombres incompatibles
   (tildes, espacios) y `organizar` **devuelve el nombre original** al mover
   el documento. El nombre limpio solo sirve para trabajar.
3. **La clasificación cuenta evidencia, no aciertos.** Al principio ganaba la
   primera carpeta que coincidía, y «Activitat_PRI_01» iba a Entornos porque
   el documento menciona «github». Ahora gana la que aporta más: una frase
   («projecte intermodular») pesa 3, una palabra corta 1, y lo que está en el
   título del documento pesa el doble. Con eso, el fichero va a intermodular.
4. **Un solo golpe no basta para clasificar por el contenido.** «ide» dentro
   de una frase no convierte un manual de placa base en apuntes de Entornos:
   por el contenido hacen falta 2 puntos.

**Tres bugs reales que aparecieron y se arreglaron:**

- **`sin_conflicto` devolvía solo el nombre**, no la ruta. Al mover un
  documento a su carpeta de destino lo dejaba en el directorio desde el que se
  ejecutaba la orden. Lo encontraron las pruebas, no yo.
- **La ficha se escribía fuera de la carpeta `md`**, porque al cambiar
  `sin_conflicto` el nombre compatible pasó a ser un `Path` y al construir la
  ruta de la ficha ganaba el componente absoluto.
- **Los nombres en NFD no se encontraban.** Los ficheros de `Baixades` tienen
  la «ó» como «o» + acento combinante (NFD), y lo que se teclea está en NFC:
  se ven iguales pero no lo son, así que `resumir 'A21_IntroduccióGit_GitHub.pdf'`
  no encontraba su ficha. Ahora todas las comparaciones normalizan a NFC.
  Esto lo habría dado el profesor en la defensa si no lo hubiera cazado.

**Qué aprendí:**

- Cuando la especificación dice «analiza el contenido», hay que leer el
  contenido. Cinco de los ficheros de la carpeta no se clasificaban por su
  nombre y sí por su texto.
- Una estructura de datos que se escribe una vez y se lee muchas veces (la
  ficha) vale más que volver a abrir el fichero cada vez.
- Las comparaciones de nombres tienen que normalizarse. Es el primer bug que
  aparece en macOS y en cualquier fichero que venga de un navegador.

---

## 2026-11-02 · `resumir` y `evaluar` no funcionan correctamente

**Prompt (agente plan):**

> Lee @src/tareas/resumen.py y @src/tareas/evaluacion.py. Estas dos órdenes
> crean el fichero con el formato correcto, pero el contenido que ponen no
> sirve. Dime exactamente qué falla en cada una y por qué.

**Lo que encontré al probarlas con los PDF de verdad:**

**`resumir` no resume.** Escribe las primeras 25 líneas de cada apartado. Una
extracción, no un resumen: no condensa, no elige lo importante y no redacta.
En un documento de 30 páginas, el «resumen» es la primera página.

**`evaluar` genera preguntas que no preguntan nada.** El detector de
definiciones busca marcas como «es» o «son», que en castellano aparecen en
casi todas las frases. El resultado son preguntas del tipo:

> 2. Tot aquell exercici que estiga copiat es puntuarà amb 0 punts...
>    a) ......  b) ......  c) ......  d) ......

Y las cuatro opciones son líneas de puntos: no hay ninguna alternativa real.
La sección de «Cálculo y problemas» además queda vacía, porque depende de que
aparezcan fórmulas con el formato `X = ...`, que no es lo habitual.

**La causa de fondo es la misma en las dos:** un resumen de todo el contenido
y unos ejercicios con sentido **necesitan entender el documento**, y eso lo
hace un modelo de lenguaje, no unas expresiones regulares. Lo que hay ahora
es un andamiaje correcto: sabe encontrar el documento, sabe escribir el
`.odt`/`.docx` con el formato que pide el enunciado y sabe colocar el texto.
Lo que no sabe es **qué texto poner**.

**Qué he hecho:** documentarlo en el README («Limitaciones conocidas») y en
el changelog, en vez de disimularlo. Un revisor que lee el código y ve que
`resumir` recorta las primeras 25 líneas se da cuenta enseguida; y si lo
tengo escrito yo, con el diagnóstico y la causa, la conversación con el
profesor va a ser sobre la solución y no sobre el desconocimiento.

**Lo que falta (semana 3):** la capa de IA. El mismo modelo del centro que
usa OpenCode, llamado desde Python con la clave en un `.env` que nunca se
sube al repo, y un modo sin red que avise de que estas dos órdenes no pueden
completarse sin conexión. Se enchufará en el mismo sitio: la función que
decide el contenido a partir del texto de la ficha.

---

## 2026-11-02 · La capa de IA: resumen y ejercicios de verdad

**Petición:** «haz lo que tengas que hacer para que funcione con IA esos dos
comandos».

**Primero, averiguar con qué se puede hablar.** El `opencode.json` global ya
tenía el proveedor del centro (`ia.simarro`), pero había dos problemas:

1. **Python noconnects con el servidor del centro**: el tráfico pasa por un
   proxy con su propio certificado (`ca-simarro.crt`), y Python no lo
  .confía. La solución es una variable más: `TAREAS_IA_CA`, que apunta al
   certificado.
2. **No sabía el nombre real de los modelos**. Lo saqué de
   `GET /llmapi/v1/models`: `Qwen38-DualSpark-low`, `-medium`, `-xhigh` y las
   variantes `-Thinking-`.

**Decisiones:**

1. **Cliente propio, sin dependencias.** `ia.py` habla con la API usando
   `urllib` de la biblioteca estándar. Ninguna dependencia nueva: el curso
   pide que el proyecto sea sencillo de instalar y `requests` no vale la pena
   para una llamada.
2. **La clave fuera del repo, siempre.** Las variables de entorno mandan
   sobre el `.env`, y el `.env` se busca en la carpeta de trabajo y en
   `~/.config/tareas/`. Hay un `.env.example` con las cinco variables
   documentadas y el `.env` está en el `.gitignore` desde el primer commit.
3. **La IA es opcional, no obligatoria.** Si no hay clave, no hay red o el
   servidor falla, se lanza `ErrorIA` con un mensaje de **una línea** y las
   dos órdenes caen a la versión extractiva, dejando una nota en el documento
   que dice que se ha hecho sin IA. Ninguna orden puede reventar por un
   problema de red.
4. **El modelo devuelve Markdown**, y `markdown.py` lo traduce a las
   secciones del documento: encabezados de dos niveles, viñetas, tablas con
   tabuladores y negritas de verdad en el `.odt` y el `.docx`.

**El error que me costó tiempo:** al conectar la IA, **las pruebas empezaron a
llamar a la red de verdad**. La suite tardaba dos minutos y gastaba créditos.
Eso no puede ser: un `pytest` tiene que ser instantáneo y no puede depender
de que haya red. Lo resolví con un fixture automático en `tests/conftest.py`
que aparta la configuración de la IA, y las pruebas de la capa que sí
necesitan el modelo simulan la llamada a `urlopen`.

**Cómo quedó (probado con un PDF real de Sistemas Informáticos):**

- El resumen son 3 páginas con «Ideas principales» (8 puntos con los conceptos
  que hay que saberse), un apartado por tema y una **tabla** con la rúbrica de
  corrección.
- Los ejercicios son 6 preguntas de tipo test con **alternativas reales**
  (no líneas de puntos), la respuesta correcta marcada, 3 preguntas de
  desarrollo y las soluciones al final. Todo en el idioma del documento.
- Tardan entre 1 y 4 minutos con los modelos del centro. Es lo que hay.

**Qué aprendí:**

- Un fallo que solo aparece en la red es el que más se esconde: la primera
  versión de las pruebas «funcionaba» porque no había clave. En cuanto la
  puse, la suite se fue a dos minutos. **Las pruebas que dependen del mundo
  exterior hay que aislarlas siempre**, aunque no lo parezca.
- El «modo sin red» no es un extra: es la diferencia entre una herramienta
  que se rompe y una que te explica qué pasa. Y se implementa en un solo sitio:
  el punto donde se llama al modelo.
- Mandar el texto del documento a un modelo es una decisión de privacidad,
  no un detalle técnico. Por eso la URL del servidor se configura, y por eso
  hay una alternativa con Ollama en local que no manda nada fuera del
  ordenador.






---

## 2026-11-02 · La IA busca en internet y decide los ejercicios

**Petición:** «que el comando resumen utilice la IA no solo para resumir, sino
para que, en caso de que la documentación de entrada tenga contenido escaso o
demasiado resumido, la IA busque en internet y complete de forma resumida todos
los contenidos». Y: «el comando evaluar no ha funcionado sobre ese PDF; la IA
debe entender el contexto y usar el contenido del documento + el resumen
completado». Y un comando nuevo, `tareas clasificar`.

**Primero, mirar el documento queFallaba.** `Ud1-Introduccion-a-las-Bases-de-Datos.pdf`:
17 páginas y **431 caracteres** de texto. Era un PDF de diapositivas.

**Causa raíz, y no era la que yo pensaba.** Yo使用的是 `pdftotext` con las
**tres primeras páginas**, y por eso solo salía el índice y un título. El
documento entero tenía **5 204 caracteres**: la información estaba, pero en
las páginas 4 a 17. Arreglé `contenido.py` para que lea más páginas hasta
llegar a 8 000 caracteres (con un tope de 40 páginas). El mismo documento pasó
de 431 a 4 985 caracteres.

**Cómo se hace que la IA busque en internet.** Un modelo de la API del centro
no tiene herramienta de búsqueda, y aunque la tuviera no podría llamarse a sí
mismo. Así que se inventó un **protocolo**:

```
[[BUSCAR: consulta]]
```

El modelo escribe esa línea y termina su turno. La herramienta la busca, le
pasa los resultados y le vuelve a preguntar. Lo importante es **quién decide**:
no soy yo, es el modelo, según si ve que le falta información. Un modelo que
no necesita nada no busca nada, y uno que tiene un documento escueto busca por
concepto.

La búsqueda usa la **API de Wikipedia** (abierta, sin clave, con el texto
plano del artículo y su URL) y el Instant Answer de DuckDuckGo. Wikipedia
devolvió 28 000 caracteres de «Base de datos»: de sobra para completar unas
diapositivas.

**Lo que hizo el modelo con el PDF de prueba** (esto es lo que se le pidió):

- Detectó que el documento era demasiado escueto, pidió una búsqueda y
  completó el resumen con la información de Wikipedia, incluyendo una **tabla**
  comparando fichero y base de datos. Al final del documento se escriben las
  fuentes con su URL.
- En los ejercicios, entendió que el tema era **puramente teórico** y escribió:
  «Este documento es puramente teórico (definiciones, conceptos, fases de
  diseño y terminología), por lo que no admite ejercicios de cálculo
  numérico. Se ha omitido el apartado «Cálculo y problemas» por carecer de
  fórmulas o datos cuantitativos.» Eso es exactamente lo que pedía el
  enunciado: que la IA entienda de qué va el documento.
- Y como antes se había hecho el resumen, ese resumen (con la información de
  internet) se usó como contexto: las preguntas salen sobre el contenido real
  del tema, no solo sobre las 400 palabras del original.

**El comando `clasificar`.** Aquí las carpetas **no** están escritas en
`acciones.json`: las decide la IA mirando el contenido. El modelo responde con
un formato muy simple (`[Carpeta]` seguido de `- documento`), que la
herramienta lee, sanea (para que el nombre se pueda crear en Windows) y usa
para mover los documentos. Probado con cuatro ficheros:

```
Recetas   -> Bizcocho de limon.txt, Tortilla de patatas.txt
Historia  -> Historia de Roma.txt
Hardware  -> Manual de la placa base Gigabyte.txt
```

**Lo que aprendí:**

- **Un fallo que parecía de la IA era de mi lectura.** Antes de culpar al
  modelo por «no entender» el documento, comprobé cuántos caracteres tenía de
  verdad. La mitad del problema era que yo le daba 431 caracteres de un
  documento de 5 204. Antes de pedirle más inteligencia al modelo, hay que
  darle bien los datos.
- **Un protocolo en texto plano es más robusto que depender de que el modelo
  soporte «function calling».** No todos los servidores lo implementan, y
  este no. Con una marca `[[BUSCAR: ...]]` funciona en cualquier API
  compatible con OpenAI.
- **Quien debe decidir si un documento está completo es el modelo, no el
  código.** Si el código decide, hay que codificar cuándo «es poco texto», y
  eso siempre se queda corto o se pasa. El modelo lo sabe mirando lo que tiene.
- **La IA también se equivoca, y hay que decirlo.** El revisor es el que
  avisa de los casos raros (un fichero ya renombrado, una ficha que no
  aparece). Eso va en el prompt de `deshacer`, no en el código de `deshacer`.
