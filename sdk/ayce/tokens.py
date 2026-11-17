"""
ayce — tokens del léxico.
Define los tipos de token y la tabla de palabras reservadas.
"""

from enum import Enum, auto
from dataclasses import dataclass


class TokenType(Enum):
    # Literales
    INT        = auto()
    FLOAT      = auto()
    STRING     = auto()
    FSTRING    = auto()   # texto + lista de expresiones embebidas (parseadas después)
    BYTES      = auto()
    TRUE       = auto()
    FALSE      = auto()
    NONE       = auto()

    # Identificadores y palabras reservadas
    IDENT      = auto()
    VAR        = auto()
    CONST      = auto()
    IF         = auto()
    THEN       = auto()
    ELSE       = auto()
    END        = auto()
    WHILE      = auto()
    FOR        = auto()
    DO         = auto()
    IN         = auto()
    BREAK      = auto()
    CONTINUE   = auto()
    TASK       = auto()
    RETURN     = auto()
    GLOBAL     = auto()
    SAY        = auto()
    INLET      = auto()
    RANGE      = auto()

    # Tipos compuestos de usuario (v0.3)
    TEMPLATE   = auto()
    SHAPE      = auto()
    VARIANT    = auto()
    SELF       = auto()      # self dentro de métodos de Template
    NEW        = auto()      # para construir Shape: new Punto { x: 1, y: 2 }
    IS         = auto()      # para comparar variantes: c is Color::Rojo

    # Manejo de errores (v0.4)
    TRY        = auto()
    RESCUE     = auto()
    RAISE      = auto()

    # Módulos (v0.5)
    REQUIRE    = auto()      # require
    FROM       = auto()      # from
    AS         = auto()      # as

    # Tipos primitivos (palabras reservadas)
    INT_T      = auto()
    FLOAT_T    = auto()
    STRING_T   = auto()
    BOOL_T     = auto()
    BYTES_T    = auto()

    # Tipos colección (palabras reservadas v0.6.2: list/dict/tuple/set sin tipo elem)
    LIST_T     = auto()
    DICT_T     = auto()
    TUPLE_T    = auto()
    SET_T      = auto()

    # Operadores
    PLUS       = auto()   # +
    MINUS      = auto()   # -
    STAR       = auto()   # *
    SLASH      = auto()   # /
    DOUBLE_SLASH = auto() # //
    PERCENT    = auto()   # %
    POW        = auto()   # **
    EQ         = auto()   # ==
    NEQ        = auto()   # !=
    LT         = auto()   # <
    GT         = auto()   # >
    LTE        = auto()   # <=
    GTE        = auto()   # >=
    AND        = auto()   # &&
    OR         = auto()   # ||
    NOT        = auto()   # !
    AMP        = auto()   # &  (AND bit a bit — los modificadores &in/&out/&inout se lexifican aparte)
    BIT_XOR    = auto()   # ^  (XOR bit a bit)
    BIT_NOT    = auto()   # ~  (NOT bit a bit, unario)
    LSHIFT     = auto()   # << (desplazamiento a la izquierda)
    RSHIFT     = auto()   # >> (desplazamiento a la derecha)
    ASSIGN     = auto()   # =
    QUESTION   = auto()   # ?
    # Asignación compuesta (v0.4)
    PLUS_ASSIGN  = auto() # +=
    MINUS_ASSIGN = auto() # -=
    STAR_ASSIGN  = auto() # *=
    SLASH_ASSIGN = auto() # /=
    DSLASH_ASSIGN= auto() # //=
    PERCENT_ASSIGN= auto()# %=
    AMP_ASSIGN   = auto() # &=
    OR_ASSIGN    = auto() # |=
    XOR_ASSIGN   = auto() # ^=
    LSHIFT_ASSIGN= auto() # <<=
    RSHIFT_ASSIGN= auto() # >>=

    # Puntuación y delimitadores
    LPAREN     = auto()   # (
    RPAREN     = auto()   # )
    LBRACKET   = auto()   # [
    RBRACKET   = auto()   # ]
    LBRACE     = auto()   # {
    RBRACE     = auto()   # }
    LT_        = auto()   # <   (mismo token que LT; el parser decide por contexto)
    GT_        = auto()   # >   (mismo token que GT; el parser decide por contexto)
    COLON      = auto()   # :
    SEMICOLON  = auto()   # ;
    COMMA      = auto()   # ,
    DOUBLE_COLON = auto() # ::  (acceso a miembros — v0.5: reemplaza a .)
    VARARGS    = auto()   # ... (varargs en parámetros)
    PIPE       = auto()   # |
    ARROW      = auto()   # =>

    # Modificadores de parámetros
    AMP_IN     = auto()   # &in
    AMP_OUT    = auto()   # &out
    AMP_INOUT  = auto()   # &inout

    # Separadores
    NEWLINE    = auto()
    EOF        = auto()


KEYWORDS = {
    "var":      TokenType.VAR,
    "const":    TokenType.CONST,
    "if":       TokenType.IF,
    "then":     TokenType.THEN,
    "else":     TokenType.ELSE,
    "end":      TokenType.END,
    "while":    TokenType.WHILE,
    "for":      TokenType.FOR,
    "do":       TokenType.DO,
    "in":       TokenType.IN,
    "break":    TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "task":     TokenType.TASK,
    "return":   TokenType.RETURN,
    "global":   TokenType.GLOBAL,
    "say":      TokenType.SAY,
    "inlet":    TokenType.INLET,
    "range":    TokenType.RANGE,
    "Template": TokenType.TEMPLATE,
    "Shape":    TokenType.SHAPE,
    "Variant":  TokenType.VARIANT,
    "self":     TokenType.SELF,
    "new":      TokenType.NEW,
    "is":       TokenType.IS,
    "try":      TokenType.TRY,
    "rescue":   TokenType.RESCUE,
    "raise":    TokenType.RAISE,
    "require":  TokenType.REQUIRE,
    "from":     TokenType.FROM,
    "as":       TokenType.AS,
    "not":      TokenType.NOT,    # v0.6.2: alias de '!'
    "True":     TokenType.TRUE,
    "False":    TokenType.FALSE,
    "none":     TokenType.NONE,
    "int":      TokenType.INT_T,
    "float":    TokenType.FLOAT_T,
    "string":   TokenType.STRING_T,
    "bool":     TokenType.BOOL_T,
    "bytes":    TokenType.BYTES_T,
    "list":     TokenType.LIST_T,
    "dict":     TokenType.DICT_T,
    "tuple":    TokenType.TUPLE_T,
    "set":      TokenType.SET_T,
}


@dataclass
class Token:
    type:   TokenType
    value:  object
    line:   int
    col:    int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.col})"
