"""
ayce — Batches stdlib extra (v0.6.1).

Batches adicionales equivalentes a módulos stdlib de Python que no estaban
en v0.5.1. Cada batch expone tareas (AyceNativeTask) y constantes.

Importado por batches.py vía get_extra_batches().
"""

import math as _math
import re as _re
import copy as _copy
import hashlib as _hashlib
import base64 as _base64
import binascii as _binascii
import csv as _csv
import io as _io
import calendar as _calendar
import statistics as _statistics
import difflib as _difflib
import textwrap as _textwrap
import unicodedata as _unicodedata
import uuid as _uuid
import secrets as _secrets
import hmac as _hmac
import platform as _platform
import zlib as _zlib
import bz2 as _bz2
import lzma as _lzma
import gzip as _gzip
import pickle as _pickle
import sqlite3 as _sqlite3
import zipfile as _zipfile
import tarfile as _tarfile
import shutil as _shutil
import glob as _glob
import tempfile as _tempfile
import pprint as _pprint
import inspect as _inspect
import traceback as _traceback
import warnings as _warnings
import builtins as _builtins
import logging as _logging
import argparse as _argparse
import threading as _threading
import queue as _queue
import types as _types
import codecs as _codecs
import locale as _locale
import subprocess as _subprocess
import struct as _struct
import decimal as _decimal
import fractions as _fractions
import bisect as _bisect
import heapq as _heapq
import itertools as _itertools
import functools as _functools
import collections as _collections
import os as _os
import os.path as _opath
import time as _time
import stat as _stat_mod
import socket as _socket
import ssl as _ssl
import http.client as _httpclient
import email.message as _emailmsg
import email.parser as _emailparser
import email.policy as _emailpolicy
import signal as _signal
import multiprocessing as _multiprocessing
import gettext as _gettext
from datetime import datetime as _datetime, date as _date, time as _dtime, timedelta as _timedelta
import urllib.parse as _urlparse

from .errors import AyceRuntimeError


# ──────────────────────────────────────────────────────────────────────
#  Reutilizamos AyceNativeTask / AyceNativeBatch / helpers de batches.py
# ──────────────────────────────────────────────────────────────────────

from .batches import (
    AyceNativeTask,
    AyceNativeBatch,
    _to_ayce,
    _from_ayce,
    _type_name,
    _const,
    _task,
    _is_batch,
)


def _err(line, col, msg):
    return AyceRuntimeError("<builtin-extra>", line, col, msg)


def _nargs(args, expected, name, line, col):
    if isinstance(expected, tuple):
        if len(args) not in expected:
            raise _err(line, col, f"{name} requiere {expected} argumentos, se recibieron {len(args)}")
    else:
        if len(args) != expected:
            raise _err(line, col, f"{name} requiere {expected} argumentos, se recibieron {len(args)}")


def _xa_is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _xa_is_str(x):
    return isinstance(x, str)


def _xa_is_list(x):
    return type(x).__name__ == "AyceList"


def _xa_is_dict(x):
    return type(x).__name__ == "AyceDict"


def _xa_is_set(x):
    return type(x).__name__ == "AyceSet"


def _xa_is_tuple(x):
    return type(x).__name__ == "AyceTuple"


def _to_py_list(x):
    if _xa_is_list(x):
        return [_from_ayce(e) for e in x.elements]
    if isinstance(x, list):
        return x
    raise _err(0, 0, f"se esperaba lista, se recibió {_type_name(x)}")


def _to_py_dict(x):
    if _xa_is_dict(x):
        return {_from_ayce(k): _from_ayce(v) for k, v in x.pairs.items()}
    if isinstance(x, dict):
        return x
    raise _err(0, 0, f"se esperaba diccionario, se recibió {_type_name(x)}")


def _wrap(func):
    """Crea un AyceNativeTask desde una función Python pura (interp, args, line, col)."""
    return AyceNativeTask(func.__name__, func)

# ──────────────────────────────────────────────────────────────────────
#  copy
# ──────────────────────────────────────────────────────────────────────
def _build_copy_batch():
    exports = {}

    def _shallow(interp, args, line, col):
        _nargs(args, 1, "copy::shallow", line, col)
        return _to_ayce(_copy.copy(_from_ayce(args[0])))
    exports["shallow"] = _task(_wrap(_shallow))

    def _deep(interp, args, line, col):
        _nargs(args, 1, "copy::deep", line, col)
        return _to_ayce(_copy.deepcopy(_from_ayce(args[0])))
    exports["deep"] = _task(_wrap(_deep))

    return AyceNativeBatch("copy", exports)


# ──────────────────────────────────────────────────────────────────────
#  re — expresiones regulares
# ──────────────────────────────────────────────────────────────────────
def _build_re_batch():
    exports = {}

    def _match(interp, args, line, col):
        _nargs(args, (2, 3), "re::match", line, col)
        pattern, string = args[0], args[1]
        flags = args[2] if len(args) == 3 else 0
        if not (_xa_is_str(pattern) and _xa_is_str(string)):
            raise _err(line, col, "re::match requiere strings")
        m = _re.match(pattern, string, flags=flags)
        if m is None:
            return None
        groups = [_to_ayce(g) for g in m.groups()]
        return _to_ayce({"match": m.group(0), "groups": groups, "start": m.start(), "end": m.end()})
    exports["match"] = _task(_wrap(_match))

    def _search(interp, args, line, col):
        _nargs(args, (2, 3), "re::search", line, col)
        pattern, string = args[0], args[1]
        flags = args[2] if len(args) == 3 else 0
        if not (_xa_is_str(pattern) and _xa_is_str(string)):
            raise _err(line, col, "re::search requiere strings")
        m = _re.search(pattern, string, flags=flags)
        if m is None:
            return None
        groups = [_to_ayce(g) for g in m.groups()]
        return _to_ayce({"match": m.group(0), "groups": groups, "start": m.start(), "end": m.end()})
    exports["search"] = _task(_wrap(_search))

    def _find_all(interp, args, line, col):
        _nargs(args, (2, 3), "re::find_all", line, col)
        pattern, string = args[0], args[1]
        flags = args[2] if len(args) == 3 else 0
        if not (_xa_is_str(pattern) and _xa_is_str(string)):
            raise _err(line, col, "re::find_all requiere strings")
        return _to_ayce(_re.findall(pattern, string, flags=flags))
    exports["find_all"] = _task(_wrap(_find_all))

    def _replace(interp, args, line, col):
        _nargs(args, 3, "re::replace", line, col)
        pattern, string, repl = args[0], args[1], args[2]
        if not all(_xa_is_str(x) for x in (pattern, string, repl)):
            raise _err(line, col, "re::replace requiere strings")
        return _re.sub(pattern, repl, string)
    exports["replace"] = _task(_wrap(_replace))

    def _split(interp, args, line, col):
        _nargs(args, (2, 3), "re::split", line, col)
        pattern, string = args[0], args[1]
        if not (_xa_is_str(pattern) and _xa_is_str(string)):
            raise _err(line, col, "re::split requiere strings")
        return _to_ayce(_re.split(pattern, string))
    exports["split"] = _task(_wrap(_split))

    # Constantes flags
    exports["IGNORECASE"] = _const(_re.IGNORECASE)
    exports["MULTILINE"] = _const(_re.MULTILINE)
    exports["DOTALL"] = _const(_re.DOTALL)

    return AyceNativeBatch("re", exports)


