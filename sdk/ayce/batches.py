"""
ayce — Batches built-in (v0.5).

Batches equivalentes a los módulos stdlib de Python, embebidos en el intérprete.
Se acceden con `require math`, `require random`, etc.

Cada batch expone tareas (AyceTask sintética) y constantes.
"""

import math as _math
import random as _random
import time as _time
import os as _os
import sys as _sys
import json as _json
from .ast_nodes import (
    TaskDecl, TaskSignature, Param, PrimitiveType, UserTypeName,
    ListType, DictType, TupleType, SetType,
    IntLit, FloatLit, StringLit, BoolLit,
)
from .errors import AyceRuntimeError, AyceTypeError


# ──────────────────────────────────────────────────────────────────────
#  AyceNativeTask — tarea implementada en Python (no en ayce)
# ──────────────────────────────────────────────────────────────────────
class AyceNativeTask:
    """Tarea nativa: implementada en Python, callable desde ayce.

    `func` recibe (interp, args, line, col) y devuelve un valor ayce."""
    def __init__(self, name, func, param_types=None, return_type=None):
        self.name = name
        self.func = func
        self.param_types = param_types or []
        self.return_type = return_type

    def __repr__(self):
        return f"<native task {self.name}>"


class AyceNativeBatch:
    """Batch nativo: contiene constantes y tareas nativas.
    Como AyceBatch pero no se carga desde archivo.
    Implementa la misma interfaz que AyceBatch (find_export, name, filename, exports)."""
    def __init__(self, name, exports):
        self.name = name
        self.filename = f"<builtin:{name}>"
        # exports: dict nombre → (value, type_node, is_const, initialized)
        self.exports = exports

    def find_export(self, name):
        if name in self.exports:
            return self.exports[name][0]
        return None

    def __repr__(self):
        return f"<builtin batch {self.name}>"


# Alias para que isinstance(target, AyceBatch) funcione también con batches built-in.
# AyceBatch está en interpreter.py; aquí lo importamos de forma diferida para evitar import circular.
def _is_batch(target):
    """Devuelve True si target es cualquier tipo de batch (built-in o cargado)."""
    from .interpreter import AyceBatch
    return isinstance(target, (AyceBatch, AyceNativeBatch))


# ──────────────────────────────────────────────────────────────────────
#  Wrappers para tipos de Python → ayce
# ──────────────────────────────────────────────────────────────────────

def _to_ayce(value):
    """Convierte un valor Python a su equivalente ayce."""
    from .interpreter import AyceList, AyceDict, AyceTuple, AyceSet
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value
    if value is None:
        return None
    if isinstance(value, list):
        return AyceList([_to_ayce(v) for v in value],
                        ListType(flexible=True))
    if isinstance(value, tuple):
        return AyceTuple([_to_ayce(v) for v in value],
                         TupleType(flexible=True))
    if isinstance(value, set):
        return AyceSet([_to_ayce(v) for v in value],
                       SetType(flexible=True))
    if isinstance(value, dict):
        pairs = [(_to_ayce(k), _to_ayce(v)) for k, v in value.items()]
        return AyceDict(pairs, DictType(flexible=True))
    return value


def _from_ayce(value):
    """Convierte un valor ayce a Python (para pasarlo a funciones nativas)."""
    from .interpreter import AyceList, AyceDict, AyceTuple, AyceSet
    if isinstance(value, (bool, int, float, str, bytes)) or value is None:
        return value
    if isinstance(value, AyceList):
        return [_from_ayce(v) for v in value.elements]
    if isinstance(value, AyceTuple):
        return tuple(_from_ayce(v) for v in value.elements)
    if isinstance(value, AyceSet):
        return [_from_ayce(v) for v in value.elements]
    if isinstance(value, AyceDict):
        return {_from_ayce(k): _from_ayce(v) for k, v in value.pairs.items()}
    return value


def _type_name(value):
    """Nombre corto del tipo para mensajes de error."""
    from .interpreter import AyceList, AyceDict, AyceTuple, AyceSet
    if isinstance(value, bool): return "bool"
    if isinstance(value, int):  return "int"
    if isinstance(value, float): return "float"
    if isinstance(value, str):  return "string"
    if isinstance(value, bytes): return "bytes"
    if value is None: return "none"
    if isinstance(value, AyceList): return "list"
    if isinstance(value, AyceDict): return "dict"
    if isinstance(value, AyceTuple): return "tuple"
    if isinstance(value, AyceSet): return "set"
    return type(value).__name__


# ──────────────────────────────────────────────────────────────────────
#  Helpers para construir batches
# ──────────────────────────────────────────────────────────────────────

def _const(value):
    """Crea una entrada de constante en el dict de exports."""
    if isinstance(value, bool):
        return (value, PrimitiveType(name="bool"), True, True)
    if isinstance(value, int):
        return (value, PrimitiveType(name="int"), True, True)
    if isinstance(value, float):
        return (value, PrimitiveType(name="float"), True, True)
    if isinstance(value, str):
        return (value, PrimitiveType(name="string"), True, True)
    return (value, None, True, True)


