"""Buscar en internet sin claves ni servicios de pago.

Se usa sobre todo la **API de Wikipedia**, que es abierta, sin clave, y da
texto plano de artículos con su URL: justo lo que hace falta para «completar»
un documento que viene esquemático. Como complemento se consulta el
«Instant Answer» de DuckDuckGo, que tampoco necesita clave.

Si no hay red, o el servicio contesta con un error, la búsqueda devuelve una
lista vacía y quien llama sigue con lo que tenía. **Nunca revienta.**
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

#: Idiomas en los que se busca, por orden.
IDIOMAS = ("es", "en")


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
                "User-Agent": "tareas-cli/1.0 (organizador de apuntes; uso educativo)",
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
    if len(resumen) >= MINIMO_FRAGMENTO:
        fuentes.append(
            Fuente(
                titulo=datos.get("Heading") or consulta,
                url=datos.get("AbstractURL") or "https://duckduckgo.com",
                fragmento=resumen[:MAXIMO_FRAGMENTO],
                origen="duckduckgo",
            )
        )
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


def buscar(consulta: str, limite: int = 3) -> list[Fuente]:
    """Busca información en internet.

    Si la consulta es demasiado larga y no encuentra nada, se prueba con
    versiones más cortas: un modelo suele pedir «Introducción a las bases de
    datos conceptos ficheros SGBD Alejandro Hernández Doménech», y con eso no
    encuentra ni Wikipedia.

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
    """
    palabras = _palabras_significativas(consulta)

    def puntuacion(fuente: Fuente) -> int:
        titulo = fuente.titulo.lower()
        return sum(1 for palabra in palabras if _coincide(palabra, titulo))

    return sorted(fuentes, key=lambda f: -puntuacion(f))


def _buscar_version(consulta: str, limite: int) -> list[Fuente]:
    """Busca con una consulta concreta, sin acortarla."""
    consulta = consulta.strip()
    if not consulta:
        return []

    fuentes: list[Fuente] = []
    vistas: set[str] = set()

    for idioma in IDIOMAS:
        for fuente in _wikipedia(idioma, consulta, limite):
            if fuente.url in vistas:
                continue
            vistas.add(fuente.url)
            fuentes.append(fuente)
        if len(fuentes) >= limite:
            break

    if len(fuentes) < limite:
        for fuente in _duckduckgo(consulta):
            if fuente.url in vistas:
                continue
            vistas.add(fuente.url)
            fuentes.append(fuente)

    return _ordenar(fuentes, consulta)[:limite]


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
