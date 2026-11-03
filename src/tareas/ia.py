"""La capa de IA: llamar a un modelo para resumir y para preparar ejercicios.

El modelo se llama por una API compatible con OpenAI (la de los modelos del
centro, la de OpenCode Go, o un Ollama en local). La configuración se lee de
tres sitios, por orden:

1. Las **variables de entorno**: ``TAREAS_IA_URL``, ``TAREAS_IA_KEY``,
   ``TAREAS_MODELO`` y, si hace falta, ``TAREAS_IA_CA``.
2. El fichero **.env** de la carpeta desde la que se lanza la orden.
3. El fichero **.env** de la configuración del usuario.

La clave **nunca** se escribe en el repo: el ``.env`` está en el ``.gitignore``
desde el primer commit y hay un ``.env.example`` que explica qué poner.

Si no hay clave, o no hay red, o el modelo falla, esta módulo **no revienta**:
levanta un ``ErrorIA`` con un mensaje de una línea, y la CLI lo enseña y sigue
con la versión sin IA.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_dir

from .busqueda import Fuente
from .errores import ErrorIA, TareasError

#: Variables de entorno que se leen.
VAR_URL = "TAREAS_IA_URL"
VAR_CLAVE = "TAREAS_IA_KEY"
VAR_MODELO = "TAREAS_MODELO"
VAR_CA = "TAREAS_IA_CA"

#: Modelo por defecto si no se indica otro.
MODELO_POR_DEFECTO = "qwen3.8-flash-next"

#: Cuántos caracteres del documento se le envían al modelo.
MAXIMO_CARACTERES = 24000

#: Cuánto se espera de respuesta, en segundos. Los modelos del centro tardan
#: bastante con documentos largos, así que el margen es amplio.
TIEMPO_ESPERA = 600

#: Cuántos tokens se piden como máximo.
TOKENS_MAXIMOS = 3000

#: Variable para cambiar el tiempo de espera.
VAR_TIEMPO = "TAREAS_IA_TIMEOUT"


@dataclass
class ConfiguracionIA:
    """De dónde sale la configuración del modelo."""

    url: str = ""
    clave: str = ""
    modelo: str = MODELO_POR_DEFECTO
    ca: str = ""
    tiempo: int = TIEMPO_ESPERA


def ruta_de_usuario() -> Path:
    """La carpeta de configuración del usuario."""
    return Path(user_config_dir("tareas"))


def leer_dotenv(ruta: Path) -> dict[str, str]:
    """Lee un fichero .env sencillo: ``CLAVE=valor`` por línea.

    Se ignoran los comentarios (#), las líneas en blanco y las comillas que
    rodeen el valor. No sustituye a python-dotenv, pero evita una dependencia
    para cuatro líneas.
    """
    valores: dict[str, str] = {}
    if not ruta.is_file():
        return valores
    try:
        texto = ruta.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return valores

    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        if clave:
            valores[clave] = valor
    return valores


def configuracion() -> ConfiguracionIA:
    """Junta la configuración de las variables de entorno y de los .env."""
    valores: dict[str, str] = {}

    for ruta in (Path.cwd() / ".env", ruta_de_usuario() / ".env"):
        for clave, valor in leer_dotenv(ruta).items():
            valores.setdefault(clave, valor)

    # Las variables de entorno del proceso mandan sobre los ficheros.
    for clave in (VAR_URL, VAR_CLAVE, VAR_MODELO, VAR_CA, VAR_TIEMPO):
        if os.environ.get(clave):
            valores[clave] = os.environ[clave]

    tiempo = TIEMPO_ESPERA
    if valores.get(VAR_TIEMPO):
        try:
            tiempo = int(valores[VAR_TIEMPO])
        except ValueError:
            tiempo = TIEMPO_ESPERA

    return ConfiguracionIA(
        url=valores.get(VAR_URL, "").strip(),
        clave=valores.get(VAR_CLAVE, "").strip(),
        modelo=valores.get(VAR_MODELO, "").strip() or MODELO_POR_DEFECTO,
        ca=valores.get(VAR_CA, "").strip(),
        tiempo=tiempo,
    )


def disponible() -> bool:
    """Si se puede usar el modelo ahora mismo."""
    config = configuracion()
    return bool(config.url and config.clave)


def motivo_de_no_disponible() -> str:
    """Por qué no se puede usar el modelo, en una línea."""
    config = configuracion()
    if not config.url:
        return f"falta la variable {VAR_URL} (la dirección del servidor de modelos)"
    if not config.clave:
        return f"falta la variable {VAR_CLAVE} (la clave del modelo)"
    return ""


def _contexto_ssl(config: ConfiguracionIA) -> ssl.SSLContext:
    """El contexto SSL, con el certificado del centro si hace falta."""
    if not config.ca:
        return ssl.create_default_context()
    ruta = Path(config.ca).expanduser()
    if not ruta.is_file():
        return ssl.create_default_context()
    try:
        return ssl.create_default_context(cafile=str(ruta))
    except OSError:
        return ssl.create_default_context()


def _endpoint(config: ConfiguracionIA, ruta: str) -> str:
    """Construye la URL completa de la petición."""
    base = config.url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/{ruta}"
    return f"{base}/v1/{ruta}"


def pedir(
    sistema: str,
    usuario: str,
    contenido: str = "",
    temperatura: float = 0.3,
) -> str:
    """Le pide una respuesta al modelo y devuelve el texto.

    Lanza ErrorIA con un mensaje de una línea si algo falla: sin clave, sin
    red, con un error del servidor o con una respuesta que no se entiende.
    """
    config = configuracion()
    if not config.url or not config.clave:
        raise ErrorIA(f"no se puede usar el modelo: {motivo_de_no_disponible()}")

    cuerpo = {
        "model": config.modelo,
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario if usuario else contenido},
        ],
        "max_tokens": TOKENS_MAXIMOS,
        "temperature": temperatura,
    }

    peticion = urllib.request.Request(
        _endpoint(config, "chat/completions"),
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.clave}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            peticion, timeout=config.tiempo, context=_contexto_ssl(config)
        ) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ErrorIA(f"el servidor de modelos respondió con un error ({exc.code})") from exc
    except urllib.error.URLError as exc:
        raise ErrorIA(f"no se puede contactar con el servidor de modelos: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ErrorIA("el servidor de modelos no ha contestado a tiempo") from exc
    except OSError as exc:
        raise ErrorIA(f"no se puede contactar con el servidor de modelos: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ErrorIA("el servidor de modelos ha contestado algo que no es JSON") from exc

    return _extraer_texto(datos)


def _extraer_texto(datos: dict) -> str:
    """Saca el texto de la respuesta del modelo."""
    if not isinstance(datos, dict):
        raise ErrorIA("el servidor de modelos ha contestado algo inesperado")

    # Formato de chat completions (compatible con OpenAI).
    opciones = datos.get("choices")
    if isinstance(opciones, list) and opciones:
        mensaje = opciones[0].get("message") or {}
        contenido = mensaje.get("content")
        if isinstance(contenido, str) and contenido.strip():
            return contenido.strip()
        if isinstance(contenido, list):
            partes = [
                parte.get("text", "")
                for parte in contenido
                if isinstance(parte, dict)
            ]
            unido = "".join(partes).strip()
            if unido:
                return unido

    # Formato de respuestas (some providers).
    salida = datos.get("output")
    if isinstance(salida, list):
        partes = []
        for elemento in salida:
            for contenido in elemento.get("content", []) or []:
                if isinstance(contenido, dict) and contenido.get("text"):
                    partes.append(contenido["text"])
        if partes:
            return "\n".join(partes).strip()

    raise ErrorIA("el servidor de modelos no ha devuelto ningún texto")


#: Lo que escribe el modelo cuando quiere que se busque algo en internet.
RE_BUSQUEDA = re.compile(r"\[\[\s*BUSCAR\s*:\s*(.+?)\s*\]\]", re.IGNORECASE)


def buscar_en_la_respuesta(respuesta: str) -> list[str]:
    """Las consultas que el modelo pide buscar."""
    consultas = []
    for encontrada in RE_BUSQUEDA.findall(respuesta):
        consulta = encontrada.strip().strip('"').strip("'")
        if consulta and consulta not in consultas:
            consultas.append(consulta)
    return consultas


def pedir_con_busqueda(
    sistema: str,
    usuario: str,
    maximo_consultas: int = 3,
) -> tuple[str, list[Fuente]]:
    """Le pide una respuesta al modelo y, si lo pide, busca en internet.

    El modelo tiene un protocolo: si necesita información que no está en lo
    que le han dado, escribe una línea con la forma::

        [[BUSCAR: consulta]]

    y termina su turno. Entonces se busca la consulta, se le pasan los
    resultados y se le vuelve a preguntar. Así el modelo decide **él
    mismo** si el documento es demasiado escueto y hay que completarlo.

    Devuelve la respuesta final y las fuentes que se han usado.
    """
    from .busqueda import buscar, como_texto

    mensajes: list[dict[str, str]] = [
        {"role": "system", "content": sistema},
        {"role": "user", "content": usuario},
    ]
    fuentes: list[Fuente] = []
    vistas: set[str] = set()

    for _ in range(maximo_consultas + 1):
        respuesta = pedir_con_historial(sistema, mensajes)
        consultas = buscar_en_la_respuesta(respuesta)

        if not consultas:
            return respuesta, fuentes

        for consulta in consultas:
            for fuente in buscar(consulta):
                if fuente.url in vistas:
                    continue
                vistas.add(fuente.url)
                fuentes.append(fuente)

        if not fuentes:
            # Se ha intentado buscar y no ha salido nada: se sigue con lo que
            # hay, para no quedarse esperando.
            return respuesta, fuentes

        mensajes.append({"role": "assistant", "content": respuesta})
        mensajes.append(
            {
                "role": "user",
                "content": (
                    "RESULTADOS DE LA BÚSQUEDA EN INTERNET:\n\n"
                    f"{como_texto(fuentes)}\n\n"
                    "Continúa con la tarea usando esta información. No la repitas "
                    "entera: úsala para completar lo que faltaba. Si te falta algo "
                    "más, pídelo otra vez con [[BUSCAR: consulta]]; si ya tienes "
                    "suficiente, escribe la respuesta final."
                ),
            }
        )

    return respuesta, fuentes


def pedir_con_historial(sistema: str, mensajes: list[dict[str, str]]) -> str:
    """Pide una respuesta teniendo en cuenta el historial de la conversación."""
    config = configuracion()
    if not config.url or not config.clave:
        raise ErrorIA(f"no se puede usar el modelo: {motivo_de_no_disponible()}")

    cuerpo = {
        "model": config.modelo,
        "messages": mensajes,
        "max_tokens": TOKENS_MAXIMOS,
        "temperature": 0.3,
    }

    peticion = urllib.request.Request(
        _endpoint(config, "chat/completions"),
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.clave}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            peticion, timeout=config.tiempo, context=_contexto_ssl(config)
        ) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ErrorIA(f"el servidor de modelos respondió con un error ({exc.code})") from exc
    except urllib.error.URLError as exc:
        raise ErrorIA(f"no se puede contactar con el servidor de modelos: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ErrorIA("el servidor de modelos no ha contestado a tiempo") from exc
    except OSError as exc:
        raise ErrorIA(f"no se puede contactar con el servidor de modelos: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ErrorIA("el servidor de modelos ha contestado algo que no es JSON") from exc

    return _extraer_texto(datos)
