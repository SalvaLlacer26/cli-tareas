"""Escribir documentos de texto: LibreOffice, Word, WordPad o Bloc de notas.

El formato se elige según el sistema operativo y según qué programas puede
abrir el usuario, con este orden de preferencia:

1. **LibreOffice** (.odt) — Linux
2. **Word** (.docx) — Windows y macOS
3. **WordPad** (.rtf)
4. **Bloc de notas** (.txt)

Los cuatro se generan con la biblioteca estándar: un .odt y un .docx son
ficheros ZIP con el XML dentro, y un .rtf es texto con comandos entre llaves.
No hace falta tener instalado nada para escribirlos: solo para abrirlos.

Todos los documentos salen presentados igual: los apartados van numerados
(«1.», «1.1»…), con un índice enlazado al principio para saltar a cada uno,
separación entre los párrafos y los títulos, un encabezado con la unidad a la
izquierda y la asignatura a la derecha, y el número de página al pie.
"""

from __future__ import annotations

import platform
import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path

#: Formato de LibreOffice (OpenDocument Text).
ODT = ".odt"

#: Formato de Microsoft Word (Office Open XML).
DOCX = ".docx"

#: Formato de WordPad (Rich Text Format).
RTF = ".rtf"

#: Formato de Bloc de notas (texto plano).
TXT = ".txt"

#: Orden de preferencia según el sistema operativo.
PREFERENCIAS = {
    "linux": (ODT, DOCX, RTF, TXT),
    "darwin": (DOCX, RTF, TXT),
    "win32": (DOCX, RTF, TXT),
}


@dataclass
class Seccion:
    """Un bloque del documento: un título y sus líneas.

    «nivel» es 1 para un apartado principal y 2 para uno de segundo nivel.
    Las líneas pueden llevar marcas de negrita de Markdown (**así**), que los
    escritores convierten en negrita de verdad.

    «marcador» es el nombre del enlace interno del título: lo rellena la
    numeración automática para que el índice pueda saltar aquí.
    """

    titulo: str
    lineas: list[str]
    nivel: int = 1
    marcador: str = ""


@dataclass
class Indice(Seccion):
    """El índice del documento: cada entrada es (texto, marcador destino)."""

    entradas: list[tuple[str, str]] = field(default_factory=list)


def partes_de(linea: str) -> list[tuple[str, bool]]:
    """Parte una línea en trozos, diciendo cuáles van en negrita.

    «Los **apuntes** de BBDD» ->
    [('Los ', False), ('apuntes', True), (' de BBDD', False)]
    """
    if "**" not in linea:
        return [(linea, False)]

    partes: list[tuple[str, bool]] = []
    for indice, trozo in enumerate(linea.split("**")):
        if trozo:
            partes.append((trozo, indice % 2 == 1))
    return partes or [(linea, False)]


def formato_preferido() -> str:
    """La extensión que se usa en este sistema operativo."""
    sistema = platform.system().lower()
    return PREFERENCIAS.get(sistema, (DOCX, RTF, TXT))[0]


def _numerar(secciones: list[Seccion]) -> tuple[list[Seccion], Indice | None]:
    """Numera los títulos de los apartados y construye el índice.

    Los apartados de primer nivel se numeran «1.», «2.»… y los de segundo
    «1.1», «1.2»… Las secciones sin título (las notas) se dejan igual. Si
    hay menos de dos apartados, el índice no aporta nada y no se crea.
    """
    numeradas: list[Seccion] = []
    entradas: list[tuple[str, str, int]] = []
    contador_1 = 0
    contador_2 = 0

    for numero, seccion in enumerate(secciones, start=1):
        if not seccion.titulo:
            numeradas.append(seccion)
            continue
        if seccion.nivel <= 1:
            contador_1 += 1
            contador_2 = 0
            prefijo = f"{contador_1}."
        else:
            contador_2 += 1
            prefijo = f"{contador_1}.{contador_2}"
        titulo = f"{prefijo} {seccion.titulo}"
        marcador = f"seccion{numero}"
        numeradas.append(replace(seccion, titulo=titulo, marcador=marcador))
        entradas.append((titulo, marcador, seccion.nivel))

    if len(entradas) < 2:
        return numeradas, None

    lineas = [
        f"{'   ' if nivel > 1 else ''}{texto}" for texto, _, nivel in entradas
    ]
    indice = Indice(
        titulo="Índice",
        lineas=lineas,
        entradas=[(texto, marcador) for texto, marcador, _ in entradas],
    )
    return numeradas, indice


