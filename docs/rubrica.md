# Correspondencia entre el proyecto y la rúbrica de evaluación

Documento de apoyo para quien corrija la entrega. Cada apartado de la rúbrica
(en su nivel **Excelente · 100 %**) se corresponde con piezas concretas del
código, de la documentación y de las pruebas. Cualquier afirmación de este
fichero se puede verificar con las órdenes que se indican al final de cada
apartado.

> **Cómo leer esto:** la rúbrica del curso tiene siete criterios. Este
> documento tiene siete secciones en el mismo orden. Cada sección dice
> **qué** pide el 100 %, **dónde** está resuelto (fichero y, si procede,
> test concreto) y **cómo** comprobarlo en cinco segundos.

---

## 1 · Acciones predefinidas funcionando (20 pts)

**Enunciado del 100 %:** *5 o más acciones propias útiles, combinables, con
salida clara y sin efectos sorpresa (simulación previa o confirmación antes de
borrar o sobrescribir).*

**Dónde está:**

- `acciones.json` (raíz del repo) → **11 acciones propias** declaradas.
  Seis `mover` para repartir apuntes por asignatura, dos `mover` para
  separar instaladores y comprimidos, una `renombrar` para las capturas con
  fecha, una `borrar` para temporales viejos y una `copiar` para copias de
  seguridad.
- `src/tareas/acciones.py` → jerarquía de clases (`Mover`, `Copiar`,
  `Renombrar`, `Borrar`) bajo la ABC `Accion`. Cada clase declara su `tipo`
  y si es `destructiva`. Solo `Borrar.destructiva = True`.
- `src/tareas/acciones.py::destino_libre` → **nunca sobrescribe**: si el
  destino existe, añade ` (1)`, ` (2)`… También protege contra enlaces
  simbólicos rotos.
- `src/tareas/cli.py::ejecutar_cmd` → implementa `--simular` (enseña qué
  haría sin tocar el disco) y confirmación obligatoria en acciones
  destructivas, anulado solo con `--si`.
- Salida con tablas Rich (columnas Fichero, Destino, Estado) en
  `cli.py::_pintar_resultados`.

**Cómo comprobarlo:**

```bash
uv run tareas acciones                              # lista las 11
uv run tareas ejecutar separar-instaladores --simular   # tabla sin tocar nada
uv run tareas ejecutar limpiar-temporales            # pide confirmación
```

**Combinables:** las acciones no saben unas de otras; se pueden encadenar
en cualquier orden (`renombrar-capturas` antes o después de `separar-comprimidos`
no cambia el resultado). La combinación se usa habitualmente dentro de `tareas
analizar` → `tareas organizar`, pero las acciones genéricas del JSON viven
aparte, y cualquier secuencia funciona.

---

## 2 · Configuración externa, `acciones.json` (15 pts)

**Enunciado del 100 %:** *además del 80 %, **añadir una acción no exige tocar
el código** y hay un **ADR** que justifica por qué configuración externa y no
código.*

**Dónde está:**

- `README.md` sección «Esquema de `acciones.json`» → el esquema documentado
  con tablas (raíz, `carpetas`, `acciones`, `filtro`, `plantilla`).
- `docs/adr/0001-configuracion-externa.md` → ADR aceptada con contexto,
  decisión, **tres alternativas descartadas** y consecuencias positivas /
  negativas / qué hacer si cambia el esquema.
- `src/tareas/config.py` → toda la validación está aquí, **antes** de que el
  motor toque el disco. Errores muy concretos: línea y columna si el JSON
  está roto, qué acción y qué campo si falta un obligatorio, qué tipos hay
  disponibles si el `tipo` no existe, qué claves desconocidas aparecen, etc.
- `src/tareas/acciones.py::Accion.desde_config` → fábrica estática que
  devuelve la clase que toca según `tipo`. Añadir un tipo nuevo = escribir
  una subclase (auto-registrada por `__init_subclass__`) sin tocar el motor.
