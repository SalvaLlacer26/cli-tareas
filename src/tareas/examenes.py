"""El modo de pruebas interactivo: un examen en HTML que corrige la IA.

«tareas formulario_evaluar» prepara los mismos ejercicios que «evaluar» pero los
presenta como un formulario en el navegador: preguntas tipo test con
botones de opción, apartados de desarrollo y de cálculo con su hueco para
escribir, y un botón de «Enviar respuestas».

Al enviar, una **página servida en local** (`127.0.0.1`, nunca sale a
internet) corrige el tipo test comparando respuestas y pide a la IA que
corrija las preguntas escritas. La clave del modelo sigue viviendo en el
.env: el navegador no la ve ni la necesita.
"""

from __future__ import annotations

import html
import json
import threading
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .errores import ErrorIA

#: Tipos de pregunta admitidos.
TEST = "test"
DESARROLLO = "desarrollo"
CALCULO = "calculo"

#: Cómo se le pide la batería estructurada.
SISTEMA = (
    "Eres un profesor que prepara exámenes interactivos para estudiantes de "
    "1º de DAM. Respondes SOLO con un array JSON válido, sin explicaciones "
    "ni marcas de código."
)

#: Instrucciones para el modelo cuando corrige las respuestas escritas.
SISTEMA_CORRECCION = (
    "Eres un profesor corrigiendo exámenes. Respondes SOLO con un array JSON "
    "válido, sin explicaciones fuera del JSON."
)

#: Lo mínimo de texto que se le enseña al modelo del documento.
MINIMO_CONTENIDO = 40


@dataclass
class Pregunta:
    """Una pregunta del examen interactivo."""

    numero: int
    tipo: str
    enunciado: str
    opciones: list[str] = field(default_factory=list)
    #: Para el tipo test, la letra correcta («a», «b»…); para el resto, la
    #: solución o las pautas que espera el profesor.
    solucion: str = ""


