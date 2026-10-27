"""Excepciones propias de la herramienta.

Toda la jerarquía hereda de TareasError, así que la CLI puede capturar un
único tipo y usar su ``codigo_salida`` para terminar. Así ningún error
previsible llega al usuario como una traza de Python.
"""


class TareasError(Exception):
    """Base de todos los errores previsibles de la herramienta."""

    codigo_salida = 1


class ConfigError(TareasError):
    """acciones.json no existe, no es JSON o no cumple el esquema."""

    codigo_salida = 3


class AccionNoValida(ConfigError):
    """Una acción concreta tiene un campo mal: dice cuál y por qué."""

    def __init__(self, accion: str, campo: str, motivo: str) -> None:
        super().__init__(f"Acción «{accion}», campo «{campo}»: {motivo}")
        self.accion = accion
        self.campo = campo
        self.motivo = motivo


class CarpetaNoValida(ConfigError):
    """La sección «carpetas» del fichero de acciones está mal.

    Es un error de configuración, así que sale con código 3, como los demás.
    """

    def __init__(self, carpeta: str, campo: str, motivo: str) -> None:
        super().__init__(f"Carpeta «{carpeta}», campo «{campo}»: {motivo}")
        self.carpeta = carpeta
        self.campo = campo
        self.motivo = motivo
