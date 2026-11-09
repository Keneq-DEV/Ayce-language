"""
ayce — Lexer / Tokenizer.
Convierte el código fuente .ayce en una secuencia de tokens.

Cada token lleva línea y columna para mensajes de error útiles.
"""

from .tokens import Token, TokenType, KEYWORDS
from .errors import AyceSyntaxError


# Caracteres válidos para iniciar un identificador (incluye acentos del español)
_ID_START = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_áéíóúüñÁÉÍÓÚÜÑ"
_ID_CONT  = _ID_START + "0123456789"

# Caracteres válidos en un identificador (incluidos dígitos después del primer char)
def _is_id_start(c):
    return c in _ID_START

def _is_id_cont(c):
    return c in _ID_CONT


class Lexer:
    def __init__(self, source: str, filename: str = "<stdin>"):
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []
        # Profundidad de delimitadores: cuando >0, los NEWLINE se ignoran
        self.bracket_depth = 0

    # ──────────────────────────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────────────────────────
    def _peek(self, offset=0):
        p = self.pos + offset
        return self.source[p] if p < len(self.source) else "\0"

    def _advance(self):
        c = self.source[self.pos]
        self.pos += 1
        if c == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return c

    def _emit(self, type_, value, line=None, col=None):
        self.tokens.append(Token(
            type_,
            value,
            line if line is not None else self.line,
            col  if col  is not None else self.col,
        ))

    def _error(self, msg, line=None, col=None):
        raise AyceSyntaxError(
            self.filename,
            line if line is not None else self.line,
            col  if col  is not None else self.col,
            msg,
        )

    # ──────────────────────────────────────────────────────────────────
    #  Token principal
    # ──────────────────────────────────────────────────────────────────
    def tokenize(self) -> list[Token]:
        # Ignorar BOM UTF-8 al inicio del archivo (común en Windows)
        if self.source and self.source[0] == "\ufeff":
            self.pos = 1

        while self.pos < len(self.source):
            c = self._peek()

            # Whitespace (no newline)
            if c in " \t\r":
                self._advance()
                continue

            # Comentario ### ... ### (multilínea)
            if c == "#" and self._peek(1) == "#" and self._peek(2) == "#":
                self._advance(); self._advance(); self._advance()  # consume ###
                while self.pos < len(self.source):
                    if self._peek() == "#" and self._peek(1) == "#" and self._peek(2) == "#":
                        self._advance(); self._advance(); self._advance()  # consume ###
                        break
                    self._advance()
                continue

            # Comentario ## hasta fin de línea
            if c == "#" and self._peek(1) == "#":
                while self.pos < len(self.source) and self._peek() != "\n":
                    self._advance()
                continue

            # Newline (se respeta la profundidad de brackets)
            if c == "\n":
                self._advance()
                if self.bracket_depth == 0:
                    # Colapsar múltiples newlines en uno
                    if not self.tokens or self.tokens[-1].type != TokenType.NEWLINE:
                        self._emit(TokenType.NEWLINE, "\\n")
                continue

            # Strings: "..." o f"..." o b"..."
            if c == '"':
                self._lex_string(prefix="")
                continue
            if c == "f" and self._peek(1) == '"':
                self._advance()  # consume 'f'
                self._lex_string(prefix="f")
                continue
            if c == "b" and self._peek(1) == '"':
                self._advance()  # consume 'b'
                self._lex_string(prefix="b")
                continue

            # Números: 0-9 o . seguido de dígito
            if c.isdigit() or (c == "." and self._peek(1).isdigit()):
                self._lex_number()
                continue

            # Identificadores y palabras reservadas
            if _is_id_start(c):
                # Pero ya cubrimos 'f' y 'b' arriba; si llegamos aquí es porque
                # no estaban seguidos de '"'. Por eso _lex_ident es seguro.
                self._lex_ident()
                continue

            # Operadores y puntuación
            self._lex_operator()

        # EOF
        if not self.tokens or self.tokens[-1].type != TokenType.NEWLINE:
            self._emit(TokenType.NEWLINE, "\\n")
        self._emit(TokenType.EOF, None)
        return self.tokens

    # ──────────────────────────────────────────────────────────────────
    #  Literales
    # ──────────────────────────────────────────────────────────────────
    def _split_fstring_expr(self, full: str):
        """Separa la expresión del formato en una f-string.
        {expr:formato} → (expr, formato)
        {expr}         → (expr, "")
        El : que separa es el primer : que NO está dentro de () [] <> {} ni en un string.
        """
        depth = 0
        in_string = False
        i = 0
        while i < len(full):
            c = full[i]
            if in_string:
                if c == '"':
                    in_string = False
                i += 1
                continue
            if c == '"':
                in_string = True
            elif c in "([{<":
                depth += 1
            elif c in ")]}>":
                if depth > 0:
                    depth -= 1
            elif c == ":" and depth == 0:
                return full[:i].strip(), full[i+1:].strip()
            i += 1
        return full.strip(), ""

    def _lex_string(self, prefix: str):
        line, col = self.line, self.col
        # Consumir la comilla de apertura
        self._advance()  # '"'

        parts: list = []  # para f-string: lista de (str | expr_source_string)
        current = []

        while True:
            if self.pos >= len(self.source):
                self._error("String sin cerrar (faltan comillas finales)", line, col)

            c = self._peek()

            if c == '"':
                self._advance()  # cierra comillas
                break

            if c == "\\":
                self._advance()
                esc = self._peek()
                self._advance()
                if esc == "n":   current.append("\n")
                elif esc == "t": current.append("\t")
                elif esc == "r": current.append("\r")
                elif esc == '"': current.append('"')
                elif esc == "\\": current.append("\\")
                elif esc == "x":
                    # \xHH
                    h1 = self._peek(); self._advance()
                    h2 = self._peek(); self._advance()
                    try:
                        current.append(chr(int(h1 + h2, 16)))
                    except ValueError:
                        self._error(f"Secuencia hexadecimal inválida: \\x{h1}{h2}")
                else:
                    # Barra invertida seguida de otro char: la dejamos literal
                    current.append("\\" + esc)
                continue

            # f-string: apertura de expresión {{
            if prefix == "f" and c == "{" and self._peek(1) == "{":
                self._advance(); self._advance()
                current.append("{")
                continue
            # f-string: cierre literal }}
            if prefix == "f" and c == "}" and self._peek(1) == "}":
                self._advance(); self._advance()
                current.append("}")
                continue
            # f-string: apertura de expresión {
            if prefix == "f" and c == "{":
                # Finalizar la parte literal actual
                if current:
                    parts.append(("text", "".join(current)))
                    current = []
                self._advance()  # consume '{'
                expr_chars = []
                depth = 1
                while depth > 0:
                    if self.pos >= len(self.source):
                        self._error("Expresión en f-string sin cerrar (falta '}')")
                    ec = self._peek()
                    if ec == "{":
                        depth += 1
                    elif ec == "}":
                        depth -= 1
                        if depth == 0:
                            self._advance()
                            break
                    expr_chars.append(ec)
                    self._advance()
                # Separar expresión de formato: {expr:formato}
                # El : que separa es el primer : que NO está dentro de () [] <> {}
                full = "".join(expr_chars)
                expr_part, fmt_part = self._split_fstring_expr(full)
                parts.append(("expr", expr_part, fmt_part))
                continue

            # Carácter normal
            current.append(c)
            self._advance()

        # Cierre: empaquetar según prefijo
        if current:
            if prefix == "f":
                parts.append(("text", "".join(current)))
            else:
                # string o bytes
                pass

        if prefix == "f":
            value = parts if parts else [("text", "")]
            self.tokens.append(Token(TokenType.FSTRING, value, line, col))
        elif prefix == "b":
            text = "".join(current)
            self.tokens.append(Token(TokenType.BYTES, text.encode("utf-8"), line, col))
        else:
            text = "".join(current)
            self.tokens.append(Token(TokenType.STRING, text, line, col))

    def _lex_number(self):
        line, col = self.line, self.col
        is_float = False
        digits = []

        while self.pos < len(self.source) and self._peek().isdigit():
            digits.append(self._advance())

        # Parte decimal
        if self._peek() == "." and self._peek(1).isdigit():
            is_float = True
            digits.append(self._advance())  # '.'
            while self.pos < len(self.source) and self._peek().isdigit():
                digits.append(self._advance())
        elif self._peek() == "." and not self._peek(1).isalpha() and self._peek(1) != "_":
            # Caso "2." → float
            is_float = True
            digits.append(self._advance())

        # Notación científica
        if self._peek() in ("e", "E"):
            save_pos = self.pos
            self._advance()  # consume e/E
            sign = ""
            if self._peek() in ("+", "-"):
                sign = self._advance()
            if self._peek().isdigit():
                is_float = True
                digits.append("e")
                digits.append(sign)
                while self.pos < len(self.source) and self._peek().isdigit():
                    digits.append(self._advance())
            else:
                # No era exponente: retroceder
                self.pos = save_pos

        text = "".join(digits)
        if is_float:
            self.tokens.append(Token(TokenType.FLOAT, float(text), line, col))
        else:
            self.tokens.append(Token(TokenType.INT, int(text), line, col))

    def _lex_ident(self):
        line, col = self.line, self.col
        chars = []
        while self.pos < len(self.source) and _is_id_cont(self._peek()):
            chars.append(self._advance())
        name = "".join(chars)

        kw = KEYWORDS.get(name)
        if kw is not None:
            self.tokens.append(Token(kw, name, line, col))
        else:
            self.tokens.append(Token(TokenType.IDENT, name, line, col))

    def _lex_operator(self):
        line, col = self.line, self.col
        c = self._peek()
        c2 = self._peek(1)
        c3 = self._peek(2)

        # Operadores de 3 caracteres (v0.4): //=
        three = c + c2 + c3
        if three == "//=":
            self._advance(); self._advance(); self._advance()
            self.tokens.append(Token(TokenType.DSLASH_ASSIGN, "//=", line, col)); return

        # Operadores de 2 caracteres
        two = c + c2
        if two == "**":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.POW, "**", line, col)); return
        if two == "==":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.EQ, "==", line, col)); return
        if two == "!=":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.NEQ, "!=", line, col)); return
        if two == "<=":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.LTE, "<=", line, col)); return
        if two == ">=":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.GTE, ">=", line, col)); return
        if two == "&&":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.AND, "&&", line, col)); return
        if two == "||":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.OR, "||", line, col)); return
        if two == "=>":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.ARROW, "=>", line, col)); return
        # División entera // (v0.4) — va antes que / para no confundirse
        if two == "//":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.DOUBLE_SLASH, "//", line, col)); return
        # Asignación compuesta (v0.4)
        if two == "+=":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.PLUS_ASSIGN, "+=", line, col)); return
        if two == "-=":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.MINUS_ASSIGN, "-=", line, col)); return
        if two == "*=":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.STAR_ASSIGN, "*=", line, col)); return
        if two == "/=":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.SLASH_ASSIGN, "/=", line, col)); return
        if two == "%=":
            self._advance(); self._advance()
            self.tokens.append(Token(TokenType.PERCENT_ASSIGN, "%=", line, col)); return

        # Operador ? (ternario v0.4)
        if c == "?":
            self._advance()
            self.tokens.append(Token(TokenType.QUESTION, "?", line, col)); return

        # Modificadores &in &out &inout
        if c == "&":
            for kw, tt in [("in", TokenType.AMP_IN),
                          ("out", TokenType.AMP_OUT),
                          ("inout", TokenType.AMP_INOUT)]:
                if self.source[self.pos:self.pos + len(kw) + 1] == "&" + kw:
                    for _ in range(len(kw) + 1):
                        self._advance()
                    self.tokens.append(Token(tt, "&" + kw, line, col)); return
            self._error(f"Modificador '&' inválido. Se esperaba &in, &out o &inout")

        # Operadores de 1 carácter
        single = {
            "+": TokenType.PLUS,      "-": TokenType.MINUS,
            "*": TokenType.STAR,      "/": TokenType.SLASH,
            "%": TokenType.PERCENT,
            "<": TokenType.LT,        ">": TokenType.GT,
            "!": TokenType.NOT,        "=": TokenType.ASSIGN,
            "(": TokenType.LPAREN,    ")": TokenType.RPAREN,
            "[": TokenType.LBRACKET,  "]": TokenType.RBRACKET,
            "{": TokenType.LBRACE,    "}": TokenType.RBRACE,
            ":": TokenType.COLON,     ";": TokenType.SEMICOLON,
            ",": TokenType.COMMA,     ".": TokenType.DOT,
            "|": TokenType.PIPE,
        }
        if c in single:
            self._advance()
            tt = single[c]
            # Actualizar profundidad de brackets (NO incluye < y >,
            # que son ambivalentes: comparación o delimitadores de dict)
            if c in "([{":
                self.bracket_depth += 1
            elif c in ")]}":
                if self.bracket_depth > 0:
                    self.bracket_depth -= 1
            self.tokens.append(Token(tt, c, line, col))
            return

        self._error(f"Carácter inesperado: {c!r}")
