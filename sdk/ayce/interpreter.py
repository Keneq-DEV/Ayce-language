"""
ayce — Intérprete con verificación de tipos y ejecución.
Realiza análisis semántico + evaluación tree-walking.
"""

from .ast_nodes import *
from .errors import (
    AyceTypeError, AyceRuntimeError, AyceSyntaxError,
    BreakSignal, ContinueSignal, ReturnSignal, RaiseSignal,
    AyceError,
)
from .tokens import Token

import sys


# ──────────────────────────────────────────────────────────────────────
#  Valores en runtime
# ──────────────────────────────────────────────────────────────────────
class AyceList:
    """Lista mutable. Lleva el tipo declarado."""
    def __init__(self, elements, type_node):
        self.elements = list(elements)
        self.type_node = type_node   # ListType

    def __repr__(self):
        return "[" + ", ".join(repr(e) for e in self.elements) + "]"

    def __eq__(self, other):
        # v0.6.2 (spec 7.2): == compara VALORES en colecciones, no identidad.
        if not isinstance(other, AyceList):
            return NotImplemented
        if len(self.elements) != len(other.elements):
            return False
        return all(a == b for a, b in zip(self.elements, other.elements))

class AyceDict:
    def __init__(self, pairs, type_node):
        self.pairs = dict(pairs)
        self.type_node = type_node

    def __repr__(self):
        return "<" + ", ".join(f"{k!r}: {v!r}" for k, v in self.pairs.items()) + ">"

    def __eq__(self, other):
        # v0.6.2 (spec 7.2): == compara VALORES (mismas claves con mismos valores).
        if not isinstance(other, AyceDict):
            return NotImplemented
        if len(self.pairs) != len(other.pairs):
            return False
        for k, v in self.pairs.items():
            if k not in other.pairs:
                return False
            if not (other.pairs[k] == v):
                return False
        return True

class AyceTuple:
    def __init__(self, elements, type_node):
        self.elements = tuple(elements)
        self.type_node = type_node

    def __repr__(self):
        return "(" + ", ".join(repr(e) for e in self.elements) + ")"

    def __eq__(self, other):
        # v0.6.2 (spec 7.2): == compara VALORES en colecciones.
        if not isinstance(other, AyceTuple):
            return NotImplemented
        if len(self.elements) != len(other.elements):
            return False
        return all(a == b for a, b in zip(self.elements, other.elements))

class AyceSet:
    def __init__(self, elements, type_node):
        self.elements = list(elements)
        self.type_node = type_node
        # Eliminar duplicados preservando orden
        seen = []
        unique = []
        for e in self.elements:
            key = repr(e)
            if key not in seen:
                seen.append(key)
                unique.append(e)
        self.elements = unique

    def __repr__(self):
        return "{" + ", ".join(repr(e) for e in self.elements) + "}"

    def __eq__(self, other):
        # v0.6.2 (spec 7.2): == compara VALORES sin importar el orden.
        if not isinstance(other, AyceSet):
            return NotImplemented
        if len(self.elements) != len(other.elements):
            return False
        remaining = list(other.elements)
        for e in self.elements:
            for i, o in enumerate(remaining):
                if e == o:
                    del remaining[i]
                    break
            else:
                return False
        return True

class AyceTask:
    """Tarea declarada con `task`. Puede tener múltiples firmas (sobrecarga)."""
    def __init__(self, decl: TaskDecl, closure_env):
        self.decl = decl
        self.closure_env = closure_env

    def __repr__(self):
        return f"<task {self.decl.name}>"


class AyceTemplate:
    """Template (clase) definido por el usuario. Soporta herencia (v0.4.1)."""
    def __init__(self, decl: TemplateDecl, closure_env, parent_template=None):
        self.decl = decl
        self.closure_env = closure_env   # entorno donde se declaró (para métodos)
        self.parent_template = parent_template   # AyceTemplate padre o None

    @property
    def name(self):
        return self.decl.name

    def find_method(self, name):
        """Busca método en este Template y luego en el padre (herencia)."""
        for m in self.decl.methods:
            if m.name == name:
                return m
        if self.parent_template is not None:
            return self.parent_template.find_method(name)
        return None

    def all_fields(self):
        """Devuelve todos los campos: los del padre primero, luego los propios."""
        fields = []
        if self.parent_template is not None:
            fields.extend(self.parent_template.all_fields())
        fields.extend(self.decl.fields)
        return fields

    def is_subclass_of(self, other_name):
        """¿Es this subclase de other_name? (incluye self)."""
        if self.name == other_name:
            return True
        if self.parent_template is not None:
            return self.parent_template.is_subclass_of(other_name)
        return False

    def __repr__(self):
        return f"<Template {self.decl.name}>"


class AyceInstance:
    """Instancia de un Template."""
    def __init__(self, template: AyceTemplate):
        self.template = template
        self.fields = {}   # nombre → valor

    def __repr__(self):
        return f"<{self.template.name}>"


class AyceShape:
    """Shape definido por el usuario (registro inmutable)."""
    def __init__(self, decl: ShapeDecl, closure_env):
        self.decl = decl
        self.closure_env = closure_env

    @property
    def name(self):
        return self.decl.name

    def __repr__(self):
        return f"<Shape {self.decl.name}>"


class AyceShapeValue:
    """Instancia de un Shape (un registro con campos)."""
    def __init__(self, shape: AyceShape):
        self.shape = shape
        self.fields = {}

    def __repr__(self):
        items = ", ".join(f"{k}: {v!r}" for k, v in self.fields.items())
        return f"{self.shape.name} {{ {items} }}"


class AyceVariant:
    """Variant definido por el usuario."""
    def __init__(self, decl: VariantDecl, closure_env):
        self.decl = decl
        self.closure_env = closure_env

    @property
    def name(self):
        return self.decl.name

    def find_case(self, name):
        for c in self.decl.cases:
            if c.name == name:
                return c
        return None

    def __repr__(self):
        return f"<Variant {self.decl.name}>"


class AyceVariantValue:
    """Valor de un Variant: caso + payload opcional."""
    def __init__(self, variant: AyceVariant, case_name: str, payload=None):
        self.variant = variant
        self.case_name = case_name
        self.payload = payload

    def __repr__(self):
        if self.payload is not None:
            return f"{self.variant.name}::{self.case_name}({self.payload!r})"
        return f"{self.variant.name}::{self.case_name}"


class AyceBatch:
    """Batch cargado con `require`. Contiene un namespace de exports."""
    def __init__(self, name: str, filename: str, exports: dict):
        self.name = name          # nombre del batch (identificador o basename)
        self.filename = filename  # ruta del archivo .ayce cargado
        self.exports = exports    # dict nombre → (value, type_node, is_const, initialized)

    def find_export(self, name: str):
        if name in self.exports:
            v, _, _, _ = self.exports[name]
            return v
        return None

    def __repr__(self):
        return f"<batch {self.name}>"