def _task(native_func):
    """Crea una entrada de tarea nativa en el dict de exports."""
    return (native_func, None, True, True)


def _err(line, col, msg):
    return AyceRuntimeError("<builtin>", line, col, msg)


# ──────────────────────────────────────────────────────────────────────
#  Batch: math
# ──────────────────────────────────────────────────────────────────────
def _build_math_batch():
    exports = {}

    # Constantes
    exports["pi"]   = _const(_math.pi)
    exports["e"]    = _const(_math.e)
    exports["tau"]  = _const(_math.tau)
    exports["inf"]  = _const(_math.inf)
    exports["nan"]  = _const(_math.nan)

    def _abs(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "abs requiere 1 número")
        return abs(args[0])
    exports["abs"] = _task(AyceNativeTask("abs", _abs))

    def _sign(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "sign requiere 1 número")
        x = args[0]
        if x > 0: return 1
        if x < 0: return -1
        return 0
    exports["sign"] = _task(AyceNativeTask("sign", _sign))

    def _min(interp, args, line, col):
        if not args:
            raise _err(line, col, "min requiere al menos 1 argumento")
        for a in args:
            if not isinstance(a, (int, float)):
                raise _err(line, col, f"min requiere números, se recibió {_type_name(a)}")
        return min(args)
    exports["min"] = _task(AyceNativeTask("min", _min))

    def _max(interp, args, line, col):
        if not args:
            raise _err(line, col, "max requiere al menos 1 argumento")
        for a in args:
            if not isinstance(a, (int, float)):
                raise _err(line, col, f"max requiere números, se recibió {_type_name(a)}")
        return max(args)
    exports["max"] = _task(AyceNativeTask("max", _max))

    def _floor(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "floor requiere 1 número")
        return _math.floor(args[0])
    exports["floor"] = _task(AyceNativeTask("floor", _floor))

    def _ceil(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "ceil requiere 1 número")
        return _math.ceil(args[0])
    exports["ceil"] = _task(AyceNativeTask("ceil", _ceil))

    def _trunc(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "trunc requiere 1 número")
        return _math.trunc(args[0])
    exports["trunc"] = _task(AyceNativeTask("trunc", _trunc))

    def _round(interp, args, line, col):
        if len(args) < 1 or len(args) > 2:
            raise _err(line, col, "round requiere 1 o 2 argumentos")
        x = args[0]
        n = args[1] if len(args) == 2 else 0
        if not isinstance(x, (int, float)):
            raise _err(line, col, "round: primer arg debe ser número")
        if not isinstance(n, int):
            raise _err(line, col, "round: segundo arg debe ser int")
        return round(x, n)
    exports["round"] = _task(AyceNativeTask("round", _round))

    def _sqrt(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "sqrt requiere 1 número")
        if args[0] < 0:
            raise _err(line, col, "sqrt no acepta negativos")
        return _math.sqrt(args[0])
    exports["sqrt"] = _task(AyceNativeTask("sqrt", _sqrt))

    def _cbrt(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "cbrt requiere 1 número")
        # Python 3.11+ tiene math.cbrt
        if hasattr(_math, "cbrt"):
            return _math.cbrt(args[0])
        x = args[0]
        if x < 0:
            return -((-x) ** (1/3))
        return x ** (1/3)
    exports["cbrt"] = _task(AyceNativeTask("cbrt", _cbrt))

    def _pow(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], (int, float)) \
                or not isinstance(args[1], (int, float)):
            raise _err(line, col, "pow requiere 2 números")
        return args[0] ** args[1]
    exports["pow"] = _task(AyceNativeTask("pow", _pow))

    def _exp(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "exp requiere 1 número")
        return _math.exp(args[0])
    exports["exp"] = _task(AyceNativeTask("exp", _exp))

    def _ln(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "ln requiere 1 número")
        if args[0] <= 0:
            raise _err(line, col, "ln no acepta valores <= 0")
        return _math.log(args[0])
    exports["ln"] = _task(AyceNativeTask("ln", _ln))

    def _log(interp, args, line, col):
        if len(args) < 1 or len(args) > 2:
            raise _err(line, col, "log requiere 1 o 2 argumentos")
        x = args[0]
        if len(args) == 2:
            base = args[1]
            if not isinstance(x, (int, float)) or not isinstance(base, (int, float)):
                raise _err(line, col, "log requiere números")
            return _math.log(x, base)
        if not isinstance(x, (int, float)):
            raise _err(line, col, "log requiere número")
        if x <= 0:
            raise _err(line, col, "log no acepta valores <= 0")
        return _math.log(x)
    exports["log"] = _task(AyceNativeTask("log", _log))

    def _log2(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "log2 requiere 1 número")
        return _math.log2(args[0])
    exports["log2"] = _task(AyceNativeTask("log2", _log2))

    def _log10(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "log10 requiere 1 número")
        return _math.log10(args[0])
    exports["log10"] = _task(AyceNativeTask("log10", _log10))

    def _sin(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "sin requiere 1 número")
        return _math.sin(args[0])
    exports["sin"] = _task(AyceNativeTask("sin", _sin))

    def _cos(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "cos requiere 1 número")
        return _math.cos(args[0])
    exports["cos"] = _task(AyceNativeTask("cos", _cos))

    def _tan(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "tan requiere 1 número")
        return _math.tan(args[0])
    exports["tan"] = _task(AyceNativeTask("tan", _tan))

    def _asin(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "asin requiere 1 número")
        return _math.asin(args[0])
    exports["asin"] = _task(AyceNativeTask("asin", _asin))

    def _acos(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "acos requiere 1 número")
        return _math.acos(args[0])
    exports["acos"] = _task(AyceNativeTask("acos", _acos))

    def _atan(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "atan requiere 1 número")
        return _math.atan(args[0])
    exports["atan"] = _task(AyceNativeTask("atan", _atan))

    def _atan2(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], (int, float)) \
                or not isinstance(args[1], (int, float)):
            raise _err(line, col, "atan2 requiere 2 números (y, x)")
        return _math.atan2(args[0], args[1])
    exports["atan2"] = _task(AyceNativeTask("atan2", _atan2))

    def _sinh(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "sinh requiere 1 número")
        return _math.sinh(args[0])
    exports["sinh"] = _task(AyceNativeTask("sinh", _sinh))

    def _cosh(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "cosh requiere 1 número")
        return _math.cosh(args[0])
    exports["cosh"] = _task(AyceNativeTask("cosh", _cosh))

    def _tanh(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "tanh requiere 1 número")
        return _math.tanh(args[0])
    exports["tanh"] = _task(AyceNativeTask("tanh", _tanh))

    def _hypot(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], (int, float)) \
                or not isinstance(args[1], (int, float)):
            raise _err(line, col, "hypot requiere 2 números (x, y)")
        return _math.hypot(args[0], args[1])
    exports["hypot"] = _task(AyceNativeTask("hypot", _hypot))

    def _degrees(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "degrees requiere 1 número (radianes)")
        return _math.degrees(args[0])
    exports["degrees"] = _task(AyceNativeTask("degrees", _degrees))

    def _radians(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "radians requiere 1 número (grados)")
        return _math.radians(args[0])
    exports["radians"] = _task(AyceNativeTask("radians", _radians))

    def _gcd(interp, args, line, col):
        if len(args) < 2:
            raise _err(line, col, "gcd requiere al menos 2 enteros")
        for a in args:
            if not isinstance(a, int):
                raise _err(line, col, "gcd requiere enteros")
        result = args[0]
        for a in args[1:]:
            result = _math.gcd(result, a)
        return result
    exports["gcd"] = _task(AyceNativeTask("gcd", _gcd))

    def _lcm(interp, args, line, col):
        if len(args) < 2:
            raise _err(line, col, "lcm requiere al menos 2 enteros")
        for a in args:
            if not isinstance(a, int):
                raise _err(line, col, "lcm requiere enteros")
        result = args[0]
        for a in args[1:]:
            if hasattr(_math, "lcm"):
                result = _math.lcm(result, a)
            else:
                if result == 0 or a == 0:
                    return 0
                result = abs(result * a) // _math.gcd(result, a)
        return result
    exports["lcm"] = _task(AyceNativeTask("lcm", _lcm))

    def _factorial(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], int):
            raise _err(line, col, "factorial requiere 1 int")
        if args[0] < 0:
            raise _err(line, col, "factorial no acepta negativos")
        return _math.factorial(args[0])
    exports["factorial"] = _task(AyceNativeTask("factorial", _factorial))

    def _isqrt(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], int):
            raise _err(line, col, "isqrt requiere 1 int")
        if args[0] < 0:
            raise _err(line, col, "isqrt no acepta negativos")
        return _math.isqrt(args[0])
    exports["isqrt"] = _task(AyceNativeTask("isqrt", _isqrt))

    return AyceNativeBatch("math", exports)