# ──────────────────────────────────────────────────────────────────────
#  datetime
# ──────────────────────────────────────────────────────────────────────
def _build_datetime_batch():
    exports = {}

    def _now(interp, args, line, col):
        _nargs(args, 0, "datetime::now", line, col)
        d = _datetime.now()
        return _to_ayce({
            "year": d.year, "month": d.month, "day": d.day,
            "hour": d.hour, "minute": d.minute, "second": d.second,
            "microsecond": d.microsecond,
            "weekday": d.weekday(),  # 0=Monday
            "iso": d.isoformat(),
            "str": d.strftime("%Y-%m-%d %H:%M:%S"),
        })
    exports["now"] = _task(_wrap(_now))

    def _today(interp, args, line, col):
        _nargs(args, 0, "datetime::today", line, col)
        d = _date.today()
        return _to_ayce({
            "year": d.year, "month": d.month, "day": d.day,
            "weekday": d.weekday(),
            "iso": d.isoformat(),
            "str": d.strftime("%Y-%m-%d"),
        })
    exports["today"] = _task(_wrap(_today))

    def _date_make(interp, args, line, col):
        _nargs(args, 3, "datetime::date", line, col)
        y, m, d = args[0], args[1], args[2]
        if not all(isinstance(x, int) for x in (y, m, d)):
            raise _err(line, col, "datetime::date requiere (int year, int month, int day)")
        dd = _date(y, m, d)
        return _to_ayce({
            "year": dd.year, "month": dd.month, "day": dd.day,
            "weekday": dd.weekday(),
            "iso": dd.isoformat(),
        })
    exports["date"] = _task(_wrap(_date_make))

    def _datetime_make(interp, args, line, col):
        _nargs(args, (3, 6), "datetime::datetime", line, col)
        y, mo, d = args[0], args[1], args[2]
        h = args[3] if len(args) >= 4 else 0
        mi = args[4] if len(args) >= 5 else 0
        s = args[5] if len(args) >= 6 else 0
        if not all(isinstance(x, int) for x in (y, mo, d, h, mi, s)):
            raise _err(line, col, "datetime::datetime requiere ints")
        dt = _datetime(y, mo, d, h, mi, s)
        return _to_ayce({
            "year": dt.year, "month": dt.month, "day": dt.day,
            "hour": dt.hour, "minute": dt.minute, "second": dt.second,
            "weekday": dt.weekday(),
            "iso": dt.isoformat(),
        })
    exports["datetime"] = _task(_wrap(_datetime_make))

    def _strftime(interp, args, line, col):
        _nargs(args, 2, "datetime::strftime", line, col)
        ts, fmt = args[0], args[1]
        if not (isinstance(ts, (int, float)) and _xa_is_str(fmt)):
            raise _err(line, col, "datetime::strftime requiere (timestamp, string)")
        return _datetime.fromtimestamp(ts).strftime(fmt)
    exports["strftime"] = _task(_wrap(_strftime))

    def _strptime(interp, args, line, col):
        _nargs(args, 2, "datetime::strptime", line, col)
        string, fmt = args[0], args[1]
        if not (_xa_is_str(string) and _xa_is_str(fmt)):
            raise _err(line, col, "datetime::strptime requiere strings")
        d = _datetime.strptime(string, fmt)
        return _to_ayce({
            "year": d.year, "month": d.month, "day": d.day,
            "hour": d.hour, "minute": d.minute, "second": d.second,
            "iso": d.isoformat(),
        })
    exports["strptime"] = _task(_wrap(_strptime))

    def _timestamp(interp, args, line, col):
        _nargs(args, 0, "datetime::timestamp", line, col)
        return _time.time()
    exports["timestamp"] = _task(_wrap(_timestamp))

    def _from_iso(interp, args, line, col):
        _nargs(args, 1, "datetime::from_iso", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "datetime::from_iso requiere string")
        try:
            d = _datetime.fromisoformat(args[0])
        except Exception as e:
            raise _err(line, col, f"datetime::from_iso: {e}")
        return _to_ayce({
            "year": d.year, "month": d.month, "day": d.day,
            "hour": d.hour, "minute": d.minute, "second": d.second,
            "iso": d.isoformat(),
        })
    exports["from_iso"] = _task(_wrap(_from_iso))

    ## ── Ampliación v0.6.1: aritmética de fechas (timedelta) ──
    ## Los dicts de datetime aceptan las claves year/month/day/hour/minute/second.

    def _dt_from_dict(value, default_date=None):
        """Construye un datetime desde un dict ayce o un ISO string."""
        if _xa_is_str(value):
            return _datetime.fromisoformat(value)
        if not _xa_is_dict(value):
            raise ValueError("se esperaba dict de datetime o string ISO")
        d = _to_py_dict(value)
        base = default_date or _datetime(1970, 1, 1)
        return _datetime(
            int(d.get("year", base.year)),
            int(d.get("month", base.month)),
            int(d.get("day", base.day)),
            int(d.get("hour", 0)),
            int(d.get("minute", 0)),
            int(d.get("second", 0)),
        )

    def _dt_to_dict(d):
        return {
            "year": d.year, "month": d.month, "day": d.day,
            "hour": d.hour, "minute": d.minute, "second": d.second,
            "weekday": d.weekday(),
            "iso": d.isoformat(),
            "str": d.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _add_delta(interp, args, line, col, field, seconds_per_unit, name):
        _nargs(args, 2, f"datetime::{name}", line, col)
        try:
            d = _dt_from_dict(args[0])
        except Exception as e:
            raise _err(line, col, f"datetime::{name}: {e}")
        n = args[1]
        if not isinstance(n, (int, float)):
            raise _err(line, col, f"datetime::{name}: cantidad numérica")
        delta = _timedelta(**{field: n})
        return _to_ayce(_dt_to_dict(d + delta))

    def _add_days(interp, args, line, col):
        return _add_delta(interp, args, line, col, "days", 86400, "add_days")
    exports["add_days"] = _task(_wrap(_add_days))

    def _add_hours(interp, args, line, col):
        return _add_delta(interp, args, line, col, "hours", 3600, "add_hours")
    exports["add_hours"] = _task(_wrap(_add_hours))

    def _add_minutes(interp, args, line, col):
        return _add_delta(interp, args, line, col, "minutes", 60, "add_minutes")
    exports["add_minutes"] = _task(_wrap(_add_minutes))

    def _add_seconds(interp, args, line, col):
        return _add_delta(interp, args, line, col, "seconds", 1, "add_seconds")
    exports["add_seconds"] = _task(_wrap(_add_seconds))

    def _add_months(interp, args, line, col):
        _nargs(args, 2, "datetime::add_months", line, col)
        try:
            d = _dt_from_dict(args[0])
        except Exception as e:
            raise _err(line, col, f"datetime::add_months: {e}")
        n = args[1]
        if not isinstance(n, int):
            raise _err(line, col, "datetime::add_months: cantidad int")
        total = (d.year * 12 + (d.month - 1)) + n
        y = total // 12
        m = (total % 12) + 1
        # Ajustar el día si el mes destino es más corto
        day = d.day
        days_in = _calendar.monthrange(y, m)[1]
        if day > days_in:
            day = days_in
        nd = _datetime(y, m, day, d.hour, d.minute, d.second)
        return _to_ayce(_dt_to_dict(nd))
    exports["add_months"] = _task(_wrap(_add_months))

    def _add_years(interp, args, line, col):
        _nargs(args, 2, "datetime::add_years", line, col)
        try:
            d = _dt_from_dict(args[0])
        except Exception as e:
            raise _err(line, col, f"datetime::add_years: {e}")
        n = args[1]
        if not isinstance(n, int):
            raise _err(line, col, "datetime::add_years: cantidad int")
        y = d.year + n
        day = d.day
        try:
            nd = _datetime(y, d.month, day, d.hour, d.minute, d.second)
        except ValueError:
            # 29 de febrero → 28 de febrero
            nd = _datetime(y, d.month, 28, d.hour, d.minute, d.second)
        return _to_ayce(_dt_to_dict(nd))
    exports["add_years"] = _task(_wrap(_add_years))

    def _diff_days(interp, args, line, col):
        _nargs(args, 2, "datetime::diff_days", line, col)
        try:
            a = _dt_from_dict(args[0])
            b = _dt_from_dict(args[1])
        except Exception as e:
            raise _err(line, col, f"datetime::diff_days: {e}")
        return (b - a).total_seconds() / 86400.0
    exports["diff_days"] = _task(_wrap(_diff_days))

    def _diff_seconds(interp, args, line, col):
        _nargs(args, 2, "datetime::diff_seconds", line, col)
        try:
            a = _dt_from_dict(args[0])
            b = _dt_from_dict(args[1])
        except Exception as e:
            raise _err(line, col, f"datetime::diff_seconds: {e}")
        return (b - a).total_seconds()
    exports["diff_seconds"] = _task(_wrap(_diff_seconds))

    def _weekday_name(interp, args, line, col):
        _nargs(args, 1, "datetime::weekday_name", line, col)
        try:
            d = _dt_from_dict(args[0])
        except Exception as e:
            raise _err(line, col, f"datetime::weekday_name: {e}")
        names = ["Lunes", "Martes", "Miércoles", "Jueves",
                 "Viernes", "Sábado", "Domingo"]
        return names[d.weekday()]
    exports["weekday_name"] = _task(_wrap(_weekday_name))

    def _day_of_year(interp, args, line, col):
        _nargs(args, 1, "datetime::day_of_year", line, col)
        try:
            d = _dt_from_dict(args[0])
        except Exception as e:
            raise _err(line, col, f"datetime::day_of_year: {e}")
        return d.timetuple().tm_yday
    exports["day_of_year"] = _task(_wrap(_day_of_year))

    return AyceNativeBatch("datetime", exports)


# ──────────────────────────────────────────────────────────────────────
#  path (os.path)
# ──────────────────────────────────────────────────────────────────────
def _build_path_batch():
    exports = {}

    def _join(interp, args, line, col):
        if not args:
            raise _err(line, col, "path::join requiere al menos 1 string")
        parts = []
        for a in args:
            if not _xa_is_str(a):
                raise _err(line, col, "path::join: todos los args deben ser string")
            parts.append(a)
        return _opath.join(*parts)
    exports["join"] = _task(_wrap(_join))

    def _basename(interp, args, line, col):
        _nargs(args, 1, "path::basename", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "path::basename requiere string")
        return _opath.basename(args[0])
    exports["basename"] = _task(_wrap(_basename))

    def _dirname(interp, args, line, col):
        _nargs(args, 1, "path::dirname", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "path::dirname requiere string")
        return _opath.dirname(args[0])
    exports["dirname"] = _task(_wrap(_dirname))

    def _splitext(interp, args, line, col):
        _nargs(args, 1, "path::splitext", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "path::splitext requiere string")
        root, ext = _opath.splitext(args[0])
        return _to_ayce([root, ext])
    exports["splitext"] = _task(_wrap(_splitext))

    def _abspath(interp, args, line, col):
        _nargs(args, 1, "path::abspath", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "path::abspath requiere string")
        return _opath.abspath(args[0])
    exports["abspath"] = _task(_wrap(_abspath))

    def _exists(interp, args, line, col):
        _nargs(args, 1, "path::exists", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "path::exists requiere string")
        return _opath.exists(args[0])
    exports["exists"] = _task(_wrap(_exists))

    def _isfile(interp, args, line, col):
        _nargs(args, 1, "path::isfile", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "path::isfile requiere string")
        return _opath.isfile(args[0])
    exports["isfile"] = _task(_wrap(_isfile))

    def _isdir(interp, args, line, col):
        _nargs(args, 1, "path::isdir", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "path::isdir requiere string")
        return _opath.isdir(args[0])
    exports["isdir"] = _task(_wrap(_isdir))

    def _size(interp, args, line, col):
        _nargs(args, 1, "path::size", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "path::size requiere string")
        try:
            return _opath.getsize(args[0])
        except OSError as e:
            raise _err(line, col, f"path::size: {e}")
    exports["size"] = _task(_wrap(_size))

    def _normpath(interp, args, line, col):
        _nargs(args, 1, "path::normpath", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "path::normpath requiere string")
        return _opath.normpath(args[0])
    exports["normpath"] = _task(_wrap(_normpath))

    return AyceNativeBatch("path", exports)


# ──────────────────────────────────────────────────────────────────────
#  hashlib
# ──────────────────────────────────────────────────────────────────────
def _build_hashlib_batch():
    exports = {}

    def _hash_with(algorithm):
        def _h(interp, args, line, col):
            _nargs(args, 1, f"hashlib::{algorithm}", line, col)
            data = args[0]
            if _xa_is_str(data):
                data = data.encode("utf-8")
            elif isinstance(data, bytes):
                pass
            else:
                raise _err(line, col, f"hashlib::{algorithm} requiere string o bytes")
            h = getattr(_hashlib, algorithm)()
            h.update(data)
            return h.hexdigest()
        return _h

    for algo in ("md5", "sha1", "sha256", "sha512", "sha224", "sha384"):
        exports[algo] = _task(_wrap(_hash_with(algo)))

    return AyceNativeBatch("hashlib", exports)


# ──────────────────────────────────────────────────────────────────────
#  base64
# ──────────────────────────────────────────────────────────────────────
def _build_base64_batch():
    exports = {}

    def _encode(interp, args, line, col):
        _nargs(args, 1, "base64::encode", line, col)
        data = args[0]
        if _xa_is_str(data):
            data = data.encode("utf-8")
        elif not isinstance(data, bytes):
            raise _err(line, col, "base64::encode requiere string o bytes")
        return _base64.b64encode(data).decode("ascii")
    exports["encode"] = _task(_wrap(_encode))

    def _decode(interp, args, line, col):
        _nargs(args, 1, "base64::decode", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "base64::decode requiere string")
        return _base64.b64decode(args[0]).decode("utf-8")
    exports["decode"] = _task(_wrap(_decode))

    def _encode_url(interp, args, line, col):
        _nargs(args, 1, "base64::encode_urlsafe", line, col)
        data = args[0]
        if _xa_is_str(data):
            data = data.encode("utf-8")
        return _base64.urlsafe_b64encode(data).decode("ascii")
    exports["encode_urlsafe"] = _task(_wrap(_encode_url))

    def _decode_url(interp, args, line, col):
        _nargs(args, 1, "base64::decode_urlsafe", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "base64::decode_urlsafe requiere string")
        return _base64.urlsafe_b64decode(args[0]).decode("utf-8")
    exports["decode_urlsafe"] = _task(_wrap(_decode_url))

    def _hex_encode(interp, args, line, col):
        _nargs(args, 1, "base64::hex_encode", line, col)
        data = args[0]
        if _xa_is_str(data):
            data = data.encode("utf-8")
        return _binascii.hexlify(data).decode("ascii")
    exports["hex_encode"] = _task(_wrap(_hex_encode))

    def _hex_decode(interp, args, line, col):
        _nargs(args, 1, "base64::hex_decode", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "base64::hex_decode requiere string")
        return _binascii.unhexlify(args[0]).decode("utf-8")
    exports["hex_decode"] = _task(_wrap(_hex_decode))

    return AyceNativeBatch("base64", exports)


# ──────────────────────────────────────────────────────────────────────
#  hmac
# ──────────────────────────────────────────────────────────────────────
def _build_hmac_batch():
    exports = {}

    def _digest(interp, args, line, col):
        _nargs(args, (2, 3), "hmac::digest", line, col)
        key, msg = args[0], args[1]
        algo = args[2] if len(args) == 3 else "sha256"
        if _xa_is_str(key): key = key.encode("utf-8")
        if _xa_is_str(msg): msg = msg.encode("utf-8")
        return _hmac.new(key, msg, getattr(_hashlib, algo)).hexdigest()
    exports["digest"] = _task(_wrap(_digest))

    def _compare(interp, args, line, col):
        _nargs(args, 2, "hmac::compare", line, col)
        a, b = args[0], args[1]
        if _xa_is_str(a): a = a.encode("utf-8")
        if _xa_is_str(b): b = b.encode("utf-8")
        return _hmac.compare_digest(a, b)
    exports["compare"] = _task(_wrap(_compare))

    return AyceNativeBatch("hmac", exports)


# ──────────────────────────────────────────────────────────────────────
#  secrets
# ──────────────────────────────────────────────────────────────────────
def _build_secrets_batch():
    exports = {}

    def _token_hex(interp, args, line, col):
        _nargs(args, (0, 1), "secrets::token_hex", line, col)
        n = args[0] if args else 32
        if not isinstance(n, int):
            raise _err(line, col, "secrets::token_hex requiere int")
        return _secrets.token_hex(n)
    exports["token_hex"] = _task(_wrap(_token_hex))

    def _token_url(interp, args, line, col):
        _nargs(args, (0, 1), "secrets::token_urlsafe", line, col)
        n = args[0] if args else 32
        if not isinstance(n, int):
            raise _err(line, col, "secrets::token_urlsafe requiere int")
        return _secrets.token_urlsafe(n)
    exports["token_urlsafe"] = _task(_wrap(_token_url))

    def _rand_below(interp, args, line, col):
        _nargs(args, 1, "secrets::rand_below", line, col)
        if not isinstance(args[0], int):
            raise _err(line, col, "secrets::rand_below requiere int")
        return _secrets.randbelow(args[0])
    exports["rand_below"] = _task(_wrap(_rand_below))

    def _choice(interp, args, line, col):
        _nargs(args, 1, "secrets::choice", line, col)
        seq = _to_py_list(args[0]) if _xa_is_list(args[0]) else args[0]
        return _secrets.choice(seq)
    exports["choice"] = _task(_wrap(_choice))

    return AyceNativeBatch("secrets", exports)


# ──────────────────────────────────────────────────────────────────────
#  csv
# ──────────────────────────────────────────────────────────────────────
def _build_csv_batch():
    exports = {}

    def _read(interp, args, line, col):
        _nargs(args, (1, 2), "csv::read", line, col)
        path = args[0]
        delim = args[1] if len(args) == 2 else ","
        if not _xa_is_str(path) or not _xa_is_str(delim):
            raise _err(line, col, "csv::read requiere (string path, [string delim])")
        try:
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = _csv.reader(f, delimiter=delim)
                rows = [list(r) for r in reader]
            return _to_ayce(rows)
        except OSError as e:
            raise _err(line, col, f"csv::read: {e}")
    exports["read"] = _task(_wrap(_read))

    def _write(interp, args, line, col):
        _nargs(args, (2, 3), "csv::write", line, col)
        path = args[0]
        rows = args[1]
        delim = args[2] if len(args) == 3 else ","
        if not _xa_is_str(path) or not _xa_is_str(delim):
            raise _err(line, col, "csv::write: path y delim deben ser string")
        rows_py = _to_py_list(rows)
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = _csv.writer(f, delimiter=delim)
                for r in rows_py:
                    w.writerow(r)
            return None
        except OSError as e:
            raise _err(line, col, f"csv::write: {e}")
    exports["write"] = _task(_wrap(_write))

    def _read_dict(interp, args, line, col):
        _nargs(args, (1, 2), "csv::read_dict", line, col)
        path = args[0]
        delim = args[1] if len(args) == 2 else ","
        try:
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = _csv.DictReader(f, delimiter=delim)
                rows = [dict(r) for r in reader]
            return _to_ayce(rows)
        except OSError as e:
            raise _err(line, col, f"csv::read_dict: {e}")
    exports["read_dict"] = _task(_wrap(_read_dict))

    return AyceNativeBatch("csv", exports)


# ──────────────────────────────────────────────────────────────────────
#  collections
# ──────────────────────────────────────────────────────────────────────
def _build_collections_batch():
    exports = {}

    def _counter(interp, args, line, col):
        _nargs(args, 1, "collections::counter", line, col)
        seq = _to_py_list(args[0]) if _xa_is_list(args[0]) else (
            args[0].elements if _xa_is_tuple(args[0]) else
            (args[0].elements if _xa_is_set(args[0]) else args[0])
        )
        c = _collections.Counter(seq)
        return _to_ayce(dict(c))
    exports["counter"] = _task(_wrap(_counter))

    def _ordered_dict(interp, args, line, col):
        _nargs(args, (0, 1), "collections::ordered_dict", line, col)
        if not args:
            return _to_ayce({})
        d = _to_py_dict(args[0])
        return _to_ayce(dict(_collections.OrderedDict(d)))
    exports["ordered_dict"] = _task(_wrap(_ordered_dict))

    def _deque(interp, args, line, col):
        _nargs(args, (0, 1), "collections::deque", line, col)
        if not args:
            return _to_ayce([])
        seq = _to_py_list(args[0])
        return _to_ayce(list(_collections.deque(seq)))
    exports["deque"] = _task(_wrap(_deque))

    def _most_common(interp, args, line, col):
        _nargs(args, (1, 2), "collections::most_common", line, col)
        c = _collections.Counter(_to_py_list(args[0]))
        n = args[1] if len(args) == 2 else None
        return _to_ayce([list(p) for p in c.most_common(n)])
    exports["most_common"] = _task(_wrap(_most_common))

    return AyceNativeBatch("collections", exports)


# ──────────────────────────────────────────────────────────────────────
#  itertools
# ──────────────────────────────────────────────────────────────────────
def _build_itertools_batch():
    exports = {}

    def _chain(interp, args, line, col):
        if not args:
            raise _err(line, col, "itertools::chain requiere al menos 1 lista")
        lists = [_to_py_list(a) for a in args]
        return _to_ayce(list(_itertools.chain(*lists)))
    exports["chain"] = _task(_wrap(_chain))

    def _combinations(interp, args, line, col):
        _nargs(args, 2, "itertools::combinations", line, col)
        seq, r = _to_py_list(args[0]), args[1]
        if not isinstance(r, int):
            raise _err(line, col, "itertools::combinations: r debe ser int")
        return _to_ayce([list(c) for c in _itertools.combinations(seq, r)])
    exports["combinations"] = _task(_wrap(_combinations))

    def _permutations(interp, args, line, col):
        _nargs(args, (1, 2), "itertools::permutations", line, col)
        seq = _to_py_list(args[0])
        r = args[1] if len(args) == 2 else None
        return _to_ayce([list(p) for p in _itertools.permutations(seq, r)])
    exports["permutations"] = _task(_wrap(_permutations))

    def _product(interp, args, line, col):
        if not args:
            raise _err(line, col, "itertools::product requiere al menos 1 lista")
        lists = [_to_py_list(a) for a in args]
        return _to_ayce([list(p) for p in _itertools.product(*lists)])
    exports["product"] = _task(_wrap(_product))

    def _cycle(interp, args, line, col):
        _nargs(args, 2, "itertools::cycle", line, col)
        seq, n = _to_py_list(args[0]), args[1]
        if not isinstance(n, int):
            raise _err(line, col, "itertools::cycle: n debe ser int")
        it = _itertools.cycle(seq)
        return _to_ayce([next(it) for _ in range(n)])
    exports["cycle"] = _task(_wrap(_cycle))

    def _repeat(interp, args, line, col):
        _nargs(args, 2, "itertools::repeat", line, col)
        x, n = args[0], args[1]
        if not isinstance(n, int):
            raise _err(line, col, "itertools::repeat: n debe ser int")
        return _to_ayce([x] * n)
    exports["repeat"] = _task(_wrap(_repeat))

    return AyceNativeBatch("itertools", exports)


# ──────────────────────────────────────────────────────────────────────
#  functools
# ──────────────────────────────────────────────────────────────────────
def _build_functools_batch():
    exports = {}

    def _reduce(interp, args, line, col):
        # reduce(func, seq, [initial]) — func es un callable ayce
        _nargs(args, (2, 3), "functools::reduce", line, col)
        func = args[0]
        seq = _to_py_list(args[1])
        from .interpreter import AyceTask
        if not isinstance(func, (AyceTask, AyceNativeTask)):
            raise _err(line, col, "functools::reduce: func debe ser callable (task)")
        def call(a, b):
            return interp._call_task(func, [a, b], line, col)
        if len(args) == 3:
            acc = args[2]
            for x in seq:
                acc = call(acc, x)
        else:
            if not seq:
                raise _err(line, col, "functools::reduce: seq vacía sin inicial")
            acc = seq[0]
            for x in seq[1:]:
                acc = call(acc, x)
        return acc
    exports["reduce"] = _task(_wrap(_reduce))

    return AyceNativeBatch("functools", exports)


# ──────────────────────────────────────────────────────────────────────
#  heapq
# ──────────────────────────────────────────────────────────────────────
def _build_heapq_batch():
    exports = {}

    def _push(interp, args, line, col):
        _nargs(args, 2, "heapq::push", line, col)
        if not _xa_is_list(args[0]):
            raise _err(line, col, "heapq::push requiere lista")
        lst = args[0].elements
        _heapq.heappush(lst, args[1])
        return None
    exports["push"] = _task(_wrap(_push))

    def _pop(interp, args, line, col):
        _nargs(args, 1, "heapq::pop", line, col)
        if not _xa_is_list(args[0]):
            raise _err(line, col, "heapq::pop requiere lista")
        lst = args[0].elements
        if not lst:
            raise _err(line, col, "heapq::pop: lista vacía")
        return _heapq.heappop(lst)
    exports["pop"] = _task(_wrap(_pop))

    def _peek(interp, args, line, col):
        _nargs(args, 1, "heapq::peek", line, col)
        if not _xa_is_list(args[0]):
            raise _err(line, col, "heapq::peek requiere lista")
        lst = args[0].elements
        if not lst:
            raise _err(line, col, "heapq::peek: lista vacía")
        return lst[0]
    exports["peek"] = _task(_wrap(_peek))

    def _heapify(interp, args, line, col):
        _nargs(args, 1, "heapq::heapify", line, col)
        if not _xa_is_list(args[0]):
            raise _err(line, col, "heapq::heapify requiere lista")
        _heapq.heapify(args[0].elements)
        return None
    exports["heapify"] = _task(_wrap(_heapify))

    return AyceNativeBatch("heapq", exports)


# ──────────────────────────────────────────────────────────────────────
#  bisect
# ──────────────────────────────────────────────────────────────────────
def _build_bisect_batch():
    exports = {}

    def _insert(interp, args, line, col):
        _nargs(args, 2, "bisect::insert", line, col)
        if not _xa_is_list(args[0]):
            raise _err(line, col, "bisect::insert requiere lista")
        lst = args[0].elements
        x = args[1]
        _bisect.insort(lst, x)
        return None
    exports["insert"] = _task(_wrap(_insert))

    def _bisect_left(interp, args, line, col):
        _nargs(args, 2, "bisect::left", line, col)
        if not _xa_is_list(args[0]):
            raise _err(line, col, "bisect::left requiere lista")
        return _bisect.bisect_left(args[0].elements, args[1])
    exports["left"] = _task(_wrap(_bisect_left))

    def _bisect_right(interp, args, line, col):
        _nargs(args, 2, "bisect::right", line, col)
        if not _xa_is_list(args[0]):
            raise _err(line, col, "bisect::right requiere lista")
        return _bisect.bisect_right(args[0].elements, args[1])
    exports["right"] = _task(_wrap(_bisect_right))

    return AyceNativeBatch("bisect", exports)


# ──────────────────────────────────────────────────────────────────────
#  statistics
# ──────────────────────────────────────────────────────────────────────
def _build_statistics_batch():
    exports = {}

    def _mean(interp, args, line, col):
        _nargs(args, 1, "statistics::mean", line, col)
        seq = _to_py_list(args[0])
        return _statistics.mean(seq)
    exports["mean"] = _task(_wrap(_mean))

    def _median(interp, args, line, col):
        _nargs(args, 1, "statistics::median", line, col)
        seq = _to_py_list(args[0])
        return _statistics.median(seq)
    exports["median"] = _task(_wrap(_median))

    def _mode(interp, args, line, col):
        _nargs(args, 1, "statistics::mode", line, col)
        seq = _to_py_list(args[0])
        try:
            return _statistics.mode(seq)
        except _statistics.StatisticsError as e:
            raise _err(line, col, f"statistics::mode: {e}")
    exports["mode"] = _task(_wrap(_mode))

    def _stdev(interp, args, line, col):
        _nargs(args, 1, "statistics::stdev", line, col)
        seq = _to_py_list(args[0])
        try:
            return _statistics.stdev(seq)
        except _statistics.StatisticsError as e:
            raise _err(line, col, f"statistics::stdev: {e}")
    exports["stdev"] = _task(_wrap(_stdev))

    def _variance(interp, args, line, col):
        _nargs(args, 1, "statistics::variance", line, col)
        seq = _to_py_list(args[0])
        try:
            return _statistics.variance(seq)
        except _statistics.StatisticsError as e:
            raise _err(line, col, f"statistics::variance: {e}")
    exports["variance"] = _task(_wrap(_variance))

    def _quantiles(interp, args, line, col):
        _nargs(args, (1, 2), "statistics::quantiles", line, col)
        seq = _to_py_list(args[0])
        n = args[1] if len(args) == 2 else 4
        return _to_ayce(_statistics.quantiles(seq, n=n))
    exports["quantiles"] = _task(_wrap(_quantiles))

    return AyceNativeBatch("statistics", exports)


# ──────────────────────────────────────────────────────────────────────
#  textwrap
# ──────────────────────────────────────────────────────────────────────
def _build_textwrap_batch():
    exports = {}

    def _do_wrap(interp, args, line, col):
        _nargs(args, (1, 2), "textwrap::wrap", line, col)
        text = args[0]
        if not _xa_is_str(text):
            raise _err(line, col, "textwrap::wrap requiere string")
        width = args[1] if len(args) == 2 else 70
        return _to_ayce(_textwrap.wrap(text, width=width))
    exports["wrap"] = _task(_wrap(_do_wrap))

    def _fill(interp, args, line, col):
        _nargs(args, (1, 2), "textwrap::fill", line, col)
        text = args[0]
        width = args[1] if len(args) == 2 else 70
        return _textwrap.fill(text, width=width)
    exports["fill"] = _task(_wrap(_fill))

    def _dedent(interp, args, line, col):
        _nargs(args, 1, "textwrap::dedent", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "textwrap::dedent requiere string")
        return _textwrap.dedent(args[0])
    exports["dedent"] = _task(_wrap(_dedent))

    def _indent(interp, args, line, col):
        _nargs(args, 2, "textwrap::indent", line, col)
        text, prefix = args[0], args[1]
        if not (_xa_is_str(text) and _xa_is_str(prefix)):
            raise _err(line, col, "textwrap::indent requiere strings")
        return _textwrap.indent(text, prefix)
    exports["indent"] = _task(_wrap(_indent))

    return AyceNativeBatch("textwrap", exports)


# ──────────────────────────────────────────────────────────────────────
#  difflib
# ──────────────────────────────────────────────────────────────────────
def _build_difflib_batch():
    exports = {}

    def _ratio(interp, args, line, col):
        _nargs(args, 2, "difflib::ratio", line, col)
        a, b = args[0], args[1]
        if not (_xa_is_str(a) and _xa_is_str(b)):
            raise _err(line, col, "difflib::ratio requiere strings")
        return _difflib.SequenceMatcher(None, a, b).ratio()
    exports["ratio"] = _task(_wrap(_ratio))

    def _unified_diff(interp, args, line, col):
        _nargs(args, 2, "difflib::unified_diff", line, col)
        a, b = args[0], args[1]
        if not (_xa_is_list(a) and _xa_is_list(b)):
            raise _err(line, col, "difflib::unified_diff requiere listas")
        la = _to_py_list(a)
        lb = _to_py_list(b)
        diff = list(_difflib.unified_diff(la, lb, lineterm=""))
        return _to_ayce(diff)
    exports["unified_diff"] = _task(_wrap(_unified_diff))

    def _get_close_matches(interp, args, line, col):
        _nargs(args, (2, 4), "difflib::get_close_matches", line, col)
        word = args[0]
        possibilities = _to_py_list(args[1])
        n = args[2] if len(args) >= 3 else 3
        cutoff = args[3] if len(args) == 4 else 0.6
        return _to_ayce(_difflib.get_close_matches(word, possibilities, n=n, cutoff=cutoff))
    exports["get_close_matches"] = _task(_wrap(_get_close_matches))

    return AyceNativeBatch("difflib", exports)


# ──────────────────────────────────────────────────────────────────────
#  unicodedata
# ──────────────────────────────────────────────────────────────────────
def _build_unicodedata_batch():
    exports = {}

    def _name(interp, args, line, col):
        _nargs(args, 1, "unicodedata::name", line, col)
        c = args[0]
        if not (_xa_is_str(c) and len(c) == 1):
            raise _err(line, col, "unicodedata::name requiere 1 caracter")
        try:
            return _unicodedata.name(c)
        except ValueError as e:
            raise _err(line, col, f"unicodedata::name: {e}")
    exports["name"] = _task(_wrap(_name))

    def _lookup(interp, args, line, col):
        _nargs(args, 1, "unicodedata::lookup", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "unicodedata::lookup requiere string")
        try:
            return _unicodedata.lookup(args[0])
        except KeyError as e:
            raise _err(line, col, f"unicodedata::lookup: {e}")
    exports["lookup"] = _task(_wrap(_lookup))

    def _category(interp, args, line, col):
        _nargs(args, 1, "unicodedata::category", line, col)
        c = args[0]
        if not (_xa_is_str(c) and len(c) == 1):
            raise _err(line, col, "unicodedata::category requiere 1 caracter")
        return _unicodedata.category(c)
    exports["category"] = _task(_wrap(_category))

    def _decimal(interp, args, line, col):
        _nargs(args, 1, "unicodedata::decimal", line, col)
        c = args[0]
        if not (_xa_is_str(c) and len(c) == 1):
            raise _err(line, col, "unicodedata::decimal requiere 1 caracter")
        try:
            return _unicodedata.decimal(c)
        except ValueError as e:
            raise _err(line, col, f"unicodedata::decimal: {e}")
    exports["decimal"] = _task(_wrap(_decimal))

    return AyceNativeBatch("unicodedata", exports)


# ──────────────────────────────────────────────────────────────────────
#  uuid
# ──────────────────────────────────────────────────────────────────────
def _build_uuid_batch():
    exports = {}

    def _uuid1(interp, args, line, col):
        _nargs(args, 0, "uuid::uuid1", line, col)
        return str(_uuid.uuid1())
    exports["uuid1"] = _task(_wrap(_uuid1))

    def _uuid4(interp, args, line, col):
        _nargs(args, 0, "uuid::uuid4", line, col)
        return str(_uuid.uuid4())
    exports["uuid4"] = _task(_wrap(_uuid4))

    def _parse(interp, args, line, col):
        _nargs(args, 1, "uuid::parse", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "uuid::parse requiere string")
        try:
            return str(_uuid.UUID(args[0]))
        except ValueError as e:
            raise _err(line, col, f"uuid::parse: {e}")
    exports["parse"] = _task(_wrap(_parse))

    return AyceNativeBatch("uuid", exports)


# ──────────────────────────────────────────────────────────────────────
#  calendar
# ──────────────────────────────────────────────────────────────────────
def _build_calendar_batch():
    exports = {}

    def _weekday(interp, args, line, col):
        _nargs(args, 3, "calendar::weekday", line, col)
        y, m, d = args
        if not all(isinstance(x, int) for x in (y, m, d)):
            raise _err(line, col, "calendar::weekday requiere ints")
        return _calendar.weekday(y, m, d)
    exports["weekday"] = _task(_wrap(_weekday))

    def _isleap(interp, args, line, col):
        _nargs(args, 1, "calendar::isleap", line, col)
        if not isinstance(args[0], int):
            raise _err(line, col, "calendar::isleap requiere int")
        return _calendar.isleap(args[0])
    exports["isleap"] = _task(_wrap(_isleap))

    def _leapdays(interp, args, line, col):
        _nargs(args, 2, "calendar::leapdays", line, col)
        y1, y2 = args
        if not (isinstance(y1, int) and isinstance(y2, int)):
            raise _err(line, col, "calendar::leapdays requiere ints")
        return _calendar.leapdays(y1, y2)
    exports["leapdays"] = _task(_wrap(_leapdays))

    def _month_name(interp, args, line, col):
        _nargs(args, (1, 2), "calendar::month_name", line, col)
        m = args[0]
        if not isinstance(m, int) or m < 1 or m > 12:
            raise _err(line, col, "calendar::month_name requiere int 1-12")
        locale = args[1] if len(args) == 2 else None
        return _calendar.month_name[m]
    exports["month_name"] = _task(_wrap(_month_name))

    def _day_name(interp, args, line, col):
        _nargs(args, 1, "calendar::day_name", line, col)
        d = args[0]
        if not isinstance(d, int) or d < 0 or d > 6:
            raise _err(line, col, "calendar::day_name requiere int 0-6")
        return _calendar.day_name[d]
    exports["day_name"] = _task(_wrap(_day_name))

    def _month_days(interp, args, line, col):
        _nargs(args, 2, "calendar::month_days", line, col)
        y, m = args
        if not (isinstance(y, int) and isinstance(m, int)):
            raise _err(line, col, "calendar::month_days requiere ints")
        return _calendar.monthrange(y, m)[1]
    exports["month_days"] = _task(_wrap(_month_days))

    return AyceNativeBatch("calendar", exports)


# ──────────────────────────────────────────────────────────────────────
#  decimal
# ──────────────────────────────────────────────────────────────────────
def _build_decimal_batch():
    exports = {}

    def _make(interp, args, line, col):
        _nargs(args, 1, "decimal::decimal", line, col)
        x = args[0]
        if not (isinstance(x, (int, float, str))):
            raise _err(line, col, "decimal::decimal requiere int/float/string")
        return str(_decimal.Decimal(str(x)))
    exports["decimal"] = _task(_wrap(_make))

    def _add(interp, args, line, col):
        _nargs(args, 2, "decimal::add", line, col)
        a, b = _decimal.Decimal(str(args[0])), _decimal.Decimal(str(args[1]))
        return str(a + b)
    exports["add"] = _task(_wrap(_add))

    def _sub(interp, args, line, col):
        _nargs(args, 2, "decimal::sub", line, col)
        a, b = _decimal.Decimal(str(args[0])), _decimal.Decimal(str(args[1]))
        return str(a - b)
    exports["sub"] = _task(_wrap(_sub))

    def _mul(interp, args, line, col):
        _nargs(args, 2, "decimal::mul", line, col)
        a, b = _decimal.Decimal(str(args[0])), _decimal.Decimal(str(args[1]))
        return str(a * b)
    exports["mul"] = _task(_wrap(_mul))

    def _div(interp, args, line, col):
        _nargs(args, 2, "decimal::div", line, col)
        a, b = _decimal.Decimal(str(args[0])), _decimal.Decimal(str(args[1]))
        if b == 0:
            raise _err(line, col, "decimal::div: división por cero")
        return str(a / b)
    exports["div"] = _task(_wrap(_div))

    ## ── Ampliación v0.6.1 ──

    def _compare(interp, args, line, col):
        _nargs(args, 2, "decimal::compare", line, col)
        a, b = _decimal.Decimal(str(args[0])), _decimal.Decimal(str(args[1]))
        if a < b:
            return -1
        if a > b:
            return 1
        return 0
    exports["compare"] = _task(_wrap(_compare))

    def _round_dp(interp, args, line, col):
        _nargs(args, (1, 2), "decimal::round_dp", line, col)
        a = _decimal.Decimal(str(args[0]))
        dp = args[1] if len(args) == 2 else 0
        if not isinstance(dp, int) or dp < 0:
            raise _err(line, col, "decimal::round_dp: dp debe ser int >= 0")
        q = _decimal.Decimal("1." + "0" * dp) if dp > 0 else _decimal.Decimal("1")
        return str(a.quantize(q, rounding=_decimal.ROUND_HALF_UP))
    exports["round_dp"] = _task(_wrap(_round_dp))

    def _abs_dec(interp, args, line, col):
        _nargs(args, 1, "decimal::abs_dec", line, col)
        return str(abs(_decimal.Decimal(str(args[0]))))
    exports["abs_dec"] = _task(_wrap(_abs_dec))

    def _neg(interp, args, line, col):
        _nargs(args, 1, "decimal::neg", line, col)
        return str(-_decimal.Decimal(str(args[0])))
    exports["neg"] = _task(_wrap(_neg))

    def _is_zero(interp, args, line, col):
        _nargs(args, 1, "decimal::is_zero", line, col)
        return _decimal.Decimal(str(args[0])) == 0
    exports["is_zero"] = _task(_wrap(_is_zero))

    def _to_float(interp, args, line, col):
        _nargs(args, 1, "decimal::to_float", line, col)
        return float(_decimal.Decimal(str(args[0])))
    exports["to_float"] = _task(_wrap(_to_float))

    def _pow_int(interp, args, line, col):
        _nargs(args, 2, "decimal::pow_int", line, col)
        a = _decimal.Decimal(str(args[0]))
        n = args[1]
        if not isinstance(n, int) or n < 0:
            raise _err(line, col, "decimal::pow_int: exponente debe ser int >= 0")
        return str(a ** n)
    exports["pow_int"] = _task(_wrap(_pow_int))

    return AyceNativeBatch("decimal", exports)


# ──────────────────────────────────────────────────────────────────────
#  fractions
# ──────────────────────────────────────────────────────────────────────
def _build_fractions_batch():
    exports = {}

    def _frac(interp, args, line, col):
        _nargs(args, (1, 2), "fractions::fraction", line, col)
        if len(args) == 1:
            x = args[0]
            if isinstance(x, str):
                return str(_fractions.Fraction(x))
            if isinstance(x, (int, float)):
                return str(_fractions.Fraction(str(x)))
            raise _err(line, col, "fractions::fraction requiere int/float/string")
        num, den = args
        if not (isinstance(num, int) and isinstance(den, int)):
            raise _err(line, col, "fractions::fraction(num, den) requiere ints")
        return str(_fractions.Fraction(num, den))
    exports["fraction"] = _task(_wrap(_frac))

    def _num(interp, args, line, col):
        _nargs(args, 1, "fractions::numerator", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "fractions::numerator requiere string (de fractions::fraction)")
        return _fractions.Fraction(args[0]).numerator
    exports["numerator"] = _task(_wrap(_num))

    def _den(interp, args, line, col):
        _nargs(args, 1, "fractions::denominator", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "fractions::denominator requiere string")
        return _fractions.Fraction(args[0]).denominator
    exports["denominator"] = _task(_wrap(_den))

    return AyceNativeBatch("fractions", exports)


# ──────────────────────────────────────────────────────────────────────
#  struct
# ──────────────────────────────────────────────────────────────────────
def _build_struct_batch():
    exports = {}

    def _pack(interp, args, line, col):
        _nargs(args, (2,), "struct::pack", line, col)
        fmt = args[0]
        if not _xa_is_str(fmt):
            raise _err(line, col, "struct::pack requiere (string fmt, ...valores)")
        vals = args[1:]
        return _struct.pack(fmt, *vals)
    exports["pack"] = _task(_wrap(_pack))

    def _unpack(interp, args, line, col):
        _nargs(args, 2, "struct::unpack", line, col)
        fmt, data = args[0], args[1]
        if not _xa_is_str(fmt):
            raise _err(line, col, "struct::unpack requiere (string fmt, bytes data)")
        if _xa_is_str(data):
            data = data.encode("latin-1")
        return _to_ayce(list(_struct.unpack(fmt, data)))
    exports["unpack"] = _task(_wrap(_unpack))

    return AyceNativeBatch("struct", exports)


# ──────────────────────────────────────────────────────────────────────
#  glob
# ──────────────────────────────────────────────────────────────────────
def _build_glob_batch():
    exports = {}

    def _glob_task(interp, args, line, col):
        _nargs(args, (1, 2), "glob::glob", line, col)
        pattern = args[0]
        recursive = args[1] if len(args) == 2 else False
        if not _xa_is_str(pattern):
            raise _err(line, col, "glob::glob requiere string")
        return _to_ayce(_glob.glob(pattern, recursive=recursive))
    exports["glob"] = _task(_wrap(_glob_task))

    def _iglob_task(interp, args, line, col):
        _nargs(args, (1, 2), "glob::iglob", line, col)
        pattern = args[0]
        recursive = args[1] if len(args) == 2 else False
        if not _xa_is_str(pattern):
            raise _err(line, col, "glob::iglob requiere string")
        return _to_ayce(list(_glob.iglob(pattern, recursive=recursive)))
    exports["iglob"] = _task(_wrap(_iglob_task))

    return AyceNativeBatch("glob", exports)


# ──────────────────────────────────────────────────────────────────────
#  tempfile
# ──────────────────────────────────────────────────────────────────────
def _build_tempfile_batch():
    exports = {}

    def _mktemp(interp, args, line, col):
        _nargs(args, (0, 1), "tempfile::mktemp", line, col)
        suffix = args[0] if args else ".tmp"
        if not _xa_is_str(suffix):
            raise _err(line, col, "tempfile::mktemp requiere string suffix")
        return _tempfile.mktemp(suffix=suffix)
    exports["mktemp"] = _task(_wrap(_mktemp))

    def _mkdtemp(interp, args, line, col):
        _nargs(args, 0, "tempfile::mkdtemp", line, col)
        return _tempfile.mkdtemp()
    exports["mkdtemp"] = _task(_wrap(_mkdtemp))

    def _gettempdir(interp, args, line, col):
        _nargs(args, 0, "tempfile::gettempdir", line, col)
        return _tempfile.gettempdir()
    exports["gettempdir"] = _task(_wrap(_gettempdir))

    return AyceNativeBatch("tempfile", exports)


# ──────────────────────────────────────────────────────────────────────
#  shutil
# ──────────────────────────────────────────────────────────────────────
def _build_shutil_batch():
    exports = {}

    def _copy(interp, args, line, col):
        _nargs(args, 2, "shutil::copy", line, col)
        if not (_xa_is_str(args[0]) and _xa_is_str(args[1])):
            raise _err(line, col, "shutil::copy requiere strings")
        try:
            _shutil.copy(args[0], args[1])
            return None
        except OSError as e:
            raise _err(line, col, f"shutil::copy: {e}")
    exports["copy"] = _task(_wrap(_copy))

    def _copy2(interp, args, line, col):
        _nargs(args, 2, "shutil::copy2", line, col)
        if not (_xa_is_str(args[0]) and _xa_is_str(args[1])):
            raise _err(line, col, "shutil::copy2 requiere strings")
        _shutil.copy2(args[0], args[1])
        return None
    exports["copy2"] = _task(_wrap(_copy2))

    def _move(interp, args, line, col):
        _nargs(args, 2, "shutil::move", line, col)
        if not (_xa_is_str(args[0]) and _xa_is_str(args[1])):
            raise _err(line, col, "shutil::move requiere strings")
        _shutil.move(args[0], args[1])
        return None
    exports["move"] = _task(_wrap(_move))

    def _rmtree(interp, args, line, col):
        _nargs(args, 1, "shutil::rmtree", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "shutil::rmtree requiere string")
        _shutil.rmtree(args[0])
        return None
    exports["rmtree"] = _task(_wrap(_rmtree))

    def _disk_usage(interp, args, line, col):
        _nargs(args, 1, "shutil::disk_usage", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "shutil::disk_usage requiere string")
        u = _shutil.disk_usage(args[0])
        return _to_ayce({"total": u.total, "used": u.used, "free": u.free})
    exports["disk_usage"] = _task(_wrap(_disk_usage))

    def _which(interp, args, line, col):
        _nargs(args, 1, "shutil::which", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "shutil::which requiere string")
        r = _shutil.which(args[0])
        return r if r else ""
    exports["which"] = _task(_wrap(_which))

    return AyceNativeBatch("shutil", exports)


# ──────────────────────────────────────────────────────────────────────
#  pprint
# ──────────────────────────────────────────────────────────────────────
def _build_pprint_batch():
    exports = {}

    def _pformat(interp, args, line, col):
        _nargs(args, (1, 2), "pprint::format", line, col)
        val = _from_ayce(args[0])
        width = args[1] if len(args) == 2 else 80
        return _pprint.pformat(val, width=width)
    exports["format"] = _task(_wrap(_pformat))

    def _pprint_print(interp, args, line, col):
        _nargs(args, (1, 2), "pprint::print", line, col)
        val = _from_ayce(args[0])
        width = args[1] if len(args) == 2 else 80
        _pprint.pprint(val, width=width)
        return None
    exports["print"] = _task(_wrap(_pprint_print))

    return AyceNativeBatch("pprint", exports)


# ──────────────────────────────────────────────────────────────────────
#  traceback
# ──────────────────────────────────────────────────────────────────────
def _build_traceback_batch():
    exports = {}

    def _format_exc(interp, args, line, col):
        _nargs(args, 0, "traceback::format_exc", line, col)
        return _traceback.format_exc()
    exports["format_exc"] = _task(_wrap(_format_exc))

    def _format_stack(interp, args, line, col):
        _nargs(args, 0, "traceback::format_stack", line, col)
        return _to_ayce(_traceback.format_stack())
    exports["format_stack"] = _task(_wrap(_format_stack))

    return AyceNativeBatch("traceback", exports)


# ──────────────────────────────────────────────────────────────────────
#  warnings
# ──────────────────────────────────────────────────────────────────────
def _build_warnings_batch():
    exports = {}

    def _warn(interp, args, line, col):
        _nargs(args, (1, 2), "warnings::warn", line, col)
        msg = args[0]
        if not _xa_is_str(msg):
            raise _err(line, col, "warnings::warn requiere string")
        category_name = args[1] if len(args) == 2 else "UserWarning"
        cat_map = {
            "UserWarning": _builtins.UserWarning,
            "DeprecationWarning": _builtins.DeprecationWarning,
            "RuntimeWarning": _builtins.RuntimeWarning,
            "SyntaxWarning": _builtins.SyntaxWarning,
            "FutureWarning": _builtins.FutureWarning,
        }
        cat = cat_map.get(category_name, _builtins.UserWarning)
        _warnings.warn(msg, cat)
        return None
    exports["warn"] = _task(_wrap(_warn))

    return AyceNativeBatch("warnings", exports)


# ──────────────────────────────────────────────────────────────────────
#  platform
# ──────────────────────────────────────────────────────────────────────
def _build_platform_batch():
    exports = {}

    def _system(interp, args, line, col):
        _nargs(args, 0, "platform::system", line, col)
        return _platform.system()
    exports["system"] = _task(_wrap(_system))

    def _release(interp, args, line, col):
        _nargs(args, 0, "platform::release", line, col)
        return _platform.release()
    exports["release"] = _task(_wrap(_release))

    def _version(interp, args, line, col):
        _nargs(args, 0, "platform::version", line, col)
        return _platform.version()
    exports["version"] = _task(_wrap(_version))

    def _machine(interp, args, line, col):
        _nargs(args, 0, "platform::machine", line, col)
        return _platform.machine()
    exports["machine"] = _task(_wrap(_machine))

    def _processor(interp, args, line, col):
        _nargs(args, 0, "platform::processor", line, col)
        return _platform.processor()
    exports["processor"] = _task(_wrap(_processor))

    def _python_version(interp, args, line, col):
        _nargs(args, 0, "platform::python_version", line, col)
        return _platform.python_version()
    exports["python_version"] = _task(_wrap(_python_version))

    def _uname(interp, args, line, col):
        _nargs(args, 0, "platform::uname", line, col)
        u = _platform.uname()
        return _to_ayce({
            "system": u.system,
            "node": u.node,
            "release": u.release,
            "version": u.version,
            "machine": u.machine,
            "processor": u.processor,
        })
    exports["uname"] = _task(_wrap(_uname))

    return AyceNativeBatch("platform", exports)


# ──────────────────────────────────────────────────────────────────────
#  codecs
# ──────────────────────────────────────────────────────────────────────
def _build_codecs_batch():
    exports = {}

    def _encode(interp, args, line, col):
        _nargs(args, (2, 3), "codecs::encode", line, col)
        s, encoding = args[0], args[1]
        errors = args[2] if len(args) == 3 else "strict"
        if not (_xa_is_str(s) and _xa_is_str(encoding)):
            raise _err(line, col, "codecs::encode requiere (string, string encoding)")
        result = _codecs.encode(s, encoding, errors)
        if isinstance(result, bytes):
            return result.decode("latin-1")
        return result
    exports["encode"] = _task(_wrap(_encode))

    def _decode(interp, args, line, col):
        _nargs(args, (2, 3), "codecs::decode", line, col)
        s, encoding = args[0], args[1]
        errors = args[2] if len(args) == 3 else "strict"
        if not (_xa_is_str(s) and _xa_is_str(encoding)):
            raise _err(line, col, "codecs::decode requiere (string, string encoding)")
        if isinstance(s, str):
            data = s.encode("latin-1")
        else:
            data = s
        result = _codecs.decode(data, encoding, errors)
        if isinstance(result, bytes):
            return result.decode("utf-8", errors="replace")
        return result
    exports["decode"] = _task(_wrap(_decode))

    return AyceNativeBatch("codecs", exports)


# ──────────────────────────────────────────────────────────────────────
#  locale
# ──────────────────────────────────────────────────────────────────────
def _build_locale_batch():
    exports = {}

    def _getlocale(interp, args, line, col):
        _nargs(args, 0, "locale::getlocale", line, col)
        return _to_ayce(list(_locale.getlocale()))
    exports["getlocale"] = _task(_wrap(_getlocale))

    def _getpreferredencoding(interp, args, line, col):
        _nargs(args, 0, "locale::getpreferredencoding", line, col)
        return _locale.getpreferredencoding()
    exports["getpreferredencoding"] = _task(_wrap(_getpreferredencoding))

    def _setlocale(interp, args, line, col):
        _nargs(args, (1, 2), "locale::setlocale", line, col)
        category = args[0] if args else _locale.LC_ALL
        loc = args[1] if len(args) == 2 else ""
        return _locale.setlocale(category, loc)
    exports["setlocale"] = _task(_wrap(_setlocale))

    exports["LC_ALL"] = _const(_locale.LC_ALL)
    exports["LC_TIME"] = _const(_locale.LC_TIME)
    exports["LC_NUMERIC"] = _const(_locale.LC_NUMERIC)

    return AyceNativeBatch("locale", exports)


# ──────────────────────────────────────────────────────────────────────
#  subprocess
# ──────────────────────────────────────────────────────────────────────
def _build_subprocess_batch():
    exports = {}

    def _run(interp, args, line, col):
        _nargs(args, 1, "subprocess::run", line, col)
        cmd = args[0]
        if _xa_is_str(cmd):
            cmd = cmd.split()
        elif _xa_is_list(cmd):
            cmd = _to_py_list(cmd)
        else:
            raise _err(line, col, "subprocess::run requiere string o lista")
        try:
            r = _subprocess.run(cmd, capture_output=True, text=True)
            return _to_ayce({
                "returncode": r.returncode,
                "stdout": r.stdout,
                "stderr": r.stderr,
            })
        except FileNotFoundError as e:
            raise _err(line, col, f"subprocess::run: {e}")
    exports["run"] = _task(_wrap(_run))

    def _output(interp, args, line, col):
        _nargs(args, 1, "subprocess::output", line, col)
        cmd = args[0]
        if _xa_is_str(cmd):
            cmd = cmd.split()
        elif _xa_is_list(cmd):
            cmd = _to_py_list(cmd)
        try:
            return _subprocess.check_output(cmd, text=True)
        except (_subprocess.CalledProcessError, FileNotFoundError) as e:
            raise _err(line, col, f"subprocess::output: {e}")
    exports["output"] = _task(_wrap(_output))

    return AyceNativeBatch("subprocess", exports)


# ──────────────────────────────────────────────────────────────────────
#  logging
# ──────────────────────────────────────────────────────────────────────
def _build_logging_batch():
    exports = {}

    _logging.basicConfig(level=_logging.INFO)
    _log = _logging.getLogger("ayce")

    def _debug(interp, args, line, col):
        _nargs(args, 1, "logging::debug", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "logging::debug requiere string")
        _log.debug(args[0])
        return None
    exports["debug"] = _task(_wrap(_debug))

    def _info(interp, args, line, col):
        _nargs(args, 1, "logging::info", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "logging::info requiere string")
        _log.info(args[0])
        return None
    exports["info"] = _task(_wrap(_info))

    def _warning(interp, args, line, col):
        _nargs(args, 1, "logging::warning", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "logging::warning requiere string")
        _log.warning(args[0])
        return None
    exports["warning"] = _task(_wrap(_warning))

    def _error(interp, args, line, col):
        _nargs(args, 1, "logging::error", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "logging::error requiere string")
        _log.error(args[0])
        return None
    exports["error"] = _task(_wrap(_error))

    def _critical(interp, args, line, col):
        _nargs(args, 1, "logging::critical", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "logging::critical requiere string")
        _log.critical(args[0])
        return None
    exports["critical"] = _task(_wrap(_critical))

    return AyceNativeBatch("logging", exports)


# ──────────────────────────────────────────────────────────────────────
#  threading
# ──────────────────────────────────────────────────────────────────────
def _build_threading_batch():
    exports = {}

    def _current_thread(interp, args, line, col):
        _nargs(args, 0, "threading::current_thread", line, col)
        return _threading.current_thread().name
    exports["current_thread"] = _task(_wrap(_current_thread))

    def _active_count(interp, args, line, col):
        _nargs(args, 0, "threading::active_count", line, col)
        return _threading.active_count()
    exports["active_count"] = _task(_wrap(_active_count))

    def _enumerate(interp, args, line, col):
        _nargs(args, 0, "threading::enumerate", line, col)
        return _to_ayce([t.name for t in _threading.enumerate()])
    exports["enumerate"] = _task(_wrap(_enumerate))

    return AyceNativeBatch("threading", exports)


# ──────────────────────────────────────────────────────────────────────
#  queue
# ──────────────────────────────────────────────────────────────────────
def _build_queue_batch():
    exports = {}

    def _create(interp, args, line, col):
        _nargs(args, (0, 1), "queue::create", line, col)
        maxsize = args[0] if args else 0
        # Devolvemos un dict que actúa como cola
        return _to_ayce({"_q": [], "_max": maxsize})
    exports["create"] = _task(_wrap(_create))

    def _put(interp, args, line, col):
        _nargs(args, 2, "queue::put", line, col)
        if not _xa_is_dict(args[0]):
            raise _err(line, col, "queue::put requiere cola (de queue::create)")
        q = args[0].pairs
        if "_q" not in q:
            raise _err(line, col, "queue::put: cola inválida")
        q["_q"].elements.append(args[1])
        return None
    exports["put"] = _task(_wrap(_put))

    def _get(interp, args, line, col):
        _nargs(args, 1, "queue::get", line, col)
        if not _xa_is_dict(args[0]):
            raise _err(line, col, "queue::get requiere cola")
        q = args[0].pairs
        if "_q" not in q or not q["_q"].elements:
            raise _err(line, col, "queue::get: cola vacía")
        return q["_q"].elements.pop(0)
    exports["get"] = _task(_wrap(_get))

    def _size(interp, args, line, col):
        _nargs(args, 1, "queue::size", line, col)
        if not _xa_is_dict(args[0]):
            raise _err(line, col, "queue::size requiere cola")
        q = args[0].pairs
        if "_q" not in q:
            return 0
        return len(q["_q"].elements)
    exports["size"] = _task(_wrap(_size))

    return AyceNativeBatch("queue", exports)


# ──────────────────────────────────────────────────────────────────────
#  types
# ──────────────────────────────────────────────────────────────────────
def _build_types_batch():
    exports = {}

    def _is_int_t(interp, args, line, col):
        _nargs(args, 1, "types::is_int", line, col)
        return isinstance(args[0], int) and not isinstance(args[0], bool)
    exports["is_int"] = _task(_wrap(_is_int_t))

    def _is_float_t(interp, args, line, col):
        _nargs(args, 1, "types::is_float", line, col)
        return isinstance(args[0], float)
    exports["is_float"] = _task(_wrap(_is_float_t))

    def _is_str_t(interp, args, line, col):
        _nargs(args, 1, "types::is_str", line, col)
        return _xa_is_str(args[0])
    exports["is_str"] = _task(_wrap(_is_str_t))

    def _is_bool_t(interp, args, line, col):
        _nargs(args, 1, "types::is_bool", line, col)
        return isinstance(args[0], bool)
    exports["is_bool"] = _task(_wrap(_is_bool_t))

    def _is_list_t(interp, args, line, col):
        _nargs(args, 1, "types::is_list", line, col)
        return _xa_is_list(args[0])
    exports["is_list"] = _task(_wrap(_is_list_t))

    def _is_dict_t(interp, args, line, col):
        _nargs(args, 1, "types::is_dict", line, col)
        return _xa_is_dict(args[0])
    exports["is_dict"] = _task(_wrap(_is_dict_t))

    def _is_set_t(interp, args, line, col):
        _nargs(args, 1, "types::is_set", line, col)
        return _xa_is_set(args[0])
    exports["is_set"] = _task(_wrap(_is_set_t))

    def _is_tuple_t(interp, args, line, col):
        _nargs(args, 1, "types::is_tuple", line, col)
        return _xa_is_tuple(args[0])
    exports["is_tuple"] = _task(_wrap(_is_tuple_t))

    def _is_none_t(interp, args, line, col):
        _nargs(args, 1, "types::is_none", line, col)
        return args[0] is None
    exports["is_none"] = _task(_wrap(_is_none_t))

    return AyceNativeBatch("types", exports)


# ──────────────────────────────────────────────────────────────────────
#  zipfile
# ──────────────────────────────────────────────────────────────────────
def _build_zipfile_batch():
    exports = {}

    def _list(interp, args, line, col):
        _nargs(args, 1, "zipfile::list", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "zipfile::list requiere string path")
        try:
            with _zipfile.ZipFile(args[0], "r") as z:
                return _to_ayce(z.namelist())
        except Exception as e:
            raise _err(line, col, f"zipfile::list: {e}")
    exports["list"] = _task(_wrap(_list))

    def _extract_all(interp, args, line, col):
        _nargs(args, (1, 2), "zipfile::extract_all", line, col)
        path = args[0]
        dest = args[1] if len(args) == 2 else "."
        if not (_xa_is_str(path) and _xa_is_str(dest)):
            raise _err(line, col, "zipfile::extract_all requiere strings")
        try:
            with _zipfile.ZipFile(path, "r") as z:
                z.extractall(dest)
            return None
        except Exception as e:
            raise _err(line, col, f"zipfile::extract_all: {e}")
    exports["extract_all"] = _task(_wrap(_extract_all))

    def _create(interp, args, line, col):
        _nargs(args, 2, "zipfile::create", line, col)
        zip_path, files = args[0], args[1]
        if not _xa_is_str(zip_path) or not _xa_is_list(files):
            raise _err(line, col, "zipfile::create requiere (string zip_path, lista files)")
        try:
            with _zipfile.ZipFile(zip_path, "w") as z:
                for f in _to_py_list(files):
                    z.write(f)
            return None
        except Exception as e:
            raise _err(line, col, f"zipfile::create: {e}")
    exports["create"] = _task(_wrap(_create))

    def _read(interp, args, line, col):
        _nargs(args, 2, "zipfile::read", line, col)
        zip_path, member = args[0], args[1]
        if not (_xa_is_str(zip_path) and _xa_is_str(member)):
            raise _err(line, col, "zipfile::read requiere strings")
        try:
            with _zipfile.ZipFile(zip_path, "r") as z:
                return z.read(member).decode("utf-8")
        except Exception as e:
            raise _err(line, col, f"zipfile::read: {e}")
    exports["read"] = _task(_wrap(_read))

    return AyceNativeBatch("zipfile", exports)


# ──────────────────────────────────────────────────────────────────────
#  gzip / bz2 / lzma / zlib
# ──────────────────────────────────────────────────────────────────────
def _compress_batch(name, compress_fn, decompress_fn):
    exports = {}

    def _compress(interp, args, line, col):
        _nargs(args, 1, f"{name}::compress", line, col)
        data = args[0]
        if _xa_is_str(data):
            data = data.encode("utf-8")
        elif not isinstance(data, bytes):
            raise _err(line, col, f"{name}::compress requiere string o bytes")
        return compress_fn(data).decode("latin-1")
    exports["compress"] = _task(_wrap(_compress))

    def _decompress(interp, args, line, col):
        _nargs(args, 1, f"{name}::decompress", line, col)
        data = args[0]
        if _xa_is_str(data):
            data = data.encode("latin-1")
        elif not isinstance(data, bytes):
            raise _err(line, col, f"{name}::decompress requiere string o bytes")
        try:
            return decompress_fn(data).decode("utf-8")
        except Exception as e:
            raise _err(line, col, f"{name}::decompress: {e}")
    exports["decompress"] = _task(_wrap(_decompress))

    return AyceNativeBatch(name, exports)


# ──────────────────────────────────────────────────────────────────────
#  pickle
# ──────────────────────────────────────────────────────────────────────
def _build_pickle_batch():
    exports = {}

    def _dumps(interp, args, line, col):
        _nargs(args, 1, "pickle::dumps", line, col)
        return _pickle.dumps(_from_ayce(args[0])).hex()
    exports["dumps"] = _task(_wrap(_dumps))

    def _loads(interp, args, line, col):
        _nargs(args, 1, "pickle::loads", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "pickle::loads requiere string hex")
        try:
            return _to_ayce(_pickle.loads(bytes.fromhex(args[0])))
        except Exception as e:
            raise _err(line, col, f"pickle::loads: {e}")
    exports["loads"] = _task(_wrap(_loads))

    return AyceNativeBatch("pickle", exports)


# ──────────────────────────────────────────────────────────────────────
#  sqlite3
# ──────────────────────────────────────────────────────────────────────
def _build_sqlite3_batch():
    exports = {}

    def _connect(interp, args, line, col):
        _nargs(args, 1, "sqlite3::connect", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "sqlite3::connect requiere string path")
        try:
            conn = _sqlite3.connect(args[0])
            return conn  # devuelve la conexión Python pura
        except Exception as e:
            raise _err(line, col, f"sqlite3::connect: {e}")
    exports["connect"] = _task(_wrap(_connect))

    def _execute(interp, args, line, col):
        _nargs(args, (2, 3), "sqlite3::execute", line, col)
        conn, sql = args[0], args[1]
        params = args[2] if len(args) == 3 else []
        if not (_xa_is_str(sql)):
            raise _err(line, col, "sqlite3::execute: sql debe ser string")
        if _xa_is_list(params):
            params = _to_py_list(params)
        try:
            cur = conn.execute(sql, params)
            rows = cur.fetchall()
            conn.commit()
            return _to_ayce([list(r) for r in rows])
        except Exception as e:
            raise _err(line, col, f"sqlite3::execute: {e}")
    exports["execute"] = _task(_wrap(_execute))

    def _close(interp, args, line, col):
        _nargs(args, 1, "sqlite3::close", line, col)
        args[0].close()
        return None
    exports["close"] = _task(_wrap(_close))

    return AyceNativeBatch("sqlite3", exports)


# ──────────────────────────────────────────────────────────────────────
#  urllib (parse)
# ──────────────────────────────────────────────────────────────────────
def _build_urllib_batch():
    exports = {}

    def _parse_url(interp, args, line, col):
        _nargs(args, 1, "urllib::parse", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "urllib::parse requiere string")
        p = _urlparse.urlparse(args[0])
        return _to_ayce({
            "scheme": p.scheme,
            "netloc": p.netloc,
            "path": p.path,
            "params": p.params,
            "query": p.query,
            "fragment": p.fragment,
        })
    exports["parse"] = _task(_wrap(_parse_url))

    def _urlencode(interp, args, line, col):
        _nargs(args, 1, "urllib::urlencode", line, col)
        if not _xa_is_dict(args[0]):
            raise _err(line, col, "urllib::urlencode requiere dict")
        return _urlparse.urlencode(_to_py_dict(args[0]))
    exports["urlencode"] = _task(_wrap(_urlencode))

    def _quote(interp, args, line, col):
        _nargs(args, 1, "urllib::quote", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "urllib::quote requiere string")
        return _urlparse.quote(args[0])
    exports["quote"] = _task(_wrap(_quote))

    def _unquote(interp, args, line, col):
        _nargs(args, 1, "urllib::unquote", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "urllib::unquote requiere string")
        return _urlparse.unquote(args[0])
    exports["unquote"] = _task(_wrap(_unquote))

    ## ── Ampliación v0.6.1 ──

    def _urlopen(interp, args, line, col):
        _nargs(args, (1, 2), "urllib::urlopen", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "urllib::urlopen requiere string url")
        headers = _to_py_dict(args[1]) if len(args) == 2 and _xa_is_dict(args[1]) else {}
        import http.client as _hc
        p = _urlparse.urlparse(args[0])
        if not p.scheme or not p.netloc:
            raise _err(line, col, f"urllib::urlopen: URL inválida: {args[0]}")
        cls = _hc.HTTPSConnection if p.scheme == "https" else _hc.HTTPConnection
        try:
            conn = cls(p.netloc, timeout=15)
            conn.request("GET", p.path or "/", headers=headers)
            resp = conn.getresponse()
            body = resp.read().decode("utf-8", errors="replace")
            out = {
                "status": resp.status,
                "reason": resp.reason,
                "body": body,
                "headers": {k.lower(): v for k, v in resp.getheaders()},
            }
            conn.close()
        except Exception as e:
            raise _err(line, col, f"urllib::urlopen: {e}")
        return _to_ayce(out)
    exports["urlopen"] = _task(_wrap(_urlopen))

    def _parse_qs(interp, args, line, col):
        _nargs(args, 1, "urllib::parse_qs", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "urllib::parse_qs requiere string query")
        pairs = _urlparse.parse_qsl(args[0])
        out = {}
        for k, v in pairs:
            if k in out:
                # valor repetido → lista
                existing = out[k]
                if isinstance(existing, list):
                    existing.append(v)
                else:
                    out[k] = [existing, v]
            else:
                out[k] = v
        return _to_ayce(out)
    exports["parse_qs"] = _task(_wrap(_parse_qs))

    def _join(interp, args, line, col):
        _nargs(args, 2, "urllib::join", line, col)
        if not (_xa_is_str(args[0]) and _xa_is_str(args[1])):
            raise _err(line, col, "urllib::join requiere (string base, string path)")
        try:
            return _urlparse.urljoin(args[0], args[1])
        except Exception as e:
            raise _err(line, col, f"urllib::join: {e}")
    exports["join"] = _task(_wrap(_join))

    return AyceNativeBatch("urllib", exports)


# ──────────────────────────────────────────────────────────────────────
#  array (genérico)
# ──────────────────────────────────────────────────────────────────────
def _build_array_batch():
    exports = {}

    def _make(interp, args, line, col):
        _nargs(args, 1, "array::make", line, col)
        seq = _to_py_list(args[0]) if _xa_is_list(args[0]) else args[0]
        return _to_ayce(list(seq))
    exports["make"] = _task(_wrap(_make))

    return AyceNativeBatch("array", exports)


# ──────────────────────────────────────────────────────────────────────
#  Punto de entrada
# ──────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────
#  stat — información de archivos (equivalente al módulo stat de Python)
# ──────────────────────────────────────────────────────────────────────
def _build_stat_batch():
    exports = {}

    exports["S_IFDIR"] = _const(_stat_mod.S_IFDIR)
    exports["S_IFREG"] = _const(_stat_mod.S_IFREG)
    exports["S_IFLNK"] = _const(_stat_mod.S_IFLNK)
    exports["S_IRUSR"] = _const(_stat_mod.S_IRUSR)
    exports["S_IWUSR"] = _const(_stat_mod.S_IWUSR)
    exports["S_IXUSR"] = _const(_stat_mod.S_IXUSR)

    def _st(interp, args, line, col):
        _nargs(args, 1, "stat::stat", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "stat::stat requiere string path")
        try:
            s = _os.stat(args[0])
        except FileNotFoundError:
            raise _err(line, col, f"stat::stat: archivo no encontrado: {args[0]}")
        except Exception as e:
            raise _err(line, col, f"stat::stat: {e}")
        return _to_ayce({
            "size": s.st_size,
            "mode": s.st_mode,
            "mtime": s.st_mtime,
            "ctime": s.st_ctime,
            "atime": s.st_atime,
            "is_dir": _stat_mod.S_ISDIR(s.st_mode),
            "is_file": _stat_mod.S_ISREG(s.st_mode),
            "is_link": _stat_mod.S_ISLNK(s.st_mode),
        })
    exports["stat"] = _task(_wrap(_st))

    def _mode_str(interp, args, line, col):
        _nargs(args, 1, "stat::mode_str", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "stat::mode_str requiere string path")
        try:
            s = _os.stat(args[0])
        except FileNotFoundError:
            raise _err(line, col, f"stat::mode_str: archivo no encontrado: {args[0]}")
        m = _stat_mod.S_IMODE(s.st_mode)
        out = ""
        for shift, chars in ((6, "rwx"), (3, "rwx"), (0, "rwx")):
            bits = (m >> shift) & 7
            for i, c in enumerate(chars):
                out += c if bits & (4 >> i) else "-"
        return out
    exports["mode_str"] = _task(_wrap(_mode_str))

    def _is_dir(interp, args, line, col):
        _nargs(args, 1, "stat::is_dir", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "stat::is_dir requiere string path")
        return _os.path.isdir(args[0])
    exports["is_dir"] = _task(_wrap(_is_dir))

    def _is_file(interp, args, line, col):
        _nargs(args, 1, "stat::is_file", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "stat::is_file requiere string path")
        return _os.path.isfile(args[0])
    exports["is_file"] = _task(_wrap(_is_file))

    def _is_link(interp, args, line, col):
        _nargs(args, 1, "stat::is_link", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "stat::is_link requiere string path")
        return _os.path.islink(args[0])
    exports["is_link"] = _task(_wrap(_is_link))

    def _size(interp, args, line, col):
        _nargs(args, 1, "stat::size", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "stat::size requiere string path")
        try:
            return _os.path.getsize(args[0])
        except FileNotFoundError:
            raise _err(line, col, f"stat::size: archivo no encontrado: {args[0]}")
    exports["size"] = _task(_wrap(_size))

    def _mtime(interp, args, line, col):
        _nargs(args, 1, "stat::mtime", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "stat::mtime requiere string path")
        try:
            return _os.path.getmtime(args[0])
        except FileNotFoundError:
            raise _err(line, col, f"stat::mtime: archivo no encontrado: {args[0]}")
    exports["mtime"] = _task(_wrap(_mtime))

    return AyceNativeBatch("stat", exports)


# ──────────────────────────────────────────────────────────────────────
#  tarfile — archivos TAR (crear, listar, extraer)
# ──────────────────────────────────────────────────────────────────────
def _build_tarfile_batch():
    exports = {}

    def _create(interp, args, line, col):
        _nargs(args, 2, "tarfile::create", line, col)
        tar_path, files = args[0], args[1]
        if not _xa_is_str(tar_path):
            raise _err(line, col, "tarfile::create requiere string tar_path")
        if not _xa_is_list(files):
            raise _err(line, col, "tarfile::create requiere lista de archivos")
        try:
            with _tarfile.open(tar_path, "w") as tf:
                for f in _to_py_list(files):
                    if not _xa_is_str(f):
                        raise _err(line, col, "tarfile::create: los archivos deben ser strings")
                    tf.add(f, arcname=_opath.basename(f))
        except Exception as e:
            raise _err(line, col, f"tarfile::create: {e}")
        return None
    exports["create"] = _task(_wrap(_create))

    def _create_gz(interp, args, line, col):
        _nargs(args, 2, "tarfile::create_gz", line, col)
        tar_path, files = args[0], args[1]
        if not _xa_is_str(tar_path):
            raise _err(line, col, "tarfile::create_gz requiere string tar_path")
        if not _xa_is_list(files):
            raise _err(line, col, "tarfile::create_gz requiere lista de archivos")
        try:
            with _tarfile.open(tar_path, "w:gz") as tf:
                for f in _to_py_list(files):
                    if not _xa_is_str(f):
                        raise _err(line, col, "tarfile::create_gz: los archivos deben ser strings")
                    tf.add(f, arcname=_opath.basename(f))
        except Exception as e:
            raise _err(line, col, f"tarfile::create_gz: {e}")
        return None
    exports["create_gz"] = _task(_wrap(_create_gz))

    def _list(interp, args, line, col):
        _nargs(args, 1, "tarfile::list", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "tarfile::list requiere string tar_path")
        try:
            with _tarfile.open(args[0], "r") as tf:
                entries = []
                for m in tf.getmembers():
                    entries.append({
                        "name": m.name,
                        "size": m.size,
                        "is_dir": m.isdir(),
                        "is_file": m.isfile(),
                        "mtime": m.mtime,
                    })
        except Exception as e:
            raise _err(line, col, f"tarfile::list: {e}")
        return _to_ayce(entries)
    exports["list"] = _task(_wrap(_list))

    def _extract(interp, args, line, col):
        _nargs(args, (1, 2), "tarfile::extract", line, col)
        tar_path = args[0]
        dest = args[1] if len(args) == 2 else "."
        if not (_xa_is_str(tar_path) and _xa_is_str(dest)):
            raise _err(line, col, "tarfile::extract requiere strings")
        try:
            with _tarfile.open(tar_path, "r") as tf:
                tf.extractall(dest)
        except Exception as e:
            raise _err(line, col, f"tarfile::extract: {e}")
        return None
    exports["extract"] = _task(_wrap(_extract))

    def _read(interp, args, line, col):
        _nargs(args, 2, "tarfile::read", line, col)
        tar_path, member = args[0], args[1]
        if not (_xa_is_str(tar_path) and _xa_is_str(member)):
            raise _err(line, col, "tarfile::read requiere strings")
        try:
            with _tarfile.open(tar_path, "r") as tf:
                f = tf.extractfile(member)
                if f is None:
                    raise _err(line, col, f"tarfile::read: no es un archivo: {member}")
                return f.read().decode("utf-8", errors="replace")
        except AyceRuntimeError:
            raise
        except Exception as e:
            raise _err(line, col, f"tarfile::read: {e}")
    exports["read"] = _task(_wrap(_read))

    return AyceNativeBatch("tarfile", exports)


# ──────────────────────────────────────────────────────────────────────
#  binascii — conversiones binarias (hex, base64, crc32)
# ──────────────────────────────────────────────────────────────────────
def _build_binascii_batch():
    exports = {}

    def _hexlify(interp, args, line, col):
        _nargs(args, 1, "binascii::hexlify", line, col)
        data = args[0]
        if _xa_is_str(data):
            data = data.encode("utf-8")
        elif not isinstance(data, bytes):
            raise _err(line, col, "binascii::hexlify requiere string o bytes")
        return _binascii.hexlify(data).decode("ascii")
    exports["hexlify"] = _task(_wrap(_hexlify))

    def _unhexlify(interp, args, line, col):
        _nargs(args, 1, "binascii::unhexlify", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "binascii::unhexlify requiere string hex")
        try:
            raw = _binascii.unhexlify(args[0])
        except Exception as e:
            raise _err(line, col, f"binascii::unhexlify: {e}")
        return raw.decode("utf-8", errors="replace")
    exports["unhexlify"] = _task(_wrap(_unhexlify))

    def _a2b_base64(interp, args, line, col):
        _nargs(args, 1, "binascii::a2b_base64", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "binascii::a2b_base64 requiere string")
        try:
            raw = _binascii.a2b_base64(args[0].encode("ascii"))
        except Exception as e:
            raise _err(line, col, f"binascii::a2b_base64: {e}")
        return raw.decode("utf-8", errors="replace")
    exports["a2b_base64"] = _task(_wrap(_a2b_base64))

    def _b2a_base64(interp, args, line, col):
        _nargs(args, 1, "binascii::b2a_base64", line, col)
        data = args[0]
        if _xa_is_str(data):
            data = data.encode("utf-8")
        elif not isinstance(data, bytes):
            raise _err(line, col, "binascii::b2a_base64 requiere string o bytes")
        return _binascii.b2a_base64(data).decode("ascii").rstrip("\n")
    exports["b2a_base64"] = _task(_wrap(_b2a_base64))

    def _crc32(interp, args, line, col):
        _nargs(args, 1, "binascii::crc32", line, col)
        data = args[0]
        if _xa_is_str(data):
            data = data.encode("utf-8")
        elif not isinstance(data, bytes):
            raise _err(line, col, "binascii::crc32 requiere string o bytes")
        return _binascii.crc32(data) & 0xFFFFFFFF
    exports["crc32"] = _task(_wrap(_crc32))

    def _crc_hqx(interp, args, line, col):
        _nargs(args, 2, "binascii::crc_hqx", line, col)
        data, crc = args[0], args[1]
        if _xa_is_str(data):
            data = data.encode("utf-8")
        if not isinstance(data, bytes):
            raise _err(line, col, "binascii::crc_hqx requiere string o bytes")
        if not isinstance(crc, int):
            raise _err(line, col, "binascii::crc_hqx requiere crc int")
        return _binascii.crc_hqx(data, crc)
    exports["crc_hqx"] = _task(_wrap(_crc_hqx))

    return AyceNativeBatch("binascii", exports)


# ──────────────────────────────────────────────────────────────────────
#  socket — redes TCP/UDP con handles
# ──────────────────────────────────────────────────────────────────────
def _build_socket_batch():
    exports = {}

    def _tcp_connect(interp, args, line, col):
        _nargs(args, (2, 3), "socket::tcp_connect", line, col)
        host, port = args[0], args[1]
        timeout = args[2] if len(args) == 3 else 10.0
        if not (_xa_is_str(host) and isinstance(port, int)):
            raise _err(line, col, "socket::tcp_connect requiere (string host, int port)")
        try:
            sock = _socket.create_connection((host, port), timeout=timeout)
        except Exception as e:
            raise _err(line, col, f"socket::tcp_connect: {e}")
        return sock
    exports["tcp_connect"] = _task(_wrap(_tcp_connect))

    def _send(interp, args, line, col):
        _nargs(args, 2, "socket::send", line, col)
        sock, data = args[0], args[1]
        if _xa_is_str(data):
            data = data.encode("utf-8")
        elif not isinstance(data, bytes):
            raise _err(line, col, "socket::send requiere string o bytes")
        try:
            sock.sendall(data)
        except Exception as e:
            raise _err(line, col, f"socket::send: {e}")
        return None
    exports["send"] = _task(_wrap(_send))

    def _recv(interp, args, line, col):
        _nargs(args, (1, 2), "socket::recv", line, col)
        sock = args[0]
        n = args[1] if len(args) == 2 else 4096
        if not isinstance(n, int):
            raise _err(line, col, "socket::recv requiere int bufsize")
        try:
            data = sock.recv(n)
        except Exception as e:
            raise _err(line, col, f"socket::recv: {e}")
        return data.decode("utf-8", errors="replace")
    exports["recv"] = _task(_wrap(_recv))

    def _recv_line(interp, args, line, col):
        _nargs(args, (1, 2), "socket::recv_line", line, col)
        sock = args[0]
        max_len = args[1] if len(args) == 2 else 65536
        buf = b""
        try:
            while len(buf) < max_len:
                b = sock.recv(1)
                if not b or b == b"\n":
                    break
                buf += b
        except Exception as e:
            raise _err(line, col, f"socket::recv_line: {e}")
        return buf.decode("utf-8", errors="replace").rstrip("\r")
    exports["recv_line"] = _task(_wrap(_recv_line))

    def _send_line(interp, args, line, col):
        _nargs(args, 2, "socket::send_line", line, col)
        sock, data = args[0], args[1]
        if not _xa_is_str(data):
            raise _err(line, col, "socket::send_line requiere string")
        try:
            sock.sendall((data + "\n").encode("utf-8"))
        except Exception as e:
            raise _err(line, col, f"socket::send_line: {e}")
        return None
    exports["send_line"] = _task(_wrap(_send_line))

    def _close(interp, args, line, col):
        _nargs(args, 1, "socket::close", line, col)
        try:
            args[0].close()
        except Exception:
            pass
        return None
    exports["close"] = _task(_wrap(_close))

    def _udp_send(interp, args, line, col):
        _nargs(args, 3, "socket::udp_send", line, col)
        host, port, data = args[0], args[1], args[2]
        if not (_xa_is_str(host) and isinstance(port, int)):
            raise _err(line, col, "socket::udp_send requiere (string host, int port)")
        if _xa_is_str(data):
            data = data.encode("utf-8")
        elif not isinstance(data, bytes):
            raise _err(line, col, "socket::udp_send requiere string o bytes")
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            s.sendto(data, (host, port))
            s.close()
        except Exception as e:
            raise _err(line, col, f"socket::udp_send: {e}")
        return None
    exports["udp_send"] = _task(_wrap(_udp_send))

    def _udp_recv(interp, args, line, col):
        _nargs(args, (1, 2), "socket::udp_recv", line, col)
        port = args[0]
        n = args[1] if len(args) == 2 else 4096
        if not isinstance(port, int):
            raise _err(line, col, "socket::udp_recv requiere int port")
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            s.bind(("0.0.0.0", port))
            s.settimeout(10.0)
            data, addr = s.recvfrom(n)
            s.close()
        except Exception as e:
            raise _err(line, col, f"socket::udp_recv: {e}")
        return _to_ayce({"data": data.decode("utf-8", errors="replace"),
                         "from": addr[0], "port": addr[1]})
    exports["udp_recv"] = _task(_wrap(_udp_recv))

    def _local_addr(interp, args, line, col):
        _nargs(args, 1, "socket::local_addr", line, col)
        try:
            host, port = args[0].getsockname()
        except Exception as e:
            raise _err(line, col, f"socket::local_addr: {e}")
        return _to_ayce({"host": host, "port": port})
    exports["local_addr"] = _task(_wrap(_local_addr))

    def _peer_addr(interp, args, line, col):
        _nargs(args, 1, "socket::peer_addr", line, col)
        try:
            host, port = args[0].getpeername()
        except Exception as e:
            raise _err(line, col, f"socket::peer_addr: {e}")
        return _to_ayce({"host": host, "port": port})
    exports["peer_addr"] = _task(_wrap(_peer_addr))

    return AyceNativeBatch("socket", exports)


# ──────────────────────────────────────────────────────────────────────
#  ssl — TLS sobre sockets
# ──────────────────────────────────────────────────────────────────────
def _build_ssl_batch():
    exports = {}

    exports["PROTOCOL_TLS_CLIENT"] = _const(_ssl.PROTOCOL_TLS_CLIENT)

    def _create_context(interp, args, line, col):
        _nargs(args, (0, 1), "ssl::create_context", line, col)
        insecure = args[0] if len(args) == 1 else False
        if not isinstance(insecure, bool):
            raise _err(line, col, "ssl::create_context requiere bool insecure")
        if insecure:
            ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
        else:
            ctx = _ssl.create_default_context()
        return ctx
    exports["create_context"] = _task(_wrap(_create_context))

    def _wrap_socket(interp, args, line, col):
        _nargs(args, (1, 3), "ssl::wrap_socket", line, col)
        sock = args[0]
        hostname = args[1] if len(args) >= 2 else ""
        insecure = args[2] if len(args) == 3 else False
        if not (_xa_is_str(hostname) and isinstance(insecure, bool)):
            raise _err(line, col, "ssl::wrap_socket requiere (socket, string hostname, bool insecure)")
        try:
            if insecure:
                ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
                ctx.check_hostname = False
                ctx.verify_mode = _ssl.CERT_NONE
            else:
                ctx = _ssl.create_default_context()
            return ctx.wrap_socket(sock, server_hostname=hostname or None)
        except Exception as e:
            raise _err(line, col, f"ssl::wrap_socket: {e}")
    exports["wrap_socket"] = _task(_wrap(_wrap_socket))

    def _cipher(interp, args, line, col):
        _nargs(args, 1, "ssl::cipher", line, col)
        try:
            c = args[0].cipher()
        except Exception as e:
            raise _err(line, col, f"ssl::cipher: {e}")
        if c is None:
            return None
        return _to_ayce({"name": c[0], "protocol": c[1], "bits": c[2]})
    exports["cipher"] = _task(_wrap(_cipher))

    def _cert(interp, args, line, col):
        _nargs(args, 1, "ssl::cert", line, col)
        try:
            der = args[0].getpeercert(binary_form=False)
        except Exception as e:
            raise _err(line, col, f"ssl::cert: {e}")
        if not der:
            return None
        d = {
            "subject": str(der.get("subject", "")),
            "issuer": str(der.get("issuer", "")),
            "notAfter": der.get("notAfter", ""),
            "notBefore": der.get("notBefore", ""),
        }
        return _to_ayce(d)
    exports["cert"] = _task(_wrap(_cert))

    return AyceNativeBatch("ssl", exports)


# ──────────────────────────────────────────────────────────────────────
#  http — cliente HTTP/HTTPS
# ──────────────────────────────────────────────────────────────────────
def _build_http_batch():
    exports = {}

    def _parse_url(url):
        p = _urlparse.urlparse(url)
        if not p.scheme or not p.netloc:
            raise ValueError(f"URL inválida: {url}")
        return p

    def _request(interp, args, line, col):
        _nargs(args, (1, 4), "http::request", line, col)
        method = args[0].upper() if _xa_is_str(args[0]) else None
        url = args[1]
        headers = _to_py_dict(args[2]) if len(args) >= 3 and _xa_is_dict(args[2]) else {}
        body = args[3] if len(args) == 4 else ""
        if method is None or not _xa_is_str(url) or not _xa_is_str(body):
            raise _err(line, col,
                "http::request requiere (string método, string url, [dict headers], [string body])")
        p = _parse_url(url)
        conn_cls = _httpclient.HTTPSConnection if p.scheme == "https" else _httpclient.HTTPConnection
        try:
            conn = conn_cls(p.netloc, timeout=15)
            conn.request(method, p.path or "/", body=body or None, headers=headers)
            resp = conn.getresponse()
            data = resp.read().decode("utf-8", errors="replace")
            resp_headers = {k.lower(): v for k, v in resp.getheaders()}
            status = resp.status
            reason = resp.reason
            conn.close()
        except AyceRuntimeError:
            raise
        except Exception as e:
            raise _err(line, col, f"http::request: {e}")
        return _to_ayce({"status": status, "reason": reason,
                         "headers": resp_headers, "body": data})
    exports["request"] = _task(_wrap(_request))

    def _get(interp, args, line, col):
        _nargs(args, (1, 2), "http::get", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "http::get requiere string url")
        headers = _to_py_dict(args[1]) if len(args) == 2 and _xa_is_dict(args[1]) else {}
        return _request(interp, ["GET", args[0], _to_ayce(headers), ""], line, col)
    exports["get"] = _task(_wrap(_get))

    def _post(interp, args, line, col):
        _nargs(args, (2, 3), "http::post", line, col)
        if not (_xa_is_str(args[0]) and _xa_is_str(args[1])):
            raise _err(line, col, "http::post requiere (string url, string body)")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if len(args) == 3:
            if not _xa_is_dict(args[2]):
                raise _err(line, col, "http::post: headers debe ser dict")
            headers.update(_to_py_dict(args[2]))
        return _request(interp, ["POST", args[0], _to_ayce(headers), args[1]], line, col)
    exports["post"] = _task(_wrap(_post))

    def _status_ok(interp, args, line, col):
        _nargs(args, 1, "http::status_ok", line, col)
        if not _xa_is_dict(args[0]):
            raise _err(line, col, "http::status_ok requiere dict respuesta")
        d = _to_py_dict(args[0])
        return "status" in d and isinstance(d["status"], int) and 200 <= d["status"] < 300
    exports["status_ok"] = _task(_wrap(_status_ok))

    return AyceNativeBatch("http", exports)


# ──────────────────────────────────────────────────────────────────────
#  email — construir y parsear mensajes
# ──────────────────────────────────────────────────────────────────────
def _build_email_batch():
    exports = {}

    def _build_msg(interp, args, line, col):
        _nargs(args, (4, 5), "email::build", line, col)
        subject, sender, to, body = args[0], args[1], args[2], args[3]
        html = args[4] if len(args) == 5 else ""
        for x, nm in ((subject, "subject"), (sender, "from"), (to, "to"), (body, "body")):
            if not _xa_is_str(x):
                raise _err(line, col, f"email::build: '{nm}' debe ser string")
        if html and not _xa_is_str(html):
            raise _err(line, col, "email::build: 'html' debe ser string")
        msg = _emailmsg.EmailMessage(policy=_emailpolicy.default)
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        if html:
            msg.set_content(body)
            msg.add_alternative(html, subtype="html")
        else:
            msg.set_content(body)
        return msg.as_string()
    exports["build"] = _task(_wrap(_build_msg))

    def _parse_msg(interp, args, line, col):
        _nargs(args, 1, "email::parse", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "email::parse requiere string mensaje")
        try:
            m = _emailparser.Parser(policy=_emailpolicy.default).parsestr(args[0])
        except Exception as e:
            raise _err(line, col, f"email::parse: {e}")
        body = ""
        if m.is_multipart():
            for part in m.walk():
                ct = part.get_content_type()
                if ct == "text/plain" and part.get_content_disposition() != "attachment":
                    body = part.get_content()
                    break
        else:
            body = m.get_content()
        headers = {k.lower(): str(v) for k, v in m.items()}
        return _to_ayce({
            "subject": str(m.get("Subject", "")),
            "from": str(m.get("From", "")),
            "to": str(m.get("To", "")),
            "body": body,
            "headers": headers,
            "is_multipart": m.is_multipart(),
        })
    exports["parse"] = _task(_wrap(_parse_msg))

    def _quote_addr(interp, args, line, col):
        _nargs(args, 2, "email::format_addr", line, col)
        if not (_xa_is_str(args[0]) and _xa_is_str(args[1])):
            raise _err(line, col, "email::format_addr requiere (string nombre, string email)")
        from email.utils import formataddr as _fa
        return _fa((args[0], args[1]))
    exports["format_addr"] = _task(_wrap(_quote_addr))

    return AyceNativeBatch("email", exports)


# ──────────────────────────────────────────────────────────────────────
#  signal — señales del sistema
# ──────────────────────────────────────────────────────────────────────
def _build_signal_batch():
    exports = {}

    for sig_name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGKILL", "SIGUSR1",
                     "SIGUSR2", "SIGALRM", "SIGCHLD", "SIGPIPE"):
        if hasattr(_signal, sig_name):
            exports[sig_name] = _const(getattr(_signal, sig_name))

    def _pid(interp, args, line, col):
        _nargs(args, 0, "signal::pid", line, col)
        return _os.getpid()
    exports["pid"] = _task(_wrap(_pid))

    def _parent_pid(interp, args, line, col):
        _nargs(args, 0, "signal::parent_pid", line, col)
        return _os.getppid()
    exports["parent_pid"] = _task(_wrap(_parent_pid))

    def _send(interp, args, line, col):
        _nargs(args, 2, "signal::send", line, col)
        pid, sig = args[0], args[1]
        if not (isinstance(pid, int) and isinstance(sig, int)):
            raise _err(line, col, "signal::send requiere (int pid, int señal)")
        try:
            _os.kill(pid, sig)
        except Exception as e:
            raise _err(line, col, f"signal::send: {e}")
        return None
    exports["send"] = _task(_wrap(_send))

    def _name(interp, args, line, col):
        _nargs(args, 1, "signal::name", line, col)
        if not isinstance(args[0], int):
            raise _err(line, col, "signal::name requiere int señal")
        try:
            return _signal.Signals(args[0]).name
        except ValueError:
            raise _err(line, col, f"signal::name: señal desconocida: {args[0]}")
    exports["name"] = _task(_wrap(_name))

    return AyceNativeBatch("signal", exports)