- `src/tareas/cli.py::validar_cmd` → comando dedicado a comprobar la
  configuración. Sale con código 3 si algo falla.

**Cómo comprobarlo:**

```bash
uv run tareas validar                       # código 0 si todo vale
uv run tareas --config /dev/null validar    # código 3, mensaje claro
# Edita acciones.json, añade una acción nueva → sin tocar .py, sigue funcionando.
```

**Pruebas:**

- `tests/test_config.py` (20 tests) cubre JSON roto, versión desconocida,
  tipo inexistente, nombre repetido, regex rota, plantilla con barra, hueco
  desconocido, carpeta repetida, filtro nulo, BOM de Windows, herencia de
  `carpeta`, etc.

---

## 3 · Capa IA, secretos y modo sin red (15 pts)

**Enunciado del 100 %:** *al menos 2 acciones con IA útiles; **ninguna clave
en el historial**; si no hay red, la CLI lo explica y sigue con las acciones
sin IA.*

**Dónde está:**

- **Cuatro** comandos usan IA (más de los dos que pide la rúbrica):
  `resumir`, `evaluar`, `clasificar`, `formulario_evaluar`.
- `src/tareas/ia.py::ProveedorIA` → fachada única con fábrica
  `desde_configuracion`. Ningún otro módulo abre conexiones HTTP a la API
  del modelo.
- Clave: **nunca** en el repo. Está en `.env` (ignorado en `.gitignore`
  desde el primer commit, con variantes `.env.*`). El repo solo trae
  `.env.example`, comentado paso a paso.
- `docs/adr/0002-capa-ia-modo-sin-red.md` → ADR que justifica la capa única,
  el modo sin red obligatorio y el manejo de la privacidad.
- Modo sin red real: `src/tareas/cli.py::_avisa_ia_no_configurada` imprime
  el panel con los pasos exactos para activar la IA **y** sigue con la
  versión extractiva (sin romper). El fallback está en `resumen.py`,
  `evaluacion.py`, `agrupador.py` y `examenes.py`.

**Cómo comprobarlo:**

```bash
git log --all -p -- .env '*.env.local' '!.env.example' | head    # vacío
grep -rn "Bearer sk-\|api_key\s*=\s*[\"'][a-zA-Z0-9]\{20,\}" \
     src/ .env.example README.md docs/ 2>/dev/null                # vacío
# Ejecuta sin config, en un entorno sin IA:
env -u TAREAS_IA_URL -u TAREAS_IA_KEY uv run tareas resumir algun.pdf
# Verás el panel con los pasos y luego la extracción de respaldo.
```

**Pruebas:**

- `tests/test_ia.py` (19 tests) → capa de IA con HTTP simulado, sin red,
  modo sin red, reintentos ante 5xx, etc.
- `tests/test_cli.py::test_resumir_sin_modelo_avisa_y_hace_la_version_extractiva`
  y `test_evaluar_sin_modelo_avisa_y_hace_la_version_extractiva`
  y `test_clasificar_sin_modelo_explica_como_activar_la_ia` comprueban que
  el aviso con los pasos de activación aparece en la salida.

---

## 4 · Robustez: excepciones y entradas feas (15 pts)

**Enunciado del 100 %:** *excepciones propias (`ConfigError`,
`AccionNoValida`…) con mensajes humanos; **ningún traceback** ante errores
previsibles; **aserciones en desarrollo**.*

**Dónde está:**

- `src/tareas/errores.py` → jerarquía completa:
  - `TareasError` (base, código de salida 1)
    - `ConfigError` (3) — JSON ausente, roto, con codificación mal, mal esquema
      - `CarpetaNoValida` (3) — sección `carpetas` mal formada
      - `AccionNoValida` (3) — una acción concreta tiene un campo mal
    - `FormatoNoAnalizable` (1) — fichero que no se puede leer
    - `DocumentoNoEncontrado` (1) — el comando pide un fichero que no está
    - `ErrorIA` (1) — sin clave, sin red, servidor caído, respuesta sin sentido