# ──────────────────────────────────────────────────────────────────────
#  Batch: random
# ──────────────────────────────────────────────────────────────────────
def _build_random_batch():
    exports = {}

    def _int(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], int) or not isinstance(args[1], int):
            raise _err(line, col, "random::int requiere 2 enteros (min, max)")
        if args[0] > args[1]:
            raise _err(line, col, "random::int: min no puede ser mayor que max")
        return _random.randint(args[0], args[1])
    exports["int"] = _task(AyceNativeTask("int", _int))

    def _float(interp, args, line, col):
        if len(args) == 0:
            return _random.random()
        if len(args) == 2 and isinstance(args[0], (int, float)) and isinstance(args[1], (int, float)):
            return _random.uniform(args[0], args[1])
        raise _err(line, col, "random::float requiere 0 o 2 argumentos numéricos")
    exports["float"] = _task(AyceNativeTask("float", _float))

    def _bool(interp, args, line, col):
        if len(args) != 0:
            raise _err(line, col, "random::bool no toma argumentos")
        return _random.choice([True, False])
    exports["bool"] = _task(AyceNativeTask("bool", _bool))

    def _choice(interp, args, line, col):
        from .interpreter import AyceList, AyceTuple, AyceSet
        if len(args) != 1:
            raise _err(line, col, "random::choice requiere 1 lista")
        seq = args[0]
        if isinstance(seq, AyceList):
            if not seq.elements:
                raise _err(line, col, "random::choice: lista vacía")
            return _random.choice(seq.elements)
        if isinstance(seq, AyceTuple):
            if not seq.elements:
                raise _err(line, col, "random::choice: tupla vacía")
            return _random.choice(list(seq.elements))
        if isinstance(seq, AyceSet):
            if not seq.elements:
                raise _err(line, col, "random::choice: set vacío")
            return _random.choice(seq.elements)
        if isinstance(seq, str):
            if not seq:
                raise _err(line, col, "random::choice: string vacío")
            return _random.choice(seq)
        raise _err(line, col, f"random::choice requiere lista, se recibió {_type_name(seq)}")
    exports["choice"] = _task(AyceNativeTask("choice", _choice))

    def _shuffle(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 1 or not isinstance(args[0], AyceList):
            raise _err(line, col, "random::shuffle requiere 1 lista")
        new_list = list(args[0].elements)
        _random.shuffle(new_list)
        return AyceList(new_list, args[0].type_node)
    exports["shuffle"] = _task(AyceNativeTask("shuffle", _shuffle))

    def _sample(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 2 or not isinstance(args[0], AyceList) or not isinstance(args[1], int):
            raise _err(line, col, "random::sample requiere (lista, k)")
        if args[1] < 0 or args[1] > len(args[0].elements):
            raise _err(line, col, "random::sample: k fuera de rango")
        result = _random.sample(args[0].elements, args[1])
        return AyceList(result, args[0].type_node)
    exports["sample"] = _task(AyceNativeTask("sample", _sample))

    def _seed(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], int):
            raise _err(line, col, "random::seed requiere 1 int")
        _random.seed(args[0])
        return None
    exports["seed"] = _task(AyceNativeTask("seed", _seed))

    return AyceNativeBatch("random", exports)


# ──────────────────────────────────────────────────────────────────────
#  Batch: string
# ──────────────────────────────────────────────────────────────────────
def _build_string_batch():
    exports = {}

    def _length(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "string::length requiere 1 string")
        return len(args[0])
    exports["length"] = _task(AyceNativeTask("length", _length))

    def _upper(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "string::upper requiere 1 string")
        return args[0].upper()
    exports["upper"] = _task(AyceNativeTask("upper", _upper))

    def _lower(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "string::lower requiere 1 string")
        return args[0].lower()
    exports["lower"] = _task(AyceNativeTask("lower", _lower))

    def _reverse(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "string::reverse requiere 1 string")
        return args[0][::-1]
    exports["reverse"] = _task(AyceNativeTask("reverse", _reverse))

    def _repeat(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], int):
            raise _err(line, col, "string::repeat requiere (string, n)")
        if args[1] < 0:
            raise _err(line, col, "string::repeat: n no puede ser negativo")
        return args[0] * args[1]
    exports["repeat"] = _task(AyceNativeTask("repeat", _repeat))

    def _contains(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], str):
            raise _err(line, col, "string::contains requiere 2 strings")
        return args[1] in args[0]
    exports["contains"] = _task(AyceNativeTask("contains", _contains))

    def _starts_with(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], str):
            raise _err(line, col, "string::starts_with requiere 2 strings")
        return args[0].startswith(args[1])
    exports["starts_with"] = _task(AyceNativeTask("starts_with", _starts_with))

    def _ends_with(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], str):
            raise _err(line, col, "string::ends_with requiere 2 strings")
        return args[0].endswith(args[1])
    exports["ends_with"] = _task(AyceNativeTask("ends_with", _ends_with))

    def _replace(interp, args, line, col):
        if len(args) != 3 or not all(isinstance(a, str) for a in args):
            raise _err(line, col, "string::replace requiere 3 strings (s, old, new)")
        return args[0].replace(args[1], args[2])
    exports["replace"] = _task(AyceNativeTask("replace", _replace))

    def _trim(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "string::trim requiere 1 string")
        return args[0].strip()
    exports["trim"] = _task(AyceNativeTask("trim", _trim))

    def _split(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], str):
            raise _err(line, col, "string::split requiere 2 strings (s, sep)")
        parts = args[0].split(args[1]) if args[1] else list(args[0])
        return AyceList(parts, ListType(elem=PrimitiveType(name="string")))
    exports["split"] = _task(AyceNativeTask("split", _split))

    def _join(interp, args, line, col):
        from .interpreter import AyceList, AyceTuple
        if len(args) != 2 or not isinstance(args[0], (AyceList, AyceTuple)) \
                or not isinstance(args[1], str):
            raise _err(line, col, "string::join requiere (lista, sep)")
        parts = args[0].elements
        if not all(isinstance(p, str) for p in parts):
            raise _err(line, col, "string::join: todos los elementos deben ser string")
        return args[1].join(parts)
    exports["join"] = _task(AyceNativeTask("join", _join))

    def _find(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], str):
            raise _err(line, col, "string::find requiere 2 strings")
        return args[0].find(args[1])
    exports["find"] = _task(AyceNativeTask("find", _find))

    def _slice(interp, args, line, col):
        if len(args) != 3 or not isinstance(args[0], str) \
                or not isinstance(args[1], int) or not isinstance(args[2], int):
            raise _err(line, col, "string::slice requiere (string, start, end)")
        return args[0][args[1]:args[2]]
    exports["slice"] = _task(AyceNativeTask("slice", _slice))

    def _pad_left(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], int):
            raise _err(line, col, "string::pad_left requiere (string, n)")
        return args[0].rjust(args[1])
    exports["pad_left"] = _task(AyceNativeTask("pad_left", _pad_left))

    def _pad_right(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], int):
            raise _err(line, col, "string::pad_right requiere (string, n)")
        return args[0].ljust(args[1])
    exports["pad_right"] = _task(AyceNativeTask("pad_right", _pad_right))

    def _pad_center(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], int):
            raise _err(line, col, "string::pad_center requiere (string, n)")
        return args[0].center(args[1])
    exports["pad_center"] = _task(AyceNativeTask("pad_center", _pad_center))

    def _to_int(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "string::to_int requiere 1 string")
        try:
            return int(args[0])
        except ValueError:
            raise _err(line, col, f"string::to_int: '{args[0]}' no es un int válido")
    exports["to_int"] = _task(AyceNativeTask("to_int", _to_int))

    def _to_float(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "string::to_float requiere 1 string")
        try:
            return float(args[0])
        except ValueError:
            raise _err(line, col, f"string::to_float: '{args[0]}' no es un float válido")
    exports["to_float"] = _task(AyceNativeTask("to_float", _to_float))

    return AyceNativeBatch("string", exports)


