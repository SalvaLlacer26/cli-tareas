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


def _pedir(url: str) -> dict | None:
    """Pide una URL y devuelve el JSON, o None si algo falla."""
    peticion = urllib.request.Request(
        url,
        headers={
            "User-Agent": "tareas-cli/1.0 (organizador de apuntes; uso educativo)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA) as respuesta:
            return json.loads(respuesta.read().decode("utf-8", errors="ignore"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None
    except json.JSONDecodeError:
        return None


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

    paginas = datos.get("query", {}).get("search", [])
    if not paginas:
        return []

    titulos = [p["title"] for p in paginas if p.get("title")]
    if not titulos:
        return []

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
    datos = _pedir(f"{base}?{extracts_url}")
    if not datos:
        return []

    fuentes: list[Fuente] = []
    for pagina in datos.get("query", {}).get("pages", {}).values():
        fragmento = (pagina.get("extract") or "").strip()
        if len(fragmento) < MINIMO_FRAGMENTO:
            continue
        titulo = pagina.get("title", "")
        fuentes.append(
            Fuente(
                titulo=titulo,
                url=f"https://{idioma}.wikipedia.org/wiki/{urllib.parse.quote(titulo.replace(' ', '_'))}",
                fragmento=fragmento[:MAXIMO_FRAGMENTO],
                origen=f"wikipedia-{idioma}",
            )
        )
    return fuentes


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


def buscar(consulta: str, limite: int = 3) -> list[Fuente]:
    """Busca información en internet.

    Devuelve una lista de fuentes (puede estar vacía). Nunca lanza: si no hay
    red, simplemente no hay resultados.
    """
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

    return fuentes[:limite]


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