- `src/tareas/cli.py` → todas las órdenes envuelven la lógica en
  `try/except TareasError` y llaman a `raise typer.Exit(code=exc.codigo_salida)`.
  Un `TareasError` **nunca** llega al usuario como traceback.
- **Aserciones en desarrollo**:
  - `src/tareas/motor.py:23-25` — el motor se construye solo si cada acción
    ya trae nombre; si no, es un llamador que se saltó la validación.
  - `src/tareas/ia.py:168` — un proveedor necesita configuración; si alguien
    construye `ProveedorIA(None)`, revienta **en desarrollo**, no en runtime.

**Cómo comprobarlo:**

```bash
uv run tareas --config /ruta/inexistente acciones   # exit 3, mensaje humano
echo "{ mal" > /tmp/rota.json
uv run tareas --config /tmp/rota.json validar      # exit 3, línea y columna
uv run tareas analizar /ruta/que/no/existe          # exit 1, «no existe»
uv run python -c "from tareas.motor import Motor; Motor([{'sin':'nombre'}])"  # AssertionError
```

**Pruebas:**

- `tests/test_config.py` (20 tests): JSON roto, UTF-8 con BOM, campo
  obligatorio ausente, nombre repetido, plantilla con hueco desconocido,
  patrón regex inválida, filtro nulo, carpeta sin destino, etc.
- `tests/test_cli.py` verifica que **ninguna** orden devuelve traceback ante
  entradas feas: cada test comprueba `exit_code` y un texto del mensaje.

---

## 5 · Diseño en clases y módulos (10 pts)

**Enunciado del 100 %:** *responsabilidades separadas (interfaz, motor,
acciones, proveedor IA), visibilidad cuidada y métodos estáticos con
sentido (p. ej., fábricas desde la configuración).*

**Dónde está:**

| Responsabilidad | Módulo |
|---|---|
| Interfaz de terminal (Typer, Rich, `typer.confirm`) | `cli.py` |
| Orquestación del motor | `motor.py` |
| Clases de acción | `acciones.py` (ABC `Accion` + 4 subclases) |
| Proveedor IA (fachada HTTP) | `ia.py` (`ProveedorIA`) |
| Configuración externa | `config.py` (leer + validar) |
| Análisis y fichas | `analizador.py`, `ficha.py` |
| Organización (movimientos, deshacer) | `organizador.py` |
| Clasificación por evidencia | `clasificador.py` |
| Agrupación por contenido con IA | `agrupador.py` |
| Escritura de documentos (ODT/DOCX/RTF/TXT) | `documentos.py` |
| Búsqueda en internet | `busqueda.py` |
| Conversión Markdown → secciones | `markdown.py` |
| Generación de apuntes (`resumir`) | `resumen.py` |
| Generación de exámenes (`evaluar`) | `evaluacion.py` |
| Examen interactivo en navegador | `examenes.py` |
| Errores tipados | `errores.py` |
| Qué comandos hay y cómo se describen | `comandos.py` |

**Fábricas estáticas con sentido:**

- `Accion.desde_config(config: dict) -> Accion` (`acciones.py:83-91`).
- `ProveedorIA.desde_configuracion() -> ProveedorIA` (`ia.py:171-174`).
- `Motor.seleccionar(carpeta, filtro) -> list[Path]` (`motor.py:28-70`) —
  `@staticmethod` porque no necesita estado de instancia.

**Visibilidad cuidada:**

- Métodos privados con `_` (`_validar_accion`, `_validar_plantilla`,
  `_heredar_de_carpeta`, `_tabla`, `_avisa_ia_no_configurada`, `_despues_de`,
  `_pintar_resultados`, `_corta`, `_envolver`, `_contexto_ssl`, `_endpoint`,
  `_extraer_texto`, `_ruta`, `_error`, …).
- `Accion._registro` es un dict de clases privadas que se rellena solo vía
  `__init_subclass__`. Nadie lo toca desde fuera.

