#!/usr/bin/env python3
"""
ayce_repl.py — REPL interactivo para ayce.

Permite escribir código ayce línea a línea y ver el resultado en tiempo real.
Las sentencias `task` y `var` declaradas en el REPL persisten entre líneas.

Uso:
    python3 tools/ayce_repl.py

Comandos especiales:
    :help     mostrar ayuda
    :clear    limpiar el entorno
    :quit     salir (también Ctrl+D o Ctrl+C)
"""

import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SDK_DIR = os.path.join(HERE, "..", "sdk")
if SDK_DIR not in sys.path:
    sys.path.insert(0, SDK_DIR)

from ayce.lexer import Lexer
from ayce.parser import Parser
from ayce.interpreter import Interpreter
from ayce.errors import AyceError
from ayce import __version__


def main():
    interp = Interpreter(filename="<repl>")
    print(f"ayce v{__version__} — REPL interactivo")
    print("Escribe :help para ayuda, :quit para salir.")
    print()

    buffer = []
    while True:
        try:
            prompt = "ayce> " if not buffer else "  ...> "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if line.strip() == ":quit":
            break
        if line.strip() == ":help":
            print("Comandos: :help, :clear, :quit")
            print("Escribe código ayce. Las tareas y variables persisten entre líneas.")
            continue
        if line.strip() == ":clear":
            interp = Interpreter(filename="<repl>")
            buffer = []
            print("(entorno reiniciado)")
            continue

        buffer.append(line)
        source = "\n".join(buffer)

        # Intentar parsear y ejecutar
        try:
            lexer = Lexer(source, filename="<repl>")
            tokens = lexer.tokenize()
            parser = Parser(tokens, filename="<repl>")
            program = parser.parse()
            # Ejecutar
            # Primera pasada: declarar tasks nuevas
            for stmt in program.stmts:
                from ayce.ast_nodes import TaskDecl
                from ayce.interpreter import AyceTask
                from ayce.ast_nodes import TaskType
                if isinstance(stmt, TaskDecl):
                    task = AyceTask(stmt, interp.global_env)
                    interp.global_env.declare(stmt.name, task, TaskType(), is_const=True)
            for stmt in program.stmts:
                from ayce.ast_nodes import TaskDecl
                if not isinstance(stmt, TaskDecl):
                    interp.exec_stmt(stmt, interp.global_env)
            buffer = []
        except AyceError as e:
            # Si es "se esperaba X pero se encontró newline" probablemente es línea incompleta
            msg = str(e)
            if "Se esperaba" in msg and ("NEWLINE" in msg or "'}'" in msg or "')'" in msg):
                # Línea probablemente incompleta, seguir leyendo
                continue
            print(f"{e}", file=sys.stderr)
            buffer = []
        except Exception as e:
            print(f"Error inesperado: {e}", file=sys.stderr)
            buffer = []

    print("¡Hasta luego!")


if __name__ == "__main__":
    main()
