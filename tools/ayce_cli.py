#!/usr/bin/env python3
"""
ayce_cli.py — CLI wrapper del SDK de ayce.

Permite ejecutar archivos .ayce sin instalar el SDK como paquete.
Añade `sdk/` al sys.path en runtime y delega al `__main__.py` del paquete.

Uso:
    python3 tools/ayce_cli.py archivo.ayce
    python3 tools/ayce_cli.py --version
    python3 tools/ayce_cli.py --help

Equivalente, tras `pip install -e sdk/`:
    ayce archivo.ayce
    python3 -m ayce archivo.ayce
"""

import sys
import os

# Resolver rutas absolutas
HERE = os.path.dirname(os.path.abspath(__file__))
SDK_DIR = os.path.join(HERE, "..", "sdk")

# Añadir el SDK al path para que `import ayce` funcione
if SDK_DIR not in sys.path:
    sys.path.insert(0, SDK_DIR)

from ayce import run_file, __version__
from ayce.errors import AyceError


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        print(f"ayce v{__version__} — Intérprete de referencia")
        print("")
        print("Uso:")
        print("  python3 tools/ayce_cli.py <archivo.ayce>")
        print("  python3 tools/ayce_cli.py --version")
        print("")
        print("Tras instalar el SDK (pip install -e sdk/):")
        print("  ayce <archivo.ayce>")
        print("  python3 -m ayce <archivo.ayce>")
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