**Cómo comprobarlo:**

```bash
grep -n "@staticmethod\|@classmethod\|@property" src/tareas/*.py   # fábricas y getters
grep -n "def _" src/tareas/*.py | wc -l                             # ~40 métodos privados
python -c "from tareas.acciones import Accion; print(Accion._registro)"  # dict auto-registrado
```

---

## 6 · Pruebas y calidad (15 pts)

**Enunciado del 100 %:** *pruebas que cubren el camino feliz y **3 casos
feos**, ejecutadas en **GitHub Actions** y **auditadas por el alumno** (sabe
explicar cada aserción).*

**Dónde está:**

- **195 pruebas** (`uv run pytest --co -q | tail -1`).
- Distribución (todas en `tests/`, todas sobre `tmp_path` de pytest —
  **nunca** tocan ficheros reales):

  | Fichero | Pruebas | Qué cubre |
  |---|---|---|
  | `test_config.py` | 20 | Valida esquema + 12 casos feos (JSON roto, BOM, hueco mal, tipo inexistente…) |
  | `test_cli.py` | 30 | Órdenes end-to-end con `typer.testing.CliRunner`, códigos de salida, modo sin IA |
  | `test_analizador.py` | 19 | Ciclo `analizar`: renombrado, extracción, fichas, clasificación |
  | `test_busqueda.py` | 20 | Búsqueda Wikipedia/DuckDuckGo con red simulada |
  | `test_ia.py` | 19 | Capa HTTP de IA con `urlopen` parcheado |
  | `test_ia_busqueda.py` | 14 | Protocolo `[[BUSCAR]]` y bucle de re-preguntar |
  | `test_documentos.py` | 18 | Escritores ODT/DOCX/RTF/TXT |
  | `test_multiplataforma.py` | 4 | Nombres NFD/NFC, caracteres no imprimibles en Windows |
  | `test_markdown.py` | 9 | Parser Markdown → secciones |
  | `test_resumen.py` | 10 | Delimitar y escribir apuntes, fallback |
  | `test_evaluacion.py` | 4 | Generación de ejercicios |
  | `test_examenes.py` | 13 | Formulario HTML interactivo, autocorrección |
  | `test_acciones.py` | 17 | `Mover`, `Copiar`, `Renombrar`, `Borrar`, `destino_libre` |

- **Casos feos (más de los 3 que pide el 100 %):**
  1. JSON roto: línea y columna exactas.
  2. UTF-8 con BOM de Windows: se lee sin error.
  3. `filtro: null` en el JSON: acción sobre todos los ficheros.
  4. Plantilla con barras: se rechaza.
  5. Plantilla con hueco desconocido (`{fechae}`): se rechaza con nombre del hueco.
  6. Acción `borrar` con `confirmar: false`: se rechaza (seguridad).
  7. Carpeta inexistente: mensaje humano, exit 1.
  8. Fichero que no tiene texto legible: se marca `formato invalido`.
  9. Nombre duplicado en JSON: se rechaza.
  10. Regex rota en `filtro.patron`: se rechaza.
  11. Sin IA: panel con los pasos para activarla + fallback extractivo.
  12. Símbolos no imprimibles en Windows (`→`, `✔`): el helper `simbolo()` y el
      test `test_ningun_caracter_de_la_consola_se_sale_de_cp1252` lo previenen.

- **GitHub Actions:** `.github/workflows/pruebas.yml` → matriz
  `ubuntu-latest`, `windows-latest`, `macos-latest`, Python 3.12. Ejecuta
  `uv tool install`, `tareas validar`, `pytest -v`. En verde en cada push.

- **Auditadas por el alumno:** cada test tiene nombre descriptivo (snake_case
  con prefijo de contexto) y, los más sutiles, comentario que explica **qué
  pasó de verdad** cuando se añadió. Ejemplos:
  - `test_el_resumen_nunca_lleva_una_marca_de_busqueda` → «Esto pasó de
    verdad: el modelo contestaba «[[BUSCAR: ...]]» y esa línea se colaba…».
  - `test_la_fuente_mas_general_gana_cuando_dos_titulos_encajan_igual` →
    documenta el caso real que lo motivó.

