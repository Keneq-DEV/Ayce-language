"""ayce — Intérprete del lenguaje ayce v0.5.1."""

from .lexer import Lexer
from .parser import Parser
from .interpreter import Interpreter
from .errors import AyceError

__version__ = "0.5.1"


def run_source(source: str, filename: str = "<stdin>", import_paths: list = None):
    """Ejecuta código ayce desde un string."""
    # Quitar BOM UTF-8 si está presente (común en Windows)
    if source and source[0] == "\ufeff":
        source = source[1:]
    lexer = Lexer(source, filename=filename)
    tokens = lexer.tokenize()
    parser = Parser(tokens, filename=filename)
    program = parser.parse()
    interp = Interpreter(filename=filename, import_paths=import_paths)
    interp.run(program)


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
