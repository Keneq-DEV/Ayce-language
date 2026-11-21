"""ayce — Intérprete del lenguaje ayce v0.6.3."""

from .lexer import Lexer
from .parser import Parser
from .interpreter import Interpreter
from .errors import AyceError, AyceSyntaxError, AyceRuntimeError

__version__ = "0.6.3"


def run_source(source: str, filename: str = "<stdin>", import_paths: list = None):
    """Ejecuta código ayce desde un string."""
    import sys
    # Quitar BOM UTF-8 si está presente (común en Windows)
    if source and source[0] == "\ufeff":
        source = source[1:]
    # v0.6.2: margen de recursión de Python para que el límite lo ponga ayce
    # (contador de llamadas → OverErr capturable) y no el intérprete huésped.
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 16000))
    lexer = Lexer(source, filename=filename)
    tokens = lexer.tokenize()
    parser = Parser(tokens, filename=filename)
    try:
        program = parser.parse()
    except RecursionError:
        # v0.6.2 (I11): estructuras demasiado anidadas → error limpio, no traceback
        raise AyceSyntaxError(filename, 0, 0,
            "Programa demasiado anidado (se superó el límite de anidamiento)")
    interp = Interpreter(filename=filename, import_paths=import_paths)
    try:
        interp.run(program)
    except RecursionError:
        # Red de seguridad: si algo escapa al contador de llamadas, error limpio
        raise AyceRuntimeError(filename, 0, 0, "Recursión demasiado profunda")


def run_file(path: str, import_paths: list = None):
    """Ejecuta un archivo .ayce."""
    # utf-8-sig elimina automáticamente el BOM si está presente
    with open(path, "r", encoding="utf-8-sig") as f:
        source = f.read()
    # Por defecto, buscar módulos en el directorio del archivo
    import os
    if import_paths is None:
        import_paths = [os.path.dirname(os.path.abspath(path))]
    run_source(source, filename=path, import_paths=import_paths)
