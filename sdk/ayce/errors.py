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


class RaiseSignal(Exception):
    """Señal interna para implementar `raise`. Lleva un valor de tipo Error."""
    def __init__(self, error_value):
        self.error_value = error_value


# ──────────────────────────────────────────────────────────────────────
#  Errores nativos de ayce (v0.4.1)
#  Nombres cortos, estilo Python pero compactos.
#  Cada error tiene: nombre, código, clase base.
# ──────────────────────────────────────────────────────────────────────

NATIVE_ERRORS = {
    # Jerarquía básica
    "Error":       {"code": 0,   "parent": None,       "desc": "Error base. Todos los errores heredan de éste."},
    "Excn":        {"code": 100, "parent": "Error",    "desc": "Excepción genérica de ejecución."},

    # Errores aritméticos
    "Div0":        {"code": 1,   "parent": "ArithErr", "desc": "División por cero."},
    "ZeroDivErr":  {"code": 1,   "parent": "ArithErr", "desc": "Alias de Div0."},
    "ArithErr":    {"code": 101, "parent": "Excn",     "desc": "Error aritmético genérico."},
    "FPErr":       {"code": 102, "parent": "ArithErr", "desc": "Error de coma flotante."},
    "OverErr":     {"code": 2,   "parent": "ArithErr", "desc": "Desbordamiento (recursión profunda)."},
    "RecursionErr":{"code": 2,   "parent": "ArithErr", "desc": "Alias de OverErr."},

    # Errores de acceso
    "KeyErr":      {"code": 3,   "parent": "Excn",     "desc": "Clave inexistente en diccionario."},
    "IndexErr":    {"code": 4,   "parent": "Excn",     "desc": "Índice fuera de rango en lista/tupla."},
    "AttrErr":     {"code": 5,   "parent": "Excn",     "desc": "Atributo/campo inexistente."},
    "NameErr":     {"code": 6,   "parent": "Excn",     "desc": "Nombre/variable no definido."},
    "NullErr":     {"code": 7,   "parent": "Excn",     "desc": "Acceso a valor none."},

    # Errores de tipos y valores
    "TypeErr":     {"code": 8,   "parent": "Excn",     "desc": "Operación entre tipos incompatibles."},
    "ValErr":      {"code": 9,   "parent": "Excn",     "desc": "Valor inválido (ej: int(\"abc\"))."},
    "CastErr":     {"code": 10,  "parent": "TypeErr",  "desc": "Conversión de tipo fallida."},
    "RangeErr":    {"code": 11,  "parent": "ValErr",   "desc": "Valor fuera de rango permitido."},
    "SizeErr":     {"code": 12,  "parent": "ValErr",   "desc": "Tamaño inválido."},
    "FPErr2":      {"code": 13,  "parent": "ValErr",   "desc": "Valor de coma flotante inválido."},

    # Errores de argumentos y estado
    "ArgErr":      {"code": 14,  "parent": "Excn",     "desc": "Argumento inválido."},
    "StateErr":    {"code": 15,  "parent": "Excn",     "desc": "Estado inválido."},
    "RunErr":      {"code": 16,  "parent": "Excn",     "desc": "Error genérico de ejecución."},
    "NotImplErr":  {"code": 17,  "parent": "RunErr",   "desc": "Función no implementada."},
    "AssertErr":   {"code": 18,  "parent": "RunErr",   "desc": "Aserción fallida."},
    "StopErr":     {"code": 19,  "parent": "RunErr",   "desc": "Iteración detenida."},

    # Errores de sistema
    "SysErr":      {"code": 20,  "parent": "Excn",     "desc": "Error del sistema."},
    "OSysErr":     {"code": 21,  "parent": "SysErr",   "desc": "Error del sistema operativo."},
    "IOErr":       {"code": 22,  "parent": "SysErr",   "desc": "Error de entrada/salida."},
    "FileErr":     {"code": 23,  "parent": "IOErr",    "desc": "Archivo no encontrado."},
    "PermErr":     {"code": 24,  "parent": "SysErr",   "desc": "Sin permisos."},
    "TimeErr":     {"code": 25,  "parent": "SysErr",   "desc": "Timeout."},
    "KInt":        {"code": 26,  "parent": "SysErr",   "desc": "Interrupción del usuario (Ctrl+C)."},
    "SysExitErr":  {"code": 27,  "parent": "SysErr",   "desc": "Salida del sistema."},

    # Errores de memoria
    "MemErr":      {"code": 28,  "parent": "SysErr",   "desc": "Sin memoria."},
    "MallocErr":   {"code": 29,  "parent": "MemErr",   "desc": "Asignación de memoria fallida."},
    "StackErr":    {"code": 30,  "parent": "MemErr",   "desc": "Stack overflow."},
    "HeapErr":     {"code": 31,  "parent": "MemErr",   "desc": "Heap corruption."},

    # Errores de red y conexión
    "NetErr":      {"code": 32,  "parent": "SysErr",   "desc": "Error de red genérico."},
    "ConnErr":     {"code": 33,  "parent": "NetErr",   "desc": "Conexión fallida."},
    "HTTPERR":     {"code": 34,  "parent": "NetErr",   "desc": "Error HTTP."},
    "URL":         {"code": 35,  "parent": "NetErr",   "desc": "URL inválida."},

    # Errores de datos y formato
    "ParseErr":    {"code": 36,  "parent": "Excn",     "desc": "Error de sintaxis en runtime."},
    "FmtErr":      {"code": 37,  "parent": "ParseErr", "desc": "Formato inválido (f-string mal formada)."},
    "JSONErr":     {"code": 38,  "parent": "ParseErr", "desc": "JSON inválido."},
    "XMLErr":      {"code": 39,  "parent": "ParseErr", "desc": "XML inválido."},
    "EncErr":      {"code": 40,  "parent": "ParseErr", "desc": "Error de codificación."},
    "UnicodeErr":  {"code": 41,  "parent": "EncErr",   "desc": "Error Unicode."},
    "TabErr":      {"code": 42,  "parent": "ParseErr", "desc": "Error de tabulación."},

    # Errores de módulos
    "ImportErr":   {"code": 43,  "parent": "Excn",     "desc": "Import fallido."},
    "ModErr":      {"code": 44,  "parent": "ImportErr","desc": "Módulo no encontrado."},

    # Errores de concurrencia
    "ThreadErr":   {"code": 45,  "parent": "Excn",     "desc": "Error de hilo."},
    "LockErr":     {"code": 46,  "parent": "ThreadErr","desc": "Lock/bloqueo."},
    "SyncErr":     {"code": 47,  "parent": "ThreadErr","desc": "Error de sincronización."},

    # Errores varios
    "BufErr":      {"code": 48,  "parent": "Excn",     "desc": "Error de buffer."},
    "CacheErr":    {"code": 49,  "parent": "Excn",     "desc": "Error de caché."},
    "ConfigErr":   {"code": 50,  "parent": "Excn",     "desc": "Configuración inválida."},
    "DBErr":       {"code": 51,  "parent": "Excn",     "desc": "Error de base de datos."},
    "SQLITErr":    {"code": 52,  "parent": "DBErr",    "desc": "Error SQLite."},
    "SortErr":     {"code": 53,  "parent": "Excn",     "desc": "Error de ordenamiento."},
    "HashErr":     {"code": 54,  "parent": "Excn",     "desc": "Hash inválido."},
    "IterErr":     {"code": 55,  "parent": "Excn",     "desc": "Iterador agotado."},
}


def get_error_hierarchy():
    """Devuelve la lista de nombres de errores nativos ordenada por jerarquía.
    Los padres van antes que los hijos para poder registrarlos en orden."""
    visited = set()
    order = []

    def visit(name):
        if name in visited or name not in NATIVE_ERRORS:
            return
        parent = NATIVE_ERRORS[name]["parent"]
        if parent:
            visit(parent)
        visited.add(name)
        order.append(name)

    for name in NATIVE_ERRORS:
        visit(name)
    return order


def is_native_error_name(name: str) -> bool:
    return name in NATIVE_ERRORS


def get_native_error_info(name: str):
    return NATIVE_ERRORS.get(name)

