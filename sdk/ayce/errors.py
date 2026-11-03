"""
ayce — Errores con ubicación de línea y columna.
"""

class AyceError(Exception):
    """Base de todos los errores de ayce."""
    def __init__(self, filename: str, line: int, col: int, msg: str):
        self.filename = filename
        self.line = line
        self.col = col
        self.msg = msg
        super().__init__(self._format())

    def _format(self) -> str:
        return f"{self.filename}:{self.line}:{self.col}: {self.msg}"


class AyceSyntaxError(AyceError):
    """Error léxico o sintáctico."""
    def __init__(self, filename, line, col, msg):
        super().__init__(filename, line, col, f"Error de sintaxis: {msg}")


class AyceTypeError(AyceError):
    """Error de tipos detectado en análisis semántico o en ejecución."""
    def __init__(self, filename, line, col, msg):
        super().__init__(filename, line, col, f"Error de tipos: {msg}")


class AyceRuntimeError(AyceError):
    """Error en tiempo de ejecución (índice fuera de rango, clave inexistente, etc.)."""
    def __init__(self, filename, line, col, msg):
        super().__init__(filename, line, col, f"Error en ejecución: {msg}")


class BreakSignal(Exception):
    """Señal interna para implementar `break`."""
    pass


class ContinueSignal(Exception):
    """Señal interna para implementar `continue`."""
    pass


class ReturnSignal(Exception):
    """Señal interna para implementar `return`."""
    def __init__(self, value):
        self.value = value
