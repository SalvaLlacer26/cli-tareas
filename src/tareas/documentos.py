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
"""

from __future__ import annotations

import platform
import zipfile
from dataclasses import dataclass
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
    """

    titulo: str
    lineas: list[str]
    nivel: int = 1


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


def escribir_documento(ruta: Path, titulo: str, secciones: list[Seccion]) -> Path:
    """Escribe un documento con el formato que toque en este sistema."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    extension = ruta.suffix.lower() or formato_preferido()
    ruta = ruta.with_suffix(extension)

    if extension == ODT:
        _escribir_odt(ruta, titulo, secciones)
    elif extension == DOCX:
        _escribir_docx(ruta, titulo, secciones)
    elif extension == RTF:
        ruta.write_text(_a_rtf(titulo, secciones), encoding="utf-8")
    else:
        ruta.write_text(_a_texto(titulo, secciones), encoding="utf-8")
    return ruta


# ----------------------------------------------------------------- texto


def _a_texto(titulo: str, secciones: list[Seccion]) -> str:
    """El documento en texto plano, con tabuladores para las tablas."""
    lineas = [titulo, "=" * len(titulo), ""]
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
    """Escapa los caracteres que el RTF usa para sus propios comandos."""
    replacements = {
        "\\": "\\\\",
        "{": "\\{",
        "}": "\\}",
        "\t": "\\tab ",
        "\n": "\\line ",
    }
    for caracter, sustituto in replacements.items():
        texto = texto.replace(caracter, sustituto)
    return texto


def _a_rtf(titulo: str, secciones: list[Seccion]) -> str:
    """El documento en RTF, con títulos en negrita y tablas con tabuladores."""
    partes = [
        r"{\rtf1\ansi\ansicpg1252\deff0",
        r"{\fonttbl{\f0\fswiss Calibri;}}",
        r"\f0\fs22 ",
        r"{\b\fs32 " + _escapar_rtf(titulo) + r"\b0\par",
        r"\par ",
    ]
    for seccion in secciones:
        if seccion.titulo:
            tamano = 26 if seccion.nivel <= 1 else 24
            sangria = "" if seccion.nivel <= 1 else r"\li360 "
            partes.append(sangria + r"{\b\fs" + str(tamano) + " " + _escapar_rtf(seccion.titulo) + r"\b0\par")
            partes.append(r"\par ")
        for linea in seccion.lineas:
            for texto, negrita in partes_de(linea):
                if negrita:
                    partes.append(r"{\b " + _escapar_rtf(texto) + r"\b0}")
                else:
                    partes.append(_escapar_rtf(texto))
            partes.append(r"\par ")
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
        if seccion.titulo:
            estilo = "Heading_20_1" if seccion.nivel <= 1 else "Heading_20_2"
            cuerpo.append(_p_odt(seccion.titulo, estilo))
        sangria = seccion.nivel > 1
        for linea in seccion.lineas:
            cuerpo.append(_p_odt_rich(linea, sangria))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'office:version="1.2">'
        "<office:body><office:text>"
        + "".join(cuerpo)
        + "</office:text></office:body></office:document-content>"
    )


_STYLES_ODT = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<office:document-styles '
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
    'office:version="1.2"><office:styles>'
    '<style:style style:name="Standard" style:family="paragraph"/>'
    '<style:style style:name="Title" style:family="paragraph">'
    '<style:text-properties fo:font-size="20pt" fo:font-weight="bold" '
    'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"/>'
    "</style:style>"
    '<style:style style:name="Heading_20_1" style:family="paragraph">'
    '<style:paragraph-properties fo:margin-top="0.3cm"/>'
    '<style:text-properties fo:font-size="14pt" fo:font-weight="bold" '
    'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"/>'
    "</style:style>"
    '<style:style style:name="Heading_20_2" style:family="paragraph">'
    '<style:paragraph-properties fo:margin-top="0.2cm" fo:margin-left="0.4cm"/>'
    '<style:text-properties fo:font-size="12pt" fo:font-weight="bold" '
    'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"/>'
    "</style:style>"
    '<style:style style:name="Negrita" style:family="text">'
    '<style:text-properties fo:font-weight="bold" '
    'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"/>'
    "</style:style>"
    '<style:style style:name="Sangria" style:family="paragraph">'
    '<style:paragraph-properties fo:margin-left="0.4cm"/>'
    "</style:style>"
    "</office:styles></office:document-styles>"
)


def _escribir_odt(ruta: Path, titulo: str, secciones: list[Seccion]) -> None:
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
        paquete.writestr("styles.xml", _STYLES_ODT)


# ------------------------------------------------------------------ word


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


def _a_document_xml(titulo: str, secciones: list[Seccion]) -> str:
    """El contenido del documento de Word."""
    cuerpo = [_p_docx(titulo, "Title")]
    for seccion in secciones:
        if seccion.titulo:
            estilo = "Heading1" if seccion.nivel <= 1 else "Heading2"
            cuerpo.append(_p_docx(seccion.titulo, estilo))
        sangria = seccion.nivel > 1
        for linea in seccion.lineas:
            cuerpo.append(_p_docx_rich(linea, sangria))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
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
    "</Types>"
)

_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    "</Relationships>"
)

_RELS_DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
    'Target="styles.xml"/>'
    "</Relationships>"
)

_STYLES_DOCX = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
    '<w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
    '<w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
    '<w:pPr><w:ind w:left="360"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
    "</w:styles>"
)


def _escribir_docx(ruta: Path, titulo: str, secciones: list[Seccion]) -> None:
    """Escribe un .docx: es un ZIP con cuatro cosas dentro."""
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as paquete:
        paquete.writestr("[Content_Types].xml", _CONTENT_TYPES)
        paquete.writestr("_rels/.rels", _RELS)
        paquete.writestr("word/_rels/document.xml.rels", _RELS_DOCUMENT)
        paquete.writestr("word/document.xml", _a_document_xml(titulo, secciones))
        paquete.writestr("word/styles.xml", _STYLES_DOCX)