def escribir_documento(
    ruta: Path,
    titulo: str,
    secciones: list[Seccion],
    *,
    unidad: str = "",
    asignatura: str = "",
) -> Path:
    """Escribe un documento con el formato que toque en este sistema.

    Numera los apartados, añade el índice enlazado y prepara el encabezado
    (unidad a la izquierda, asignatura a la derecha) y el pie con el número
    de página.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    extension = ruta.suffix.lower() or formato_preferido()
    ruta = ruta.with_suffix(extension)

    secciones, indice = _numerar(list(secciones))
    if indice is not None:
        # El índice va detrás de la nota inicial (si la hay) y antes del contenido.
        posicion = 1 if secciones and not secciones[0].titulo else 0
        secciones.insert(posicion, indice)

    if extension == ODT:
        _escribir_odt(ruta, titulo, secciones, unidad, asignatura)
    elif extension == DOCX:
        _escribir_docx(ruta, titulo, secciones, unidad, asignatura)
    elif extension == RTF:
        ruta.write_text(_a_rtf(titulo, secciones, unidad, asignatura), encoding="utf-8")
    else:
        ruta.write_text(_a_texto(titulo, secciones, unidad, asignatura), encoding="utf-8")
    return ruta


def _cabecera_en_texto(unidad: str, asignatura: str) -> str:
    """Las dos datos del encabezado unidos para los formatos planos."""
    return " · ".join(dato for dato in (unidad, asignatura) if dato)


# ----------------------------------------------------------------- texto


def _a_texto(titulo: str, secciones: list[Seccion], unidad: str, asignatura: str) -> str:
    """El documento en texto plano, con tabuladores para las tablas."""
    lineas = [titulo, "=" * len(titulo), ""]
    cabecera = _cabecera_en_texto(unidad, asignatura)
    if cabecera:
        lineas.extend([cabecera, ""])
    for seccion in secciones:
        if seccion.titulo:
            sangria = "" if seccion.nivel <= 1 else "  "
            lineas.append(f"{sangria}{seccion.titulo}")
            lineas.append("-" * len(f"{sangria}{seccion.titulo}"))
        lineas.extend(seccion.lineas)
        lineas.append("")
    return "\n".join(lineas)


# ------------------------------------------------------------------- rtf


def _escapar_rtf(texto: str) -> str:
    """Escapa los caracteres que el RTF usa para sus propios comandos.

    El RTF se guarda como texto cp1252: las tildes, las viñetas y los guiones
    van con su código «\\'hh», y lo que no está en ese mapa se manda como
    Unicode («\\uN?»). Si se escriben los bytes UTF-8 crudos, Word y WordPad
    lo ven de churro en Windows.
    """
    salida: list[str] = []
    for caracter in texto:
        if caracter == "\\":
            salida.append("\\\\")
        elif caracter == "{":
            salida.append("\\{")
        elif caracter == "}":
            salida.append("\\}")
        elif caracter == "\t":
            salida.append("\\tab ")
        elif caracter == "\n":
            salida.append("\\line ")
        elif ord(caracter) < 128:
            salida.append(caracter)
        else:
            try:
                codigo = caracter.encode("cp1252")
                salida.append("".join(f"\\'{byte:02x}" for byte in codigo))
            except UnicodeEncodeError:
                salida.append(f"\\u{ord(caracter)}?")
    return "".join(salida)


#: Posición del tabulador de la derecha en el encabezado, en twips
#: (A4 con márgenes de 2,5 cm).
TAB_DERECHA_RTF = 9072


def _a_rtf(titulo: str, secciones: list[Seccion], unidad: str, asignatura: str) -> str:
    """El documento en RTF, con títulos en negrita y tablas con tabuladores."""
    partes = [
        r"{\rtf1\ansi\ansicpg1252\deff0",
        r"{\fonttbl{\f0\fswiss Calibri;}}",
    ]

    # El encabezado con la unidad a la izquierda y la asignatura a la derecha.
    if unidad or asignatura:
        partes.append(
            r"{\header \pard\tx"
            + str(TAB_DERECHA_RTF)
            + " "
            + _escapar_rtf(unidad)
            + r"\tab "
            + _escapar_rtf(asignatura)
            + r"\par}"
        )

    # Y el pie con el número de página, a la derecha.
    partes.append(
        r"{\footer \pard\qr "
        + _escapar_rtf("Página ")
        + r"{\field{\*\fldinst PAGE}{\fldrslt 1}}\par}"
    )

    partes.append(r"\f0\fs22 ")
    partes.append(r"{\pard\sb240\sa240\b\fs32 " + _escapar_rtf(titulo) + r"\b0\par}")
    for seccion in secciones:
        if seccion.titulo:
            tamano = 26 if seccion.nivel <= 1 else 24
            sangria = "" if seccion.nivel <= 1 else r"\li360 "
            partes.append(
                sangria
                + r"{\pard\sb240\sa120\b\fs"
                + str(tamano)
                + " "
                + _escapar_rtf(seccion.titulo)
                + r"\b0\par}"
            )
        for linea in seccion.lineas:
            partes.append(r"{\pard\sa120 ")
            for texto, negrita in partes_de(linea):
                if negrita:
                    partes.append(r"{\b " + _escapar_rtf(texto) + r"\b0}")
                else:
                    partes.append(_escapar_rtf(texto))
            partes.append(r"\par}")
        partes.append(r"\par ")
    partes.append("}")
    return "".join(partes)


# ------------------------------------------------------------- openoffice


def _xml_escapar(texto: str) -> str:
    return (
        texto.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _p_odt(texto: str, estilo: str = "Standard") -> str:
    """Un párrafo de OpenDocument."""
    return (
        f'<text:p text:style-name="{estilo}">'
        f'{_xml_escapar(texto)}</text:p>'
    )


def _p_odt_titulo(seccion: Seccion, estilo: str) -> str:
    """Un título de apartado, con su marcador para que el índice enlace aquí."""
    interior = (
        f'<text:bookmark text:name="{seccion.marcador}"/>' if seccion.marcador else ""
    ) + _xml_escapar(seccion.titulo)
    return f'<text:p text:style-name="{estilo}">{interior}</text:p>'


def _p_odt_entrada(texto: str, marcador: str, sangria: bool) -> str:
    """Una línea del índice, enlazada con su apartado."""
    estilo = "Sangria" if sangria else "Indice"
    return (
        f'<text:p text:style-name="{estilo}">'
        f'<text:a xlink:type="simple" xlink:href="#{marcador}">'
        f"{_xml_escapar(texto)}</text:a></text:p>"
    )


def _p_odt_rich(texto: str, sangria: bool = False) -> str:
    """Un párrafo de OpenDocument con negritas dentro."""
    trozos = partes_de(texto)
    if not any(negrita for _, negrita in trozos):
        return _p_odt(texto)

    interior = "".join(
        f'<text:span text:style-name="Negrita">{_xml_escapar(trozo)}</text:span>'
        if negrita
        else _xml_escapar(trozo)
        for trozo, negrita in trozos
    )
    estilo = "Sangria" if sangria else "Standard"
    return f'<text:p text:style-name="{estilo}">{interior}</text:p>'


def _a_content_xml(titulo: str, secciones: list[Seccion]) -> str:
    """El contenido del documento de OpenDocument."""
    cuerpo = [_p_odt(titulo, "Title")]
    for seccion in secciones:
        if isinstance(seccion, Indice):
            cuerpo.append(_p_odt(seccion.titulo, "Heading_20_1"))
            for texto, marcador in seccion.entradas:
                sangria = texto.startswith("   ")
                cuerpo.append(
                    _p_odt_entrada(texto.strip(), marcador, sangria)
                )
            continue
        if seccion.titulo:
            estilo = "Heading_20_1" if seccion.nivel <= 1 else "Heading_20_2"
            cuerpo.append(_p_odt_titulo(seccion, estilo))
        sangria = seccion.nivel > 1
        for linea in seccion.lineas:
            cuerpo.append(_p_odt_rich(linea, sangria))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        'office:version="1.2">'
        "<office:body><office:text>"
        + "".join(cuerpo)
        + "</office:text></office:body></office:document-content>"
    )


def _styles_odt(unidad: str, asignatura: str) -> str:
    """Los estilos del .odt: separación entre párrafos, índice y página.

    La página lleva el encabezado con la unidad a la izquierda y la
    asignatura a la derecha (separadas por un tabulador con parada a la
    derecha) y el pie con el número de página alineado al final.
    """
    cabecera = ""
    if unidad or asignatura:
        cabecera = (
            "<style:header>"
            f'<text:p text:style-name="Cabecera">{_xml_escapar(unidad)}'
            "<text:tab/>"
            f"{_xml_escapar(asignatura)}</text:p>"
            "</style:header>"
        )
    pie = (
        "<style:footer>"
        '<text:p text:style-name="PieDePagina">Página '
        '<text:page-number text:select-page="current">1</text:page-number>'
        "</text:p>"
        "</style:footer>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-styles '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
        'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
        'office:version="1.2">'
        "<office:styles>"
        # La separación por defecto entre párrafos: es lo que evita que el
        # texto corrido quede pegado al título siguiente.
        '<style:default-style style:family="paragraph">'
        '<style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0.15cm"/>'
        "</style:default-style>"
        '<style:default-style style:family="page-number">'
        '<style:text-properties fo:font-size="10pt"/>'
        "</style:default-style>"
        # La página «Standard» la pide solo el primer párrafo del documento:
        # ponerla en todos los estilos cortaría en página en cada cambio de
        # estilo. Las demás páginas siguen heredando la del flujo.
        '<style:style style:name="Standard" style:family="paragraph"/>'
        '<style:style style:name="Title" style:family="paragraph" '
        'style:master-page-name="Standard">'
        '<style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0.5cm"/>'
        '<style:text-properties fo:font-size="20pt" fo:font-weight="bold"/>'
        "</style:style>"
        '<style:style style:name="Heading_20_1" style:family="paragraph">'
        '<style:paragraph-properties fo:margin-top="0.5cm" fo:margin-bottom="0.2cm"/>'
        '<style:text-properties fo:font-size="14pt" fo:font-weight="bold"/>'
        "</style:style>"
        '<style:style style:name="Heading_20_2" style:family="paragraph">'
        '<style:paragraph-properties fo:margin-top="0.3cm" fo:margin-bottom="0.15cm" '
        'fo:margin-left="0.4cm"/>'
        '<style:text-properties fo:font-size="12pt" fo:font-weight="bold"/>'
        "</style:style>"
        '<style:style style:name="Negrita" style:family="text">'
        '<style:text-properties fo:font-weight="bold"/>'
        "</style:style>"
        '<style:style style:name="Sangria" style:family="paragraph">'
        '<style:paragraph-properties fo:margin-left="0.4cm"/>'
        "</style:style>"
        '<style:style style:name="Indice" style:family="paragraph"/>'
        # El encabezado: tabulador con parada a la derecha de la línea de texto.
        '<style:style style:name="Cabecera" style:family="paragraph">'
        '<style:paragraph-properties>'
        '<style:tab-stops>'
        '<style:tab-stop style:position="16cm" style:type="right"/>'
        "</style:tab-stops>"
        "</style:paragraph-properties>"
        '<style:text-properties fo:font-size="10pt"/>'
        "</style:style>"
        '<style:style style:name="PieDePagina" style:family="paragraph" '
        'style:default-style="Default Page Number">'
        '<style:paragraph-properties fo:text-align="end"/>'
        "</style:style>"
        "</office:styles>"
        '<office:master-styles>'
        '<style:page-layout style:name="PLG_A4">'
        '<style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm" '
        'fo:margin-top="2.5cm" fo:margin-bottom="2cm" '
        'fo:margin-left="2.5cm" fo:margin-right="2.5cm" '
        'style:num-format="1"/>'
        "<style:header-style>"
        '<style:header-footer-properties fo:min-height="0.6cm" fo:margin-bottom="0.4cm"/>'
        "</style:header-style>"
        "<style:footer-style>"
        '<style:header-footer-properties fo:min-height="0.6cm" fo:margin-top="0.4cm"/>'
        "</style:footer-style>"
        "</style:page-layout>"
        '<style:master-page style:name="Standard" style:page-layout-name="PLG_A4">'
        + cabecera
        + pie
        + "</style:master-page>"
        "</office:master-styles>"
        "</office:document-styles>"
    )


def _escribir_odt(
    ruta: Path, titulo: str, secciones: list[Seccion], unidad: str, asignatura: str
) -> None:
    """Escribe un .odt: es un ZIP con cuatro cosas dentro."""
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as paquete:
        # El primer fichero del ZIP tiene que ser «mimetype» y sin comprimir.
        paquete.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/vnd.oasis.opendocument.text",
            compress_type=zipfile.ZIP_STORED,
        )
        paquete.writestr(
            "META-INF/manifest.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
            'manifest:version="1.2">'
            '<manifest:file-entry manifest:full-path="/" '
            'manifest:media-type="application/vnd.oasis.opendocument.text"/>'
            '<manifest:file-entry manifest:full-path="content.xml" '
            'manifest:media-type="text/xml"/>'
            '<manifest:file-entry manifest:full-path="styles.xml" '
            'manifest:media-type="text/xml"/>'
            "</manifest:manifest>",
        )
        paquete.writestr("content.xml", _a_content_xml(titulo, secciones))
        paquete.writestr("styles.xml", _styles_odt(unidad, asignatura))


# ------------------------------------------------------------------ word

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

#: Posición del tabulador de la derecha en el encabezado, en twips
#: (A4 con márgenes de 2,5 cm).
TAB_DERECHA_DOCX = 9072


def _p_docx(texto: str, estilo: str | None = None) -> str:
    """Un párrafo de Word."""
    formato = ""
    if estilo == "Title":
        formato = '<w:pPr><w:pStyle w:val="Title"/></w:pPr>'
    elif estilo == "Heading1":
        formato = '<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
    elif estilo == "Heading2":
        formato = '<w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
    return (
        "<w:p>"
        + formato
        + '<w:r><w:t xml:space="preserve">'
        + _xml_escapar(texto)
        + "</w:t></w:r></w:p>"
    )


def _p_docx_titulo(seccion: Seccion, estilo: str) -> str:
    """Un título de apartado de Word, con su marcador para el índice."""
    formato = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>'
    if seccion.marcador:
        identificador = seccion.marcador.removeprefix("seccion")
        inicio = f'<w:bookmarkStart w:id="{identificador}" w:name="{seccion.marcador}"/>'
        final = f'<w:bookmarkEnd w:id="{identificador}"/>'
    else:
        inicio = final = ""
    return (
        f"<w:p>{formato}{inicio}"
        f'<w:r><w:t xml:space="preserve">{_xml_escapar(seccion.titulo)}</w:t></w:r>'
        f"{final}</w:p>"
    )


def _p_docx_entrada(texto: str, marcador: str, sangria: bool) -> str:
    """Una línea del índice de Word, enlazada con su apartado."""
    formato = '<w:pPr><w:ind w:left="360"/></w:pPr>' if sangria else ""
    return (
        f'<w:p>{formato}<w:hyperlink w:anchor="{marcador}">'
        f'<w:r><w:t xml:space="preserve">{_xml_escapar(texto)}</w:t></w:r>'
        "</w:hyperlink></w:p>"
    )


def _p_docx_rich(texto: str, sangria: bool = False) -> str:
    """Un párrafo de Word con negritas dentro."""
    trozos = partes_de(texto)
    if not any(negrita for _, negrita in trozos):
        return _p_docx(texto)

    formato = '<w:pPr><w:ind w:left="360"/></w:pPr>' if sangria else ""
    interior = "".join(
        "<w:r><w:rPr><w:b/></w:rPr>"
        f'<w:t xml:space="preserve">{_xml_escapar(trozo)}</w:t></w:r>'
        if negrita
        else f'<w:r><w:t xml:space="preserve">{_xml_escapar(trozo)}</w:t></w:r>'
        for trozo, negrita in trozos
    )
    return f"<w:p>{formato}{interior}</w:p>"


def _sect_pr(unidad: str, asignatura: str) -> str:
    """La sección del documento: quién manda en el encabezado y el pie."""
    referencias = '<w:footerReference r:id="rId3" w:type="default"/>'
    if unidad or asignatura:
        referencias = (
            '<w:headerReference r:id="rId2" w:type="default"/>' + referencias
        )
    return (
        "<w:sectPr>"
        + referencias
        + '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" '
        'w:header="709" w:footer="709" w:gutter="0"/>'
        "</w:sectPr>"
    )


def _a_document_xml(
    titulo: str, secciones: list[Seccion], unidad: str, asignatura: str
) -> str:
    """El contenido del documento de Word."""
    cuerpo = [_p_docx(titulo, "Title")]
    for seccion in secciones:
        if isinstance(seccion, Indice):
            cuerpo.append(_p_docx(seccion.titulo, "Heading1"))
            for texto, marcador in seccion.entradas:
                cuerpo.append(
                    _p_docx_entrada(texto.strip(), marcador, texto.startswith("   "))
                )
            continue
        if seccion.titulo:
            estilo = "Heading1" if seccion.nivel <= 1 else "Heading2"
            cuerpo.append(_p_docx_titulo(seccion, estilo))
        sangria = seccion.nivel > 1
        for linea in seccion.lineas:
            cuerpo.append(_p_docx_rich(linea, sangria))
    cuerpo.append(_sect_pr(unidad, asignatura))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{NS_W}" xmlns:r="{NS_R}">'
        "<w:body>" + "".join(cuerpo) + "</w:body></w:document>"
    )


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/word/header1.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
    '<Override PartName="/word/footer1.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
    "</Types>"
)

_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    f'Type="{NS_R}/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)

_RELS_DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    f'Type="{NS_R}/styles" Target="styles.xml"/>'
    '<Relationship Id="rId2" '
    f'Type="{NS_R}/header" Target="header1.xml"/>'
    '<Relationship Id="rId3" '
    f'Type="{NS_R}/footer" Target="footer1.xml"/>'
    "</Relationships>"
)

_STYLES_DOCX = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:styles xmlns:w="{NS_W}">'
    # La separación por defecto después de cada párrafo: evita que el texto
    # corrido quede pegado al título de abajo.
    "<w:docDefaults><w:pPrDefault><w:pPr>"
    '<w:spacing w:after="160" w:line="276" w:lineRule="auto"/>'
    "</w:pPr></w:pPrDefault></w:docDefaults>"
    '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
    '<w:pPr><w:spacing w:after="240"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
    '<w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
    '<w:pPr><w:ind w:left="360"/><w:spacing w:before="160" w:after="120"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
    "</w:styles>"
)


def _header_xml(unidad: str, asignatura: str) -> str:
    """El encabezado de Word: unidad a la izquierda, asignatura a la derecha."""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:hdr xmlns:w="{NS_W}" xmlns:r="{NS_R}">'
        "<w:p><w:pPr><w:tabs>"
        f'<w:tab w:val="right" w:pos="{TAB_DERECHA_DOCX}"/>'
        "</w:tabs></w:pPr>"
        f'<w:r><w:t xml:space="preserve">{_xml_escapar(unidad)}</w:t></w:r>'
        "<w:r><w:tab/></w:r>"
        f'<w:r><w:t xml:space="preserve">{_xml_escapar(asignatura)}</w:t></w:r>'
        "</w:p></w:hdr>"
    )


#: El pie de Word con el número de página, a la derecha. El «PAGE» lo sustituye
#: el visor al abrir o imprimir el documento.
FOOTER_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:ftr xmlns:w="{NS_W}" xmlns:r="{NS_R}">'
    '<w:p><w:pPr><w:jc w:val="right"/></w:pPr>'
    '<w:r><w:t xml:space="preserve">Página </w:t></w:r>'
    '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    "<w:r><w:t>1</w:t></w:r>"
    '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    "</w:p></w:ftr>"
)


def _escribir_docx(
    ruta: Path, titulo: str, secciones: list[Seccion], unidad: str, asignatura: str
) -> None:
    """Escribe un .docx: es un ZIP con las piezas de Word dentro."""
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as paquete:
        paquete.writestr("[Content_Types].xml", _CONTENT_TYPES)
        paquete.writestr("_rels/.rels", _RELS)
        paquete.writestr("word/_rels/document.xml.rels", _RELS_DOCUMENT)
        paquete.writestr(
            "word/document.xml", _a_document_xml(titulo, secciones, unidad, asignatura)
        )
        paquete.writestr("word/styles.xml", _STYLES_DOCX)
        paquete.writestr("word/header1.xml", _header_xml(unidad, asignatura))
        paquete.writestr("word/footer1.xml", FOOTER_XML)