# ──────────────────────────────────────────────────────────────────────
#  multiprocessing — información de procesos
# ──────────────────────────────────────────────────────────────────────
def _build_multiprocessing_batch():
    exports = {}

    def _cpu_count(interp, args, line, col):
        _nargs(args, 0, "multiprocessing::cpu_count", line, col)
        return _multiprocessing.cpu_count()
    exports["cpu_count"] = _task(_wrap(_cpu_count))

    def _current_pid(interp, args, line, col):
        _nargs(args, 0, "multiprocessing::current_pid", line, col)
        return _os.getpid()
    exports["current_pid"] = _task(_wrap(_current_pid))

    def _parent_pid(interp, args, line, col):
        _nargs(args, 0, "multiprocessing::parent_pid", line, col)
        return _os.getppid()
    exports["parent_pid"] = _task(_wrap(_parent_pid))

    def _active_children(interp, args, line, col):
        _nargs(args, 0, "multiprocessing::active_children", line, col)
        return _to_ayce([c.pid for c in _multiprocessing.active_children() if c.pid])
    exports["active_children"] = _task(_wrap(_active_children))

    def _info(interp, args, line, col):
        _nargs(args, 0, "multiprocessing::info", line, col)
        try:
            load1, load5, load15 = _os.getloadavg()
        except Exception:
            load1 = load5 = load15 = 0.0
        return _to_ayce({
            "pid": _os.getpid(),
            "parent_pid": _os.getppid(),
            "cpu_count": _multiprocessing.cpu_count(),
            "load1": load1,
            "load5": load5,
            "load15": load15,
        })
    exports["info"] = _task(_wrap(_info))

    return AyceNativeBatch("multiprocessing", exports)