# ──────────────────────────────────────────────────────────────────────
#  Entorno (scope)
# ──────────────────────────────────────────────────────────────────────
class Env:
    def __init__(self, parent=None):
        self.vars = {}     # nombre → (value, type_node, is_const, initialized)
        self.parent = parent

    def lookup(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def declare(self, name, value, type_node, is_const=False, initialized=True):
        self.vars[name] = (value, type_node, is_const, initialized)

    def assign(self, name, value, filename, line, col):
        env = self
        while env is not None:
            if name in env.vars:
                v, t, is_const, _ = env.vars[name]
                if is_const:
                    raise AyceRuntimeError(filename, line, col,
                        f"No se puede reasignar la constante '{name}'")
                env.vars[name] = (value, t, False, True)
                return
            env = env.parent
        raise AyceRuntimeError(filename, line, col,
            f"Variable '{name}' no declarada")

    def find_global_env(self):
        env = self
        while env.parent is not None:
            env = env.parent
        return env


# ──────────────────────────────────────────────────────────────────────
#  Intérprete
# ──────────────────────────────────────────────────────────────────────
class Interpreter:
    # v0.6.2: límite de profundidad de llamadas AYCE (evita el RecursionError
    # crudo de Python; se convierte en OverErr/RecursionErr capturable).
    MAX_CALL_DEPTH = 2000

    def __init__(self, filename: str = "<stdin>", import_paths: list = None):
        self.filename = filename
        # v0.6.3: ruta absoluta del programa principal (para <GUARD>-<MAIN>).
        # El Interpreter raíz es el programa; los hijos de `require` heredan
        # esta ruta y como su propio filename es distinto, su guard no corre.
        if filename.startswith("<"):
            self._main_file = filename
        else:
            import os
            self._main_file = os.path.abspath(filename)
        self.global_env = Env()
        # v0.6.2: profundidad de llamadas actual
        self._ayce_depth = 0
        # v0.6.2: builtins globales del lenguaje (ord, chr, urandom,
        # bytes_from_ints, bytes_to_ints) — como los builtins de CPython:
        # están en el intérprete, sin `require`, y la stdlib algorítmica
        # se apoya sólo en ellos para tocar la máquina.
        from .batches import get_global_builtins
        for _name, _task_val in get_global_builtins().items():
            self.global_env.declare(_name, _task_val, TaskType(), is_const=True)
        # Cache de batchs ya cargados: ruta_absoluta → AyceBatch
        self._batch_cache: dict = {}
        # Paths donde buscar batchs por identificador
        self.import_paths = import_paths or ["."]
        # Stack de archivos en proceso de carga (para detectar ciclos)
        self._loading_stack: list = []

    def run(self, program: Program):
        # Primera pasada: procesar requires (v0.5) y declarar tasks, templates, shapes y variants
        for stmt in program.stmts:
            if isinstance(stmt, RequireStmt):
                self._exec_require(stmt, self.global_env)

        for stmt in program.stmts:
            if isinstance(stmt, TaskDecl):
                # v0.6.2: si el task ya fue declarado, las nuevas firmas se
                # FUNDEN como overloads (igual que la sintaxis `|` dentro de
                # una sola declaración); antes, la última pisaba a las demás.
                existing = self.global_env.lookup(stmt.name)
                if existing is not None:
                    prev_task = existing[0]
                    if isinstance(prev_task, AyceTask):
                        prev_task.decl.signatures.extend(stmt.signatures)
                        prev_task.decl.bodies.extend(stmt.bodies)
                        continue
                task = AyceTask(stmt, self.global_env)
                self.global_env.declare(stmt.name, task, TaskType(), is_const=True)
            elif isinstance(stmt, TemplateDecl):
                # Resolver padre si hay herencia (v0.4.1)
                parent_tpl = None
                if stmt.parent_name:
                    existing = self.global_env.lookup(stmt.parent_name)
                    if existing is None:
                        raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                            f"El Template padre '{stmt.parent_name}' no está declarado")
                    parent_tpl = existing[0]
                    if not isinstance(parent_tpl, AyceTemplate):
                        raise AyceTypeError(self.filename, stmt.line, stmt.col,
                            f"'{stmt.parent_name}' no es un Template")
                tpl = AyceTemplate(stmt, self.global_env, parent_template=parent_tpl)
                self.global_env.declare(stmt.name, tpl,
                                        UserTypeName(name=stmt.name), is_const=True)
            elif isinstance(stmt, ShapeDecl):
                shp = AyceShape(stmt, self.global_env)
                self.global_env.declare(stmt.name, shp,
                                        UserTypeName(name=stmt.name), is_const=True)
            elif isinstance(stmt, VariantDecl):
                var = AyceVariant(stmt, self.global_env)
                self.global_env.declare(stmt.name, var,
                                        UserTypeName(name=stmt.name), is_const=True)

        # Registrar Template Error nativo (si el usuario no lo definió)
        self._register_native_error()

        # Arreglo de la 0.6.3 (diseño del cliente): el guard principal es un PUNTO DE
        # ENTRADA, no un `if`. Si el archivo tiene <GUARD>-<MAIN> y este
        # archivo es el programa que se ejecutó, el nivel superior queda
        # CALLADO: ni say, ni llamadas, ni State, ni asignaciones sueltas.
        # "Si el print imprime, no es guard." Sólo escapan de la regla:
        #   - los cuerpos de los guards (son el programa), y
        #   - las DECLARACIONES de datos var/const del nivel superior, que
        #     sí se inicializan (como los globals de C) para que el cuerpo
        #     del guard pueda usarlas.
        # Las tasks/templates/shapes/variants ya se declararon en la primera
        # pasada y los `require` también se procesan ahí: son importaciones,
        # no acciones. Sin guard, o bajo require (hijo: _is_main_file() es
        # False), el nivel superior corre completo como siempre.
        guard_entrada = self._is_main_file() and any(
            isinstance(s, GuardMainStmt) for s in program.stmts
        )

        # Segunda pasada: ejecutar sentencias sueltas (no declaraciones de tipos ni tasks)
        for stmt in program.stmts:
            if isinstance(stmt, (TaskDecl, TemplateDecl, ShapeDecl, VariantDecl, RequireStmt)):
                continue
            if guard_entrada and not isinstance(
                    stmt, (GuardMainStmt, VarDecl, ConstDecl, DeclGroup)):
                continue
            try:
                self.exec_stmt(stmt, self.global_env)
            except BreakSignal:
                raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                    "'break' sólo es válido dentro de un bucle")
            except ContinueSignal:
                raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                    "'continue' sólo es válido dentro de un bucle")
            except ReturnSignal:
                raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                    "'return' sólo es válido dentro de una tarea")
            except RaiseSignal as r:
                # Error no capturado por try/rescue — propagar como error de runtime
                err_val = r.error_value
                if isinstance(err_val, AyceInstance) and "mensaje" in err_val.fields:
                    msg = err_val.fields.get("mensaje", "error desconocido")
                    raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                        f"Error no capturado: {msg}")
                raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                    "Error no capturado")

    def _register_native_error(self):
        """Registra TODOS los errores nativos como Templates con herencia (v0.4.1).
        En v0.5 el constructor se llama `build` (no init)."""
        from .ast_nodes import FieldDecl
        from .errors import NATIVE_ERRORS, get_error_hierarchy

        # No registrar si el usuario ya definió "Error"
        if self.global_env.lookup("Error") is not None:
            return

        # build común para todos los errores
        def make_build():
            return TaskDecl(
                name="build",
                signatures=[TaskSignature(params=[
                    Param(type_node=PrimitiveType(name="string"), name="mensaje"),
                    Param(type_node=PrimitiveType(name="int"), name="codigo", default=IntLit(value=0)),
                ])],
                return_type=None,
                bodies=[[
                    AssignStmt(
                        target=ModuleAccessExpr(name="mensaje", target=SelfExpr()),
                        value=IdentExpr(name="mensaje"),
                    ),
                    AssignStmt(
                        target=ModuleAccessExpr(name="codigo", target=SelfExpr()),
                        value=IdentExpr(name="codigo"),
                    ),
                ]],
            )

        # Crear los Templates en orden de jerarquía (padres antes que hijos)
        templates = {}
        for name in get_error_hierarchy():
            info = NATIVE_ERRORS[name]
            parent_name = info["parent"]
            parent_tpl = templates.get(parent_name) if parent_name else None

            # Cada error tiene los campos mensaje y codigo
            # Los hijos heredan los campos del padre, así que no los redeclaran
            fields = []
            if parent_tpl is None:
                # Es la raíz (Error) — define los campos
                fields = [
                    FieldDecl(name="mensaje", type_node=PrimitiveType(name="string")),
                    FieldDecl(name="codigo", type_node=PrimitiveType(name="int"), default=IntLit(value=0)),
                ]

            decl = TemplateDecl(
                name=name,
                fields=fields,
                methods=[make_build()] if parent_tpl is None else [],
                parent_name=parent_name or "",
            )
            tpl = AyceTemplate(decl, self.global_env, parent_template=parent_tpl)
            templates[name] = tpl
            self.global_env.declare(name, tpl, UserTypeName(name=name), is_const=True)

    # ──────────────────────────────────────────────────────────────────
    #  Sentencias
    # ──────────────────────────────────────────────────────────────────
    def exec_stmt(self, stmt, env: Env):
        if isinstance(stmt, VarDecl):
            self._exec_var_decl(stmt, env)
        elif isinstance(stmt, ConstDecl):
            self._exec_const_decl(stmt, env)
        elif isinstance(stmt, DeclGroup):
            # v0.6.3: var/const múltiple — cada declaración pasa por la
            # maquinaria común (verificación de tipos, coerción, const).
            for d in stmt.decls:
                self.exec_stmt(d, env)
        elif isinstance(stmt, AssignStmt):
            self._exec_assign(stmt, env)
        elif isinstance(stmt, CompoundAssignStmt):
            self._exec_compound_assign(stmt, env)
        elif isinstance(stmt, SayStmt):
            self._exec_say(stmt, env)
        elif isinstance(stmt, IfStmt):
            self._exec_if(stmt, env)
        elif isinstance(stmt, WhileStmt):
            self._exec_while(stmt, env)
        elif isinstance(stmt, ForStmt):
            self._exec_for(stmt, env)
        elif isinstance(stmt, StateStmt):
            self._exec_state(stmt, env)
        elif isinstance(stmt, GuardMainStmt):
            self._exec_guard_main(stmt, env)
        elif isinstance(stmt, TryStmt):
            self._exec_try(stmt, env)
        elif isinstance(stmt, RaiseStmt):
            self._exec_raise(stmt, env)
        elif isinstance(stmt, RequireStmt):
            self._exec_require(stmt, env)
        elif isinstance(stmt, BreakStmt):
            raise BreakSignal()
        elif isinstance(stmt, ContinueStmt):
            raise ContinueSignal()
        elif isinstance(stmt, ReturnStmt):
            value = self.eval(stmt.value, env) if stmt.value is not None else None
            raise ReturnSignal(value)
        elif isinstance(stmt, GlobalStmt):
            self._exec_global(stmt, env)
        elif isinstance(stmt, ExprStmt):
            self.eval(stmt.expr, env)
        elif isinstance(stmt, TaskDecl):
            # Ya declarado en primera pasada — nada que hacer
            pass
        else:
            raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                f"Sentencia no soportada: {type(stmt).__name__}")

    def _exec_var_decl(self, stmt: VarDecl, env: Env):
        if stmt.init is not None:
            value = self.eval(stmt.init, env)
            # Verificar tipo
            value = self._check_value_matches_type(value, stmt.type_node, stmt.line, stmt.col, env)
            # v0.6.2: la promoción int → float (spec 4.4) sí se aplica al valor guardado
            value = self._coerce_value(value, stmt.type_node)
            # v0.6.2: el valor lista/dict/set adopta el tipo declarado para que
            # la escritura posterior también valide (modo estricto, spec 4.3)
            self._attach_declared_type(value, stmt.type_node)
            initialized = True
        else:
            # Variable sin inicializar: se registra como no inicializada.
            # No se puede leer hasta que reciba un valor.
            value = None
            initialized = False
        env.declare(stmt.name, value, stmt.type_node, is_const=False, initialized=initialized)

    def _exec_const_decl(self, stmt: ConstDecl, env: Env):
        # v0.6.2 (spec 5.2): redeclarar una constante en el mismo ámbito es error
        if stmt.name in env.vars and env.vars[stmt.name][2]:
            raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                f"La constante '{stmt.name}' ya está declarada en este ámbito")
        value = self.eval(stmt.init, env)
        value = self._check_value_matches_type(value, stmt.type_node, stmt.line, stmt.col, env)
        value = self._coerce_value(value, stmt.type_node)
        self._attach_declared_type(value, stmt.type_node)
        env.declare(stmt.name, value, stmt.type_node, is_const=True)

    def _coerce_value(self, value, type_node):
        """v0.6.2: devuelve el valor con la promoción int → float aplicada
        (antes la promoción se calculaba y se perdía)."""
        if isinstance(type_node, PrimitiveType) and type_node.name == "float":
            if isinstance(value, int) and not isinstance(value, bool):
                return float(value)
        return value

    def _attach_declared_type(self, value, type_node):
        """v0.6.2: si el tipo declarado es una colección estricta y el valor
        se creó como literal flexible, el valor adopta el tipo declarado.
        Así l[i] = v, d<k> = v y ::append/::insert validan el modo estricto."""
        if isinstance(type_node, ListType) and isinstance(value, AyceList):
            if not type_node.flexible and value.type_node.flexible:
                value.type_node = type_node
        elif isinstance(type_node, DictType) and isinstance(value, AyceDict):
            if not type_node.flexible and value.type_node.flexible:
                value.type_node = type_node
        elif isinstance(type_node, SetType) and isinstance(value, AyceSet):
            if not type_node.flexible and value.type_node.flexible:
                value.type_node = type_node

    def _exec_assign(self, stmt: AssignStmt, env: Env):
        target = stmt.target
        value = self.eval(stmt.value, env)

        if isinstance(target, IdentExpr):
            # Verificar que el tipo de la variable ya declarada coincida
            existing = env.lookup(target.name)
            if existing is None:
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    f"Variable '{target.name}' no declarada")
            old_val, type_node, _, _ = existing
            value = self._check_value_matches_type(value, type_node, target.line, target.col, env)
            value = self._coerce_value(value, type_node)
            self._attach_declared_type(value, type_node)
            env.assign(target.name, value, self.filename, target.line, target.col)

        elif isinstance(target, IndexExpr):
            # Asignación a lista: lista[i] = valor
            container = self.eval(target.target, env)
            idx = self.eval(target.index, env)
            if isinstance(container, AyceTuple):
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    "Las tuplas son inmutables: no se puede asignar a una posición")
            if isinstance(container, str) or isinstance(container, bytes):
                # v0.6.2: strings y bytes son inmutables en ayce.
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    "Los strings y bytes son inmutables: no se puede asignar a s[i]")
            if not isinstance(container, AyceList):
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    "La indexación con [] sólo aplica a listas")
            # v0.6.2: bool no es un índice válido (spec 4.4: bool no es int)
            if isinstance(idx, bool):
                raise AyceTypeError(self.filename, target.line, target.col,
                    "El índice debe ser int, no bool")
            if not isinstance(idx, int):
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    "El índice debe ser int")
            if idx < 0 or idx >= len(container.elements):
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    f"Índice {idx} fuera de rango (longitud {len(container.elements)})")
            # Verificar tipo del elemento (v0.6.2: también por escritura)
            elem_type = container.type_node.elem if not container.type_node.flexible else None
            if elem_type is not None:
                self._check_value_matches_type(value, elem_type, target.line, target.col, env)
            container.elements[idx] = value

        elif isinstance(target, DictAccessExpr):
            # Asignación a dict: d<clave> = valor
            container = self.eval(target.target, env)
            key = self.eval(target.key, env)
            if not isinstance(container, AyceDict):
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    "El acceso con <> sólo aplica a diccionarios")
            # v0.6.2: clave bool sólo si el dict la declara (<bool, ...>)
            if isinstance(key, bool):
                kt = container.type_node.key_type if isinstance(container.type_node, DictType) else None
                if not (isinstance(kt, PrimitiveType) and kt.name == "bool"):
                    raise AyceTypeError(self.filename, target.line, target.col,
                        "La clave no puede ser bool (usá int(key) o 1/0)")
            # v0.6.2: el valor asignado valida el tipo declarado (modo estricto)
            tn = container.type_node
            if isinstance(tn, DictType) and not tn.flexible and tn.value_types:
                self._check_value_matches_type(value, tn.value_types[0], target.line, target.col, env)
            container.pairs[key] = value

        elif isinstance(target, ModuleAccessExpr):
            # Asignación a campo de instancia: p::x = valor (v0.5: usa ::)
            obj = self.eval(target.target, env)
            if isinstance(obj, AyceInstance):
                if target.name not in obj.fields:
                    raise AyceRuntimeError(self.filename, target.line, target.col,
                        f"El campo '{target.name}' no existe en {obj.template.name}")
                obj.fields[target.name] = value
            elif isinstance(obj, AyceShapeValue):
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    f"Los Shape son inmutables: no se puede asignar a {obj.shape.name}::{target.name}")
            else:
                raise AyceTypeError(self.filename, target.line, target.col,
                    f"No se puede asignar a campo de {self._type_name(obj)}")

        else:
            raise AyceRuntimeError(self.filename, target.line, target.col,
                "Objetivo de asignación inválido")

    def _exec_say(self, stmt: SayStmt, env: Env):
        out = []
        for arg in stmt.args:
            v = self.eval(arg, env)
            out.append(self._format_value(v))
        print(" ".join(out))

    def _exec_if(self, stmt: IfStmt, env: Env):
        for cond, body in stmt.branches:
            if cond is None:
                # Rama else
                block_env = Env(parent=env)
                for s in body:
                    self.exec_stmt(s, block_env)
                return
            cond_val = self.eval(cond, env)
            if not isinstance(cond_val, bool):
                raise AyceTypeError(self.filename, cond.line, cond.col,
                    f"La condición del if debe ser bool, se recibió {self._type_name(cond_val)}")
            if cond_val:
                block_env = Env(parent=env)
                for s in body:
                    self.exec_stmt(s, block_env)
                return

    def _exec_while(self, stmt: WhileStmt, env: Env):
        while True:
            cond_val = self.eval(stmt.cond, env)
            if not isinstance(cond_val, bool):
                raise AyceTypeError(self.filename, stmt.cond.line, stmt.cond.col,
                    f"La condición del while debe ser bool, se recibió {self._type_name(cond_val)}")
            if not cond_val:
                break
            block_env = Env(parent=env)
            try:
                for s in stmt.body:
                    self.exec_stmt(s, block_env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def _exec_for(self, stmt: ForStmt, env: Env):
        iterable_val = self.eval(stmt.iterable, env)
        # Convertir a lista de elementos
        if isinstance(iterable_val, AyceList):
            items = iterable_val.elements
            elem_type = iterable_val.type_node.elem if not iterable_val.type_node.flexible else None
        elif isinstance(iterable_val, AyceTuple):
            items = list(iterable_val.elements)
            elem_type = None  # tuplas pueden ser heterogéneas
        elif isinstance(iterable_val, AyceSet):
            items = iterable_val.elements
            elem_type = iterable_val.type_node.elem if not iterable_val.type_node.flexible else None
        elif isinstance(iterable_val, list):
            # range() devuelve una lista de ints
            items = iterable_val
            elem_type = PrimitiveType(name="int")
        elif isinstance(iterable_val, str):
            # v0.6.2 (spec 6.5/9.3): iterar un string recorre sus CARACTERES
            items = list(iterable_val)
            elem_type = PrimitiveType(name="string")
        else:
            raise AyceTypeError(self.filename, stmt.iterable.line, stmt.iterable.col,
                f"No se puede iterar sobre {self._type_name(iterable_val)}")

        for item in items:
            block_env = Env(parent=env)
            block_env.declare(stmt.var_name, item, elem_type, is_const=False)
            try:
                for s in stmt.body:
                    self.exec_stmt(s, block_env)
            except BreakSignal:
                return
            except ContinueSignal:
                continue

    # ──────────────────────────────────────────────────────────────────
    #  State/box y guard principal (v0.6.3 — diseño del cliente)
    # ──────────────────────────────────────────────────────────────────
    def _exec_state(self, stmt: StateStmt, env: Env):
        """State <expr> - < ... > — evalúa el sujeto UNA vez y prueba los
        brazos en orden. El primero cuyo patrón coincide ejecuta su cuerpo con
        `box` vinculado al sujeto. `box is null` es el brazo de reserva: sólo
        corre si ningún otro brazo coincidió. Sin reserva y sin coincidencia:
        no hace nada.

        Coherencia (v0.6.3): los brazos de TIPO sólo aportan información
        cuando el tipo del sujeto es desconocido (variables none, entradas de
        inlet/json::parse). Si el sujeto es una variable con tipo concreto
        declarado, el intérprete ya conoce el tipo y avisa una sola vez qué
        brazos son estáticos (nunca/siempre coinciden). Los brazos de valor y
        de variante no se analizan: hablan del valor o del caso, no del tipo."""
        self._state_warn_coherence(stmt, env)
        subject = self.eval(stmt.subject, env)
        for patterns, body in stmt.arms:
            if patterns is None or self._pattern_matches_any(patterns, subject, env):
                arm_env = Env(parent=env)
                arm_env.declare("box", subject, None, is_const=False)
                for s in body:
                    self.exec_stmt(s, arm_env)
                return

    def _pattern_matches_any(self, alts, value, env) -> bool:
        return any(self._pattern_matches(a, value, env) for a in alts)

    def _pattern_matches(self, alt: PatternAlt, value, env) -> bool:
        if alt.kind == "type":
            return self._pattern_type_matches(value, alt.type_node)
        if alt.kind == "value":
            expected = self.eval(alt.value_expr, env)
            try:
                return self._values_equal(value, expected, alt.line, alt.col)
            except AyceTypeError:
                # Un patrón de valor no comparable con el sujeto simplemente
                # no coincide (ej: box is 1 cuando box es una lista).
                return False
        if alt.kind == "ident":
            existing = env.lookup(alt.name)
            if existing is None:
                raise AyceRuntimeError(self.filename, alt.line, alt.col,
                    f"Variable '{alt.name}' no declarada")
            val, _, _, initialized = existing
            if not initialized:
                raise AyceRuntimeError(self.filename, alt.line, alt.col,
                    f"Variable '{alt.name}' usada antes de ser inicializada")
            # Si el identificador nombra un tipo de usuario, es un patrón de tipo
            if isinstance(val, (AyceTemplate, AyceShape, AyceVariant)):
                return self._pattern_type_matches(value, UserTypeName(name=alt.name))
            try:
                return self._values_equal(value, val, alt.line, alt.col)
            except AyceTypeError:
                return False
        if alt.kind == "variant":
            if not isinstance(value, AyceVariantValue):
                return False
            return (value.variant.name == alt.type_name
                    and value.case_name == alt.case_name)
        return False

    def _values_equal(self, a, b, line, col) -> bool:
        """Igualdad == de ayce, con la MISMA semántica que BinaryExpr '==':
        comparar con none siempre es válido, y tipos incompatibles son error
        (salvo int/float que se permiten entre sí)."""
        if a is None or b is None:
            return a == b
        if type(a) != type(b):
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                pass
            else:
                raise AyceTypeError(self.filename, line, col,
                    f"No se puede comparar {self._type_name(a)} con {self._type_name(b)}")
        return a == b

    def _pattern_type_matches(self, value, type_node) -> bool:
        """Versión silenciosa y PROFUNDA de _value_matches_type para patrones:
        en colecciones verifica también el tipo de elemento, así que
        `box is int[]` distingue una lista de ints de una lista de strings."""
        if isinstance(type_node, ListType):
            if not isinstance(value, AyceList):
                return False
            if not type_node.flexible and type_node.elem is not None:
                return all(self._pattern_type_matches(e, type_node.elem)
                           for e in value.elements)
            return True
        if isinstance(type_node, SetType):
            if not isinstance(value, AyceSet):
                return False
            if not type_node.flexible and type_node.elem is not None:
                return all(self._pattern_type_matches(e, type_node.elem)
                           for e in value.elements)
            return True
        if isinstance(type_node, TupleType):
            if not isinstance(value, AyceTuple):
                return False
            if type_node.flexible:
                return True
            if type_node.elem_types:
                if len(value.elements) != len(type_node.elem_types):
                    return False
                return all(self._pattern_type_matches(e, et)
                           for e, et in zip(value.elements, type_node.elem_types))
            return True
        if isinstance(type_node, DictType):
            if not isinstance(value, AyceDict):
                return False
            if type_node.flexible:
                return True
            if type_node.key_type is not None:
                for k in value.pairs:
                    if not self._pattern_type_matches(k, type_node.key_type):
                        return False
                if type_node.value_types:
                    for v in value.pairs.values():
                        if not any(self._pattern_type_matches(v, vt)
                                   for vt in type_node.value_types):
                            return False
            return True
        # Primitivos, task y tipos de usuario: igual que la verificación común
        return self._value_matches_type(value, type_node)

    # ── Coherencia de los brazos de tipo en State (v0.6.3) ────────────────
    # `none` es el tipo del valor desconocido: sobre una variable none (o sin
    # anotar) los brazos de tipo están vivos y State resuelve en runtime —
    # el caso canónico de inlet y json::parse. Sobre una variable con tipo
    # concreto declarado el intérprete ya sabe el tipo, así que esos brazos
    # son estáticos: o nunca coinciden (código muerto) o siempre coinciden
    # (un if disfrazado que deja muertos los brazos siguientes). Se avisa UNA
    # vez por State, a stderr, sin alterar la ejecución ni la salida. Los
    # brazos de valor y de variante no se analizan: hablan del valor o del
    # caso, no del tipo.
    def _type_cat(self, tn) -> str:
        if isinstance(tn, PrimitiveType):
            return "prim"
        if isinstance(tn, ListType):
            return "list"
        if isinstance(tn, DictType):
            return "dict"
        if isinstance(tn, SetType):
            return "set"
        if isinstance(tn, TupleType):
            return "tuple"
        if isinstance(tn, UserTypeName):
            return "user"
        if isinstance(tn, TaskType):
            return "task"
        return "?"

    def _state_declared_overlap(self, pat, dec):
        """'always' / 'never' / None — ¿puede un patrón de tipo `pat` coincidir
        con algún valor que quepa en el tipo declarado `dec`? None significa
        que no se puede saber de forma estática (p. ej. colecciones flexibles):
        en ese caso el brazo se considera vivo y no se avisa."""
        pc, dc = self._type_cat(pat), self._type_cat(dec)
        if pc == "?" or dc == "?":
            return None
        if pc != dc:
            return "never"
        if pc == "prim":
            if pat.name == "none":
                return "always"  # el patrón none coincide con cualquier valor
            return "always" if pat.name == dec.name else "never"
        if pc in ("list", "set"):
            if pat.flexible:
                return "always"
            if dec.flexible or pat.elem is None or dec.elem is None:
                return None
            return self._state_declared_overlap(pat.elem, dec.elem)
        if pc == "dict":
            if pat.flexible:
                return "always"
            if dec.flexible or pat.key_type is None or dec.key_type is None:
                return None
            k = self._state_declared_overlap(pat.key_type, dec.key_type)
            if pat.value_types and dec.value_types:
                vs = [self._state_declared_overlap(pv, dv)
                      for pv in pat.value_types for dv in dec.value_types]
                v = ("always" if "always" in vs
                     else "never" if all(s == "never" for s in vs)
                     else None)
            else:
                v = None
            if k == "never" or v == "never":
                return "never"
            if k == "always" and v == "always":
                return "always"
            return None
        if pc == "tuple":
            if pat.flexible:
                return "always"
            if dec.flexible or not pat.elem_types or not dec.elem_types:
                return None
            if len(pat.elem_types) != len(dec.elem_types):
                return "never"
            sts = [self._state_declared_overlap(p, d)
                   for p, d in zip(pat.elem_types, dec.elem_types)]
            if "never" in sts:
                return "never"
            if all(s == "always" for s in sts):
                return "always"
            return None
        if pc == "user":
            return "always" if pat.name == dec.name else "never"
        return "always"  # task == task

    def _type_to_text(self, tn) -> str:
        """Texto corto de un nodo de tipo para los avisos de State."""
        if tn is None:
            return "?"
        if isinstance(tn, PrimitiveType):
            return tn.name
        if isinstance(tn, ListType):
            return ("list" if tn.flexible or tn.elem is None
                    else self._type_to_text(tn.elem) + "[]")
        if isinstance(tn, SetType):
            return ("set" if tn.flexible or tn.elem is None
                    else self._type_to_text(tn.elem) + "{}")
        if isinstance(tn, DictType):
            if tn.flexible or tn.key_type is None:
                return "dict"
            vals = (" || ".join(self._type_to_text(v) for v in tn.value_types)
                    or "?")
            return f"<{self._type_to_text(tn.key_type)}, {vals}>"
        if isinstance(tn, TupleType):
            if tn.flexible or not tn.elem_types:
                return "tuple"
            return "(" + ", ".join(self._type_to_text(t)
                                   for t in tn.elem_types) + ")"
        if isinstance(tn, UserTypeName):
            return tn.name
        if isinstance(tn, TaskType):
            return "task"
        return "?"

    def _state_warn_coherence(self, stmt: StateStmt, env: Env):
        """Aviso de coherencia: una sola vez por nodo State, sólo cuando el
        sujeto es una variable con tipo concreto declarado y hay brazos de
        tipo. Escribe a stderr; no altera la ejecución ni la salida."""
        if getattr(stmt, "_coherence_checked", False):
            return
        stmt._coherence_checked = True
        if not isinstance(stmt.subject, IdentExpr):
            return
        existing = env.lookup(stmt.subject.name)
        if existing is None:
            return
        declared = existing[1]
        if declared is None or (isinstance(declared, PrimitiveType)
                                and declared.name == "none"):
            return  # caso canónico: tipo desconocido → todos los brazos vivos
        decl_txt = self._type_to_text(declared)
        findings = []
        for i, (patterns, _body) in enumerate(stmt.arms, 1):
            if patterns is None:
                continue  # brazo de reserva (box is null)
            type_alts = [a for a in patterns if a.kind == "type"]
            if not type_alts:
                continue
            txt = " || ".join(self._type_to_text(a.type_node)
                              for a in type_alts)
            pat_txt = f"box is type ({txt})"
            sts = [self._state_declared_overlap(a.type_node, declared)
                   for a in type_alts]
            if "always" in sts:
                findings.append(
                    f"brazo {i} `{pat_txt}` SIEMPRE coincide con "
                    f"'{stmt.subject.name}' ({decl_txt}) → los brazos que "
                    f"siguen nunca corren")
            elif sts and all(s == "never" for s in sts):
                findings.append(
                    f"brazo {i} `{pat_txt}` NUNCA coincide con "
                    f"'{stmt.subject.name}' ({decl_txt}) → código muerto")
        if not findings:
            return
        lines = [
            f"aviso[State] línea {stmt.line}: '{stmt.subject.name}' está "
            f"declarada como {decl_txt}: sus brazos de tipo son estáticos "
            f"(el intérprete ya conoce el tipo)."
        ]
        lines.extend("  · " + f for f in findings)
        lines.append(
            "  → si el tipo se decide en runtime (inlet, json::parse...), "
            f"declara la variable none: var {stmt.subject.name}: none = ..."
        )
        print("\n".join(lines), file=sys.stderr, flush=True)

    def _exec_guard_main(self, stmt: GuardMainStmt, env: Env):
        """<GUARD>-<MAIN> { cuerpo } — el guard principal del cliente: el
        PUNTO DE ENTRADA del programa (arreglo de la 0.6.3, decisión del cliente). Cuando
        el archivo se ejecuta como programa principal, SÓLO corren los cuerpos
        de los guards: el resto del nivel superior queda callado. Si el archivo
        se cargó con `require` (batch/módulo), el guard se omite por completo
        y el nivel superior corre (inicialización del módulo).
        Es más estricto que `if __name__ == "__main__":` de Python: en Python
        el nivel superior corre siempre; acá no — "si imprime el print, no es
        guard"."""
        if not self._is_main_file():
            return
        block_env = Env(parent=env)
        for s in stmt.body:
            self.exec_stmt(s, block_env)

    def _is_main_file(self) -> bool:
        """¿El archivo que se está ejecutando ahora es el programa principal?
        v0.6.3: el Interpreter raíz guarda la ruta del archivo de entrada
        (_main_file) y cada `require` se la propaga a sus hijos; el archivo
        cargado como batch tiene su propio filename, así que no es main."""
        import os
        if self.filename.startswith("<"):
            # REPL / stdin: la sesión interactiva es el programa principal
            return self.filename == self._main_file
        return os.path.abspath(self.filename) == self._main_file

    def _exec_global(self, stmt: GlobalStmt, env: Env):
        # Verificar que las variables existan en el entorno global
        global_env = env.find_global_env()
        for name in stmt.names:
            if global_env.lookup(name) is None:
                raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                    f"La variable global '{name}' no está declarada")
        # Marcar estas variables como accesibles para asignación desde este scope
        # Implementación simple: en assign(), ya subimos por la cadena hasta encontrarla.
        # 'global' sólo valida que exista; la asignación posterior funciona naturalmente.

    def _exec_try(self, stmt: TryStmt, env: Env):
        """try ... rescue(nombre: Tipo) ... end — filtra por tipo (v0.4.1).
        v0.6.2: admite VARIOS rescue en orden (spec 12.1); el primero cuyo
        tipo coincida con la jerarquía ejecuta su cuerpo."""
        # Normalizar: lista nueva `rescues` o formato v0.6.2 de un solo rescue
        clauses = stmt.rescues
        if not clauses and (stmt.rescue_name or stmt.rescue_type or stmt.rescue_body):
            clauses = [(stmt.rescue_name, stmt.rescue_type, stmt.rescue_body)]
        try:
            block_env = Env(parent=env)
            for s in stmt.body:
                self.exec_stmt(s, block_env)
        except RaiseSignal as r:
            if not self._run_rescue_clauses(clauses, env, r.error_value):
                raise
        except (AyceRuntimeError, AyceTypeError) as e:
            # Errores nativos de ayce se convierten en el error específico
            error_inst = self._make_native_error(e)
            if not self._run_rescue_clauses(clauses, env, error_inst):
                raise

    def _run_rescue_clauses(self, clauses, env: Env, error_val):
        """Ejecuta el primer rescue cuyo tipo coincida. Devuelve True si alguno
        manejó el error; False si hay que relanzarlo."""
        for rescue_name, rescue_type, rescue_body in clauses:
            if rescue_type:
                if not self._error_matches_type(error_val, rescue_type):
                    continue  # no coincide — probar el siguiente rescue
            rescue_env = Env(parent=env)
            if rescue_name:
                rescue_env.declare(rescue_name, error_val,
                                   UserTypeName(name="Error"), is_const=False)
            for s in rescue_body:
                self.exec_stmt(s, rescue_env)
            return True
        return False

    def _error_matches_type(self, error_val, type_name: str) -> bool:
        """¿El error coincide con el tipo especificado en rescue? (con herencia)"""
        if isinstance(error_val, AyceInstance):
            return error_val.template.is_subclass_of(type_name)
        return False

    def _make_native_error(self, e: "AyceError"):
        """Convierte un AyceError nativo en una instancia del error específico."""
        from .errors import NATIVE_ERRORS

        # Determinar qué error nativo corresponde
        error_name = "RunErr"  # por defecto
        msg = e.msg
        if isinstance(e, AyceTypeError):
            error_name = "TypeErr"
        elif isinstance(e, AyceRuntimeError):
            # Detectar tipos específicos por el mensaje
            if "JSONDecodeError" in msg:
                error_name = "JSONDecodeError"
            elif "División por cero" in msg or "división por cero" in msg:
                error_name = "Div0"
            elif "Índice" in msg and "fuera de rango" in msg:
                error_name = "IndexErr"
            elif "Clave" in msg and "no encontrada" in msg:
                error_name = "KeyErr"
            elif "no está declarada" in msg or "no declarado" in msg:
                error_name = "NameErr"
            elif "no existe" in msg and "campo" in msg:
                error_name = "AttrErr"
            elif "Recursión" in msg or "recursión" in msg:
                error_name = "OverErr"
            elif "entrada cerrada" in msg.lower():
                error_name = "IOErr"
            elif "Potencia" in msg or "Desbordamiento numérico" in msg:
                error_name = "FPErr"
            else:
                error_name = "RunErr"

        # Buscar el Template del error específico
        existing = self.global_env.lookup(error_name)
        if existing is None:
            # Fallback a Error base
            existing = self.global_env.lookup("Error")
            error_name = "Error"

        if existing is not None:
            tpl_val = existing[0]
            if isinstance(tpl_val, AyceTemplate):
                inst = AyceInstance(tpl_val)
                # Inicializar todos los campos (incluidos los heredados)
                for f in tpl_val.all_fields():
                    inst.fields[f.name] = None
                inst.fields["mensaje"] = msg
                # Código del error nativo
                info = NATIVE_ERRORS.get(error_name, {})
                inst.fields["codigo"] = info.get("code", 1)
                return inst
        return {"mensaje": msg, "codigo": 1}

    def _exec_raise(self, stmt: RaiseStmt, env: Env):
        """raise Error("mensaje", codigo)"""
        error_val = self.eval(stmt.error_expr, env)
        raise RaiseSignal(error_val)

    # ──────────────────────────────────────────────────────────────────
    #  Batchs (v0.5)
    # ──────────────────────────────────────────────────────────────────
    def _exec_require(self, stmt: RequireStmt, env: Env):
        """Procesa una sentencia `require`."""
        # 1. Modo string: require "ruta.ayce" [as A] — siempre carga desde archivo
        if stmt.mode == "string":
            batch_path = stmt.batch_spec
            batch_name = stmt.alias if stmt.alias else self._basename(batch_path)
            batch = self._load_batch(batch_path, stmt.line, stmt.col)
            bind_name = stmt.alias if stmt.alias else self._basename(batch_path)
            env.declare(bind_name, batch, UserTypeName(name=batch.name), is_const=True)
            return

        # 2. Modo batch entero: require M [as A]
        #    v0.6.2: la stdlib escrita en ayce (.ayce en disco) tiene PRIORIDAD
        #    sobre los batches built-in (wrappers de Python). Así el usuario
        #    puede reemplazar o complementar los builtins con su propio código
        #    ayce. Si no hay .ayce que coincida, se cae al builtin.
        if stmt.mode == "batch":
            batch_name = stmt.batch_spec
            # Primero intentar cargar como archivo .ayce
            batch_path = self._try_resolve_batch_path(batch_name)
            if batch_path is not None:
                batch = self._load_batch(batch_path, stmt.line, stmt.col)
                bind_name = stmt.alias if stmt.alias else batch_name
                env.declare(bind_name, batch, UserTypeName(name=batch.name), is_const=True)
                return
            # No hay .ayce — intentar built-in
            builtin = self._get_builtin_batch(batch_name)
            if builtin is not None:
                bind_name = stmt.alias if stmt.alias else batch_name
                env.declare(bind_name, builtin, UserTypeName(name=batch_name), is_const=True)
                return
            # Tampoco hay builtin — error claro de "no encontrado"
            raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                f"No se encontró el batch '{batch_name}' (ni como archivo .ayce "
                f"ni como batch built-in)")
            bind_name = stmt.alias if stmt.alias else stmt.batch_spec
            env.declare(bind_name, batch, UserTypeName(name=batch.name), is_const=True)
            return

        # 3. Modo selectivo: require X[, Y as Z] from M
        #    v0.6.2: igual que el modo batch, prioriza .ayce sobre built-in.
        if stmt.mode == "selective":
            batch_name = stmt.batch_spec
            batch_path = self._try_resolve_batch_path(batch_name)
            if batch_path is not None:
                batch = self._load_batch(batch_path, stmt.line, stmt.col)
                for item_name, item_alias in stmt.items:
                    export = batch.find_export(item_name)
                    if export is None:
                        raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                            f"El batch '{batch.name}' no exporta '{item_name}'")
                    if item_name in batch.exports:
                        v, t, is_const, init_flag = batch.exports[item_name]
                    else:
                        v, t, is_const, init_flag = export, None, True, True
                    bind_name = item_alias if item_alias else item_name
                    env.declare(bind_name, v, t, is_const=is_const, initialized=init_flag)
                return
            # No hay .ayce — probar built-in
            builtin = self._get_builtin_batch(batch_name)
            if builtin is not None:
                for item_name, item_alias in stmt.items:
                    if item_name not in builtin.exports:
                        raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                            f"El batch '{builtin.name}' no exporta '{item_name}'")
                    v, t, is_const, init_flag = builtin.exports[item_name]
                    bind_name = item_alias if item_alias else item_name
                    env.declare(bind_name, v, t, is_const=is_const, initialized=init_flag)
                return
            raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                f"No se encontró el batch '{batch_name}' (ni como archivo .ayce "
                f"ni como batch built-in)")

        raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
            f"Modo de require desconocido: {stmt.mode}")

    def _get_builtin_batch(self, name: str):
        """Devuelve el AyceNativeBatch con el nombre dado, o None si no existe."""
        from .batches import get_builtin_batches
        return get_builtin_batches().get(name)

    def _basename(self, path: str) -> str:
        """Devuelve el nombre del archivo sin extensión ni directorio."""
        import os
        base = os.path.basename(path)
        if base.endswith(".ayce"):
            base = base[:-5]
        return base

    def _try_resolve_batch_path(self, batch_name: str):
        """Como _resolve_batch_path pero devuelve None en vez de lanzar
        si no encuentra el archivo. Útil para priorizar la stdlib ayce
        sobre los batches built-in: si hay .ayce, lo usamos; si no, caemos
        al builtin."""
        import os
        target = batch_name + ".ayce"
        searched_dirs = set()

        current_dir = os.path.dirname(os.path.abspath(self.filename))
        cwd = os.getcwd()

        def check_dir(d):
            if d in searched_dirs:
                return None
            searched_dirs.add(d)
            c = os.path.join(d, target)
            if os.path.exists(c):
                return os.path.abspath(c)
            return None

        def walk_down(root_dir, max_depth=4):
            if not os.path.isdir(root_dir):
                return None
            for dirpath, dirnames, filenames in os.walk(root_dir):
                rel = os.path.relpath(dirpath, root_dir)
                depth = 0 if rel == "." else rel.count(os.sep) + 1
                if depth > max_depth:
                    dirnames[:] = []
                    continue
                dirnames[:] = [d for d in dirnames
                              if not d.startswith(".")
                              and d not in ("__pycache__", "node_modules", ".git",
                                            ".venv", "venv", "env", "build", "dist",
                                            ".idea", ".vscode", "site-packages")]
                r = check_dir(dirpath)
                if r is not None:
                    return r
            return None

        r = check_dir(current_dir)
        if r is not None:
            return r
        r = check_dir(cwd)
        if r is not None:
            return r
        for p in self.import_paths:
            r = check_dir(os.path.abspath(p))
            if r is not None:
                return r
        roots_to_walk = [current_dir, cwd]
        parent = current_dir
        while True:
            parent = os.path.dirname(parent)
            if parent == os.path.dirname(parent):
                break
            roots_to_walk.append(parent)
        for root_dir in roots_to_walk:
            r = walk_down(root_dir, max_depth=4)
            if r is not None:
                return r
        return None

    def _load_batch(self, path: str, line: int, col: int) -> AyceBatch:
        """Carga un batch desde un archivo .ayce. Usa caché y detecta ciclos."""
        import os
        # Resolver rutas relativas al directorio del archivo actual
        if not os.path.isabs(path):
            current_dir = os.path.dirname(os.path.abspath(self.filename))
            abs_path = os.path.normpath(os.path.join(current_dir, path))
        else:
            abs_path = path
        if abs_path in self._batch_cache:
            return self._batch_cache[abs_path]
        if abs_path in self._loading_stack:
            cycle = " -> ".join(self._loading_stack + [abs_path])
            raise AyceRuntimeError(self.filename, line, col,
                f"Import cíclico detectado: {cycle}")
        if not os.path.exists(abs_path):
            raise AyceRuntimeError(self.filename, line, col,
                f"El archivo del batch no existe: {path}")

        # Leer el archivo (utf-8-sig para BOM)
        with open(abs_path, "r", encoding="utf-8-sig") as f:
            source = f.read()

        # Parsear
        from .lexer import Lexer
        from .parser import Parser
        lexer = Lexer(source, filename=abs_path)
        tokens = lexer.tokenize()
        parser = Parser(tokens, filename=abs_path)
        program = parser.parse()

        # Ejecutar el batch en un Interpreter hijo que comparte la caché
        # y los import_paths, pero tiene su propio global_env
        child = Interpreter(filename=abs_path, import_paths=self.import_paths)
        child._batch_cache = self._batch_cache  # compartir caché
        # v0.6.3: el hijo hereda la ruta del programa principal; como su
        # filename es el del batch, sus bloques <GUARD>-<MAIN> no corren.
        child._main_file = self._main_file
        child._loading_stack = self._loading_stack + [abs_path]
        child.run(program)

        # El global_env del child contiene los exports del batch
        exports = dict(child.global_env.vars)
        # Filtrar el Error nativo y otros errores nativos (no se exportan)
        exports = {k: v for k, v in exports.items()
                   if k not in ("Error",) and not self._is_native_error_export(k, v)}

        batch = AyceBatch(
            name=self._basename(abs_path),
            filename=abs_path,
            exports=exports,
        )
        self._batch_cache[abs_path] = batch
        return batch

    def _is_native_error_export(self, name: str, value_tuple) -> bool:
        """Devuelve True si `name` es uno de los errores nativos (no exportar)."""
        from .errors import NATIVE_ERRORS
        if name in NATIVE_ERRORS:
            return True
        return False

    def _exec_compound_assign(self, stmt: CompoundAssignStmt, env: Env):
        """x += 5, x -= 2, etc."""
        target = stmt.target
        current = self.eval(target, env)
        value = self.eval(stmt.value, env)

        op = stmt.op[:-1]  # quitar el '=' final: "+=" → "+"
        # v0.6.2 (spec 4.4): bool no entra en la aritmética compuesta
        if op in ("+", "-", "*", "/", "%", "//") and \
                (isinstance(current, bool) or isinstance(value, bool)):
            raise AyceTypeError(self.filename, stmt.line, stmt.col,
                f"{stmt.op} no acepta bool (usá int(value) o float(value))")
        if op == "+":
            # Concatenación de strings con autoconversión
            if isinstance(current, str) or isinstance(value, str):
                if isinstance(current, bytes) and isinstance(value, bytes):
                    new_val = current + value
                elif isinstance(current, bytes) or isinstance(value, bytes):
                    # v0.6.2 (tabla 22): bytes sólo se concatena con bytes
                    raise AyceTypeError(self.filename, stmt.line, stmt.col,
                        "bytes sólo se concatena con bytes (usá string(b) para convertir)")
                else:
                    new_val = self._to_string_concat(current) + self._to_string_concat(value)
            elif isinstance(current, (int, float)) and isinstance(value, (int, float)):
                new_val = current + value
            else:
                raise AyceTypeError(self.filename, stmt.line, stmt.col,
                    f"No se puede aplicar {op}= a {self._type_name(current)} y {self._type_name(value)}")
        elif op == "-":
            if not (isinstance(current, (int, float)) and isinstance(value, (int, float))):
                raise AyceTypeError(self.filename, stmt.line, stmt.col,
                    f"-= requiere números")
            new_val = current - value
        elif op == "*":
            if not (isinstance(current, (int, float)) and isinstance(value, (int, float))):
                raise AyceTypeError(self.filename, stmt.line, stmt.col,
                    f"*= requiere números")
            new_val = current * value
        elif op == "/":
            if not (isinstance(current, (int, float)) and isinstance(value, (int, float))):
                raise AyceTypeError(self.filename, stmt.line, stmt.col,
                    f"/= requiere números")
            if value == 0:
                raise AyceRuntimeError(self.filename, stmt.line, stmt.col, "División por cero")
            new_val = float(current) / float(value)
        elif op == "//":
            if not (isinstance(current, int) and isinstance(value, int)):
                raise AyceTypeError(self.filename, stmt.line, stmt.col,
                    f"//= requiere enteros")
            if value == 0:
                raise AyceRuntimeError(self.filename, stmt.line, stmt.col, "División por cero")
            new_val = current // value
        elif op == "%":
            if not (isinstance(current, int) and isinstance(value, int)):
                raise AyceTypeError(self.filename, stmt.line, stmt.col,
                    f"%= requiere enteros")
            if value == 0:
                # v0.6.2 (I8): corregido el typo "Batch por cero"
                raise AyceRuntimeError(self.filename, stmt.line, stmt.col, "Módulo por cero")
            new_val = current % value
        elif op in ("&", "|", "^", "<<", ">>"):
            # v0.6.2: asignación compuesta bit a bit &=, |=, ^=, <<=, >>=
            if not (isinstance(current, int) and isinstance(value, int) and
                    not isinstance(current, bool) and not isinstance(value, bool)):
                raise AyceTypeError(self.filename, stmt.line, stmt.col,
                    f"{op}= requiere enteros")
            if op == "&":
                new_val = current & value
            elif op == "|":
                new_val = current | value
            elif op == "^":
                new_val = current ^ value
            elif op == "<<":
                if value < 0:
                    raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                        "Desplazamiento negativo en <<=")
                new_val = current << value
            else:  # >>
                if value < 0:
                    raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                        "Desplazamiento negativo en >>=")
                new_val = current >> value
        else:
            raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                f"Operador compuesto no soportado: {stmt.op}")

        # Asignar el nuevo valor al target
        if isinstance(target, IdentExpr):
            # v0.6.2: el resultado compuesto también valida el tipo declarado
            existing = env.lookup(target.name)
            if existing is not None:
                _, type_node, _, _ = existing
                new_val = self._check_value_matches_type(new_val, type_node,
                                                          stmt.line, stmt.col, env)
                new_val = self._coerce_value(new_val, type_node)
            env.assign(target.name, new_val, self.filename, target.line, target.col)
        elif isinstance(target, IndexExpr):
            container = self.eval(target.target, env)
            idx = self.eval(target.index, env)
            if isinstance(container, AyceList):
                # v0.6.2: bool no es índice; validar rango y tipo del elemento
                if isinstance(idx, bool):
                    raise AyceTypeError(self.filename, target.line, target.col,
                        "El índice debe ser int, no bool")
                if not isinstance(idx, int):
                    raise AyceTypeError(self.filename, target.line, target.col,
                        "El índice debe ser int")
                if idx < 0 or idx >= len(container.elements):
                    raise AyceRuntimeError(self.filename, target.line, target.col,
                        f"Índice {idx} fuera de rango (longitud {len(container.elements)})")
                elem_type = container.type_node.elem if not container.type_node.flexible else None
                if elem_type is not None:
                    self._check_value_matches_type(new_val, elem_type,
                                                   target.line, target.col, env)
                container.elements[idx] = new_val
            elif isinstance(container, str) or isinstance(container, bytes):
                # v0.6.2: strings y bytes son inmutables.
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    "Los strings y bytes son inmutables: no se puede asignar a s[i]")
            else:
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    "No se puede asignar a índice de ese tipo")
        elif isinstance(target, ModuleAccessExpr):
            obj = self.eval(target.target, env)
            if isinstance(obj, AyceInstance):
                obj.fields[target.name] = new_val
            else:
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    "No se puede asignar a campo de ese tipo")
        else:
            raise AyceRuntimeError(self.filename, target.line, target.col,
                "Objetivo de asignación compuesta inválido")

    # ──────────────────────────────────────────────────────────────────
    #  Expresiones
    # ──────────────────────────────────────────────────────────────────
    def eval(self, expr, env: Env):
        if isinstance(expr, IntLit):
            return expr.value
        if isinstance(expr, FloatLit):
            return expr.value
        if isinstance(expr, StringLit):
            return expr.value
        if isinstance(expr, BytesLit):
            return expr.value
        if isinstance(expr, BoolLit):
            return expr.value
        if isinstance(expr, NoneLit):
            return None
        if isinstance(expr, IdentExpr):
            existing = env.lookup(expr.name)
            if existing is None:
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    f"Variable '{expr.name}' no declarada")
            val, _, _, initialized = existing
            if not initialized:
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    f"Variable '{expr.name}' usada antes de ser inicializada")
            return val
        if isinstance(expr, FStringLit):
            return self._eval_fstring(expr, env)
        if isinstance(expr, ListLit):
            elements = [self.eval(e, env) for e in expr.elements]
            # El tipo se asigna en el momento de la declaración (var x: int[] = ...)
            # Pero necesitamos un tipo por defecto flexible para literales
            return AyceList(elements, ListType(flexible=True, line=expr.line, col=expr.col))
        if isinstance(expr, DictLit):
            pairs = []
            for k_expr, v_expr in expr.pairs:
                k = self.eval(k_expr, env)
                v = self.eval(v_expr, env)
                pairs.append((k, v))
            return AyceDict(pairs, DictType(flexible=True, line=expr.line, col=expr.col))
        if isinstance(expr, TupleLit):
            elements = [self.eval(e, env) for e in expr.elements]
            return AyceTuple(elements, TupleType(flexible=True, line=expr.line, col=expr.col))
        if isinstance(expr, SetLit):
            elements = [self.eval(e, env) for e in expr.elements]
            return AyceSet(elements, SetType(flexible=True, line=expr.line, col=expr.col))
        if isinstance(expr, IndexExpr):
            target = self.eval(expr.target, env)
            idx = self.eval(expr.index, env)
            # v0.6.2 (spec 4.4): bool no es un índice válido (bool no es int)
            if isinstance(idx, bool):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    "El índice debe ser int, no bool")
            if isinstance(target, AyceList):
                if not isinstance(idx, int):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "El índice debe ser int")
                if idx < 0 or idx >= len(target.elements):
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"Índice {idx} fuera de rango (longitud {len(target.elements)})")
                return target.elements[idx]
            if isinstance(target, AyceTuple):
                if not isinstance(idx, int):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "El índice debe ser int")
                if idx < 0 or idx >= len(target.elements):
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"Índice {idx} fuera de rango (longitud {len(target.elements)})")
                return target.elements[idx]
            if isinstance(target, str):
                # v0.6.2: indexación de strings — s[i] devuelve un string de 1 char.
                if not isinstance(idx, int):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "El índice de string debe ser int")
                if idx < 0 or idx >= len(target):
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"Índice {idx} fuera de rango (longitud {len(target)})")
                return target[idx]
            if isinstance(target, bytes):
                # v0.6.2: indexación de bytes — b[i] devuelve el byte como int (0-255).
                if not isinstance(idx, int):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "El índice de bytes debe ser int")
                if idx < 0 or idx >= len(target):
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"Índice {idx} fuera de rango (longitud {len(target)})")
                return target[idx]
            raise AyceTypeError(self.filename, expr.line, expr.col,
                f"No se puede indexar {self._type_name(target)}")
        if isinstance(expr, DictAccessExpr):
            target = self.eval(expr.target, env)
            key = self.eval(expr.key, env)
            if not isinstance(target, AyceDict):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"No se puede acceder con <> a {self._type_name(target)}")
            # v0.6.2: clave bool sólo si el dict la declara (<bool, ...>)
            if isinstance(key, bool):
                kt = target.type_node.key_type if isinstance(target.type_node, DictType) else None
                if not (isinstance(kt, PrimitiveType) and kt.name == "bool"):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "La clave no puede ser bool (usá int(key) o 1/0)")
            if key not in target.pairs:
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    f"Clave {key!r} no encontrada en el diccionario")
            return target.pairs[key]
        if isinstance(expr, MethodCallExpr):
            return self._eval_method_call(expr, env)
        if isinstance(expr, CallExpr):
            return self._eval_call(expr, env)
        if isinstance(expr, UnaryExpr):
            operand = self.eval(expr.operand, env)
            if expr.op == "!":
                if not isinstance(operand, bool):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        f"El operador ! requiere bool, se recibió {self._type_name(operand)}")
                return not operand
            if expr.op == "-":
                # v0.6.2 (spec 4.4): bool no es número (-True es error)
                if isinstance(operand, bool):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "El operador - unario no acepta bool (usá int(value))")
                if isinstance(operand, int) or isinstance(operand, float):
                    return -operand
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"El operador - unario requiere número, se recibió {self._type_name(operand)}")
            if expr.op == "~":
                if not isinstance(operand, int) or isinstance(operand, bool):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        f"El operador ~ bit a bit requiere entero, se recibió {self._type_name(operand)}")
                return ~operand
        if isinstance(expr, BinaryExpr):
            return self._eval_binary(expr, env)
        if isinstance(expr, RangeExpr):
            start = self.eval(expr.start, env)
            end = self.eval(expr.end, env)
            if not isinstance(start, int) or not isinstance(end, int):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"range() requiere dos int, se recibió {self._type_name(start)} y {self._type_name(end)}")
            return list(range(start, end))
        if isinstance(expr, InletExpr):
            prompt = ""
            if expr.prompt is not None:
                prompt = self.eval(expr.prompt, env)
                if not isinstance(prompt, str):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        f"El prompt de inlet debe ser string, se recibió {self._type_name(prompt)}")
            if expr.target_type == "none":
                try:
                    raw = input(prompt)
                except EOFError:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "Entrada cerrada (EOF) en inlet")
                stripped = raw.strip()
                lower = stripped.lower()
                if lower in ("true", "yes", "y", "sí", "si", "verdadero"):
                    return True
                if lower in ("false", "no", "n", "falso"):
                    return False
                try:
                    return int(stripped)
                except ValueError:
                    pass
                try:
                    return float(stripped)
                except ValueError:
                    return raw
            # Si no hay tipo, devolver string
            if not expr.target_type or expr.target_type == "string":
                try:
                    return input(prompt)
                except EOFError:
                    # v0.6.2 (I22): stdin cerrado → error limpio capturable, no traceback
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "Entrada cerrada (EOF) en inlet")
            # Si hay tipo, repetir hasta que sea válido
            while True:
                try:
                    raw = input(prompt)
                except EOFError:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "Entrada cerrada (EOF) en inlet")
                if expr.target_type == "int":
                    try:
                        return int(raw)
                    except ValueError:
                        print(f"'{raw}' no es un int válido. Intentá de nuevo.")
                elif expr.target_type == "float":
                    try:
                        return float(raw)
                    except ValueError:
                        print(f"'{raw}' no es un float válido. Intentá de nuevo.")
                elif expr.target_type == "bytes":
                    try:
                        return raw.encode("utf-8")
                    except Exception:
                        print(f"'{raw}' no es convertible a bytes. Intentá de nuevo.")
                elif expr.target_type == "bool":
                    r = raw.strip().lower()
                    if r in ("true", "t", "1", "yes", "y", "s", "si", "sí", "verdadero"):
                        return True
                    if r in ("false", "f", "0", "no", "n", "falso"):
                        return False
                    print(f"'{raw}' no es un bool válido. Usá s/n, true/false, 1/0.")
                else:
                    return raw
        if isinstance(expr, TernaryExpr):
            cond_val = self.eval(expr.cond, env)
            if not isinstance(cond_val, bool):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"La condición del ternario debe ser bool, se recibió {self._type_name(cond_val)}")
            if cond_val:
                return self.eval(expr.if_true, env)
            else:
                return self.eval(expr.if_false, env)
        if isinstance(expr, TypeConvertExpr):
            return self._convert_type(expr, env)
        if isinstance(expr, SelfExpr):
            existing = env.lookup("self")
            if existing is None:
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    "'self' sólo es válido dentro de un método de Template")
            val, _, _, _ = existing
            return val
        if isinstance(expr, ModuleAccessExpr):
            target = self.eval(expr.target, env)
            from .batches import AyceNativeBatch
            # Acceso a export de batch: utils::MAX
            #   (batch cargado desde archivo .ayce o batch built-in)
            if isinstance(target, (AyceBatch, AyceNativeBatch)):
                export = target.find_export(expr.name)
                if export is None:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"El batch '{target.name}' no exporta '{expr.name}'")
                return export
            # Acceso a campo de Template instance: p::edad
            if isinstance(target, AyceInstance):
                if expr.name not in target.fields:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"El campo '{expr.name}' no existe en {target.template.name}")
                return target.fields[expr.name]
            # Acceso a campo de Shape value: punto::x
            if isinstance(target, AyceShapeValue):
                if expr.name not in target.fields:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"El campo '{expr.name}' no existe en {target.shape.name}")
                return target.fields[expr.name]
            # Acceso a caso de Variant (sin payload): Color::Rojo
            # Caso encadenado desde batch: utils::Estado::Activo
            #   aquí target es AyceVariant (devuelto por el ModuleAccessExpr anterior)
            if isinstance(target, AyceVariant):
                case = target.find_case(expr.name)
                if case is None:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"El caso '{expr.name}' no existe en Variant {target.name}")
                if case.payload_type is not None:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"El caso '{expr.name}' requiere un payload; usá {target.name}::{expr.name}(valor)")
                return AyceVariantValue(target, expr.name, None)
            raise AyceTypeError(self.filename, expr.line, expr.col,
                f"No se puede acceder a miembro '::{expr.name}' de {self._type_name(target)}")
        if isinstance(expr, NewExpr):
            # Construcción de Shape
            existing = env.lookup(expr.type_name)
            if existing is None:
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    f"Tipo '{expr.type_name}' no declarado")
            shape_val, _, _, _ = existing
            if not isinstance(shape_val, AyceShape):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"'{expr.type_name}' no es un Shape")
            instance = AyceShapeValue(shape_val)
            # Inicializar campos con defaults si los tiene
            for f in shape_val.decl.fields:
                if f.default is not None:
                    instance.fields[f.name] = self.eval(f.default, env)
            # Asignar campos pasados
            passed_names = set()
            for fname, fval_expr in expr.fields:
                if not any(f.name == fname for f in shape_val.decl.fields):
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"El campo '{fname}' no existe en Shape {shape_val.name}")
                instance.fields[fname] = self.eval(fval_expr, env)
                passed_names.add(fname)
            # Verificar que todos los campos sin default estén asignados
            for f in shape_val.decl.fields:
                if f.name not in passed_names and f.default is None:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"Falta asignar el campo '{f.name}' en {shape_val.name}")
            return instance
        if isinstance(expr, TemplateCallExpr):
            # Construcción de Template: Persona("Carlos", 25)
            existing = env.lookup(expr.type_name)
            if existing is None:
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    f"Tipo '{expr.type_name}' no declarado")
            tpl_val, _, _, _ = existing
            if not isinstance(tpl_val, AyceTemplate):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"'{expr.type_name}' no es un Template")
            instance = AyceInstance(tpl_val)
            # Inicializar campos con defaults
            for f in tpl_val.all_fields():
                if f.default is not None:
                    instance.fields[f.name] = self.eval(f.default, env)
            # Si hay un método `build`, llamarlo con los args (v0.5: build reemplaza a init)
            build_method = tpl_val.find_method("build")
            if build_method is not None:
                args = [self.eval(a, env) for a in expr.args]
                self._call_template_build(tpl_val, build_method, instance, args, expr.line, expr.col)
            elif expr.args:
                # v0.6.2 (tabla 64): sin build, la construcción no acepta argumentos
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    f"{tpl_val.name} no declara build y no acepta argumentos "
                    f"({len(expr.args)} pasados)")
            return instance
        if isinstance(expr, IsExpr):
            left = self.eval(expr.left, env)
            if not isinstance(left, AyceVariantValue):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"is sólo aplica a Variant, se recibió {self._type_name(left)}")
            if left.variant.name != expr.type_name:
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    f"El variant no es del tipo {expr.type_name}")
            return left.case_name == expr.case_name
        raise AyceRuntimeError(self.filename, expr.line, expr.col,
            f"Expresión no soportada: {type(expr).__name__}")

    def _eval_fstring(self, expr: FStringLit, env: Env) -> str:
        out = []
        for part in expr.parts:
            if part[0] == "text":
                out.append(part[1])
            elif part[0] == "expr":
                # part = ("expr", Expr, fmt_str)
                expr_node = part[1]
                fmt_str = part[2] if len(part) > 2 else ""
                v = self.eval(expr_node, env)
                if fmt_str:
                    out.append(self._apply_format(v, fmt_str))
                else:
                    out.append(self._format_value(v))
        return "".join(out)

    def _apply_format(self, value, fmt: str) -> str:
        """Aplica un formato tipo Python: :.2f, :10d, :>10, :05d, etc."""
        # Construir el spec de Python y usar format()
        # fmt ya viene sin el ':' inicial (lo quitó el lexer)
        try:
            # Mapear tipos de ayce a Python
            if isinstance(value, bool):
                # bool en Python se formatea como int con 'd'
                if fmt.endswith("d"):
                    return format(int(value), fmt)
                return ("True" if value else "False")
            if isinstance(value, int):
                return format(value, fmt)
            if isinstance(value, float):
                return format(value, fmt)
            if isinstance(value, str):
                return format(value, fmt)
            if value is None:
                return "none"
            return format(self._format_value(value), fmt)
        except (ValueError, TypeError):
            # Si el formato falla, devolver sin formato
            return self._format_value(value)

    def _eval_binary(self, expr: BinaryExpr, env):
        # Cortocircuito en && y ||
        if expr.op == "&&":
            left = self.eval(expr.left, env)
            if not isinstance(left, bool):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"&& requiere bool, se recibió {self._type_name(left)}")
            if not left:
                return False
            right = self.eval(expr.right, env)
            if not isinstance(right, bool):
                raise AyceTypeError(self.filename, expr.right.line, expr.right.col,
                    f"&& requiere bool, se recibió {self._type_name(right)}")
            return right
        if expr.op == "||":
            left = self.eval(expr.left, env)
            if not isinstance(left, bool):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"|| requiere bool, se recibió {self._type_name(left)}")
            if left:
                return True
            right = self.eval(expr.right, env)
            if not isinstance(right, bool):
                raise AyceTypeError(self.filename, expr.right.line, expr.right.col,
                    f"|| requiere bool, se recibió {self._type_name(right)}")
            return right

        left = self.eval(expr.left, env)
        right = self.eval(expr.right, env)

        # Aritmética
        if expr.op in ("+", "-", "*", "/", "%", "**", "//"):
            # Concatenación de strings con autoconversión
            # Si uno de los operandos es string, el otro se convierte a string
            if expr.op == "+" and (isinstance(left, str) or isinstance(right, str)):
                # Pero no si ambos son bytes (eso es suma de bytes)
                if isinstance(left, bytes) and isinstance(right, bytes):
                    return left + right
                # v0.6.2 (tabla 22): bytes sólo se concatena con bytes
                if isinstance(left, bytes) or isinstance(right, bytes):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "bytes sólo se concatena con bytes (usá string(b) para convertir)")
                return self._to_string_concat(left) + self._to_string_concat(right)
            # Suma de bytes
            if expr.op == "+" and isinstance(left, bytes) and isinstance(right, bytes):
                return left + right
            # Concatenación de listas (v0.6.2): [1,2] + [3,4] = [1,2,3,4]
            if expr.op == "+" and isinstance(left, AyceList) and isinstance(right, AyceList):
                new_elems = list(left.elements) + list(right.elements)
                # El tipo resultante: si alguno es flexible, queda flexible.
                # Si ambos tienen elem_type y coinciden, conserva ese elem_type.
                lt = left.type_node
                rt = right.type_node
                if lt.flexible or rt.flexible:
                    new_type = ListType(elem=None, flexible=True,
                                        line=expr.line, col=expr.col)
                elif (lt.elem is not None and rt.elem is not None and
                      self._type_signature(lt.elem) == self._type_signature(rt.elem)):
                    new_type = ListType(elem=lt.elem, flexible=False,
                                        line=expr.line, col=expr.col)
                else:
                    # tipos heterogéneos -> lista flexible
                    new_type = ListType(elem=None, flexible=True,
                                        line=expr.line, col=expr.col)
                return AyceList(new_elems, new_type)
            # División entera // (v0.4): requiere ints, devuelve int
            if expr.op == "//":
                if not (isinstance(left, int) and isinstance(right, int) and
                        not isinstance(left, bool) and not isinstance(right, bool)):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        f"El operador // requiere enteros, "
                        f"se recibió {self._type_name(left)} y {self._type_name(right)}")
                if right == 0:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col, "División por cero")
                return left // right
            # v0.6.2 (spec 4.4): bool no entra en la aritmética (True + 1 es error)
            if isinstance(left, bool) or isinstance(right, bool):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"El operador {expr.op} no acepta bool (usá int(value) o float(value))")
            if not (isinstance(left, (int, float)) and isinstance(right, (int, float))):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"El operador {expr.op} requiere números, "
                    f"se recibió {self._type_name(left)} y {self._type_name(right)}")
            if expr.op == "+": return left + right
            if expr.op == "-": return left - right
            if expr.op == "*": return left * right
            if expr.op == "/":
                if right == 0:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "División por cero")
                return float(left) / float(right)  # siempre float
            if expr.op == "%":
                if right == 0:
                    # v0.6.2 (I8): corregido el typo "Batch por cero"
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "Módulo por cero")
                return left % right
            if expr.op == "**":
                # v0.6.2 (I10): sin fugas de Python — 0**negativo es Div0 y la
                # base negativa con exponente fraccional no produce complex
                if left == 0 and right < 0:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "División por cero")
                if isinstance(left, (int, float)) and left < 0 \
                        and isinstance(right, float) and not float(right).is_integer():
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "Potencia de base negativa con exponente fraccional")
                try:
                    return left ** right
                except OverflowError:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "Desbordamiento numérico en **")
                except ZeroDivisionError:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "División por cero")

        # Operadores bit a bit (v0.6.2): & | ^ << >> — solo enteros (no bool)
        if expr.op in ("&", "|", "^", "<<", ">>"):
            for side in (left, right):
                if not isinstance(side, int) or isinstance(side, bool):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        f"El operador {expr.op} bit a bit requiere enteros, "
                        f"se recibió {self._type_name(side)}")
            if expr.op == "&": return left & right
            if expr.op == "|": return left | right
            if expr.op == "^": return left ^ right
            if expr.op == "<<":
                if right < 0:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "Desplazamiento negativo en <<")
                return left << right
            if expr.op == ">>":
                if right < 0:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "Desplazamiento negativo en >>")
                return left >> right

        # Comparaciones
        if expr.op in ("==", "!="):
            # v0.6.2: comparar con none es siempre válido (estilo Python `x is None`).
            # Cualquier valor puede preguntarse si es none o no es none.
            if left is None or right is None:
                return (left == right) if expr.op == "==" else (left != right)
            # Igualdad de tipos compatibles
            if type(left) != type(right):
                # int y float se permiten
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    pass
                else:
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        f"No se puede comparar {self._type_name(left)} con {self._type_name(right)}")
            return (left == right) if expr.op == "==" else (left != right)
        if expr.op in ("<", ">", "<=", ">="):
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                pass
            elif isinstance(left, str) and isinstance(right, str):
                pass
            else:
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"No se puede comparar {self._type_name(left)} con {self._type_name(right)} con {expr.op}")
            if expr.op == "<":  return left < right
            if expr.op == ">":  return left > right
            if expr.op == "<=": return left <= right
            if expr.op == ">=": return left >= right

        raise AyceRuntimeError(self.filename, expr.line, expr.col,
            f"Operador no soportado: {expr.op}")

    def _eval_method_call(self, expr: MethodCallExpr, env):
        target = self.eval(expr.target, env)
        method = expr.method
        args = [self.eval(a, env) for a in expr.args]

        # ── Batch: llamada a función exportada (utils::saludar(), utils::Punto(x, y)) ──
        #   (Batch cargado desde archivo .ayce o batch built-in)
        from .batches import AyceNativeBatch, AyceNativeTask
        if isinstance(target, (AyceBatch, AyceNativeBatch)):
            export = target.find_export(method)
            if export is None:
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    f"El batch '{target.name}' no exporta '{method}'")
            # Tarea implementada en ayce (AyceTask)
            if isinstance(export, AyceTask):
                return self._call_task(export, args, expr.line, expr.col)
            # Tarea nativa implementada en Python (AyceNativeTask)
            from .batches import AyceNativeTask
            if isinstance(export, AyceNativeTask):
                try:
                    return export.func(self, args, expr.line, expr.col)
                except (AyceRuntimeError, AyceTypeError):
                    raise
                except Exception as e:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"Error en batch built-in '{target.name}::{method}': {e}")
            # Si es un Template, construir instancia
            if isinstance(export, AyceTemplate):
                instance = AyceInstance(export)
                for f in export.all_fields():
                    if f.default is not None:
                        instance.fields[f.name] = self.eval(f.default, env)
                    else:
                        instance.fields[f.name] = None
                build_method = export.find_method("build")
                if build_method is not None:
                    self._call_template_build(export, build_method, instance, args,
                                               expr.line, expr.col)
                elif args:
                    # v0.6.2 (tabla 64): sin build, la construcción no acepta argumentos
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"{export.name} no declara build y no acepta argumentos "
                        f"({len(args)} pasados)")
                return instance
            # Si es un Variant con payload: Modulo::VariantName::Caso(valor)
            # No aplicable aquí — eso sería otra cadena de postfix
            raise AyceRuntimeError(self.filename, expr.line, expr.col,
                f"'{method}' en el batch '{target.name}' no es una tarea ni un Template")

        # ── Instancia de Template: llamada a método ──
        if isinstance(target, AyceInstance):
            method_decl = target.template.find_method(method)
            if method_decl is None:
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    f"El método '{method}' no existe en {target.template.name}")
            # Crear entorno: closure de la template + self
            call_env = Env(parent=target.template.closure_env)
            call_env.declare("self", target,
                             UserTypeName(name=target.template.name), is_const=True)
            # Bind de parámetros (una sola firma por método, sin sobrecarga por ahora)
            sig = method_decl.signatures[0]
            body = method_decl.bodies[0]
            params = sig.params
            filled = list(args)
            for i in range(len(args), len(params)):
                p = params[i]
                if p.default is not None:
                    filled.append(self.eval(p.default, self.global_env))
                else:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"Falta argumento para '{p.name}' en {target.template.name}.{method}")
            for i, p in enumerate(params):
                call_env.declare(p.name, filled[i], p.type_node,
                                is_const=(p.modifier == "const"))
            # v0.6.2 (I5): los métodos también cuentan para el límite de recursión
            self._ayce_depth += 1
            try:
                if self._ayce_depth > self.MAX_CALL_DEPTH:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "Recursión demasiado profunda: se superó el límite de llamadas anidadas")
                try:
                    for s in body:
                        self.exec_stmt(s, call_env)
                except ReturnSignal as r:
                    return r.value
                if method_decl.return_type is not None:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"El método '{method}' declara retorno pero no ejecutó return")
                return None
            finally:
                self._ayce_depth -= 1

        # ── Variant con payload: Resultado.Ok(42) ──
        # En este caso el parser genera MethodCallExpr porque ve Color.Rojo(args)
        # Pero el target es un Variant (no un caso), así que esto no aplica.
        # En realidad, si target es AyceVariant y method es un caso con payload:
        if isinstance(target, AyceVariant):
            case = target.find_case(method)
            if case is not None:
                if case.payload_type is None:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"El caso '{method}' no lleva payload; usá {target.name}.{method}")
                if len(args) != 1:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"El caso '{method}' requiere exactamente 1 payload")
                return AyceVariantValue(target, method, args[0])
            raise AyceRuntimeError(self.filename, expr.line, expr.col,
                f"El caso '{method}' no existe en Variant {target.name}")

        # ── Listas ──
        if isinstance(target, AyceList):
            if method == "append":
                if len(args) != 1:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "append requiere 1 argumento")
                # v0.6.2 (spec 4.3): append valida el tipo declarado de la lista
                tn = target.type_node
                if isinstance(tn, ListType) and not tn.flexible and tn.elem is not None:
                    self._check_value_matches_type(args[0], tn.elem, expr.line, expr.col, env)
                target.elements.append(args[0])
                return None
            if method == "insert":
                if len(args) != 2:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "insert requiere 2 argumentos (índice, valor)")
                if not isinstance(args[0], int) or isinstance(args[0], bool):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "insert: el índice debe ser int")
                # v0.6.2 (spec 4.3): insert valida el tipo declarado de la lista
                tn = target.type_node
                if isinstance(tn, ListType) and not tn.flexible and tn.elem is not None:
                    self._check_value_matches_type(args[1], tn.elem, expr.line, expr.col, env)
                target.elements.insert(args[0], args[1])
                return None
            if method == "delete":
                if len(args) != 1:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "delete requiere 1 argumento (índice)")
                if not isinstance(args[0], int):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "delete: el índice debe ser int")
                if args[0] < 0 or args[0] >= len(target.elements):
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        f"delete: índice {args[0]} fuera de rango")
                target.elements.pop(args[0])
                return None
            if method == "len":
                return len(target.elements)
            if method == "contains":
                if len(args) != 1:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "contains requiere 1 argumento")
                return args[0] in target.elements
            if method == "clear":
                target.elements.clear()
                return None
            if method == "copy":
                # Devuelve una copia superficial (shallow) de la lista.
                if len(args) != 0:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "copy no toma argumentos")
                return AyceList(list(target.elements),
                                ListType(flexible=True, line=expr.line, col=expr.col))
            if method == "extend":
                if len(args) != 1 or not isinstance(args[0], AyceList):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "extend requiere 1 lista")
                target.elements.extend(args[0].elements)
                return None
            if method == "pop":
                if len(args) == 0:
                    if not target.elements:
                        raise AyceRuntimeError(self.filename, expr.line, expr.col,
                            "pop: lista vacía")
                    return target.elements.pop()
                if len(args) == 1 and isinstance(args[0], int):
                    idx = args[0]
                    if idx < 0 or idx >= len(target.elements):
                        raise AyceRuntimeError(self.filename, expr.line, expr.col,
                            f"pop: índice {idx} fuera de rango")
                    return target.elements.pop(idx)
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    "pop requiere 0 args o 1 int")
            if method == "index":
                if len(args) != 1:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "index requiere 1 argumento")
                try:
                    return target.elements.index(args[0])
                except ValueError:
                    return -1
            if method == "count":
                if len(args) != 1:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "count requiere 1 argumento")
                return target.elements.count(args[0])
            if method == "reverse":
                target.elements.reverse()
                return None
            if method == "sort":
                # sort solo para listas comparables (int, float, string)
                if len(args) != 0:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "sort no toma argumentos")
                try:
                    target.elements.sort()
                except TypeError:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "sort: los elementos no son comparables entre sí")
                return None
            if method == "first":
                if not target.elements:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "first: lista vacía")
                return target.elements[0]
            if method == "last":
                if not target.elements:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "last: lista vacía")
                return target.elements[-1]
            if method == "is_empty":
                return len(target.elements) == 0
            if method == "join":
                # Convierte lista de strings a un solo string con separador.
                if len(args) != 1 or not isinstance(args[0], str):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "join requiere 1 string (separador)")
                parts = []
                for e in target.elements:
                    if not isinstance(e, str):
                        raise AyceTypeError(self.filename, expr.line, expr.col,
                            "join: todos los elementos deben ser string")
                    parts.append(e)
                return args[0].join(parts)
            raise AyceRuntimeError(self.filename, expr.line, expr.col,
                f"Las listas no tienen el método '{method}'")

        # ── Diccionarios ──
        if isinstance(target, AyceDict):
            if method == "remove":
                if len(args) != 1:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "remove requiere 1 argumento (clave)")
                if args[0] in target.pairs:
                    del target.pairs[args[0]]
                return None
            if method == "has":
                if len(args) != 1:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "has requiere 1 argumento")
                return args[0] in target.pairs
            if method == "len":
                return len(target.pairs)
            if method == "keys":
                return AyceList(list(target.pairs.keys()),
                                ListType(flexible=True, line=expr.line, col=expr.col))
            if method == "values":
                return AyceList(list(target.pairs.values()),
                                ListType(flexible=True, line=expr.line, col=expr.col))
            if method == "items":
                # Devuelve lista de tuplas (clave, valor)
                items = [AyceTuple([k, v], TupleType(flexible=True, line=expr.line, col=expr.col))
                         for k, v in target.pairs.items()]
                return AyceList(items, ListType(flexible=True, line=expr.line, col=expr.col))
            if method == "clear":
                target.pairs.clear()
                return None
            raise AyceRuntimeError(self.filename, expr.line, expr.col,
                f"Los diccionarios no tienen el método '{method}'")

        # ── Tuplas ──
        if isinstance(target, AyceTuple):
            if method == "len":
                return len(target.elements)
            if method == "contains":
                if len(args) != 1:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "contains requiere 1 argumento")
                return args[0] in target.elements
            raise AyceRuntimeError(self.filename, expr.line, expr.col,
                f"Las tuplas no tienen el método '{method}'")

        # ── Sets ──
        if isinstance(target, AyceSet):
            if method == "add":
                if len(args) != 1:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "add requiere 1 argumento")
                if args[0] not in target.elements:
                    target.elements.append(args[0])
                return None
            if method == "remove":
                if len(args) != 1:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "remove requiere 1 argumento (valor)")
                if args[0] in target.elements:
                    target.elements.remove(args[0])
                return None
            if method == "contains":
                if len(args) != 1:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "contains requiere 1 argumento")
                return args[0] in target.elements
            if method == "len":
                return len(target.elements)
            if method == "clear":
                target.elements.clear()
                return None
            raise AyceRuntimeError(self.filename, expr.line, expr.col,
                f"Los sets no tienen el método '{method}'")

        # ── Strings ──
        if isinstance(target, str):
            if method == "len":
                return len(target)
            if method == "contains":
                if len(args) != 1 or not isinstance(args[0], str):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "string.contains requiere 1 string")
                return args[0] in target
            if method == "upper":
                return target.upper()
            if method == "lower":
                return target.lower()
            if method == "split":
                if len(args) != 1 or not isinstance(args[0], str):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "string.split requiere 1 string")
                return AyceList(target.split(args[0]),
                                ListType(elem=PrimitiveType(name="string"),
                                         line=expr.line, col=expr.col))
            # Métodos nuevos v0.4
            if method == "slice":
                if len(args) != 2 or not isinstance(args[0], int) or not isinstance(args[1], int):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "string.slice requiere 2 int (inicio, fin)")
                return target[args[0]:args[1]]
            if method == "replace":
                if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], str):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "string.replace requiere 2 strings (viejo, nuevo)")
                return target.replace(args[0], args[1])
            if method == "trim":
                if len(args) != 0:
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "string.trim no toma argumentos")
                return target.strip()
            if method == "starts_with":
                if len(args) != 1 or not isinstance(args[0], str):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "string.starts_with requiere 1 string")
                return target.startswith(args[0])
            if method == "ends_with":
                if len(args) != 1 or not isinstance(args[0], str):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "string.ends_with requiere 1 string")
                return target.endswith(args[0])
            if method == "find":
                if len(args) != 1 or not isinstance(args[0], str):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "string.find requiere 1 string")
                idx = target.find(args[0])
                return idx  # -1 si no está
            if method == "reverse":
                if len(args) != 0:
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "string.reverse no toma argumentos")
                return target[::-1]
            if method == "repeat":
                if len(args) != 1 or not isinstance(args[0], int):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "string.repeat requiere 1 int")
                return target * args[0]
            raise AyceRuntimeError(self.filename, expr.line, expr.col,
                f"string no tiene el método '{method}'")

        # ── Bytes ──
        if isinstance(target, bytes):
            if method == "len":
                return len(target)
            raise AyceRuntimeError(self.filename, expr.line, expr.col,
                f"bytes no tiene el método '{method}'")

        raise AyceTypeError(self.filename, expr.line, expr.col,
            f"El tipo {self._type_name(target)} no tiene métodos")

    def _eval_call(self, expr: CallExpr, env: Env):
        # Caso: llamada a método de instancia — p.metodo(args)
        # El parser genera MethodCallExpr para eso, así que CallExpr con target IdentExpr
        # es siempre llamada a tarea o construcción de Template.
        if not isinstance(expr.target, IdentExpr):
            raise AyceRuntimeError(self.filename, expr.line, expr.col,
                "Sólo se pueden llamar tareas por nombre")
        name = expr.target.name
        existing = env.lookup(name)
        if existing is None:
            raise AyceRuntimeError(self.filename, expr.line, expr.col,
                f"'{name}' no declarado")
        target_val, _, _, _ = existing
        # Si es un Template, construir instancia
        if isinstance(target_val, AyceTemplate):
            args = [self.eval(a, env) for a in expr.args]
            instance = AyceInstance(target_val)
            # Inicializar TODOS los campos con None primero (serán asignados por build)
            for f in target_val.all_fields():
                if f.default is not None:
                    instance.fields[f.name] = self.eval(f.default, env)
                else:
                    instance.fields[f.name] = None
            build_method = target_val.find_method("build")
            if build_method is not None:
                self._call_template_build(target_val, build_method, instance, args,
                                          expr.line, expr.col)
            elif args:
                # v0.6.2 (tabla 64): sin build, la construcción no acepta argumentos
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    f"{target_val.name} no declara build y no acepta argumentos "
                    f"({len(args)} pasados)")
            return instance
        # Si es un Variant con payload (caso Ok(valor)) — pero eso se maneja en postfix,
        # porque el parser genera CallExpr con target = FieldAccessExpr.
        # Si es un Variant directamente llamado (no debería), error.
        if isinstance(target_val, AyceVariant):
            raise AyceRuntimeError(self.filename, expr.line, expr.col,
                f"Para construir un caso de Variant usá {name}.Caso(valor)")
        # Si es un Shape, error (los Shape se construyen con `new`)
        if isinstance(target_val, AyceShape):
            raise AyceRuntimeError(self.filename, expr.line, expr.col,
                f"Para construir un Shape usá: new {name} {{ ... }}")
        # Si es una tarea, llamarla
        if isinstance(target_val, AyceTask):
            return self._call_task(target_val, [self.eval(a, env) for a in expr.args],
                                    expr.line, expr.col)
        # v0.6.2: tarea nativa retenida en una variable (p.ej. `var f: task =
        # primitives::math_sqrt` o require selectivo de un batch built-in).
        from .batches import AyceNativeTask
        if isinstance(target_val, AyceNativeTask):
            args = [self.eval(a, env) for a in expr.args]
            try:
                return target_val.func(self, args, expr.line, expr.col)
            except (AyceRuntimeError, AyceTypeError):
                raise
            except Exception as e:
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    f"Error en tarea nativa '{name}': {e}")
        raise AyceRuntimeError(self.filename, expr.line, expr.col,
            f"'{name}' no es una tarea ni un Template")

    def _call_template_build(self, template: AyceTemplate, build_decl: TaskDecl,
                             instance: AyceInstance, args: list, line: int, col: int):
        """Llama al método `build` de un Template sobre una instancia recién creada."""
        # Crear entorno: closure de la template + self + parámetros
        call_env = Env(parent=template.closure_env)
        call_env.declare("self", instance,
                         UserTypeName(name=template.name), is_const=True)
        # build tiene una sola firma (no se permite sobrecarga de build por ahora)
        sig = build_decl.signatures[0]
        body = build_decl.bodies[0]
        # Aplicar defaults y bind de parámetros (similar a _call_task)
        params = sig.params
        # v0.6.2 (I19): argumentos de más en build = error (igual que en llamadas),
        # salvo que el último parámetro sea varargs
        if not (params and params[-1].varargs) and len(args) > len(params):
            raise AyceRuntimeError(self.filename, line, col,
                f"El build de {template.name} recibe {len(params)} argumento(s), "
                f"se pasaron {len(args)}")
        filled = list(args)
        for i in range(len(args), len(params)):
            p = params[i]
            if p.default is not None:
                filled.append(self.eval(p.default, self.global_env))
            else:
                raise AyceRuntimeError(self.filename, line, col,
                    f"Falta argumento para parámetro '{p.name}' en build de {template.name}")
        for i, p in enumerate(params):
            call_env.declare(p.name, filled[i], p.type_node,
                            is_const=(p.modifier == "const"))
        try:
            for s in body:
                self.exec_stmt(s, call_env)
        except ReturnSignal:
            pass  # build puede tener return sin valor para salir temprano


    def _call_task(self, task: AyceTask, args: list, line: int, col: int):
        decl = task.decl
        # v0.6.2 (I5): límite de profundidad de llamadas — un bucle recursivo
        # infinito produce OverErr/RecursionErr capturable, no un traceback crudo.
        self._ayce_depth += 1
        try:
            if self._ayce_depth > self.MAX_CALL_DEPTH:
                raise AyceRuntimeError(self.filename, line, col,
                    "Recursión demasiado profunda: se superó el límite de llamadas anidadas")
            # Seleccionar firma por número y tipo de argumentos
            for sig_idx, sig in enumerate(decl.signatures):
                filled = self._signature_matches(sig, args)
                if filled is not None:
                    return self._run_task_body(task, sig, decl.bodies[sig_idx], filled, line, col)
            raise AyceRuntimeError(self.filename, line, col,
                f"La tarea '{decl.name}' no tiene una firma que coincida con los argumentos recibidos")
        finally:
            self._ayce_depth -= 1

    def _signature_matches(self, sig: TaskSignature, args: list):
        """Devuelve la lista de argumentos finales (con defaults aplicados) si la firma
        coincide, o None si no coincide."""
        params = sig.params
        # Caso varargs (v0.6.3 coherente): los parámetros fijos aceptan
        # defaults y CADA argumento extra debe cumplir el tipo del '...'.
        # Un extra que no cumple hace que la firma no coincida (misma regla
        # silenciosa que los parámetros fijos), así que las sobrecargas
        # siguen decidiendo bien.
        if params and params[-1].varargs:
            fixed = len(params) - 1
            obligatorios = sum(1 for p in params[:fixed] if p.default is None)
            if len(args) < obligatorios:
                return None
            filled = []
            for i in range(fixed):
                if i < len(args):
                    if not self._value_matches_type(args[i], params[i].type_node):
                        return None
                    filled.append(args[i])
                else:
                    filled.append(self.eval(params[i].default, self.global_env))
            # Verificar y empaquetar el resto como varargs
            for extra in args[fixed:]:
                if not self._value_matches_type(extra, params[-1].type_node):
                    return None
            varargs_list = AyceList(args[fixed:],
                                    ListType(elem=params[-1].type_node, line=0, col=0))
            filled.append(varargs_list)
            return filled

        # Sin varargs: número exacto, con defaults para los que falten
        if len(args) > len(params):
            return None
        # Llenar con defaults
        filled = list(args)
        for i in range(len(args), len(params)):
            p = params[i]
            if p.default is not None:
                filled.append(self.eval(p.default, self.global_env))
            else:
                return None  # Falta un argumento obligatorio
        # Verificar tipos
        for i, p in enumerate(params):
            if not self._value_matches_type(filled[i], p.type_node):
                return None
        return filled

    def _run_task_body(self, task: AyceTask, sig: TaskSignature, body: list, args: list, line, col):
        # Crear nuevo entorno con el closure de la tarea
        call_env = Env(parent=task.closure_env)
        # Bind de parámetros (args ya viene con defaults aplicados y varargs empaquetado)
        for i, p in enumerate(sig.params):
            call_env.declare(p.name, args[i], p.type_node,
                            is_const=(p.modifier == "const"))
        try:
            for s in body:
                self.exec_stmt(s, call_env)
        except ReturnSignal as r:
            return r.value
        # Si no hay return explícito:
        if task.decl.return_type is not None:
            raise AyceRuntimeError(self.filename, line, col,
                f"La tarea '{task.decl.name}' declara retorno pero no ejecutó return en este camino")
        return None

    # ──────────────────────────────────────────────────────────────────
    #  Verificación de tipos
    # ──────────────────────────────────────────────────────────────────
    def _type_signature(self, type_node) -> str:
        """Devuelve un string canónico para un TypeNode, ignorando line/col.
        Útil para comparar si dos tipos son estructuralmente iguales."""
        if type_node is None:
            return "?"
        if isinstance(type_node, PrimitiveType):
            return type_node.name
        if isinstance(type_node, UserTypeName):
            return type_node.name
        if isinstance(type_node, ListType):
            if type_node.flexible or type_node.elem is None:
                return "list"
            return f"list[{self._type_signature(type_node.elem)}]"
        if isinstance(type_node, DictType):
            if type_node.flexible:
                return "dict"
            k = self._type_signature(type_node.key_type) if type_node.key_type else "?"
            vs = ",".join(self._type_signature(v) for v in type_node.value_types)
            return f"dict<{k}:{vs}>"
        if isinstance(type_node, TupleType):
            if type_node.flexible:
                return "tuple"
            es = ",".join(self._type_signature(e) for e in type_node.elem_types)
            return f"tuple({es})"
        if isinstance(type_node, SetType):
            if type_node.flexible:
                return "set"
            return f"set[{self._type_signature(type_node.elem)}]"
        return "?"

    def _check_value_matches_type(self, value, type_node, line, col, env):
        """Verifica que el valor sea compatible con el tipo declarado.
        v0.6.2: devuelve el valor (con la promoción int→float ya aplicada)."""
        if type_node is None:
            return value
        if isinstance(type_node, PrimitiveType):
            expected = type_node.name
            actual = self._type_name(value)
            if expected == "int":
                # v0.6.2 (spec 4.4): bool no es int
                if isinstance(value, bool):
                    raise AyceTypeError(self.filename, line, col,
                        f"Se esperaba int, se recibió bool (usá int(value) para convertir)")
                if not isinstance(value, int):
                    raise AyceTypeError(self.filename, line, col,
                        f"Se esperaba int, se recibió {actual}")
            if expected == "float":
                # Promoción int → float automática al asignar
                if isinstance(value, int) and not isinstance(value, bool):
                    value = float(value)
                elif not isinstance(value, float):
                    raise AyceTypeError(self.filename, line, col,
                        f"Se esperaba float, se recibió {actual}")
            if expected == "string" and not isinstance(value, str):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba string, se recibió {actual}")
            if expected == "bool" and not isinstance(value, bool):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba bool, se recibió {actual}")
            if expected == "bytes" and not isinstance(value, bytes):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba bytes, se recibió {actual}")
            if expected == "none" and value is not None:
                # 'none' como tipo admite None
                pass
            return value
        if isinstance(type_node, ListType):
            if not isinstance(value, AyceList):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba lista, se recibió {self._type_name(value)}")
            if not type_node.flexible and type_node.elem is not None:
                for elem in value.elements:
                    if not self._value_matches_type(elem, type_node.elem):
                        raise AyceTypeError(self.filename, line, col,
                            f"Elemento de lista no coincide con tipo declarado")
            return value
        if isinstance(type_node, DictType):
            if not isinstance(value, AyceDict):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba diccionario, se recibió {self._type_name(value)}")
            return value
        if isinstance(type_node, TupleType):
            if not isinstance(value, AyceTuple):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba tupla, se recibió {self._type_name(value)}")
            return value
        if isinstance(type_node, SetType):
            if not isinstance(value, AyceSet):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba set, se recibió {self._type_name(value)}")
            return value
        if isinstance(type_node, TaskType):
            # v0.6.2: también acepta tareas nativas (AyceNativeTask de los
            # batches built-in), necesarias para las librerías stdlib en ayce.
            from .batches import AyceNativeTask
            if not isinstance(value, (AyceTask, AyceNativeTask)):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba task, se recibió {self._type_name(value)}")
            return value
        if isinstance(type_node, UserTypeName):
            # Tipo definido por el usuario
            type_name = type_node.name
            if isinstance(value, AyceInstance) and value.template.is_subclass_of(type_name):
                return value
            if isinstance(value, AyceShapeValue) and value.shape.name == type_name:
                return value
            if isinstance(value, AyceVariantValue) and value.variant.name == type_name:
                return value
            # Si el valor es el tipo mismo (Template/Shape/Variant como valor)
            if isinstance(value, (AyceTemplate, AyceShape, AyceVariant)) and value.name == type_name:
                return value
            # v0.5: alias de tipo importado (require X as Y from M)
            # Si `type_name` es un alias (apunta a un AyceTemplate/AyceShape/AyceVariant en el env),
            # comparamos por referencia del tipo subyacente.
            if env is not None:
                existing = env.lookup(type_name)
                if existing is not None:
                    alias_target = existing[0]
                    if isinstance(value, AyceInstance) and isinstance(alias_target, AyceTemplate) \
                            and value.template is alias_target:
                        return value
                    if isinstance(value, AyceShapeValue) and isinstance(alias_target, AyceShape) \
                            and value.shape is alias_target:
                        return value
                    if isinstance(value, AyceVariantValue) and isinstance(alias_target, AyceVariant) \
                            and value.variant is alias_target:
                        return value
            raise AyceTypeError(self.filename, line, col,
                f"Se esperaba {type_name}, se recibió {self._type_name(value)}")
        if isinstance(type_node, QualifiedTypeName):
            # v0.5: tipo cualificado de batch (Module::Type)
            # Buscamos el batch en el env y comprobamos que el valor coincida
            existing = env.lookup(type_node.module_name) if env is not None else None
            if existing is None:
                raise AyceTypeError(self.filename, line, col,
                    f"Batch '{type_node.module_name}' no declarado")
            batch = existing[0]
            if not isinstance(batch, AyceBatch):
                raise AyceTypeError(self.filename, line, col,
                    f"'{type_node.module_name}' no es un batch")
            export = batch.find_export(type_node.type_name)
            if export is None:
                raise AyceTypeError(self.filename, line, col,
                    f"El batch '{type_node.module_name}' no exporta '{type_node.type_name}'")
            # Verificar que el valor coincida con el tipo exportado
            if isinstance(value, AyceInstance) and isinstance(export, AyceTemplate) \
                    and value.template.is_subclass_of(type_node.type_name):
                return value
            if isinstance(value, AyceShapeValue) and isinstance(export, AyceShape) \
                    and value.shape.name == type_node.type_name:
                return value
            if isinstance(value, AyceVariantValue) and isinstance(export, AyceVariant) \
                    and value.variant.name == type_node.type_name:
                return value
            raise AyceTypeError(self.filename, line, col,
                f"Se esperaba {type_node.module_name}::{type_node.type_name}, "
                f"se recibió {self._type_name(value)}")

    def _value_matches_type(self, value, type_node) -> bool:
        """Versión silenciosa de _check_value_matches_type para resolución de sobrecarga."""
        if type_node is None:
            return True
        if isinstance(type_node, PrimitiveType):
            t = type_node.name
            if t == "int":   return isinstance(value, int) and not isinstance(value, bool)
            if t == "float": return isinstance(value, float)
            if t == "string": return isinstance(value, str)
            if t == "bool":  return isinstance(value, bool)
            if t == "bytes": return isinstance(value, bytes)
            if t == "none":
                # v0.6.3: 'none' como tipo de parámetro coincide con CUALQUIER
                # valor, igual que en las declaraciones (_check_value_matches_type
                # ya lo trataba como flexible). Así funcionan tasks que reciben
                # datos de inlet sin tipo y los filtran con guard/match.
                return True
            return False
        if isinstance(type_node, ListType):
            return isinstance(value, AyceList)
        if isinstance(type_node, DictType):
            return isinstance(value, AyceDict)
        if isinstance(type_node, TupleType):
            return isinstance(value, AyceTuple)
        if isinstance(type_node, SetType):
            return isinstance(value, AyceSet)
        if isinstance(type_node, TaskType):
            from .batches import AyceNativeTask
            return isinstance(value, (AyceTask, AyceNativeTask))
        if isinstance(type_node, UserTypeName):
            type_name = type_node.name
            if isinstance(value, AyceInstance) and value.template.is_subclass_of(type_name):
                return True
            if isinstance(value, AyceShapeValue) and value.shape.name == type_name:
                return True
            if isinstance(value, AyceVariantValue) and value.variant.name == type_name:
                return True
            return False
        return True  # Conservador: si no reconocemos el tipo, lo permitimos

    # ──────────────────────────────────────────────────────────────────
    #  Utilidades
    # ──────────────────────────────────────────────────────────────────
    def _type_name(self, value) -> str:
        if isinstance(value, bool): return "bool"
        if isinstance(value, int):  return "int"
        if isinstance(value, float): return "float"
        if isinstance(value, str):  return "string"
        if isinstance(value, bytes): return "bytes"
        if value is None: return "none"
        if isinstance(value, AyceList): return "list"
        if isinstance(value, AyceDict): return "dict"
        if isinstance(value, AyceTuple): return "tuple"
        if isinstance(value, AyceSet):  return "set"
        if isinstance(value, AyceTask): return "task"
        if isinstance(value, AyceInstance): return "instance"
        if isinstance(value, AyceTemplate): return "template"
        return type(value).__name__

    def _to_string_concat(self, value) -> str:
        """Convierte un valor a string para concatenación con +.
        Es lo que usa el operador + cuando uno de los operandos es string."""
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            if value == int(value) and abs(value) < 1e16:
                return f"{value:.1f}"
            return str(value)
        if value is None:
            return "none"
        return self._format_value(value)

    def _raise_native_error(self, name: str, msg: str, line: int, col: int):
        """v0.6.2 (spec 4.5/tabla 19): lanza un error nativo concreto como
        RaiseSignal — capturable con rescue ValErr / CastErr / etc."""
        from .errors import NATIVE_ERRORS
        existing = self.global_env.lookup(name)
        if existing is not None and isinstance(existing[0], AyceTemplate):
            tpl_val = existing[0]
            inst = AyceInstance(tpl_val)
            for f in tpl_val.all_fields():
                inst.fields[f.name] = None
            inst.fields["mensaje"] = msg
            inst.fields["codigo"] = NATIVE_ERRORS.get(name, {}).get("code", 1)
            raise RaiseSignal(inst)
        # Fallback: error de ejecución normal
        raise AyceRuntimeError(self.filename, line, col, msg)

    def _convert_type(self, expr, env=None):
        """Implementa int(x), float(x), string(x), bool(x), bytes(x)."""
        # env puede venir de eval() o ser None; si es None usamos global_env
        actual_env = env if env is not None else self.global_env
        val = self.eval(expr.arg, actual_env)
        target = expr.target_type

        if target == "int":
            if isinstance(val, bool):
                return 1 if val else 0
            if isinstance(val, int):
                return val
            if isinstance(val, float):
                return int(val)  # trunca
            if isinstance(val, str):
                try:
                    return int(val)
                except ValueError:
                    # v0.6.2 (I7): string no numérica → ValErr (no TypeErr)
                    self._raise_native_error("ValErr",
                        f'int(): no se puede convertir "{val}" a int',
                        expr.line, expr.col)
            raise AyceTypeError(self.filename, expr.line, expr.col,
                f"No se puede convertir {self._type_name(val)} a int")

        if target == "float":
            if isinstance(val, bool):
                return 1.0 if val else 0.0
            if isinstance(val, int):
                return float(val)
            if isinstance(val, float):
                return val
            if isinstance(val, str):
                try:
                    return float(val)
                except ValueError:
                    # v0.6.2 (I7): string no numérica → CastErr (no TypeErr)
                    self._raise_native_error("CastErr",
                        f'float(): no se puede convertir "{val}" a float',
                        expr.line, expr.col)
            raise AyceTypeError(self.filename, expr.line, expr.col,
                f"No se puede convertir {self._type_name(val)} a float")

        if target == "string":
            return self._to_string_concat(val)

        if target == "bool":
            if isinstance(val, bool):
                return val
            if isinstance(val, int):
                return val != 0
            if isinstance(val, float):
                return val != 0.0
            if isinstance(val, str):
                return val != ""
            if val is None:
                return False
            # Colecciones y otros: True si no están vacíos
            if isinstance(val, AyceList):
                return len(val.elements) > 0
            if isinstance(val, AyceDict):
                return len(val.pairs) > 0
            if isinstance(val, AyceSet):
                return len(val.elements) > 0
            if isinstance(val, AyceTuple):
                return len(val.elements) > 0
            return True

        if target == "bytes":
            if isinstance(val, bytes):
                return val
            if isinstance(val, str):
                return val.encode("utf-8")
            raise AyceTypeError(self.filename, expr.line, expr.col,
                f"No se puede convertir {self._type_name(val)} a bytes")

        raise AyceTypeError(self.filename, expr.line, expr.col,
            f"Tipo de conversión desconocido: {target}")



    def _format_value(self, value) -> str:
        if value is None: return "none"
        if isinstance(value, bool): return "True" if value else "False"
        if isinstance(value, int):  return str(value)
        if isinstance(value, float):
            # Formatear float: si es entero, añadir .0
            # (v0.6.2: inf/nan no admiten comparación con int() — proteger)
            if value != value:
                return "nan"
            if value == float("inf"):
                return "inf"
            if value == float("-inf"):
                return "-inf"
            if value == int(value) and abs(value) < 1e16:
                return f"{value:.1f}"
            return str(value)
        if isinstance(value, str):  return value
        if isinstance(value, bytes): return f'b"{value.decode("utf-8", errors="replace")}"'
        if isinstance(value, AyceList):
            return "[" + ", ".join(self._repr_value(e) for e in value.elements) + "]"
        if isinstance(value, AyceDict):
            return "<" + ", ".join(f"{self._repr_value(k)}: {self._repr_value(v)}"
                                    for k, v in value.pairs.items()) + ">"
        if isinstance(value, AyceTuple):
            return "(" + ", ".join(self._repr_value(e) for e in value.elements) + ")"
        if isinstance(value, AyceSet):
            return "{" + ", ".join(self._repr_value(e) for e in value.elements) + "}"
        if isinstance(value, AyceTask):
            return f"<task {value.decl.name}>"
        if isinstance(value, AyceInstance):
            items = ", ".join(f"{k}: {self._repr_value(v)}" for k, v in value.fields.items())
            return f"{value.template.name} {{ {items} }}"
        if isinstance(value, AyceShapeValue):
            items = ", ".join(f"{k}: {self._repr_value(v)}" for k, v in value.fields.items())
            return f"{value.shape.name} {{ {items} }}"
        if isinstance(value, AyceVariantValue):
            if value.payload is not None:
                return f"{value.variant.name}::{value.case_name}({self._repr_value(value.payload)})"
            return f"{value.variant.name}::{value.case_name}"
        if isinstance(value, (AyceTemplate, AyceShape, AyceVariant)):
            return repr(value)
        return str(value)

    def _repr_value(self, value) -> str:
        """Representación interna (con comillas para strings, para distinguirlos de identificadores)."""
        if isinstance(value, str):
            return f'"{value}"'
        return self._format_value(value)