# ──────────────────────────────────────────────────────────────────────
#  Batch: list
# ──────────────────────────────────────────────────────────────────────
def _build_list_batch():
    exports = {}

    def _length(interp, args, line, col):
        from .interpreter import AyceList, AyceTuple, AyceSet
        if len(args) != 1:
            raise _err(line, col, "list::length requiere 1 argumento")
        if isinstance(args[0], (AyceList, AyceTuple, AyceSet)):
            return len(args[0].elements)
        raise _err(line, col, f"list::length requiere lista, se recibió {_type_name(args[0])}")
    exports["length"] = _task(AyceNativeTask("length", _length))

    def _sort(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 1 or not isinstance(args[0], AyceList):
            raise _err(line, col, "list::sort requiere 1 lista")
        new_list = sorted(args[0].elements, key=lambda x: (str(type(x).__name__), x))
        return AyceList(new_list, args[0].type_node)
    exports["sort"] = _task(AyceNativeTask("sort", _sort))

    def _reverse(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 1 or not isinstance(args[0], AyceList):
            raise _err(line, col, "list::reverse requiere 1 lista")
        new_list = list(reversed(args[0].elements))
        return AyceList(new_list, args[0].type_node)
    exports["reverse"] = _task(AyceNativeTask("reverse", _reverse))

    def _sum(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 1 or not isinstance(args[0], AyceList):
            raise _err(line, col, "list::sum requiere 1 lista")
        try:
            return sum(args[0].elements)
        except TypeError:
            raise _err(line, col, "list::sum: elementos no numéricos")
    exports["sum"] = _task(AyceNativeTask("sum", _sum))

    def _min(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 1 or not isinstance(args[0], AyceList):
            raise _err(line, col, "list::min requiere 1 lista")
        if not args[0].elements:
            raise _err(line, col, "list::min: lista vacía")
        return min(args[0].elements)
    exports["min"] = _task(AyceNativeTask("min", _min))

    def _max(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 1 or not isinstance(args[0], AyceList):
            raise _err(line, col, "list::max requiere 1 lista")
        if not args[0].elements:
            raise _err(line, col, "list::max: lista vacía")
        return max(args[0].elements)
    exports["max"] = _task(AyceNativeTask("max", _max))

    def _unique(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 1 or not isinstance(args[0], AyceList):
            raise _err(line, col, "list::unique requiere 1 lista")
        seen = []
        result = []
        for e in args[0].elements:
            key = repr(e)
            if key not in seen:
                seen.append(key)
                result.append(e)
        return AyceList(result, args[0].type_node)
    exports["unique"] = _task(AyceNativeTask("unique", _unique))

    def _flatten(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 1 or not isinstance(args[0], AyceList):
            raise _err(line, col, "list::flatten requiere 1 lista")
        result = []
        for e in args[0].elements:
            if isinstance(e, AyceList):
                result.extend(e.elements)
            else:
                result.append(e)
        return AyceList(result, ListType(flexible=True))
    exports["flatten"] = _task(AyceNativeTask("flatten", _flatten))

    def _chunk(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 2 or not isinstance(args[0], AyceList) or not isinstance(args[1], int):
            raise _err(line, col, "list::chunk requiere (lista, n)")
        if args[1] <= 0:
            raise _err(line, col, "list::chunk: n debe ser positivo")
        chunks = [args[0].elements[i:i+args[1]] for i in range(0, len(args[0].elements), args[1])]
        result = [AyceList(c, args[0].type_node) for c in chunks]
        return AyceList(result, ListType(flexible=True))
    exports["chunk"] = _task(AyceNativeTask("chunk", _chunk))

    def _zip(interp, args, line, col):
        from .interpreter import AyceList, AyceTuple
        if len(args) < 2:
            raise _err(line, col, "list::zip requiere al menos 2 listas")
        for a in args:
            if not isinstance(a, AyceList):
                raise _err(line, col, "list::zip: todos los argumentos deben ser listas")
        tuples = []
        min_len = min(len(a.elements) for a in args)
        for i in range(min_len):
            tuples.append(AyceTuple([a.elements[i] for a in args], TupleType(flexible=True)))
        return AyceList(tuples, ListType(flexible=True))
    exports["zip"] = _task(AyceNativeTask("zip", _zip))

    def _find(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 2 or not isinstance(args[0], AyceList):
            raise _err(line, col, "list::find requiere (lista, valor)")
        for i, e in enumerate(args[0].elements):
            if e == args[1]:
                return i
        return -1
    exports["find"] = _task(AyceNativeTask("find", _find))

    def _contains(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) != 2 or not isinstance(args[0], AyceList):
            raise _err(line, col, "list::contains requiere (lista, valor)")
        return args[1] in args[0].elements
    exports["contains"] = _task(AyceNativeTask("contains", _contains))

    def _concat(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) < 1:
            raise _err(line, col, "list::concat requiere al menos 1 lista")
        result = []
        for a in args:
            if not isinstance(a, AyceList):
                raise _err(line, col, "list::concat: todos los argumentos deben ser listas")
            result.extend(a.elements)
        return AyceList(result, ListType(flexible=True))
    exports["concat"] = _task(AyceNativeTask("concat", _concat))

    def _range(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) == 1 and isinstance(args[0], int):
            return AyceList(list(range(args[0])), ListType(elem=PrimitiveType(name="int")))
        if len(args) == 2 and isinstance(args[0], int) and isinstance(args[1], int):
            return AyceList(list(range(args[0], args[1])),
                            ListType(elem=PrimitiveType(name="int")))
        if len(args) == 3 and all(isinstance(a, int) for a in args):
            return AyceList(list(range(args[0], args[1], args[2])),
                            ListType(elem=PrimitiveType(name="int")))
        raise _err(line, col, "list::range requiere 1, 2 o 3 ints")
    exports["range"] = _task(AyceNativeTask("range", _range))

    return AyceNativeBatch("list", exports)


# ──────────────────────────────────────────────────────────────────────
#  Batch: dict
# ──────────────────────────────────────────────────────────────────────
def _build_dict_batch():
    exports = {}

    def _keys(interp, args, line, col):
        from .interpreter import AyceDict, AyceList
        if len(args) != 1 or not isinstance(args[0], AyceDict):
            raise _err(line, col, "dict::keys requiere 1 dict")
        return AyceList(list(args[0].pairs.keys()), ListType(flexible=True))
    exports["keys"] = _task(AyceNativeTask("keys", _keys))

    def _values(interp, args, line, col):
        from .interpreter import AyceDict, AyceList
        if len(args) != 1 or not isinstance(args[0], AyceDict):
            raise _err(line, col, "dict::values requiere 1 dict")
        return AyceList(list(args[0].pairs.values()), ListType(flexible=True))
    exports["values"] = _task(AyceNativeTask("values", _values))

    def _items(interp, args, line, col):
        from .interpreter import AyceDict, AyceList, AyceTuple
        if len(args) != 1 or not isinstance(args[0], AyceDict):
            raise _err(line, col, "dict::items requiere 1 dict")
        items = [AyceTuple([k, v], TupleType(flexible=True))
                 for k, v in args[0].pairs.items()]
        return AyceList(items, ListType(flexible=True))
    exports["items"] = _task(AyceNativeTask("items", _items))

    def _merge(interp, args, line, col):
        from .interpreter import AyceDict
        if len(args) != 2 or not isinstance(args[0], AyceDict) or not isinstance(args[1], AyceDict):
            raise _err(line, col, "dict::merge requiere 2 dicts")
        merged = dict(args[0].pairs)
        merged.update(args[1].pairs)
        return AyceDict(merged, args[0].type_node)
    exports["merge"] = _task(AyceNativeTask("merge", _merge))

    def _invert(interp, args, line, col):
        from .interpreter import AyceDict
        if len(args) != 1 or not isinstance(args[0], AyceDict):
            raise _err(line, col, "dict::invert requiere 1 dict")
        inverted = {}
        for k, v in args[0].pairs.items():
            inverted[v] = k
        return AyceDict(inverted, DictType(flexible=True))
    exports["invert"] = _task(AyceNativeTask("invert", _invert))

    def _has_key(interp, args, line, col):
        from .interpreter import AyceDict
        if len(args) != 2 or not isinstance(args[0], AyceDict):
            raise _err(line, col, "dict::has_key requiere (dict, clave)")
        return args[1] in args[0].pairs
    exports["has_key"] = _task(AyceNativeTask("has_key", _has_key))

    def _get_or_default(interp, args, line, col):
        from .interpreter import AyceDict
        if len(args) != 3 or not isinstance(args[0], AyceDict):
            raise _err(line, col, "dict::get_or_default requiere (dict, clave, default)")
        return args[0].pairs.get(args[1], args[2])
    exports["get_or_default"] = _task(AyceNativeTask("get_or_default", _get_or_default))

    def _length(interp, args, line, col):
        from .interpreter import AyceDict
        if len(args) != 1 or not isinstance(args[0], AyceDict):
            raise _err(line, col, "dict::length requiere 1 dict")
        return len(args[0].pairs)
    exports["length"] = _task(AyceNativeTask("length", _length))

    return AyceNativeBatch("dict", exports)


# ──────────────────────────────────────────────────────────────────────
#  Batch: io
# ──────────────────────────────────────────────────────────────────────
def _build_io_batch():
    exports = {}

    def _read_file(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "io::read_file requiere 1 string (ruta)")
        try:
            with open(args[0], "r", encoding="utf-8-sig") as f:
                return f.read()
        except FileNotFoundError:
            raise _err(line, col, f"io::read_file: archivo no encontrado: {args[0]}")
        except IOError as e:
            raise _err(line, col, f"io::read_file: error de lectura: {e}")
    exports["read_file"] = _task(AyceNativeTask("read_file", _read_file))

    def _write_file(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], str):
            raise _err(line, col, "io::write_file requiere (ruta, contenido)")
        try:
            with open(args[0], "w", encoding="utf-8") as f:
                f.write(args[1])
            return None
        except IOError as e:
            raise _err(line, col, f"io::write_file: error de escritura: {e}")
    exports["write_file"] = _task(AyceNativeTask("write_file", _write_file))

    def _append_file(interp, args, line, col):
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], str):
            raise _err(line, col, "io::append_file requiere (ruta, contenido)")
        try:
            with open(args[0], "a", encoding="utf-8") as f:
                f.write(args[1])
            return None
        except IOError as e:
            raise _err(line, col, f"io::append_file: error de escritura: {e}")
    exports["append_file"] = _task(AyceNativeTask("append_file", _append_file))

    def _file_exists(interp, args, line, col):
        import os
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "io::file_exists requiere 1 string (ruta)")
        return os.path.exists(args[0])
    exports["file_exists"] = _task(AyceNativeTask("file_exists", _file_exists))

    def _print(interp, args, line, col):
        parts = []
        for a in args:
            parts.append(interp._format_value(_to_ayce(a)))
        print(" ".join(parts))
        return None
    exports["print"] = _task(AyceNativeTask("print", _print))

    def _read_line(interp, args, line, col):
        prompt = ""
        if len(args) == 1 and isinstance(args[0], str):
            prompt = args[0]
        return input(prompt)
    exports["read_line"] = _task(AyceNativeTask("read_line", _read_line))

    def _read_int(interp, args, line, col):
        prompt = args[0] if args and isinstance(args[0], str) else ""
        while True:
            raw = input(prompt)
            try:
                return int(raw)
            except ValueError:
                print(f"'{raw}' no es un int válido. Intentá de nuevo.")
    exports["read_int"] = _task(AyceNativeTask("read_int", _read_int))

    def _read_float(interp, args, line, col):
        prompt = args[0] if args and isinstance(args[0], str) else ""
        while True:
            raw = input(prompt)
            try:
                return float(raw)
            except ValueError:
                print(f"'{raw}' no es un float válido. Intentá de nuevo.")
    exports["read_float"] = _task(AyceNativeTask("read_float", _read_float))

    return AyceNativeBatch("io", exports)


# ──────────────────────────────────────────────────────────────────────
#  Batch: time
# ──────────────────────────────────────────────────────────────────────
def _build_time_batch():
    exports = {}

    def _now(interp, args, line, col):
        if args:
            raise _err(line, col, "time::now no toma argumentos")
        return _time.time()
    exports["now"] = _task(AyceNativeTask("now", _now))

    def _clock(interp, args, line, col):
        if args:
            raise _err(line, col, "time::clock no toma argumentos")
        return _time.perf_counter()
    exports["clock"] = _task(AyceNativeTask("clock", _clock))

    def _sleep(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], (int, float)):
            raise _err(line, col, "time::sleep requiere 1 número (segundos)")
        _time.sleep(args[0])
        return None
    exports["sleep"] = _task(AyceNativeTask("sleep", _sleep))

    def _timestamp(interp, args, line, col):
        if args:
            raise _err(line, col, "time::timestamp no toma argumentos")
        import datetime
        return datetime.datetime.now().isoformat()
    exports["timestamp"] = _task(AyceNativeTask("timestamp", _timestamp))

    return AyceNativeBatch("time", exports)


# ──────────────────────────────────────────────────────────────────────
#  Batch: os
# ──────────────────────────────────────────────────────────────────────
def _build_os_batch():
    exports = {}

    def _cwd(interp, args, line, col):
        if args:
            raise _err(line, col, "os::cwd no toma argumentos")
        return _os.getcwd()
    exports["cwd"] = _task(AyceNativeTask("cwd", _cwd))

    def _list_dir(interp, args, line, col):
        from .interpreter import AyceList
        if len(args) == 0:
            path = "."
        elif len(args) == 1 and isinstance(args[0], str):
            path = args[0]
        else:
            raise _err(line, col, "os::list_dir requiere 0 o 1 string (ruta)")
        try:
            entries = _os.listdir(path)
            return AyceList(entries, ListType(elem=PrimitiveType(name="string")))
        except OSError as e:
            raise _err(line, col, f"os::list_dir: {e}")
    exports["list_dir"] = _task(AyceNativeTask("list_dir", _list_dir))

    def _exists(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "os::exists requiere 1 string (ruta)")
        return _os.path.exists(args[0])
    exports["exists"] = _task(AyceNativeTask("exists", _exists))

    def _env(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "os::env requiere 1 string (nombre de variable)")
        return _os.environ.get(args[0], "")
    exports["env"] = _task(AyceNativeTask("env", _env))

    def _mkdir(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "os::mkdir requiere 1 string (ruta)")
        try:
            _os.makedirs(args[0], exist_ok=True)
            return None
        except OSError as e:
            raise _err(line, col, f"os::mkdir: {e}")
    exports["mkdir"] = _task(AyceNativeTask("mkdir", _mkdir))

    def _name(interp, args, line, col):
        if args:
            raise _err(line, col, "os::name no toma argumentos")
        return _os.name
    exports["name"] = _task(AyceNativeTask("name", _name))

    return AyceNativeBatch("os", exports)


# ──────────────────────────────────────────────────────────────────────
#  Batch: sys
# ──────────────────────────────────────────────────────────────────────
def _build_sys_batch():
    exports = {}

    def _args(interp, args, line, col):
        from .interpreter import AyceList
        if args:
            raise _err(line, col, "sys::args no toma argumentos")
        return AyceList(list(_sys.argv[1:]),
                        ListType(elem=PrimitiveType(name="string")))
    exports["args"] = _task(AyceNativeTask("args", _args))

    def _exit(interp, args, line, col):
        if len(args) > 1:
            raise _err(line, col, "sys::exit requiere 0 o 1 argumento (código)")
        code = args[0] if args else 0
        if not isinstance(code, int):
            raise _err(line, col, "sys::exit: código debe ser int")
        _sys.exit(code)
    exports["exit"] = _task(AyceNativeTask("exit", _exit))

    def _version(interp, args, line, col):
        if args:
            raise _err(line, col, "sys::version no toma argumentos")
        from . import __version__ as ayce_ver
        return ayce_ver
    exports["version"] = _task(AyceNativeTask("version", _version))

    def _python_version(interp, args, line, col):
        if args:
            raise _err(line, col, "sys::python_version no toma argumentos")
        return f"{_sys.version_info.major}.{_sys.version_info.minor}.{_sys.version_info.micro}"
    exports["python_version"] = _task(AyceNativeTask("python_version", _python_version))

    def _platform(interp, args, line, col):
        if args:
            raise _err(line, col, "sys::platform no toma argumentos")
        return _sys.platform
    exports["platform"] = _task(AyceNativeTask("platform", _platform))

    return AyceNativeBatch("sys", exports)


# ──────────────────────────────────────────────────────────────────────
#  Batch: json
# ──────────────────────────────────────────────────────────────────────
def _build_json_batch():
    exports = {}

    def _parse(interp, args, line, col):
        if len(args) != 1 or not isinstance(args[0], str):
            raise _err(line, col, "json::parse requiere 1 string")
        try:
            result = _json.loads(args[0])
            return _to_ayce(result)
        except _json.JSONDecodeError as e:
            raise _err(line, col, f"json::parse: JSON inválido: {e}")
    exports["parse"] = _task(AyceNativeTask("parse", _parse))

    def _stringify(interp, args, line, col):
        if len(args) != 1:
            raise _err(line, col, "json::stringify requiere 1 argumento")
        try:
            py_value = _from_ayce(args[0])
            return _json.dumps(py_value, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as e:
            raise _err(line, col, f"json::stringify: {e}")
    exports["stringify"] = _task(AyceNativeTask("stringify", _stringify))

    def _stringify_compact(interp, args, line, col):
        if len(args) != 1:
            raise _err(line, col, "json::stringify_compact requiere 1 argumento")
        try:
            py_value = _from_ayce(args[0])
            return _json.dumps(py_value, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            raise _err(line, col, f"json::stringify_compact: {e}")
    exports["stringify_compact"] = _task(AyceNativeTask("stringify_compact", _stringify_compact))

    return AyceNativeBatch("json", exports)


# ──────────────────────────────────────────────────────────────────────
#  Registro de todos los batches built-in
# ──────────────────────────────────────────────────────────────────────

def get_builtin_batches():
    """Devuelve un dict nombre → AyceNativeBatch con todos los batches built-in."""
    return {
        "math":   _build_math_batch(),
        "random": _build_random_batch(),
        "string": _build_string_batch(),
        "list":   _build_list_batch(),
        "dict":   _build_dict_batch(),
        "io":     _build_io_batch(),
        "time":   _build_time_batch(),
        "os":     _build_os_batch(),
        "sys":    _build_sys_batch(),
        "json":   _build_json_batch(),
    }