# ──────────────────────────────────────────────────────────────────────
#  gettext — traducciones (catálogos .mo y dicts)
# ──────────────────────────────────────────────────────────────────────
def _build_gettext_batch():
    exports = {}

    def _load_mo(interp, args, line, col):
        _nargs(args, (2, 3), "gettext::load_mo", line, col)
        domain, locale_dir = args[0], args[1]
        lang = args[2] if len(args) == 3 else "es"
        if not (_xa_is_str(domain) and _xa_is_str(locale_dir) and _xa_is_str(lang)):
            raise _err(line, col, "gettext::load_mo requiere strings")
        try:
            t = _gettext.translation(domain, locale_dir, languages=[lang])
        except FileNotFoundError:
            raise _err(line, col,
                f"gettext::load_mo: no se encontró el catálogo '{domain}' para '{lang}' en {locale_dir}")
        except Exception as e:
            raise _err(line, col, f"gettext::load_mo: {e}")
        return t
    exports["load_mo"] = _task(_wrap(_load_mo))

    def _get(interp, args, line, col):
        _nargs(args, 2, "gettext::get", line, col)
        catalog, key = args[0], args[1]
        if not _xa_is_str(key):
            raise _err(line, col, "gettext::get requiere string key")
        # handle de .mo
        if hasattr(catalog, "gettext"):
            return catalog.gettext(key)
        # dict de traducciones
        if _xa_is_dict(catalog):
            d = _to_py_dict(catalog)
            return d.get(key, key)
        raise _err(line, col, "gettext::get requiere handle de catálogo o dict")
    exports["get"] = _task(_wrap(_get))

    def _from_dict(interp, args, line, col):
        _nargs(args, 1, "gettext::from_dict", line, col)
        if not _xa_is_dict(args[0]):
            raise _err(line, col, "gettext::from_dict requiere dict")
        return args[0]
    exports["from_dict"] = _task(_wrap(_from_dict))

    def _install_json(interp, args, line, col):
        _nargs(args, 1, "gettext::install_json", line, col)
        if not _xa_is_str(args[0]):
            raise _err(line, col, "gettext::install_json requiere string path")
        import json as _json_mod
        try:
            with open(args[0], "r", encoding="utf-8") as f:
                catalog = _json_mod.load(f)
        except Exception as e:
            raise _err(line, col, f"gettext::install_json: {e}")
        if not isinstance(catalog, dict):
            raise _err(line, col, "gettext::install_json: el JSON debe ser un objeto")
        return _to_ayce(catalog)
    exports["install_json"] = _task(_wrap(_install_json))

    return AyceNativeBatch("gettext", exports)


