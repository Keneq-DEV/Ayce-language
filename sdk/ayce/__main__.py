"""
ayce — CLI entry point.
Uso:  python -m ayce <archivo.ayce>
      python ayce/__main__.py <archivo.ayce>
"""

import sys
import os

# Si se ejecuta como script directo, añadir el directorio padre al path
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ayce import run_file, __version__
from ayce.errors import AyceError


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        print(f"ayce v{__version__} — Intérprete de referencia")
        print("Uso:  python -m ayce <archivo.ayce>")
        print("      python -m ayce --version")
        return 0

    if argv[0] in ("-v", "--version"):
        print(f"ayce v{__version__}")
        return 0

    filename = argv[0]
    if not os.path.exists(filename):
        print(f"Error: el archivo '{filename}' no existe", file=sys.stderr)
        return 2

    try:
        run_file(filename)
    except AyceError as e:
        print(f"{e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nEjecución interrumpida", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
