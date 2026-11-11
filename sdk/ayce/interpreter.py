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

class AyceDict:
    def __init__(self, pairs, type_node):
        self.pairs = dict(pairs)
        self.type_node = type_node

    def __repr__(self):
        return "<" + ", ".join(f"{k!r}: {v!r}" for k, v in self.pairs.items()) + ">"

class AyceTuple:
    def __init__(self, elements, type_node):
        self.elements = tuple(elements)
        self.type_node = type_node

    def __repr__(self):
        return "(" + ", ".join(repr(e) for e in self.elements) + ")"

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
    def __init__(self, filename: str = "<stdin>", import_paths: list = None):
        self.filename = filename
        self.global_env = Env()
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

        # Segunda pasada: ejecutar sentencias sueltas (no declaraciones de tipos ni tasks)
        for stmt in program.stmts:
            if isinstance(stmt, (TaskDecl, TemplateDecl, ShapeDecl, VariantDecl, RequireStmt)):
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
            self._check_value_matches_type(value, stmt.type_node, stmt.line, stmt.col, env)
            initialized = True
        else:
            # Variable sin inicializar: se registra como no inicializada.
            # No se puede leer hasta que reciba un valor.
            value = None
            initialized = False
        env.declare(stmt.name, value, stmt.type_node, is_const=False, initialized=initialized)

    def _exec_const_decl(self, stmt: ConstDecl, env: Env):
        value = self.eval(stmt.init, env)
        self._check_value_matches_type(value, stmt.type_node, stmt.line, stmt.col, env)
        env.declare(stmt.name, value, stmt.type_node, is_const=True)

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
            self._check_value_matches_type(value, type_node, target.line, target.col, env)
            env.assign(target.name, value, self.filename, target.line, target.col)

        elif isinstance(target, IndexExpr):
            # Asignación a lista: lista[i] = valor
            container = self.eval(target.target, env)
            idx = self.eval(target.index, env)
            if isinstance(container, AyceTuple):
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    "Las tuplas son inmutables: no se puede asignar a una posición")
            if not isinstance(container, AyceList):
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    "La indexación con [] sólo aplica a listas")
            if not isinstance(idx, int):
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    "El índice debe ser int")
            if idx < 0 or idx >= len(container.elements):
                raise AyceRuntimeError(self.filename, target.line, target.col,
                    f"Índice {idx} fuera de rango (longitud {len(container.elements)})")
            # Verificar tipo del elemento
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
        """try ... rescue(nombre: Tipo) ... end — filtra por tipo (v0.4.1)"""
        try:
            block_env = Env(parent=env)
            for s in stmt.body:
                self.exec_stmt(s, block_env)
        except RaiseSignal as r:
            error_val = r.error_value
            # Si rescue tiene tipo, filtrar
            if stmt.rescue_type:
                if not self._error_matches_type(error_val, stmt.rescue_type):
                    raise  # no coincide — relanzar
            if not stmt.rescue_name:
                return
            rescue_env = Env(parent=env)
            rescue_env.declare(stmt.rescue_name, error_val,
                              UserTypeName(name="Error"), is_const=False)
            for s in stmt.rescue_body:
                self.exec_stmt(s, rescue_env)
        except (AyceRuntimeError, AyceTypeError) as e:
            # Errores nativos de ayce se convierten en el error específico
            error_inst = self._make_native_error(e)
            # Si rescue tiene tipo, filtrar
            if stmt.rescue_type:
                if not self._error_matches_type(error_inst, stmt.rescue_type):
                    raise  # no coincide — relanzar
            if not stmt.rescue_name:
                return
            rescue_env = Env(parent=env)
            rescue_env.declare(stmt.rescue_name, error_inst,
                              UserTypeName(name="Error"), is_const=False)
            for s in stmt.rescue_body:
                self.exec_stmt(s, rescue_env)

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
            if "División por cero" in msg or "división por cero" in msg:
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
        #    Primero mirar si M es un batch built-in (math, random, string, etc.)
        if stmt.mode == "batch":
            batch_name = stmt.batch_spec
            builtin = self._get_builtin_batch(batch_name)
            if builtin is not None:
                # Es built-in — bind directo, sin cargar archivo
                bind_name = stmt.alias if stmt.alias else batch_name
                env.declare(bind_name, builtin, UserTypeName(name=batch_name), is_const=True)
                return
            # No es built-in — cargar desde archivo
            batch_path = self._resolve_batch_path(batch_name)
            batch = self._load_batch(batch_path, stmt.line, stmt.col)
            bind_name = stmt.alias if stmt.alias else stmt.batch_spec
            env.declare(bind_name, batch, UserTypeName(name=batch.name), is_const=True)
            return

        # 3. Modo selectivo: require X[, Y as Z] from M
        if stmt.mode == "selective":
            batch_name = stmt.batch_spec
            # Mirar si es built-in
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
            # No es built-in — cargar desde archivo
            batch_path = self._resolve_batch_path(batch_name)
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

    def _resolve_batch_path(self, batch_name: str) -> str:
        """Resuelve un identificador de batch a una ruta absoluta.

        Orden de búsqueda (estilo Python):
          1. Directorio del archivo actual
          2. Directorio de trabajo actual (cwd)
          3. import_paths explícitos
          4. Búsqueda recursiva hacia ABAJO desde:
             - El dir del archivo actual
             - El cwd
             - CADA directorio padre hasta la raíz del proyecto
             (profundidad limitada a 4 para no recorrer todo el disco)
        """
        import os
        target = batch_name + ".ayce"
        candidates = []
        searched_dirs = set()

        current_dir = os.path.dirname(os.path.abspath(self.filename))
        cwd = os.getcwd()

        # Helper para chequear si un archivo existe en un dir
        def check_dir(d):
            if d in searched_dirs:
                return None
            searched_dirs.add(d)
            c = os.path.join(d, target)
            candidates.append(c)
            if os.path.exists(c):
                return os.path.abspath(c)
            return None

        # Helper para walk down desde un dir, hasta profundidad max_depth
        def walk_down(root_dir, max_depth=4):
            if not os.path.isdir(root_dir):
                return None
            for dirpath, dirnames, filenames in os.walk(root_dir):
                rel = os.path.relpath(dirpath, root_dir)
                depth = 0 if rel == "." else rel.count(os.sep) + 1
                if depth > max_depth:
                    dirnames[:] = []
                    continue
                # Filtrar carpetas que no deberían contener batchs
                dirnames[:] = [d for d in dirnames
                               if not d.startswith(".")
                               and d not in ("__pycache__", "node_modules", ".git",
                                             ".venv", "venv", "env", "build", "dist",
                                             ".idea", ".vscode", "site-packages")]
                result = check_dir(dirpath)
                if result is not None:
                    return result
            return None

        # 1. Directorio del archivo actual
        result = check_dir(current_dir)
        if result is not None:
            return result

        # 2. Directorio de trabajo actual (cwd)
        result = check_dir(cwd)
        if result is not None:
            return result

        # 3. import_paths explícitos
        for p in self.import_paths:
            p_abs = os.path.abspath(p)
            result = check_dir(p_abs)
            if result is not None:
                return result

        # 4. Walk down desde current_dir, cwd y CADA padre
        #    Primero recolectamos todos los padres del dir del archivo
        roots_to_walk = [current_dir, cwd]
        parent = current_dir
        while True:
            parent = os.path.dirname(parent)
            if parent == os.path.dirname(parent):  # raíz
                break
            roots_to_walk.append(parent)

        for root_dir in roots_to_walk:
            result = walk_down(root_dir, max_depth=4)
            if result is not None:
                return result

        raise AyceRuntimeError(self.filename, 0, 0,
            f"No se encontró el batch '{batch.name}'. Buscado en:\n  " +
            "\n  ".join(candidates))

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
        if op == "+":
            # Concatenación de strings con autoconversión
            if isinstance(current, str) or isinstance(value, str):
                if isinstance(current, bytes) and isinstance(value, bytes):
                    new_val = current + value
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
                raise AyceRuntimeError(self.filename, stmt.line, stmt.col, "Batch por cero")
            new_val = current % value
        else:
            raise AyceRuntimeError(self.filename, stmt.line, stmt.col,
                f"Operador compuesto no soportado: {stmt.op}")

        # Asignar el nuevo valor al target
        if isinstance(target, IdentExpr):
            env.assign(target.name, new_val, self.filename, target.line, target.col)
        elif isinstance(target, IndexExpr):
            container = self.eval(target.target, env)
            idx = self.eval(target.index, env)
            if isinstance(container, AyceList):
                container.elements[idx] = new_val
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
            raise AyceTypeError(self.filename, expr.line, expr.col,
                f"No se puede indexar {self._type_name(target)}")
        if isinstance(expr, DictAccessExpr):
            target = self.eval(expr.target, env)
            key = self.eval(expr.key, env)
            if not isinstance(target, AyceDict):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"No se puede acceder con <> a {self._type_name(target)}")
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
                if isinstance(operand, int) or isinstance(operand, float):
                    return -operand
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"El operador - unario requiere número, se recibió {self._type_name(operand)}")
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
            # Si no hay tipo, devolver string
            if not expr.target_type or expr.target_type == "string":
                return input(prompt)
            # Si hay tipo, repetir hasta que sea válido
            while True:
                raw = input(prompt)
                if expr.target_type == "int":
                    try:
                        return int(raw)
                    except ValueError:
                        say(f"'{raw}' no es un int válido. Intentá de nuevo.")
                elif expr.target_type == "float":
                    try:
                        return float(raw)
                    except ValueError:
                        say(f"'{raw}' no es un float válido. Intentá de nuevo.")
                elif expr.target_type == "bool":
                    if raw.lower() in ("true", "t", "1"):
                        return True
                    if raw.lower() in ("false", "f", "0"):
                        return False
                    say(f"'{raw}' no es un bool válido. Usá True o False.")
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
                return self._to_string_concat(left) + self._to_string_concat(right)
            # Suma de bytes
            if expr.op == "+" and isinstance(left, bytes) and isinstance(right, bytes):
                return left + right
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
            if not (isinstance(left, (int, float)) and isinstance(right, (int, float))):
                raise AyceTypeError(self.filename, expr.line, expr.col,
                    f"El operador {expr.op} requiere números o strings, "
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
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "Batch por cero")
                return left % right
            if expr.op == "**":
                return left ** right

        # Comparaciones
        if expr.op in ("==", "!="):
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
            try:
                for s in body:
                    self.exec_stmt(s, call_env)
            except ReturnSignal as r:
                return r.value
            if method_decl.return_type is not None:
                raise AyceRuntimeError(self.filename, expr.line, expr.col,
                    f"El método '{method}' declara retorno pero no ejecutó return")
            return None

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
                target.elements.append(args[0])
                return None
            if method == "insert":
                if len(args) != 2:
                    raise AyceRuntimeError(self.filename, expr.line, expr.col,
                        "insert requiere 2 argumentos (índice, valor)")
                if not isinstance(args[0], int):
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        "insert: el índice debe ser int")
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
        # Seleccionar firma por número y tipo de argumentos
        for sig_idx, sig in enumerate(decl.signatures):
            filled = self._signature_matches(sig, args)
            if filled is not None:
                return self._run_task_body(task, sig, decl.bodies[sig_idx], filled, line, col)
        raise AyceRuntimeError(self.filename, line, col,
            f"La tarea '{decl.name}' no tiene una firma que coincida con los argumentos recibidos")

    def _signature_matches(self, sig: TaskSignature, args: list):
        """Devuelve la lista de argumentos finales (con defaults aplicados) si la firma
        coincide, o None si no coincide."""
        params = sig.params
        # Caso varargs
        if params and params[-1].varargs:
            fixed = len(params) - 1
            if len(args) < fixed:
                return None
            # Verificar tipos de los parámetros fijos (considerando defaults)
            filled = list(args[:fixed])
            for i in range(fixed):
                if not self._value_matches_type(args[i], params[i].type_node):
                    return None
            # Empaquetar el resto como varargs
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
    def _check_value_matches_type(self, value, type_node, line, col, env):
        """Verifica que el valor sea compatible con el tipo declarado."""
        if type_node is None:
            return
        if isinstance(type_node, PrimitiveType):
            expected = type_node.name
            actual = self._type_name(value)
            if expected == "int" and not isinstance(value, int):
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
            return
        if isinstance(type_node, ListType):
            if not isinstance(value, AyceList):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba lista, se recibió {self._type_name(value)}")
            if not type_node.flexible and type_node.elem is not None:
                for elem in value.elements:
                    if not self._value_matches_type(elem, type_node.elem):
                        raise AyceTypeError(self.filename, line, col,
                            f"Elemento de lista no coincide con tipo declarado")
            return
        if isinstance(type_node, DictType):
            if not isinstance(value, AyceDict):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba diccionario, se recibió {self._type_name(value)}")
            return
        if isinstance(type_node, TupleType):
            if not isinstance(value, AyceTuple):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba tupla, se recibió {self._type_name(value)}")
            return
        if isinstance(type_node, SetType):
            if not isinstance(value, AyceSet):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba set, se recibió {self._type_name(value)}")
            return
        if isinstance(type_node, TaskType):
            if not isinstance(value, AyceTask):
                raise AyceTypeError(self.filename, line, col,
                    f"Se esperaba task, se recibió {self._type_name(value)}")
            return
        if isinstance(type_node, UserTypeName):
            # Tipo definido por el usuario
            type_name = type_node.name
            if isinstance(value, AyceInstance) and value.template.is_subclass_of(type_name):
                return
            if isinstance(value, AyceShapeValue) and value.shape.name == type_name:
                return
            if isinstance(value, AyceVariantValue) and value.variant.name == type_name:
                return
            # Si el valor es el tipo mismo (Template/Shape/Variant como valor)
            if isinstance(value, (AyceTemplate, AyceShape, AyceVariant)) and value.name == type_name:
                return
            # v0.5: alias de tipo importado (require X as Y from M)
            # Si `type_name` es un alias (apunta a un AyceTemplate/AyceShape/AyceVariant en el env),
            # comparamos por referencia del tipo subyacente.
            if env is not None:
                existing = env.lookup(type_name)
                if existing is not None:
                    alias_target = existing[0]
                    if isinstance(value, AyceInstance) and isinstance(alias_target, AyceTemplate) \
                            and value.template is alias_target:
                        return
                    if isinstance(value, AyceShapeValue) and isinstance(alias_target, AyceShape) \
                            and value.shape is alias_target:
                        return
                    if isinstance(value, AyceVariantValue) and isinstance(alias_target, AyceVariant) \
                            and value.variant is alias_target:
                        return
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
                return
            if isinstance(value, AyceShapeValue) and isinstance(export, AyceShape) \
                    and value.shape.name == type_node.type_name:
                return
            if isinstance(value, AyceVariantValue) and isinstance(export, AyceVariant) \
                    and value.variant.name == type_node.type_name:
                return
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
            if t == "none":  return value is None
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
            return isinstance(value, AyceTask)
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
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        f'No se puede convertir "{val}" a int')
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
                    raise AyceTypeError(self.filename, expr.line, expr.col,
                        f'No se puede convertir "{val}" a float')
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
