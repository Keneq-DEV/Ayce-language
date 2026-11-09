"""ayce — Intérprete del lenguaje ayce v0.4.1."""

from .lexer import Lexer
from .parser import Parser
from .interpreter import Interpreter
from .errors import AyceError

__version__ = "0.4.1"


def run_source(source: str, filename: str = "<stdin>"):
    """Ejecuta código ayce desde un string."""
    # Quitar BOM UTF-8 si está presente (común en Windows)
    if source and source[0] == "\ufeff":
        source = source[1:]
    lexer = Lexer(source, filename=filename)
    tokens = lexer.tokenize()
    parser = Parser(tokens, filename=filename)
    program = parser.parse()
    interp = Interpreter(filename=filename)
    interp.run(program)


def run_file(path: str):
    """Ejecuta un archivo .ayce."""
    # utf-8-sig elimina automáticamente el BOM si está presente
    with open(path, "r", encoding="utf-8-sig") as f:
        source = f.read()
    run_source(source, filename=path)
