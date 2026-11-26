"""Buscar en internet sin claves ni servicios de pago.

Se combinan varias fuentes para que quien resume o prepara un examen pueda
elegir la mejor, no solo la enciclopedia: la **API de Wikipedia** (abierta, sin
clave, texto plano con su URL) y los **resultados de la web** de DuckDuckGo en
modo *lite* (documentación, blogs técnicos, apuntes…). El «Instant Answer» de
DuckDuckGo queda como complemento.

Si no hay red, o un servicio responde con un error o cambia de formato, esa
fuente devuelve una lista vacía y se sigue con las demás. **Nunca revienta.**
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

#: Cuánto se espera de cada petición, en segundos.
TIEMPO_ESPERA = 20

#: Cuántos caracteres se guardan de cada fragmento.
MAXIMO_FRAGMENTO = 2000

#: Un artículo más corto que esto se considera un stub y se descarta.
MINIMO_FRAGMENTO = 250

#: Un fragmento de la web es más corto que un artículo: con menos de esto no
#: sirve para estudiar.
MINIMO_WEB = 80

#: Idiomas en los que se busca, por orden.
IDIOMAS = ("es", "en")

#: El navegador que se finge al pedir páginas: algunos servidores bloquean a
#: quien no se identifica.
USER_AGENT = "tareas-cli/1.0 (organizador de apuntes; uso educativo)"


@dataclass
class Fuente:
    """Un resultado de búsqueda."""

    titulo: str
    url: str
    fragmento: str
    origen: str = ""


#: Pausa entre peticiones a Wikipedia: no hay que machacar el servidor.
PAUSA = 0.4

#: Cuántas veces se reintenta una petición que falla por saturación.
REINTENTOS = 3

#: Caché de peticiones: no se repite la misma dos veces.
_CACHE: dict[str, dict | None] = {}

#: Caché de las peticiones que devuelven HTML (la web), no JSON.
_CACHE_TEXTO: dict[str, str | None] = {}


def _pedir(url: str) -> dict | None:
    """Pide una URL y devuelve el JSON, o None si algo falla.

    Wikipedia con muchas peticiones seguidas empieza a devolver 403. Por eso
    se reintenta y se espera un poco entre peticiones.
    """
    if url in _CACHE:
        return _CACHE[url]

    datos = None
    for intento in range(REINTENTOS):
        if intento:
            time.sleep(PAUSA * intento)
        peticion = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA) as respuesta:
                datos = json.loads(respuesta.read().decode("utf-8", errors="ignore"))
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429, 500, 502, 503) and intento < REINTENTOS - 1:
                continue
            datos = None
            break
        except (urllib.error.URLError, TimeoutError, OSError):
            datos = None
            break
        except json.JSONDecodeError:
            datos = None
            break

    _CACHE[url] = datos
    return datos


def _pedir_texto(url: str) -> str | None:
    """Pide una URL que devuelve HTML y devuelve el texto, o None si falla.

    Es lo mismo que `_pedir` pero sin interpretar JSON: sirve para los
    buscadores de la web. Como todo aquí, si no hay red o el servidor
    responde mal, devuelve None y quien llama sigue sin resultados.
    """
    if url in _CACHE_TEXTO:
        return _CACHE_TEXTO[url]

    texto: str | None = None
    for intento in range(REINTENTOS):
        if intento:
            time.sleep(PAUSA * intento)
        peticion = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        )
        try:
            with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA) as respuesta:
                texto = respuesta.read().decode("utf-8", errors="ignore")
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429, 500, 502, 503) and intento < REINTENTOS - 1:
                continue
            texto = None
            break
        except (urllib.error.URLError, TimeoutError, OSError):
            texto = None
            break

    _CACHE_TEXTO[url] = texto
    return texto


def _wikipedia(idioma: str, consulta: str, limite: int) -> list[Fuente]:
    """Busca artículos en Wikipedia y saca un fragmento de cada uno."""
    base = f"https://{idioma}.wikipedia.org/w/api.php"
    consulta_url = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": consulta,
            "srlimit": limite,
            "format": "json",
        }
    )
    datos = _pedir(f"{base}?{consulta_url}")
    if not datos:
        return []

    resultados = datos.get("query", {}).get("search", [])
    if not resultados:
        return []

    titulos = [p["title"] for p in resultados if p.get("title")]
    if not titulos:
        return []

    time.sleep(PAUSA)

    extracts_url = urllib.parse.urlencode(
        {
            "action": "query",
            "prop": "extracts",
            "explaintext": 1,
            "exlimit": len(titulos),
            "titles": "|".join(titulos),
            "format": "json",
        }
    )
    extracts = _pedir(f"{base}?{extracts_url}")

    # Si la Wikipedia no da los artículos completos, se usa el fragmento que
    # viene en la propia búsqueda: es menos, pero es algo.
    por_titulo: dict[str, str] = {}
    if extracts:
        for pagina in extracts.get("query", {}).get("pages", {}).values():
            if pagina.get("title"):
                por_titulo[pagina["title"]] = (pagina.get("extract") or "").strip()

    fuentes: list[Fuente] = []
    for resultado in resultados:
        titulo = resultado.get("title", "")
        fragmento = por_titulo.get(titulo, "")
        if len(fragmento) < MINIMO_FRAGMENTO:
            fragmento = _snippet_a_texto(resultado.get("snippet", ""))
        if len(fragmento) < MINIMO_FRAGMENTO:
            continue
        fuentes.append(
            Fuente(
                titulo=titulo,
                url=f"https://{idioma}.wikipedia.org/wiki/{urllib.parse.quote(titulo.replace(' ', '_'))}",
                fragmento=fragmento[:MAXIMO_FRAGMENTO],
                origen=f"wikipedia-{idioma}",
            )
        )
    return fuentes


def _snippet_a_texto(snippet: str) -> str:
    """El fragmento de la búsqueda viene con etiquetas HTML: se quitan."""
    import html

    limpio = re.sub(r"<[^>]+>", "", snippet)
    return html.unescape(limpio).strip()


def _duckduckgo(consulta: str) -> list[Fuente]:
    """El «Instant Answer» de DuckDuckGo: un dato rápido con su fuente."""
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
        {"q": consulta, "format": "json", "no_html": 1, "skip_disambig": 1}
    )
    datos = _pedir(url)
    if not datos:
        return []

    fuentes: list[Fuente] = []
    resumen = (datos.get("AbstractText") or "").strip()
    if len(resumen) >= MINIMO_WEB:
        fuentes.append(
            Fuente(
                titulo=datos.get("Heading") or consulta,
                url=datos.get("AbstractURL") or "https://duckduckgo.com",
                fragmento=resumen[:MAXIMO_FRAGMENTO],
                origen="duckduckgo",
            )
        )
    return fuentes


#: Los enlaces de resultado de DuckDuckGo vienen envueltos en una redirección
#: suya («/l/?uddg=<url escapada>»). De aquí se saca la URL de verdad.
RE_UDDG = re.compile(r"[?&]uddg=([^&]+)")


def _quitar_tags(texto: str) -> str:
    """Queda el texto sin etiquetas HTML y con las entidades decodificadas."""
    import html

    limpio = re.sub(r"<[^>]+>", " ", texto)
    limpio = html.unescape(limpio)
    return " ".join(limpio.split()).strip()


def _url_del_enlace(href: str) -> str:
    """La URL real de un enlace de resultado, desmontando la redirección."""
    import html

    href = html.unescape(href)
    encontrada = RE_UDDG.search(href)
    if encontrada:
        href = urllib.parse.unquote(encontrada.group(1))
    return href.strip()


def _es_fuente_valida(url: str) -> bool:
    """Si una URL sirve como fuente (no es basura del propio buscador)."""
    if not url.startswith(("http://", "https://")):
        return False
    dominio = urllib.parse.urlparse(url).netloc.lower()
    # Se descartan las páginas internas del propio buscador.
    return "duckduckgo.com" not in dominio


def _duckduckgo_web(consulta: str, limite: int) -> list[Fuente]:
    """Resultados de la web (no solo Wikipedia) con DuckDuckGo en modo «lite».

    La versión «lite» del buscador devuelve HTML sencillo, sin JavaScript y sin
    el bloqueo anti-bots que tiene la versión normal, y además da variedad de
    fuentes (documentación, blogs técnicos, apuntes, periódicos) más allá de la
    enciclopedia. Se leen los enlaces de resultado (con su URL real, que viene
    envuelta en una redirección del buscador) y su extracto.

    Es un análisis de HTML por patrones: si el buscador cambia de marcado, no
    se encuentra nada y la búsqueda se queda solo con Wikipedia. Nunca revienta.
    """
    url = "https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({"q": consulta})
    pagina = _pedir_texto(url)
    if not pagina:
        return []

    # Cada enlace de resultado: URL (redirigida) + título.
    enlaces = list(
        re.finditer(
            r"<a\b[^>]*?href=\"([^\"]+)\"[^>]*?class=['\"]result-link['\"][^>]*>(.*?)</a>",
            pagina,
            re.S,
        )
    )

    fuentes: list[Fuente] = []
    vistas: set[str] = set()
    for numero, m in enumerate(enlaces):
        real = _url_del_enlace(m.group(1))
        if not _es_fuente_valida(real) or real in vistas:
            continue

        # El trozo hasta el siguiente enlace delata si es un resultado
        # patrocinado (publicidad) y trae el extracto del resultado.
        inicio = m.end()
        fin = enlaces[numero + 1].start() if numero + 1 < len(enlaces) else len(pagina)
        trozo = pagina[inicio:fin]
        if "Sponsored" in trozo or "result-sponsored" in trozo:
            continue

        titulo = _quitar_tags(m.group(2))
        snippet = re.search(
            r"class=['\"]result-snippet['\"][^>]*>(.*?)</td>", trozo, re.S
        )
        fragmento = _quitar_tags(snippet.group(1)) if snippet else ""
        if not titulo or len(fragmento) < MINIMO_WEB:
            continue

        vistas.add(real)
        fuentes.append(
            Fuente(
                titulo=titulo,
                url=real,
                fragmento=fragmento[:MAXIMO_FRAGMENTO],
                origen="web",
            )
        )
        if len(fuentes) >= limite:
            break
    return fuentes


#: Tokens de encabezado que no significan nada para un buscador: «Ud1.»,
#: «Tema 3», «Unidad 2»… En los apuntes de clase aparecen constantly y
#: empastran cualquier búsqueda.
RE_ENCABEZADO = re.compile(
    r"^(?:ud|unitat|unidad|tema|apuntes?|clase|cap[ií]tulo|parte|bloque)\d*\.?$",
    re.IGNORECASE,
)


def consultas_alternativas(consulta: str) -> list[str]:
    """Varias versiones de una consulta, de la más específica a la más simple.

    Un modelo suele pedir cosas como «Introducción a las bases de datos
    conceptos ficheros SGBD Alejandro Hernández Doménech», y Wikipedia no
    encuentra nada con una consulta así de larga. Además, los apuntes empiezan
    con «Ud1.» o «Tema 3», que tampoco ayudan: se prueban también quitándolos,
    y se acortan a partir de la versión sin encabezado.
    """
    limpia = " ".join(consulta.replace('"', " ").replace("'", " ").split())
    if not limpia:
        return []

    # Se quitan los encabezados tipo «Ud1.» del principio.
    palabras = limpia.split()
    while palabras and RE_ENCABEZADO.match(palabras[0]):
        palabras.pop(0)
    sin_encabezado = " ".join(palabras)

    versiones = [limpia]
    if sin_encabezado and sin_encabezado != limpia:
        versiones.append(sin_encabezado)

    for numero in (8, 6, 5, 4, 3, 2):
        if len(palabras) > numero:
            versiones.append(" ".join(palabras[:numero]))

    # Sin repetir: la primera versión que funcione es la que se usa.
    vistas: set[str] = set()
    unicas = []
    for version in versiones:
        clave = version.lower()
        if clave in vistas:
            continue
        vistas.add(clave)
        unicas.append(version)
    return unicas


def _encaja_bien(fuentes: list[Fuente], consulta: str) -> bool:
    """Si alguna fuente encaja de verdad con la consulta.

    Una consulta larga y vaga puede devolver una coincidencia que no tiene
    nada que ver («Historia del arte» para una consulta sobre bases de
    datos). Con dos o más palabras del título coincidiendo, la fuente es
    buena de verdad.
    """
    palabras = _palabras_significativas(consulta)
    for fuente in fuentes:
        titulo = fuente.titulo.lower()
        if sum(1 for palabra in palabras if _coincide(palabra, titulo)) >= 2:
            return True
    return False


def buscar(consulta: str, limite: int = 5) -> list[Fuente]:
    """Busca información en internet.

    Si la consulta es demasiado larga y no encuentra nada, se prueba con
    versiones más cortas: un modelo suele pedir «Introducción a las bases de
    datos conceptos ficheros SGBD Alejandro Hernández Doménech», y con eso no
    encuentra ni Wikipedia.

    Consulta varias fuentes a la vez (Wikipedia y la web general) para que
    quien resume pueda elegir la mejor, no solo la enciclopedia.

    Devuelve una lista de fuentes (puede estar vacía). Nunca lanza: si no hay
    red, simplemente no hay resultados.
    """
    candidatas: list[Fuente] = []
    vistas: set[str] = set()

    for version in consultas_alternativas(consulta)[:6]:
        for fuente in _buscar_version(version, limite):
            if fuente.url in vistas:
                continue
            vistas.add(fuente.url)
            candidatas.append(fuente)
        # Se para cuando ya hay algo que encaja de verdad.
        if _encaja_bien(candidatas, version):
            break

    ordenadas = _ordenar(candidatas, consulta)
    return _sin_ruido(ordenadas, consulta)[:limite]


def _sin_ruido(fuentes: list[Fuente], consulta: str) -> list[Fuente]:
    """Quita las fuentes que no tienen nada que ver con la consulta.

    Una búsqueda larga trae de todo: al buscar «bases de datos» sale la
    biografía de alguien con «datos» en el nombre. Si hay fuentes que
    comparten palabras con la consulta, las demás no aportan nada.
    """
    if not fuentes:
        return fuentes

    palabras = _palabras_significativas(consulta)
    relevantes = [
        f
        for f in fuentes
        if any(_coincide(palabra, f.titulo.lower()) for palabra in palabras)
    ]
    return relevantes or fuentes


def _palabras_significativas(consulta: str) -> list[str]:
    """Las palabras de una consulta que de verdad significan algo."""
    return re.findall(r"[a-záéíóúñü]{4,}", consulta.lower())


def _coincide(palabra: str, texto: str) -> bool:
    """Si una palabra aparece en un texto, admitiendo el plural."""
    if palabra in texto:
        return True
    return len(palabra) > 5 and palabra[:5] in texto


def _ordenar(fuentes: list[Fuente], consulta: str) -> list[Fuente]:
    """Las fuentes más relevantes primero.

    Un artículo cuyo título coincide con las palabras de la consulta es mucho
    más útil que otro que solo la menciona de pasada. Sin esto, una búsqueda
    de «bases de datos» devuelve también biografías de gente con «datos» en el
    nombre.

    Si dos títulos coinciden en lo mismo, gana el más corto: el artículo
    general («Base de datos») explica mejor el tema que uno concreto
    («Base de datos jerárquica»).
    """
    palabras = _palabras_significativas(consulta)

    def puntuacion(fuente: Fuente) -> tuple[int, int]:
        titulo = fuente.titulo.lower()
        coincidencias = sum(1 for palabra in palabras if _coincide(palabra, titulo))
        return (-coincidencias, len(titulo))

    return sorted(fuentes, key=puntuacion)


def _buscar_version(consulta: str, limite: int) -> list[Fuente]:
    """Busca con una consulta concreta, mezclando enciclopedia y web.

    Se recogen a la vez Wikipedia (en varios idiomas), el dato rápido de
    DuckDuckGo y los resultados de la web. Así quien resume tiene de dónde
    elegir, no solo el artículo enciclopédico. Después se ordenan por
    relevancia y se recortan a `limite`, dejando hueco para que entre al menos
    una fuente web si la hay.
    """
    consulta = consulta.strip()
    if not consulta:
        return []

    fuentes: list[Fuente] = []
    vistas: set[str] = set()

    def ir_anadiendo(nuevas: list[Fuente]) -> None:
        for fuente in nuevas:
            if fuente.url in vistas:
                continue
            vistas.add(fuente.url)
            fuentes.append(fuente)

    for idioma in IDIOMAS:
        ir_anadiendo(_wikipedia(idioma, consulta, limite))

    ir_anadiendo(_duckduckgo(consulta))
    web = _duckduckgo_web(consulta, limite)
    ir_anadiendo(web)

    ordenadas = _ordenar(fuentes, consulta)
    # Si la ordenación deja fuera toda la web, se mete al menos una: la idea es
    # dar opciones distintas de la Wikipedia, no quedarnos solo con ella.
    cortadas = ordenadas[:limite]
    if web and not any(f.origen == "web" for f in cortadas) and cortadas:
        mejor_web = next((f for f in ordenadas if f.origen == "web"), None)
        if mejor_web is not None:
            cortadas = cortadas[:-1] + [mejor_web]
    return cortadas


def como_texto(fuentes: list[Fuente]) -> str:
    """Las fuentes en el formato que se le pasa al modelo."""
    if not fuentes:
        return ""
    bloques = []
    for numero, fuente in enumerate(fuentes, start=1):
        bloques.append(
            f"[{numero}] {fuente.titulo}\n"
            f"URL: {fuente.url}\n"
            f"Fuente: {fuente.origen}\n"
            f"{fuente.fragmento}"
        )
    return "\n\n".join(bloques)
