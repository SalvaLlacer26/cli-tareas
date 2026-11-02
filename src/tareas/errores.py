"""Excepciones propias de la herramienta.

Toda la jerarquía hereda de TareasError, así que la CLI puede capturar un
único tipo y usar su ``codigo_salida`` para terminar. Así ningún error
previsible llega al usuario como una traza de Python.
"""

from __future__ import annotations


class TareasError(Exception):
    """Base de todos los errores previsibles de la herramienta."""

    codigo_salida = 1


class ConfigError(TareasError):
    """El fichero de configuración no existe, no es JSON o no cumple el esquema."""

    codigo_salida = 3


class CarpetaNoValida(ConfigError):
    """La sección «carpetas» del fichero de configuración está mal.

    Es un error de configuración, así que sale con código 3, como los demás.
    """

    def __init__(self, carpeta: str, campo: str, motivo: str) -> None:
        super().__init__(f"Carpeta «{carpeta}», campo «{campo}»: {motivo}")
        self.carpeta = carpeta
        self.campo = campo
        self.motivo = motivo


class AccionNoValida(ConfigError):
    """Una acción concreta tiene un campo mal: dice cuál y por qué."""

    def __init__(self, accion: str, campo: str, motivo: str) -> None:
        super().__init__(f"Acción «{accion}», campo «{campo}»: {motivo}")
        self.accion = accion
        self.campo = campo
        self.motivo = motivo


class FormatoNoAnalizable(TareasError):
    """El formato del fichero no se puede analizar: no hay forma de leerlo."""

    codigo_salida = 1


class DocumentoNoEncontrado(TareasError):
    """No se ha encontrado el fichero o la ficha que el comando necesita."""

    codigo_salida = 1


class ErrorIA(TareasError):
    """No se ha podido usar el modelo de IA.

    El mensaje es de una línea y explica el motivo (falta la clave, no hay
    red, el servidor ha contestado un error). La CLI lo enseña y sigue
    funcionando con lo que no necesita IA.
    """

    codigo_salida = 1
