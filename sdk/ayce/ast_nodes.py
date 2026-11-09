"""
ayce — Nodos del Árbol Sintáctico Abstracto (AST).
Cada nodo lleva línea y columna para mensajes de error.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


# ──────────────────────────────────────────────────────────────────────
#  Tipos
# ──────────────────────────────────────────────────────────────────────
@dataclass
class TypeNode:
    """Nodo base para tipos."""
    line: int = 0
    col: int = 0

@dataclass
class PrimitiveType(TypeNode):
    name: str = ""           # int, float, string, bool, none, bytes

@dataclass
class ListType(TypeNode):
    elem: Optional[TypeNode] = None
    flexible: bool = False   # none[] → True

@dataclass
class DictType(TypeNode):
    key_type: Optional[TypeNode] = None
    value_types: list = field(default_factory=list)  # lista de TypeNode
    flexible: bool = False

@dataclass
class TupleType(TypeNode):
    elem_types: list = field(default_factory=list)
    flexible: bool = False

@dataclass
class SetType(TypeNode):
    elem: Optional[TypeNode] = None
    flexible: bool = False

@dataclass
class TaskType(TypeNode):
    """Tipo 'task' para parámetros callback."""
    pass


# ──────────────────────────────────────────────────────────────────────
#  Expresiones
# ──────────────────────────────────────────────────────────────────────
@dataclass
class Expr:
    line: int = 0
    col: int = 0

@dataclass
class IntLit(Expr):
    value: int = 0

@dataclass
class FloatLit(Expr):
    value: float = 0.0

@dataclass
class StringLit(Expr):
    value: str = ""

@dataclass
class BytesLit(Expr):
    value: bytes = b""

@dataclass
class BoolLit(Expr):
    value: bool = False

@dataclass
class NoneLit(Expr):
    pass

@dataclass
class FStringLit(Expr):
    parts: list = field(default_factory=list)
    # cada parte es ("text", str) o ("expr", Expr)

@dataclass
class IdentExpr(Expr):
    name: str = ""

@dataclass
class ListLit(Expr):
    elements: list = field(default_factory=list)

@dataclass
class DictLit(Expr):
    pairs: list = field(default_factory=list)  # [(key_expr, value_expr), ...]

@dataclass
class TupleLit(Expr):
    elements: list = field(default_factory=list)

@dataclass
class SetLit(Expr):
    elements: list = field(default_factory=list)

@dataclass
class IndexExpr(Expr):
    target: Optional[Expr] = None
    index: Optional[Expr] = None      # para listas/tuplas

@dataclass
class DictAccessExpr(Expr):
    target: Optional[Expr] = None
    key: Optional[Expr] = None        # para diccionarios, x<clave>

@dataclass
class MethodCallExpr(Expr):
    target: Optional[Expr] = None
    method: str = ""
    args: list = field(default_factory=list)

@dataclass
class CallExpr(Expr):
    target: Optional[Expr] = None     # normalmente IdentExpr
    args: list = field(default_factory=list)

@dataclass
class UnaryExpr(Expr):
    op: str = ""             # "!" o "-"
    operand: Optional[Expr] = None

@dataclass
class BinaryExpr(Expr):
    op: str = ""
    left: Optional[Expr] = None
    right: Optional[Expr] = None

@dataclass
class RangeExpr(Expr):
    start: Optional[Expr] = None
    end: Optional[Expr] = None

@dataclass
class InletExpr(Expr):
    """inlet(prompt, tipo) — lee entrada del teclado.
    tipo puede ser None (string), 'int', 'float', 'bool'."""
    prompt: Optional[Expr] = None
    target_type: str = ""   # "", "int", "float", "bool"


# ──────────────────────────────────────────────────────────────────────
#  Sentencias
# ──────────────────────────────────────────────────────────────────────
@dataclass
class Stmt:
    line: int = 0
    col: int = 0

@dataclass
class VarDecl(Stmt):
    name: str = ""
    type_node: Optional[TypeNode] = None
    init: Optional[Expr] = None

@dataclass
class ConstDecl(Stmt):
    name: str = ""
    type_node: Optional[TypeNode] = None
    init: Optional[Expr] = None

@dataclass
class AssignStmt(Stmt):
    target: Optional[Expr] = None   # IdentExpr, IndexExpr o DictAccessExpr
    value: Optional[Expr] = None

@dataclass
class SayStmt(Stmt):
    args: list = field(default_factory=list)

@dataclass
class IfStmt(Stmt):
    branches: list = field(default_factory=list)
    # [(cond_expr, [stmts]), ...]  + rama else opcional como (None, [stmts])

@dataclass
class WhileStmt(Stmt):
    cond: Optional[Expr] = None
    body: list = field(default_factory=list)

@dataclass
class ForStmt(Stmt):
    var_name: str = ""
    iterable: Optional[Expr] = None
    body: list = field(default_factory=list)

@dataclass
class BreakStmt(Stmt):
    pass

@dataclass
class ContinueStmt(Stmt):
    pass

@dataclass
class ReturnStmt(Stmt):
    value: Optional[Expr] = None

@dataclass
class GlobalStmt(Stmt):
    names: list = field(default_factory=list)

@dataclass
class ExprStmt(Stmt):
    expr: Optional[Expr] = None


# ──────────────────────────────────────────────────────────────────────
#  Tareas (task)
# ──────────────────────────────────────────────────────────────────────
@dataclass
class Param:
    modifier: str = ""        # "", "&in", "&out", "&inout", "const"
    type_node: Optional[TypeNode] = None
    varargs: bool = False
    name: str = ""
    default: Optional[Expr] = None
    line: int = 0
    col: int = 0

@dataclass
class TaskSignature:
    params: list = field(default_factory=list)  # lista de Param
    line: int = 0
    col: int = 0

@dataclass
class TaskDecl(Stmt):
    name: str = ""
    signatures: list = field(default_factory=list)   # lista de TaskSignature (sobrecarga)
    return_type: Optional[TypeNode] = None           # None = sin retorno
    bodies: list = field(default_factory=list)       # lista de [Stmt] (una por firma)
    is_lambda: bool = False
    line: int = 0
    col: int = 0


# ──────────────────────────────────────────────────────────────────────
#  Tipos compuestos de usuario (v0.3)
# ──────────────────────────────────────────────────────────────────────
@dataclass
class FieldDecl:
    """Declaración de un campo de Template/Shape: nombre: tipo [= default]"""
    name: str = ""
    type_node: Optional[TypeNode] = None
    default: Optional[Expr] = None
    line: int = 0
    col: int = 0

@dataclass
class VariantCase:
    """Un caso de Variant. Puede ser sin payload (Color.Rojo) o con payload (Ok(int))."""
    name: str = ""
    payload_type: Optional[TypeNode] = None   # None = sin payload
    line: int = 0
    col: int = 0

@dataclass
class TemplateDecl(Stmt):
    """Template: clase con campos y métodos (tasks). Puede heredar de otro Template."""
    name: str = ""
    fields: list = field(default_factory=list)        # lista de FieldDecl
    methods: list = field(default_factory=list)        # lista de TaskDecl
    parent_name: str = ""    # nombre del Template padre (v0.4.1) — "" si no hay herencia
    line: int = 0
    col: int = 0

@dataclass
class ShapeDecl(Stmt):
    """Shape: registro de datos inmutable, sin métodos."""
    name: str = ""
    fields: list = field(default_factory=list)        # lista de FieldDecl
    line: int = 0
    col: int = 0

@dataclass
class VariantDecl(Stmt):
    """Variant: tipo unión con casos nombrados, opcionalmente con payload."""
    name: str = ""
    cases: list = field(default_factory=list)         # lista de VariantCase
    line: int = 0
    col: int = 0

# ──────────────────────────────────────────────────────────────────────
#  Expresiones nuevas (v0.3)
# ──────────────────────────────────────────────────────────────────────
@dataclass
class SelfExpr(Expr):
    """Referencia a `self` dentro de un método de Template."""
    pass

@dataclass
class FieldAccessExpr(Expr):
    """Acceso a campo o caso: expr.nombre (ej: p.x, Color.Rojo)"""
    target: Optional[Expr] = None
    field: str = ""
    line: int = 0
    col: int = 0

@dataclass
class NewExpr(Expr):
    """Construcción de Shape: new Punto { x: 1, y: 2 }"""
    type_name: str = ""
    fields: list = field(default_factory=list)   # [(nombre, expr), ...]
    line: int = 0
    col: int = 0

@dataclass
class TemplateCallExpr(Expr):
    """Construcción de Template: Persona("Carlos", 25)"""
    type_name: str = ""
    args: list = field(default_factory=list)
    line: int = 0
    col: int = 0

@dataclass
class IsExpr(Expr):
    """Comparación de variant: expr is Tipo.Caso"""
    left: Optional[Expr] = None
    type_name: str = ""
    case_name: str = ""
    line: int = 0
    col: int = 0

@dataclass
class UserTypeName(TypeNode):
    """Referencia a un tipo definido por el usuario (Template, Shape, Variant)."""
    name: str = ""
    line: int = 0
    col: int = 0

# ──────────────────────────────────────────────────────────────────────
#  v0.4 — Manejo de errores, conversión, ternario, asignación compuesta
# ──────────────────────────────────────────────────────────────────────
@dataclass
class TryStmt(Stmt):
    """try ... rescue(nombre: Tipo) ... end"""
    body: list = field(default_factory=list)
    rescue_name: str = ""
    rescue_type: str = ""    # nombre del tipo de error (ej: "Div0", "Error", "")
    rescue_body: list = field(default_factory=list)
    line: int = 0
    col: int = 0

@dataclass
class RaiseStmt(Stmt):
    """raise Error("mensaje", codigo)"""
    error_expr: Optional[Expr] = None
    line: int = 0
    col: int = 0

@dataclass
class TernaryExpr(Expr):
    """(cond) ? a : b"""
    cond: Optional[Expr] = None
    if_true: Optional[Expr] = None
    if_false: Optional[Expr] = None

@dataclass
class CompoundAssignStmt(Stmt):
    """x += 5, x -= 2, etc."""
    target: Optional[Expr] = None
    op: str = ""    # "+=", "-=", etc.
    value: Optional[Expr] = None
    line: int = 0
    col: int = 0

@dataclass
class TypeConvertExpr(Expr):
    """int("42"), float("1.5"), string(42), bool(0), bytes("hola")"""
    target_type: str = ""  # "int", "float", "string", "bool", "bytes"
    arg: Optional[Expr] = None

# ──────────────────────────────────────────────────────────────────────
#  Programa
# ──────────────────────────────────────────────────────────────────────
@dataclass
class Program:
    stmts: list = field(default_factory=list)