# ──────────────────────────────────────────────────────────────────────
#  inspect — introspección de valores ayce en runtime
# ──────────────────────────────────────────────────────────────────────
def _build_inspect_batch():
    exports = {}

    def _type_of(interp, args, line, col):
        _nargs(args, 1, "inspect::type_of", line, col)
        from .interpreter import AyceInstance, AyceTemplate, AyceTask
        v = args[0]
        if isinstance(v, AyceInstance):
            return v.template.name if hasattr(v, "template") else "instance"
        if isinstance(v, AyceTemplate):
            return f"Template:{v.name}"
        if isinstance(v, AyceTask):
            return "task"
        if _is_batch(v):
            return "batch"
        return _type_name(v)
    exports["type_of"] = _task(_wrap(_type_of))

    def _is_template(interp, args, line, col):
        _nargs(args, 1, "inspect::is_template", line, col)
        from .interpreter import AyceTemplate
        return isinstance(args[0], AyceTemplate)
    exports["is_template"] = _task(_wrap(_is_template))

    def _is_instance(interp, args, line, col):
        _nargs(args, 1, "inspect::is_instance", line, col)
        from .interpreter import AyceInstance
        return isinstance(args[0], AyceInstance)
    exports["is_instance"] = _task(_wrap(_is_instance))

    def _is_error(interp, args, line, col):
        _nargs(args, 1, "inspect::is_error", line, col)
        from .interpreter import AyceInstance
        if not isinstance(args[0], AyceInstance):
            return False
        tmpl = args[0].template if hasattr(args[0], "template") else None
        return tmpl is not None and getattr(tmpl, "is_error", False)
    exports["is_error"] = _task(_wrap(_is_error))

    def _is_task(interp, args, line, col):
        _nargs(args, 1, "inspect::is_task", line, col)
        from .interpreter import AyceTask
        return isinstance(args[0], AyceTask)
    exports["is_task"] = _task(_wrap(_is_task))

    def _fields_of(interp, args, line, col):
        _nargs(args, 1, "inspect::fields_of", line, col)
        from .interpreter import AyceInstance
        if not isinstance(args[0], AyceInstance):
            raise _err(line, col, "inspect::fields_of requiere una instancia")
        return _to_ayce(list(args[0].fields.keys()))
    exports["fields_of"] = _task(_wrap(_fields_of))

    def _has_field(interp, args, line, col):
        _nargs(args, 2, "inspect::has_field", line, col)
        from .interpreter import AyceInstance
        if not isinstance(args[0], AyceInstance):
            raise _err(line, col, "inspect::has_field requiere una instancia")
        if not _xa_is_str(args[1]):
            raise _err(line, col, "inspect::has_field requiere string nombre")
        return args[1] in args[0].fields
    exports["has_field"] = _task(_wrap(_has_field))

    def _get_field(interp, args, line, col):
        _nargs(args, 2, "inspect::get_field", line, col)
        from .interpreter import AyceInstance
        if not isinstance(args[0], AyceInstance):
            raise _err(line, col, "inspect::get_field requiere una instancia")
        if not _xa_is_str(args[1]):
            raise _err(line, col, "inspect::get_field requiere string nombre")
        return args[0].fields.get(args[1])
    exports["get_field"] = _task(_wrap(_get_field))

    def _params_of(interp, args, line, col):
        _nargs(args, 1, "inspect::params_of", line, col)
        from .interpreter import AyceTask
        if not isinstance(args[0], AyceTask):
            raise _err(line, col, "inspect::params_of requiere una task")
        out = []
        for sig in args[0].decl.signatures:
            out.append([p.name for p in sig.params])
        return _to_ayce(out)
    exports["params_of"] = _task(_wrap(_params_of))

    def _name_of(interp, args, line, col):
        _nargs(args, 1, "inspect::name_of", line, col)
        from .interpreter import AyceTask, AyceTemplate
        if isinstance(args[0], AyceTask):
            return args[0].decl.name
        if isinstance(args[0], AyceTemplate):
            return args[0].name
        raise _err(line, col, "inspect::name_of requiere task o Template")
    exports["name_of"] = _task(_wrap(_name_of))

    def _error_info(interp, args, line, col):
        _nargs(args, 1, "inspect::error_info", line, col)
        from .interpreter import AyceInstance
        if not isinstance(args[0], AyceInstance):
            raise _err(line, col, "inspect::error_info requiere un error")
        return _to_ayce({
            "message": str(args[0].fields.get("mensaje", "")),
            "code": args[0].fields.get("codigo", 0),
        })
    exports["error_info"] = _task(_wrap(_error_info))

    return AyceNativeBatch("inspect", exports)