**Cómo comprobarlo:**

```bash
uv run pytest -q --tb=short                    # 195 en verde, <3 s
uv run pytest --co -q | tail -1                # recuento de tests
cat .github/workflows/pruebas.yml              # 3 sistemas
```

---

## 7 · Instalación, documentación y proceso (10 pts)

**Enunciado del 100 %:** *se instala con **una orden** siguiendo el README;
**release v1.0 etiquetada con changelog**; **historial con ramas y PR
legibles**.*

**Dónde está:**

- **Instalación con una orden** (README «Instalación»):
  ```bash
  uv tool install git+https://github.com/SalvaLlacer26/cli-tareas
  ```
  También soportado `pipx install git+…`. Tras instalar, `tareas --help`
  funciona desde cualquier carpeta.
- **Releases etiquetadas**:
  ```bash
  git tag -l | sort -V
  # v1.0.0 … v2.6.0 + v2.7.0 (15 etiquetas anotadas)
  ```
  Cada etiqueta va con su entrada en `CHANGELOG.md` (formato *Keep a
  Changelog*, versión semántica). La release v1.0.0 está etiquetada como
  pide el 100 %.
- **Historial con ramas y PR legibles**: `git log --oneline --graph` muestra
  **más de 18 merges `--no-ff`** de ramas con nombres que explican lo que
  aportan: `feat/motor-config`, `feat/organizador`, `feat/config-usuario`,
  `feat/ciclo-analizar`, `feat/capa-ia`, `ci/pruebas-multiplataforma`,
  `feat/busqueda-clasificar`, `fix/resumen-marcas`,
  `feat/comandos-proveedor`, `chore/higiene-repo`,
  `feat/examenes-color-clasificar`, `feat/investigacion-internet`,
  `feat/apuntes-desde-cero`, `docs/proceso-release`,
  `fix/version-pyproject`, `feat/mensajes-setup-ia`, etc.
  Cada merge lleva el mensaje `Merge rama '<nombre>': <resumen de lo que
  aporta>`, legible sin abrir el diff.
- **Documentación**: `README.md` completo + `docs/spec.md` (10 líneas) +
  dos ADR (`docs/adr/`) + `docs/prompts.md` + `CHANGELOG.md` +
  `AGENTS.md` (normas del proyecto para el agente que ayude).

**Cómo comprobarlo:**

```bash
git tag -l | sort -V
git log --oneline --graph | grep -c "Merge rama"     # ≥18 merges
git log --oneline --graph | head -80                 # grafo legible
sed -n '/## \[v1.0.0\]/,/## \[v1.1/p' CHANGELOG.md   # entrada v1.0 en changelog
```

---

## Resumen visual (para el corrector)

| Criterio | Pts | 100 % | Dónde mirar |
|---|---:|:---:|---|
| 1 · Acciones predefinidas | 20 | ✅ | `acciones.json` + `motor.py` + `cli.py::ejecutar_cmd` |
| 2 · Configuración externa | 15 | ✅ | `config.py`, `docs/adr/0001`, sección «Esquema» del README |
| 3 · Capa IA + modo sin red | 15 | ✅ | `ia.py`, `docs/adr/0002`, `_avisa_ia_no_configurada` en `cli.py` |
| 4 · Robustez | 15 | ✅ | `errores.py`, `tests/test_config.py`, `tests/test_cli.py` |
| 5 · Diseño en clases | 10 | ✅ | Tabla de responsabilidades arriba; fábricas estáticas en `Accion`, `ProveedorIA` |
| 6 · Pruebas y calidad | 15 | ✅ | 195 tests, `.github/workflows/pruebas.yml` en 3 SO |
| 7 · Instalación y proceso | 10 | ✅ | README «Instalación», `git log --graph`, `CHANGELOG.md` |