def _extraer_json(texto: str) -> list[dict]:
    """Sacar el primer array JSON de la respuesta del modelo.

    Los modelos a veces envuelven el JSON en ```json … ``` o añaden una
    frase antes; se busca el primer «[» y su «]» pareja.
    """
    inicio = texto.find("[")
    while inicio != -1:
        profundidad = 0
        for indice in range(inicio, len(texto)):
            if texto[indice] == "[":
                profundidad += 1
            elif texto[indice] == "]":
                profundidad -= 1
                if profundidad == 0:
                    try:
                        datos = json.loads(texto[inicio : indice + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(datos, list):
                        return datos
                    break
        inicio = texto.find("[", inicio + 1)
    raise ErrorIA("el modelo no ha devuelto el JSON de preguntas")


def pedir_bateria(ficha, contexto_extra: str = "") -> list[Pregunta]:
    """La batería de ejercicios en JSON estructurado, lista para el formulario.

    El tipo test lleva sus cuatro alternativas reales y la letra correcta;
    las preguntas escritas llevan las pautas de corrección. Con todo eso el
    formulario puede corregir en local el test y pasarle a la IA solo lo que
    el alumno ha escrito.
    """
    from .evaluacion import MINIMO_PREGUNTAS, TEMPERATURA_EXAMEN, _variacion
    from .ia import pedir_con_busqueda

    contenido = ficha.contenido.strip()[:12000]
    if not contenido:
        raise ErrorIA("el documento no tiene texto con el que preparar ejercicios")

    peticion = (
        "Prepara un EXAMEN sobre el TEMA al que apuntan estos apuntes, pensado "
        "para un formulario interactivo. **El documento es solo la referencia del "
        "tema: el examen se hace sobre la teoría real, no sobre lo que pone en el "
        "PDF.**\n\n"
        f"{_variacion()}\n\n"
        "INVESTIGA antes de preguntar: para cada concepto que vayas a preguntar, "
        "pide su teoría en internet con una línea [[BUSCAR: consulta]] y termina tu "
        "turno; te devolveré varias fuentes (enciclopedia y web) para que elijas. "
        "Puedes pedir varias búsquedas en el mismo turno.\n\n"
        "Cuando tengas la teoría, devuelve SOLO un array JSON con esta forma exacta:\n"
        '[\n'
        '  {"tipo": "test", "enunciado": "...", "opciones": ["...", "...", '
        '"...", "..."], "respuesta": "b"},\n'
        '  {"tipo": "desarrollo", "enunciado": "...", '
        '"solucion": "pautas de corrección"},\n'
        '  {"tipo": "calculo", "enunciado": "...", "solucion": "resultado y '
        'procedimiento"}\n'
        ']\n\n'
        "Reglas:\n"
        f"- MÍNIMO {MINIMO_PREGUNTAS} preguntas en total: al menos 5 o 6 de tipo "
        f"test y el resto repartidas entre desarrollo y cálculo, según lo que dé "
        f"el tema; un tema teórico no lleva cálculo.\n"
        "- Las preguntas de tipo test llevan CUATRO alternativas plausibles "
        "y «respuesta» con la letra correcta (a, b, c o d).\n"
        "- Los enunciados se entienden solos, sin depender del documento.\n"
        "- Pregunta la TEORÍA del tema (la que has investigado), de forma que un "
        "alumno que la haya estudiado pueda aprobar; no cosas que solo se saben "
        "por el PDF.\n"
        "- Escribe en el idioma del documento.\n"
    )
    if contexto_extra:
        peticion += (
            "\nAPUNTES del mismo tema (los escribió antes la IA, investigando la "
            "teoría): alíñate con ellos, el examen debe poder responderse "
            "estudiándolos:\n"
            f"{contexto_extra[:8000]}\n"
        )
    peticion += (
        f"\nRecuerda: primero INVESTIGA con [[BUSCAR: consulta]] y termina tu turno "
        f"hasta tener la teoría; solo entonces devuelve el JSON.\n\n"
        f"--- APUNTES (referencia del tema) ---\n{contenido}"
    )

    respuesta, _fuentes = pedir_con_busqueda(
        SISTEMA, peticion, temperatura=TEMPERATURA_EXAMEN, maximo_consultas=6
    )
    datos = _extraer_json(respuesta)

    preguntas: list[Pregunta] = []
    for elemento in datos:
        if not isinstance(elemento, dict):
            continue
        tipo = str(elemento.get("tipo", "")).strip().lower()
        enunciado = str(elemento.get("enunciado", "")).strip()
        if not enunciado:
            continue
        if tipo == TEST:
            opciones = [str(o).strip() for o in elemento.get("opciones", [])]
            respuesta_correcta = str(elemento.get("respuesta", "")).strip().lower()
            if len(opciones) != 4 or not all(opciones):
                continue
            if respuesta_correcta not in "abcd" or len(respuesta_correcta) != 1:
                continue
            preguntas.append(
                Pregunta(0, TEST, enunciado, opciones, respuesta_correcta)
            )
        elif tipo in (DESARROLLO, CALCULO):
            preguntas.append(
                Pregunta(
                    0,
                    tipo,
                    enunciado,
                    solucion=str(elemento.get("solucion", "")).strip(),
                )
            )

    if not any(p.tipo == TEST for p in preguntas) or len(preguntas) < MINIMO_PREGUNTAS:
        raise ErrorIA("el modelo no ha devuelto una batería utilizable")

    for numero, pregunta in enumerate(preguntas, start=1):
        pregunta.numero = numero
    return preguntas


def bateria_extractiva(ficha) -> list[Pregunta]:
    """La batería sin IA: desarrollo y cálculo sacados del propio texto.

    Sin modelo no hay alternativas plausibles que inventar, así que no se
    generan preguntas tipo test y las escritas se corrigen contra el texto
    del documento, no con IA.
    """
    import random

    from .evaluacion import RE_FORMULA, _apartados, _definiciones
    from .resumen import _limpiar

    preguntas: list[Pregunta] = []
    numero = 0
    texto = _limpiar(ficha.contenido)

    # Se baraja la materia prima: así, sin modelo, dos pasadas seguidas sobre
    # el mismo documento tampoco dan el mismo examen.
    apartados = _apartados(texto)
    random.shuffle(apartados)
    definiciones = _definiciones(texto)
    random.shuffle(definiciones)

    for apartado in apartados[:6]:
        numero += 1
        preguntas.append(
            Pregunta(
                numero,
                DESARROLLO,
                f"Explica con tus palabras lo que trata el apartado «{apartado}» "
                "y da un ejemplo.",
                solucion=f"Lo que cuente el apartado «{apartado}» del documento.",
            )
        )
    for definicion in definiciones[:5]:
        numero += 1
        preguntas.append(
            Pregunta(
                numero,
                DESARROLLO,
                f"¿Qué significa o qué expresa esta idea del documento? «{definicion}»",
                solucion=definicion,
            )
        )
    formulas = [
        linea.strip()
        for linea in texto.splitlines()
        if RE_FORMULA.search(linea) and len(linea.strip()) > 12
    ]
    random.shuffle(formulas)
    for formula in formulas[:4]:
        numero += 1
        preguntas.append(
            Pregunta(
                numero,
                CALCULO,
                f"Aplica y resuelve dejando el procedimiento: «{formula}».",
                solucion=f"El resultado de despejar en «{formula}».",
            )
        )
    if not preguntas:
        raise ErrorIA("el documento no da para preparar ejercicios sin modelo")
    return preguntas


# ------------------------------------------------------------- el formulario

_CSS = """
body{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;
padding:0 1rem;background:#f4f5f7;color:#222}
h1{color:#1a4d8f}
.pregunta{background:#fff;border-radius:10px;padding:1rem 1.2rem;
margin-bottom:1rem;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.etiqueta{display:inline-block;font-size:.75rem;font-weight:bold;
text-transform:uppercase;color:#fff;background:#1a4d8f;border-radius:4px;
padding:1px 8px;margin-bottom:.5rem}
.opcion{display:block;margin:.3rem 0;padding:.4rem .6rem;border:1px solid #dde;
border-radius:6px;cursor:pointer}
.opcion:hover{background:#eef3fb}
textarea{width:100%;min-height:90px;border:1px solid #ccd;border-radius:6px;
padding:.5rem;font:inherit}
button{background:#1a4d8f;color:#fff;border:0;border-radius:8px;
padding:.7rem 1.6rem;font-size:1rem;cursor:pointer}
button:hover{background:#163f75}
.correcta{border-left:6px solid #2e7d32}
.incorrecta{border-left:6px solid #c62828}
.parcial{border-left:6px solid #f9a825}
.sinia{border-left:6px solid #999}
.veredicto{font-weight:bold}
.respuesta-alumno{background:#f7f7f2;border-radius:6px;padding:.4rem .6rem;
margin:.4rem 0;white-space:pre-wrap}
.pista{color:#666;font-size:.9rem}
"""


def _etiqueta(tipo: str) -> str:
    return {"test": "Tipo test", "desarrollo": "Desarrollo", "calculo": "Cálculo"}[tipo]


def construir_pagina(titulo: str, preguntas: list[Pregunta], con_ia: bool) -> str:
    """El examen como formulario: radios para el test, huecos para escribir."""
    bloques: list[str] = []
    for pregunta in preguntas:
        nombre = f"q{pregunta.numero}"
        bloque = [
            '<div class="pregunta">',
            f'<span class="etiqueta">{_etiqueta(pregunta.tipo)}</span>',
            f"<p><b>{pregunta.numero}.</b> {html.escape(pregunta.enunciado)}</p>",
        ]
        if pregunta.tipo == TEST:
            for letra, opcion in zip("abcd", pregunta.opciones):
                bloque.append(
                    f'<label class="opcion"><input type="radio" name="{nombre}" '
                    f'value="{letra}"> <b>{letra})</b> {html.escape(opcion)}</label>'
                )
        else:
            bloque.append(
                f'<textarea name="{nombre}" '
                'placeholder="Escribe aquí tu respuesta…"></textarea>'
            )
        bloque.append("</div>")
        bloques.append("\n".join(bloque))

    aviso = "" if con_ia else (
        '<p class="pista">Este examen se ha preparado sin IA: la corrección '
        "automática solo cubre lo que el propio documento permite comprobar.</p>"
    )
    return (
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        f"<title>{html.escape(titulo)}</title><style>{_CSS}</style></head><body>"
        f"<h1>{html.escape(titulo)}</h1>{aviso}"
        + "\n".join(bloques)
        + """
<p><button onclick="enviar()">Enviar respuestas</button></p>
<p class="pista">El examen funciona en tu propio equipo: al enviar, corrige
aquí mismo y, si hay modelo configurado, la IA revisa lo escrito.</p>
<script>
async function enviar(){
  const datos={};
  document.querySelectorAll("input[type=radio]:checked").forEach(
    e=>{datos[e.name]=e.value;});
  document.querySelectorAll("textarea").forEach(
    e=>{if(e.value.trim())datos[e.name]=e.value.trim();});
  const r=await fetch("/corregir",{method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({respuestas:datos})});
  document.documentElement.innerHTML=await r.text();
}
</script></body></html>"""
    )


def _corregir_escritas_con_ia(
    escritas: list[Pregunta], respuestas: dict[str, str]
) -> dict[str, tuple[str, str]]:
    """La IA corrige las preguntas escritas de una sola vez.

    Devuelve {nombre: (veredicto, comentario)}. Si el modelo falla, dict
    vacío: quien llama decide cómo enseñar ese caso.
    """
    from .ia import pedir

    peticion = (
        "Corrige estas respuestas de un examen. Para cada una, di si es "
        "CORRECTA, PARCIAL o INCORRECTA y da un comentario breve (una o dos "
        "frases) en español.\n"
        "Responde SOLO con un array JSON:\n"
        '[{"id":"q1","veredicto":"CORRECTA","comentario":"..."}]\n\n'
        "--- PREGUNTAS Y SOLUCIONES ESPERADAS ---\n"
    )
    for pregunta in escritas:
        peticion += (
            f"\n[id q{pregunta.numero}] {pregunta.enunciado}\n"
            f"Solución esperada: {pregunta.solucion or 'la del documento'}\n"
            f"Respuesta del alumno: {respuestas.get(f'q{pregunta.numero}', '(sin responder)')}\n"
        )
    try:
        respuesta = pedir(SISTEMA_CORRECCION, peticion)
        datos = _extraer_json(respuesta)
    except ErrorIA:
        return {}

    corregidas: dict[str, tuple[str, str]] = {}
    for elemento in datos:
        if not isinstance(elemento, dict):
            continue
        identificador = str(elemento.get("id", "")).strip()
        veredicto = str(elemento.get("veredicto", "")).strip().upper()
        comentario = str(elemento.get("comentario", "")).strip()
        if identificador.startswith("q") and veredicto in (
            "CORRECTA",
            "PARCIAL",
            "INCORRECTA",
        ):
            corregidas[identificador] = (veredicto, comentario)
    return corregidas


def construir_correccion(
    titulo: str,
    preguntas: list[Pregunta],
    respuestas: dict[str, str],
    con_ia: bool,
    ruta_documento: Path | None = None,
) -> str:
    """La página de resultados: veredicto y comentario por pregunta."""
    escritas = [p for p in preguntas if p.tipo != TEST]
    corregidas = (
        _corregir_escritas_con_ia(escritas, respuestas) if (con_ia and escritas) else {}
    )

    aciertos = 0
    test_total = 0
    bloques: list[str] = []
    for pregunta in preguntas:
        nombre = f"q{pregunta.numero}"
        dada = respuestas.get(nombre, "")
        if pregunta.tipo == TEST:
            test_total += 1
            acertada = bool(dada) and dada == pregunta.solucion
            aciertos += 1 if acertada else 0
            veredicto = "CORRECTA" if acertada else ("SIN RESPONDER" if not dada else "INCORRECTA")
            detalle = (
                f"Tu respuesta: {dada})" if dada else "No la respondiste."
            )
            if not acertada:
                detalle += f" La correcta era la {pregunta.solucion})."
            clase = "correcta" if acertada else "incorrecta"
        else:
            veredicto, detalle = corregidas.get(nombre, ("SIN CORRIGIR", ""))
            if veredicto == "SIN CORRIGIR":
                detalle = (
                    "Sin IA no se corrige lo escrito: compáralo con las pautas "
                    "del documento."
                    if not con_ia
                    else "El modelo no ha podido corregir esta pregunta."
                )
            clase = {
                "CORRECTA": "correcta",
                "PARCIAL": "parcial",
                "INCORRECTA": "incorrecta",
            }.get(veredicto, "sinia")

        bloque = [
            f'<div class="pregunta {clase}">',
            f'<span class="etiqueta">{_etiqueta(pregunta.tipo)}</span>',
            f"<p><b>{pregunta.numero}.</b> {html.escape(pregunta.enunciado)}</p>",
            f'<p class="veredicto">{veredicto}</p>',
        ]
        if dada and pregunta.tipo != TEST:
            bloque.append(
                f'<div class="respuesta-alumno">{html.escape(dada)}</div>'
            )
        if detalle:
            bloque.append(f'<p class="pista">{html.escape(detalle)}</p>')
        bloque.append("</div>")
        bloques.append("\n".join(bloque))

    nota = (
        f"Nota del tipo test: <b>{aciertos} de {test_total}</b>."
        if test_total
        else ""
    )
    volver = (
        "<p><button onclick=\"location.reload()\">Volver al examen</button></p>"
    )
    return (
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        f"<title>Corrección · {html.escape(titulo)}</title>"
        f"<style>{_CSS}</style></head><body>"
        f"<h1>Corrección de {html.escape(titulo)}</h1>"
        f"<p>{nota}</p>" + "\n".join(bloques) + volver + "</body></html>"
    )


# ------------------------------------------------------- el servidor local


def crear_servidor(
    titulo: str, preguntas: list[Pregunta], con_ia: bool, ruta_documento: Path | None = None
) -> tuple[ThreadingHTTPServer, str]:
    """Arranca el servidor local del examen y devuelve (servidor, URL).

    Solo escucha en 127.0.0.1: el examen no se expone a la red. La llamada
    bloqueante al modelo ocurre dentro del hilo del servidor, nunca aquí.
    """
    pagina = construir_pagina(titulo, preguntas, con_ia)

    class Manejador(BaseHTTPRequestHandler):
        def _responder(self, cuerpo: str) -> None:
            datos = cuerpo.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def do_GET(self) -> None:  # el nombre lo impone http.server
            self._responder(pagina)

        def do_POST(self) -> None:  # el nombre lo impone http.server
            try:
                largo = int(self.headers.get("Content-Length", "0"))
                cuerpo = json.loads(self.rfile.read(largo).decode("utf-8"))
                respuestas = {
                    str(clave): str(valor)
                    for clave, valor in (cuerpo.get("respuestas") or {}).items()
                }
            except (ValueError, json.JSONDecodeError):
                respuestas = {}
            self._responder(
                construir_correccion(
                    titulo, preguntas, respuestas, con_ia, ruta_documento
                )
            )

        def log_message(self, *argumentos) -> None:  # silencioso por diseño
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    url = f"http://127.0.0.1:{servidor.server_address[1]}/"
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, url


def abrir_navegador(url: str) -> bool:
    """Intenta abrir el navegador; si no puede, que el usuario copie la URL."""
    try:
        return webbrowser.open(url)
    except Exception:  # noqa: BLE001 - abrir el navegador es un extra
        return False