def get_extra_batches():
    """Devuelve un dict con todos los batches stdlib nuevos (v0.6.1)."""
    return {
        "copy":        _build_copy_batch(),
        "re":          _build_re_batch(),
        "datetime":    _build_datetime_batch(),
        "path":        _build_path_batch(),
        "hashlib":     _build_hashlib_batch(),
        "base64":      _build_base64_batch(),
        "hmac":        _build_hmac_batch(),
        "secrets":     _build_secrets_batch(),
        "csv":         _build_csv_batch(),
        "collections": _build_collections_batch(),
        "itertools":   _build_itertools_batch(),
        "functools":   _build_functools_batch(),
        "heapq":       _build_heapq_batch(),
        "bisect":      _build_bisect_batch(),
        "statistics":  _build_statistics_batch(),
        "textwrap":    _build_textwrap_batch(),
        "difflib":     _build_difflib_batch(),
        "unicodedata": _build_unicodedata_batch(),
        "uuid":        _build_uuid_batch(),
        "calendar":    _build_calendar_batch(),
        "decimal":     _build_decimal_batch(),
        "fractions":   _build_fractions_batch(),
        "struct":      _build_struct_batch(),
        "glob":        _build_glob_batch(),
        "tempfile":    _build_tempfile_batch(),
        "shutil":      _build_shutil_batch(),
        "pprint":      _build_pprint_batch(),
        "traceback":   _build_traceback_batch(),
        "warnings":    _build_warnings_batch(),
        "platform":    _build_platform_batch(),
        "codecs":      _build_codecs_batch(),
        "locale":      _build_locale_batch(),
        "subprocess":  _build_subprocess_batch(),
        "logging":     _build_logging_batch(),
        "threading":   _build_threading_batch(),
        "queue":       _build_queue_batch(),
        "types":       _build_types_batch(),
        "zipfile":     _build_zipfile_batch(),
        "gzip":        _compress_batch("gzip", _gzip.compress, _gzip.decompress),
        "zlib":        _compress_batch("zlib", _zlib.compress, _zlib.decompress),
        "bz2":         _compress_batch("bz2", _bz2.compress, _bz2.decompress),
        "lzma":        _compress_batch("lzma", _lzma.compress, _lzma.decompress),
        "pickle":      _build_pickle_batch(),
        "sqlite3":     _build_sqlite3_batch(),
        "urllib":      _build_urllib_batch(),
        "array":       _build_array_batch(),
        # Nuevos en la ampliación v0.6.1
        "stat":           _build_stat_batch(),
        "tarfile":        _build_tarfile_batch(),
        "binascii":       _build_binascii_batch(),
        "socket":         _build_socket_batch(),
        "ssl":            _build_ssl_batch(),
        "http":           _build_http_batch(),
        "email":          _build_email_batch(),
        "signal":         _build_signal_batch(),
        "multiprocessing": _build_multiprocessing_batch(),
        "gettext":        _build_gettext_batch(),
        "inspect":        _build_inspect_batch(),
    }
