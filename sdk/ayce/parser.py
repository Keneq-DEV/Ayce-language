"""
ayce — Parser recursivo descendente.
Construye el AST a partir de la secuencia de tokens.
"""

from .tokens import Token, TokenType
from .ast_nodes import *
from .errors import AyceSyntaxError


class Parser:
    def __init__(self, tokens: list[Token], filename: str = "<stdin>"):
        self.tokens = tokens
        self.filename = filename
        self.pos = 0
        # v0.6.4: mientras se parsea el sujeto de `State <expr> - <`, el '-'
        # NO se consume como resta binaria: es el conector del bloque.
        self._stop_state_subject = False

    # ──────────────────────────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────────────────────────
    def _peek(self, offset=0) -> Token:
        p = self.pos + offset
        if p < len(self.tokens):
            return self.tokens[p]
        return self.tokens[-1]  # EOF

    def _advance(self) -> Token:
        t = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return t

    def _check(self, *types: TokenType) -> bool:
        return self._peek().type in types

    def _match(self, *types: TokenType) -> bool:
        if self._peek().type in types:
            self._advance()
            return True
        return False

    def _expect(self, type_: TokenType, what: str) -> Token:
        if self._peek().type != type_:
            # v0.6.1: '>>' se lexifica como un único token RSHIFT, pero en un
            # tipo dict anidado <K, <V1, V2>> el cierre son dos '>' seguidos.
            # Igual que hace CPython con los generics: dividimos el token.
            # v0.6.2: la división INSERTA el segundo '>' en vez de pisar el
            # token siguiente (antes se comía el '=' de la inicialización).
            if type_ == TokenType.GT and self._peek().type == TokenType.RSHIFT:
                t = self._peek()
                self.tokens[self.pos] = Token(TokenType.GT, ">", t.line, t.col)
                self.tokens.insert(self.pos + 1, Token(TokenType.GT, ">", t.line, t.col + 1))
                return self._advance()
            t = self._peek()
            raise AyceSyntaxError(
                self.filename, t.line, t.col,
                f"Se esperaba {what} pero se encontró {t.value!r}"
            )
        return self._advance()

    def _skip_newlines(self):
        while self._check(TokenType.NEWLINE):
            self._advance()

    def _skip_separators(self):
        """Skip NEWLINEs y SEMICOLONs (separadores de sentencias)."""
        while self._check(TokenType.NEWLINE, TokenType.SEMICOLON):
            self._advance()

    # ──────────────────────────────────────────────────────────────────
    #  Entrada principal
    # ──────────────────────────────────────────────────────────────────
    def parse(self) -> Program:
        stmts = []
        self._skip_separators()
        while not self._check(TokenType.EOF):
            stmts.append(self._parse_stmt())
            self._skip_separators()
        return Program(stmts=stmts)

    # ──────────────────────────────────────────────────────────────────
    #  Sentencias
    # ──────────────────────────────────────────────────────────────────
    def _parse_stmt(self) -> Stmt:
        t = self._peek()
        if t.type == TokenType.VAR:
            return self._parse_var_decl()
        if t.type == TokenType.CONST:
            return self._parse_const_decl()
        if t.type == TokenType.TASK:
            return self._parse_task_decl()
        if t.type == TokenType.TEMPLATE:
            return self._parse_template_decl()
        if t.type == TokenType.SHAPE:
            return self._parse_shape_decl()
        if t.type == TokenType.VARIANT:
            return self._parse_variant_decl()
        if t.type == TokenType.IF:
            return self._parse_if()
        if t.type == TokenType.WHILE:
            return self._parse_while()
        if t.type == TokenType.FOR:
            return self._parse_for()
        if t.type == TokenType.STATE:
            return self._parse_state()
        if t.type == TokenType.TRY:
            return self._parse_try()
        if t.type == TokenType.RAISE:
            return self._parse_raise()
        if t.type == TokenType.AFFIRM:
            return self._parse_affirm()
        if t.type == TokenType.REQUIRE:
            return self._parse_require()
        if t.type == TokenType.BREAK:
            self._advance()
            return BreakStmt(line=t.line, col=t.col)
        if t.type == TokenType.CONTINUE:
            self._advance()
            return ContinueStmt(line=t.line, col=t.col)
        if t.type == TokenType.RETURN:
            return self._parse_return()
        if t.type == TokenType.SAY:
            return self._parse_say()
        if t.type == TokenType.GLOBAL:
            return self._parse_global()
        # v0.6.4: <GUARD>-<MAIN> { ... } — el guard principal del cliente.
        # Se reconoce por contexto (GUARD y MAIN no son keywords: son
        # identificadores en una secuencia fija).
        if t.type == TokenType.LT and self._peek(1).type == TokenType.IDENT \
                and self._peek(1).value == "GUARD":
            return self._parse_guard_main()
        # Si no es keyword, es una asignación o llamada (ExprStmt)
        return self._parse_expr_or_assign()

    def _parse_var_decl(self) -> Stmt:
        """Declaración de variables (v0.6.4, diseño del cliente):

            var nombre: tipo = valor                 (una, como siempre)
            var n1-n2-n3: t1, t2, t3 = v1, v2, v3    (múltiple, separada por '-')

        Los tipos que falten son none (tipo desconocido) y los valores van
        uno a uno con los nombres. El '=' sigue siendo opcional en var."""
        t = self._expect(TokenType.VAR, "'var'")
        decls = self._parse_decl_comun(VarDecl, t, con_valor=False)
        return decls[0] if len(decls) == 1 else DeclGroup(decls=decls, line=t.line, col=t.col)

    def _parse_const_decl(self) -> Stmt:
        """Declaración de constantes; misma cola múltiple que var, con '='
        obligatorio (v0.6.4)."""
        t = self._expect(TokenType.CONST, "'const'")
        decls = self._parse_decl_comun(ConstDecl, t, con_valor=True)
        return decls[0] if len(decls) == 1 else DeclGroup(decls=decls, line=t.line, col=t.col)

    def _parse_decl_comun(self, ctor, kw, con_valor: bool) -> list:
        """Cola común de var/const: nombres separados por '-', tipos por ',',
        valores por ','. Reglas coherentes: los tipos que falten son none;
        no puede haber más tipos que nombres; con valores, exactamente uno
        por nombre."""
        names = [self._expect(TokenType.IDENT, "nombre de variable")]
        # '-' como separador de nombres: sólo si sigue otro identificador
        while self._check(TokenType.MINUS) and self._peek(1).type == TokenType.IDENT:
            self._advance()
            names.append(self._expect(TokenType.IDENT, "nombre de variable"))
        self._expect(TokenType.COLON, "':'")
        types = [self._parse_type()]
        while self._match(TokenType.COMMA):
            types.append(self._parse_type())
        n = len(names)
        if len(types) > n:
            raise AyceSyntaxError(self.filename, kw.line, kw.col,
                f"más tipos ({len(types)}) que nombres ({n}): cada nombre "
                f"lleva a lo sumo un tipo; los que falten son none")
        if con_valor:
            self._expect(TokenType.ASSIGN, "'=' (const requiere valor inicial)")
            hay_init = True
        else:
            hay_init = self._match(TokenType.ASSIGN)
        exprs = None
        if hay_init:
            exprs = [self._parse_expr()]
            while self._match(TokenType.COMMA):
                exprs.append(self._parse_expr())
            if len(exprs) > n:
                raise AyceSyntaxError(self.filename, kw.line, kw.col,
                    f"más valores ({len(exprs)}) que nombres ({n}): "
                    f"cada nombre toma exactamente un valor")
            if len(exprs) < n:
                raise AyceSyntaxError(self.filename, kw.line, kw.col,
                    f"faltan valores: hay {len(exprs)} para {n} nombres "
                    f"(los valores van uno a uno)")
        decls = []
        for i, tok in enumerate(names):
            tipo = (types[i] if i < len(types)
                    else PrimitiveType(name="none", line=tok.line, col=tok.col))
            init = exprs[i] if exprs is not None else None
            decls.append(ctor(name=tok.value, type_node=tipo, init=init,
                              line=tok.line, col=tok.col))
        return decls

    def _parse_task_decl(self) -> TaskDecl:
        t = self._expect(TokenType.TASK, "'task'")
        # v0.6.4: el nombre puede ser box — es keyword, pero puede haber APIs
        # públicas con ese nombre. Como llamadas sueltas sigue siendo keyword;
        # sólo el acceso por módulo (::nombre) lo alcanza. ('match' y 'guard'
        # volvieron a ser identificadores normales en v0.6.4.)
        if self._peek().type == TokenType.BOX:
            name = self._advance().value
        else:
            name = self._expect(TokenType.IDENT, "nombre de tarea").value

        # Sobrecarga: una o más firmas separadas por |
        # Sintaxis:  task nombre(firma1) | (firma2) | ...  [= tipo] ;
        #            { cuerpo1 } { cuerpo2 } ...
        # O bien:    task nombre(firma) = tipo => expr      (lambda)
        signatures = [self._parse_signature()]
        while self._match(TokenType.PIPE):
            signatures.append(self._parse_signature())

        # Return type (compartido por todas las firmas en sobrecarga)
        return_type = None
        if self._match(TokenType.ASSIGN):
            return_type = self._parse_type()

        # Lambda: task f(...) = tipo => expr   (sin ; ni {})
        bodies = []
        if self._check(TokenType.ARROW):
            self._advance()
            expr = self._parse_expr()
            bodies.append([ReturnStmt(value=expr, line=t.line, col=t.col)])
        else:
            # v0.6.2 (spec 15.3): ';' obligatorio sólo si NO hay tipo de retorno.
            # Con `= tipo` el ';' es opcional.
            if return_type is None:
                self._expect(TokenType.SEMICOLON, "';'")
            else:
                self._match(TokenType.SEMICOLON)
            self._skip_newlines()
            self._expect(TokenType.LBRACE, "'{'")
            # Un cuerpo por firma, separados por | dentro del mismo bloque
            # (sintaxis original del doc ayce)
            first_body = self._parse_block_body_until_pipe_or_brace()
            bodies.append(first_body)
            while self._match(TokenType.PIPE):
                self._skip_separators()
                next_body = self._parse_block_body_until_pipe_or_brace()
                bodies.append(next_body)
            self._expect(TokenType.RBRACE, "'}'")

            # Si hay más firmas que cuerpos, rellenar con cuerpo vacío
            while len(bodies) < len(signatures):
                bodies.append([])

        return TaskDecl(
            name=name,
            signatures=signatures,
            return_type=return_type,
            bodies=bodies,
            line=t.line, col=t.col,
        )

    # ──────────────────────────────────────────────────────────────────
    #  Tipos compuestos de usuario (v0.3)
    # ──────────────────────────────────────────────────────────────────
    def _parse_field_decl(self) -> FieldDecl:
        """Parsea un campo: nombre: tipo [= default]"""
        t = self._peek()
        name = self._expect(TokenType.IDENT, "nombre de campo").value
        self._expect(TokenType.COLON, "':'")
        type_node = self._parse_type()
        default = None
        if self._match(TokenType.ASSIGN):
            default = self._parse_expr()
        return FieldDecl(name=name, type_node=type_node, default=default,
                         line=t.line, col=t.col)

    def _parse_template_decl(self) -> TemplateDecl:
        """Template Nombre [: Padre] {
            campo1: tipo
            campo2: tipo
            task metodo() ; { ... }
        }"""
        t = self._expect(TokenType.TEMPLATE, "'Template'")
        name = self._expect(TokenType.IDENT, "nombre de Template").value
        # Herencia: Template Hijo : Padre (v0.4.1)
        parent_name = ""
        if self._match(TokenType.COLON):
            parent_name = self._expect(TokenType.IDENT, "nombre del Template padre").value
        self._skip_newlines()
        self._expect(TokenType.LBRACE, "'{'")
        self._skip_separators()

        fields = []
        methods = []
        while not self._check(TokenType.RBRACE, TokenType.EOF):
            if self._check(TokenType.TASK):
                methods.append(self._parse_task_decl())
            else:
                fields.append(self._parse_field_decl())
            self._skip_separators()

        self._expect(TokenType.RBRACE, "'}'")
        return TemplateDecl(name=name, fields=fields, methods=methods,
                            parent_name=parent_name, line=t.line, col=t.col)

    def _parse_shape_decl(self) -> ShapeDecl:
        """Shape Nombre {
            campo1: tipo
            campo2: tipo
        }"""
        t = self._expect(TokenType.SHAPE, "'Shape'")
        name = self._expect(TokenType.IDENT, "nombre de Shape").value
        self._skip_newlines()
        self._expect(TokenType.LBRACE, "'{'")
        self._skip_separators()

        fields = []
        while not self._check(TokenType.RBRACE, TokenType.EOF):
            fields.append(self._parse_field_decl())
            self._skip_separators()

        self._expect(TokenType.RBRACE, "'}'")
        return ShapeDecl(name=name, fields=fields, line=t.line, col=t.col)

    def _parse_variant_decl(self) -> VariantDecl:
        """Variant Nombre {
            Caso1
            Caso2(tipo_payload)
        }"""
        t = self._expect(TokenType.VARIANT, "'Variant'")
        name = self._expect(TokenType.IDENT, "nombre de Variant").value
        self._skip_newlines()
        self._expect(TokenType.LBRACE, "'{'")
        self._skip_separators()

        cases = []
        while not self._check(TokenType.RBRACE, TokenType.EOF):
            ct = self._peek()
            case_name = self._expect(TokenType.IDENT, "nombre de caso").value
            payload_type = None
            if self._match(TokenType.LPAREN):
                payload_type = self._parse_type()
                self._expect(TokenType.RPAREN, "')'")
            cases.append(VariantCase(name=case_name, payload_type=payload_type,
                                     line=ct.line, col=ct.col))
            self._skip_separators()

        self._expect(TokenType.RBRACE, "'}'")
        return VariantDecl(name=name, cases=cases, line=t.line, col=t.col)


    def _parse_signature(self) -> TaskSignature:
        t = self._peek()
        self._expect(TokenType.LPAREN, "'('")
        params = []
        if not self._check(TokenType.RPAREN):
            params.append(self._parse_param())
            while self._match(TokenType.COMMA):
                params.append(self._parse_param())
        self._expect(TokenType.RPAREN, "')'")
        # Varargs coherente (v0.6.4): a lo sumo un '...' y sólo al final de
        # la firma; en otra posición el empaquetado sería ambiguo.
        for i, p in enumerate(params):
            if p.varargs and i != len(params) - 1:
                raise AyceSyntaxError(self.filename, p.line, p.col,
                    "el parámetro '...' debe ser el último de la firma")
        return TaskSignature(params=params, line=t.line, col=t.col)

    def _parse_param(self) -> Param:
        t = self._peek()
        # En ayce, la firma es:  tipo [modificador] nombre [= default]
        # El modificador va entre el tipo y el nombre (ej: string &in origen)
        type_node = self._parse_type()
        modifier = ""
        if self._check(TokenType.AMP_IN, TokenType.AMP_OUT, TokenType.AMP_INOUT):
            modifier = self._advance().value

        varargs = False
        # Varargs: token único '...' (v0.5)
        if self._check(TokenType.VARARGS):
            self._advance()
            varargs = True

        name = self._expect(TokenType.IDENT, "nombre de parámetro").value
        default = None
        if self._match(TokenType.ASSIGN):
            default = self._parse_expr()

        return Param(
            modifier=modifier, type_node=type_node, varargs=varargs,
            name=name, default=default, line=t.line, col=t.col,
        )

    def _parse_block_body(self) -> list:
        """Lee sentencias hasta encontrar '}', 'end', 'else', 'rescue',
        'finally' o EOF. (v0.6.4: 'finally' también corta un cuerpo de try
        o de rescue, igual que 'rescue'.)"""
        self._skip_separators()
        stmts = []
        while not self._check(TokenType.RBRACE, TokenType.END, TokenType.ELSE,
                              TokenType.RESCUE, TokenType.FINALLY, TokenType.EOF):
            stmts.append(self._parse_stmt())
            self._skip_separators()
        return stmts

    def _parse_block_body_until_pipe_or_brace(self) -> list:
        """Lee sentencias hasta encontrar '}', '|' (separador de sobrecarga) o EOF."""
        self._skip_separators()
        stmts = []
        while not self._check(TokenType.RBRACE, TokenType.PIPE, TokenType.EOF):
            stmts.append(self._parse_stmt())
            self._skip_separators()
        return stmts

    def _parse_if(self) -> IfStmt:
        t = self._expect(TokenType.IF, "'if'")
        branches = []
        cond = self._parse_expr()
        self._expect(TokenType.THEN, "'then'")
        body = self._parse_block_body()
        branches.append((cond, body))

        # else if / else (sin end entre ramas — el end va al final de toda la cadena)
        # v0.6.1 fix: 'else if' sólo se interpreta como cadena else-if cuando
        # 'else' e 'if' están en la MISMA línea. Si están en líneas distintas,
        # es un bloque else normal que contiene un if anidado (con su propio end).
        # Esto resuelve la ambigüedad:
        #   if A then ... else if B then ... end      (cadena, 1 end)
        #   if A then ... else                       (bloque, 2 ends)
        #       if B then ... end
        #   end
        while self._check(TokenType.ELSE):
            else_tok = self._advance()
            if self._check(TokenType.IF) and self._peek().line == else_tok.line:
                self._advance()  # consume 'if'
                cond2 = self._parse_expr()
                self._expect(TokenType.THEN, "'then'")
                body2 = self._parse_block_body()
                branches.append((cond2, body2))
            else:
                # rama else final (bloque). Puede contener un if anidado
                # que tendrá su propio end — eso lo maneja _parse_block_body.
                body2 = self._parse_block_body()
                branches.append((None, body2))
                break

        self._expect(TokenType.END, "'end'")
        return IfStmt(branches=branches, line=t.line, col=t.col)

    def _parse_while(self) -> WhileStmt:
        t = self._expect(TokenType.WHILE, "'while'")
        cond = self._parse_expr()
        self._expect(TokenType.DO, "'do'")
        body = self._parse_block_body()
        self._expect(TokenType.END, "'end'")
        return WhileStmt(cond=cond, body=body, line=t.line, col=t.col)

    def _parse_for(self) -> ForStmt:
        t = self._expect(TokenType.FOR, "'for'")
        # v0.6.4: el objetivo puede desempaquetar cada elemento:
        #   for mes-monto in ventas do   /   for k-v in dict do
        # Un solo nombre itera los valores; varios nombres exigen que cada
        # elemento sea una tupla o lista de esa longitud.
        names = [self._expect(TokenType.IDENT, "nombre de variable de iteración").value]
        while self._match(TokenType.MINUS):
            names.append(self._expect(TokenType.IDENT, "nombre tras '-'").value)
        self._expect(TokenType.IN, "'in'")
        iterable = self._parse_expr()
        self._expect(TokenType.DO, "'do'")
        body = self._parse_block_body()
        self._expect(TokenType.END, "'end'")
        return ForStmt(var_name=names[0], iterable=iterable, body=body,
                       unpack_names=names[1:], line=t.line, col=t.col)

    # ──────────────────────────────────────────────────────────────────
    #  State/box y guard principal (v0.6.4 — diseño del cliente)
    # ──────────────────────────────────────────────────────────────────
    def _parse_brace_body(self) -> list:
        """Lee sentencias entre llaves { ... } (cuerpo de <GUARD>-<MAIN>).
        A diferencia de los cuerpos de task, no reconoce '|' como separador
        de sobrecargas: dentro del guard '|' es el operador pipe/or-bit."""
        self._skip_newlines()
        self._expect(TokenType.LBRACE, "'{'")
        self._skip_separators()
        stmts = []
        while not self._check(TokenType.RBRACE, TokenType.EOF):
            stmts.append(self._parse_stmt())
            self._skip_separators()
        self._expect(TokenType.RBRACE, "'}'")
        return stmts

    def _parse_bracket_body(self) -> list:
        """Lee sentencias entre corchetes [ ... ] (cuerpo de un brazo de State).
        Es la forma del cliente: cada brazo abre con `[` y cierra con `]`."""
        self._skip_newlines()
        self._expect(TokenType.LBRACKET, "'[' (el cuerpo del brazo abre con [ )")
        self._skip_separators()
        stmts = []
        while not self._check(TokenType.RBRACKET, TokenType.EOF):
            stmts.append(self._parse_stmt())
            self._skip_separators()
        self._expect(TokenType.RBRACKET, "']' (el cuerpo del brazo cierra con ] )")
        return stmts

    # Tokens que pueden iniciar un patrón de TIPO (v0.6.4). El resto de la
    # gramática del tipo la resuelve _parse_type (sufijos [], <K, V>, (T1, T2)).
    _PATTERN_TYPE_TOKENS = frozenset((
        TokenType.INT_T, TokenType.FLOAT_T, TokenType.STRING_T,
        TokenType.BOOL_T, TokenType.BYTES_T, TokenType.NONE,
        TokenType.LIST_T, TokenType.DICT_T, TokenType.TUPLE_T, TokenType.SET_T,
        TokenType.LT, TokenType.LPAREN,
    ))

    def _parse_pattern_alt(self) -> PatternAlt:
        """Una alternativa de patrón: tipo, literal, Tipo::Caso o identificador."""
        t = self._peek()
        # Patrón de tipo: int, string, int[], <string, int>, none, list, ...
        if t.type in self._PATTERN_TYPE_TOKENS:
            tn = self._parse_type_pattern()
            return PatternAlt(kind="type", type_node=tn, line=t.line, col=t.col)
        # Literales negativos: -1, -2.5
        if t.type == TokenType.MINUS and self._peek(1).type in (TokenType.INT, TokenType.FLOAT):
            self._advance()
            nt = self._advance()
            lit = (IntLit(value=nt.value, line=nt.line, col=nt.col)
                   if nt.type == TokenType.INT
                   else FloatLit(value=nt.value, line=nt.line, col=nt.col))
            return PatternAlt(kind="value",
                              value_expr=UnaryExpr(op="-", operand=lit, line=t.line, col=t.col),
                              line=t.line, col=t.col)
        # Literales: "a", 1, 3.14, True, False, b"..."
        if t.type in (TokenType.STRING, TokenType.INT, TokenType.FLOAT,
                      TokenType.TRUE, TokenType.FALSE, TokenType.BYTES):
            self._advance()
            cls = {TokenType.STRING: StringLit, TokenType.INT: IntLit,
                   TokenType.FLOAT: FloatLit, TokenType.BYTES: BytesLit,
                   TokenType.TRUE: BoolLit, TokenType.FALSE: BoolLit}[t.type]
            value = t.value
            if t.type == TokenType.TRUE:
                value = True
            elif t.type == TokenType.FALSE:
                value = False
            return PatternAlt(kind="value", value_expr=cls(value=value, line=t.line, col=t.col),
                              line=t.line, col=t.col)
        # Caso de Variant: Tipo::Caso
        if t.type == TokenType.IDENT and self._peek(1).type == TokenType.DOUBLE_COLON:
            self._advance()
            self._expect(TokenType.DOUBLE_COLON, "'::'")
            case_name = self._expect(TokenType.IDENT, "nombre de caso").value
            return PatternAlt(kind="variant", type_name=t.value, case_name=case_name,
                              line=t.line, col=t.col)
        # Identificador: coincide por valor; si nombra un tipo de usuario,
        # coincide por tipo (lo resuelve el intérprete en runtime).
        if t.type == TokenType.IDENT:
            self._advance()
            return PatternAlt(kind="ident", name=t.value, line=t.line, col=t.col)
        raise AyceSyntaxError(
            self.filename, t.line, t.col,
            "Se esperaba un patrón (tipo, literal, Tipo::Caso o identificador) "
            f"pero se encontró {t.value!r}"
        )

    def _parse_type_pattern(self) -> TypeNode:
        """Como _parse_type pero SIN el sufijo de set { }: en un patrón, la '{'
        que sigue es el cuerpo del brazo, no un tipo set. Los sufijos [] (listas)
        y las formas <K, V> y (T1, T2) siguen soportados."""
        t = self._peek()

        # none como marcador de modo flexible: none[], none<>, none()
        if t.type == TokenType.NONE:
            self._advance()
            if self._check(TokenType.LBRACKET):
                self._advance(); self._expect(TokenType.RBRACKET, "']'")
                return ListType(flexible=True, line=t.line, col=t.col)
            if self._check(TokenType.LT):
                self._advance(); self._expect(TokenType.GT, "'>'")
                return DictType(flexible=True, line=t.line, col=t.col)
            if self._check(TokenType.LPAREN):
                self._advance(); self._expect(TokenType.RPAREN, "')'")
                return TupleType(flexible=True, line=t.line, col=t.col)
            return PrimitiveType(name="none", line=t.line, col=t.col)

        prim_map = {
            TokenType.INT_T:    "int",
            TokenType.FLOAT_T:  "float",
            TokenType.STRING_T: "string",
            TokenType.BOOL_T:   "bool",
            TokenType.BYTES_T:  "bytes",
        }
        if t.type in prim_map:
            self._advance()
            base = PrimitiveType(name=prim_map[t.type], line=t.line, col=t.col)
            # int[][], int[][][], ... — sin el sufijo { } de set
            return self._parse_type_suffix(base, t)

        if t.type == TokenType.LIST_T:
            self._advance()
            return ListType(flexible=True, line=t.line, col=t.col)
        if t.type == TokenType.DICT_T:
            self._advance()
            return DictType(flexible=True, line=t.line, col=t.col)
        if t.type == TokenType.TUPLE_T:
            self._advance()
            return TupleType(flexible=True, line=t.line, col=t.col)
        if t.type == TokenType.SET_T:
            self._advance()
            return SetType(flexible=True, line=t.line, col=t.col)

        # Diccionario: <K, V> o <K, V1, V2>
        if t.type == TokenType.LT:
            self._advance()
            self._skip_newlines()
            key_type = self._parse_type()
            self._skip_newlines()
            value_types = []
            while self._match(TokenType.COMMA):
                self._skip_newlines()
                value_types.append(self._parse_type())
                self._skip_newlines()
            self._expect(TokenType.GT, "'>'")
            d = DictType(key_type=key_type, value_types=value_types, line=t.line, col=t.col)
            return self._parse_type_suffix(d, t)

        # Tupla heterogénea: (T1, T2, ...)
        if t.type == TokenType.LPAREN:
            self._advance()
            elem_types = [self._parse_type()]
            while self._match(TokenType.COMMA):
                elem_types.append(self._parse_type())
            self._expect(TokenType.RPAREN, "')'")
            tt = TupleType(elem_types=elem_types, line=t.line, col=t.col)
            return self._parse_type_suffix(tt, t)

        raise AyceSyntaxError(
            self.filename, t.line, t.col,
            f"Se esperaba un tipo pero se encontró {t.value!r}"
        )

    def _parse_patterns(self) -> list:
        """Patrones separados por ||:  string || int || float"""
        alts = [self._parse_pattern_alt()]
        while self._match(TokenType.OR):
            alts.append(self._parse_pattern_alt())
        return alts

    def _parse_state(self) -> StateStmt:
        """Diseño del cliente (arreglo de la 0.6.4):

            State <expr> then <
                box is type ( <patrón>[ || <patrón>...] ) [ cuerpo ]
                ...
                box is null [ cuerpo ]   (opcional, siempre el último)
            >

        El conector entre el sujeto y los brazos es 'then' (igual que el if).
        En la v0.6.4 era '-': nunca fue diseño del cliente y quedó fuera —
        si alguien escribe 'State x - <', el error de sintaxis lo dice y
        señala la forma correcta. Las comas entre brazos son opcionales."""
        t = self._expect(TokenType.STATE, "'State'")
        self._stop_state_subject = True
        try:
            subject = self._parse_expr()
        finally:
            self._stop_state_subject = False
        self._expect(TokenType.THEN, "'then' (State lleva 'State x then < ... >')")
        self._expect(TokenType.LT, "'<' para abrir los brazos del State")
        arms = []
        saw_null = False
        while True:
            self._skip_separators()
            if self._check(TokenType.GT):
                break
            if self._check(TokenType.EOF):
                nt = self._peek()
                raise AyceSyntaxError(self.filename, nt.line, nt.col,
                    "State sin '>' de cierre")
            at = self._peek()
            if at.type != TokenType.BOX:
                raise AyceSyntaxError(self.filename, at.line, at.col,
                    "Los brazos de State son 'box is type ( <patrón> ) [ ... ]' "
                    "o 'box is null [ ... ]'")
            self._advance()
            self._expect(TokenType.IS,
                "'is' (los brazos de State son 'box is type ( ... ) [ ... ]')")
            # 'type' y 'null' se reconocen por contexto: son IDENT en posición
            # de brazo, no keywords globales.
            if self._check(TokenType.IDENT) and self._peek().value == "type":
                self._advance()
                self._expect(TokenType.LPAREN, "'(' después de type")
                pats = self._parse_patterns()
                self._expect(TokenType.RPAREN, "')' para cerrar el patrón")
                if saw_null:
                    raise AyceSyntaxError(self.filename, at.line, at.col,
                        "El brazo 'box is null' debe ser el último del State")
                body = self._parse_bracket_body()
                arms.append((pats, body))
            elif self._check(TokenType.IDENT) and self._peek().value == "null":
                if saw_null:
                    raise AyceSyntaxError(self.filename, at.line, at.col,
                        "Sólo puede haber un brazo 'box is null' en un State")
                self._advance()
                body = self._parse_bracket_body()
                arms.append((None, body))
                saw_null = True
            else:
                nt = self._peek()
                raise AyceSyntaxError(self.filename, nt.line, nt.col,
                    "Después de 'box is' viene 'type ( <patrón> )' o 'null' "
                    f"(brazo de reserva), no {nt.value!r}")
            self._match(TokenType.COMMA)  # coma entre brazos: opcional
        self._expect(TokenType.GT, "'>' para cerrar el State")
        return StateStmt(subject=subject, arms=arms, line=t.line, col=t.col)

    def _parse_guard_main(self) -> GuardMainStmt:
        """Diseño del cliente (v0.6.4): el guard principal.

            <GUARD>-<MAIN> { cuerpo }

        Punto de entrada del programa (arreglo de la 0.6.4, decisión del cliente): cuando
        el archivo se ejecuta directamente, SÓLO corren los cuerpos de los
        guards; si el archivo se carga con `require`, el bloque se omite y el
        nivel superior corre. GUARD y MAIN van cada uno entre sus propios
        < >: < GUARD > - < MAIN >, y se acepta también la flecha
        <GUARD>-><MAIN> (misma grafía con la que el cliente lo escribe)."""
        t = self._expect(TokenType.LT, "'<'")
        gt = self._expect(TokenType.IDENT, "'GUARD'")
        if gt.value != "GUARD":
            raise AyceSyntaxError(self.filename, gt.line, gt.col,
                f"El guard se escribe <GUARD>-<MAIN>, no <{gt.value}>")
        self._expect(TokenType.GT, "'>' que cierra <GUARD>")
        self._expect(TokenType.MINUS, "'-' entre <GUARD> y <MAIN>")
        # <GUARD>-><MAIN> (flecha) es equivalente a <GUARD>-<MAIN>;
        # el '>' suelto de la flecha se come aquí sin reclamar.
        if self._check(TokenType.GT):
            self._advance()
        self._expect(TokenType.LT, "'<' que abre <MAIN>")
        mn = self._expect(TokenType.IDENT, "'MAIN'")
        if mn.value != "MAIN":
            raise AyceSyntaxError(self.filename, mn.line, mn.col,
                f"El guard sólo admite <MAIN>, no <{mn.value}>")
        self._expect(TokenType.GT, "'>' que cierra <MAIN>")
        body = self._parse_brace_body()
        return GuardMainStmt(body=body, line=t.line, col=t.col)

    def _parse_try(self) -> TryStmt:
        """try ... rescue(nombre: Tipo) ... [finally ...] end
        v0.6.2: varios rescue en orden (spec 12.1), con o sin paréntesis.
        v0.6.4: finally opcional al final — su cuerpo corre siempre."""
        t = self._expect(TokenType.TRY, "'try'")
        body = self._parse_block_body()
        rescues = []
        while self._check(TokenType.RESCUE):
            self._advance()
            rescue_name = ""
            rescue_type = ""
            if self._check(TokenType.LPAREN):
                self._advance()
                rescue_name = self._expect(TokenType.IDENT, "nombre de variable de error").value
                # Tipo opcional: rescue(err: Tipo)
                if self._match(TokenType.COLON):
                    # El tipo puede ser un IDENT o un tipo primitivo (Error, Div0, etc.)
                    type_tok = self._peek()
                    if type_tok.type == TokenType.IDENT:
                        rescue_type = self._advance().value
                    else:
                        raise AyceSyntaxError(self.filename, type_tok.line, type_tok.col,
                            "Se esperaba un nombre de tipo de error después de ':'")
                self._expect(TokenType.RPAREN, "')'")
            elif self._check(TokenType.IDENT):
                rescue_name = self._advance().value
                if self._match(TokenType.COLON):
                    type_tok = self._peek()
                    if type_tok.type == TokenType.IDENT:
                        rescue_type = self._advance().value
                    else:
                        raise AyceSyntaxError(self.filename, type_tok.line, type_tok.col,
                            "Se esperaba un nombre de tipo de error después de ':'")
            rescue_body = self._parse_block_body()
            rescues.append((rescue_name, rescue_type, rescue_body))
        # finally (v0.6.4): opcional, después de todos los rescue
        finally_body = None
        if self._check(TokenType.FINALLY):
            self._advance()
            finally_body = self._parse_block_body()
        self._expect(TokenType.END, "'end'")
        return TryStmt(body=body, rescues=rescues, finally_body=finally_body,
                       line=t.line, col=t.col)

    def _parse_require(self) -> RequireStmt:
        """require M [as A]
           require X[, Y as Z] from M
           require \"ruta.ayce\" [as A]
        """
        t = self._expect(TokenType.REQUIRE, "'require'")

        # Caso 1: require "ruta/archivo.ayce" [as A]
        if self._check(TokenType.STRING):
            path_tok = self._advance()
            alias = ""
            if self._match(TokenType.AS):
                alias = self._expect(TokenType.IDENT, "nombre de alias").value
            return RequireStmt(
                mode="string",
                batch_spec=path_tok.value,
                alias=alias,
                is_string_path=True,
                line=t.line, col=t.col,
            )

        # Caso 2:       require M [as A]   (módulo entero)
        # Caso 3:       require X[, Y as Z] from M  (selectivo)
        # Diferenciación con lookahead:
        #   - Si tras el primer IDENT viene `from` o `,` → selectivo (primer item sin alias)
        #   - Si viene `as`, miramos qué hay después del alias:
        #       - NEWLINE/SEMICOLON/EOF → módulo entero con alias
        #       - `,` o `from` → selectivo (primer item con alias)
        #   - Si viene NEWLINE/SEMICOLON/EOF → módulo entero sin alias
        # En v0.5, los batches built-in tienen nombres que a veces coinciden con
        # keywords reservadas (string, list, dict, time, etc.). Los aceptamos aquí.
        type_token_to_name = {
            TokenType.STRING_T: "string",
            TokenType.INT_T:    "int",
            TokenType.FLOAT_T:  "float",
            TokenType.BOOL_T:   "bool",
            TokenType.BYTES_T:  "bytes",
            TokenType.LIST_T:   "list",
            TokenType.DICT_T:   "dict",
            TokenType.TUPLE_T:  "tuple",
            TokenType.SET_T:    "set",
        }
        if self._peek().type in type_token_to_name:
            first = type_token_to_name[self._peek().type]
            self._advance()
        else:
            first = self._expect(TokenType.IDENT, "nombre de módulo o de item").value

        if self._check(TokenType.AS):
            # Mirar dos tokens adelante: después del alias, ¿qué viene?
            next_after_alias = self._peek(2).type
            if next_after_alias in (TokenType.NEWLINE, TokenType.SEMICOLON, TokenType.EOF):
                # Módulo entero con alias
                self._advance()  # consume 'as'
                alias = self._expect(TokenType.IDENT, "nombre de alias").value
                return RequireStmt(
                    mode="batch",
                    batch_spec=first,
                    alias=alias,
                    line=t.line, col=t.col,
                )
            # Sino: selectivo con alias para el primer item
        elif self._check(TokenType.NEWLINE, TokenType.SEMICOLON, TokenType.EOF):
            # Módulo entero sin alias
            return RequireStmt(
                mode="batch",
                batch_spec=first,
                alias="",
                line=t.line, col=t.col,
            )

        # Selectivo: require X[, Y as Z] from M
        items = []
        first_alias = None
        if self._match(TokenType.AS):
            first_alias = self._expect(TokenType.IDENT, "nombre de alias").value
        items.append((first, first_alias))

        while self._match(TokenType.COMMA):
            item_name = self._expect(TokenType.IDENT, "nombre de item").value
            item_alias = None
            if self._match(TokenType.AS):
                item_alias = self._expect(TokenType.IDENT, "nombre de alias").value
            items.append((item_name, item_alias))

        self._expect(TokenType.FROM, "'from' (modo selectivo requiere 'from')")
        # El nombre del módulo también puede ser una keyword de tipo (string, list, etc.)
        if self._peek().type in type_token_to_name:
            module_name = type_token_to_name[self._peek().type]
            self._advance()
        else:
            module_name = self._expect(TokenType.IDENT, "nombre de módulo").value
        return RequireStmt(
            mode="selective",
            batch_spec=module_name,
            items=items,
            line=t.line, col=t.col,
        )

    def _parse_raise(self) -> RaiseStmt:
        """raise Error("mensaje", codigo)"""
        t = self._expect(TokenType.RAISE, "'raise'")
        error_expr = self._parse_expr()
        return RaiseStmt(error_expr=error_expr, line=t.line, col=t.col)

    def _parse_return(self) -> ReturnStmt:
        t = self._expect(TokenType.RETURN, "'return'")
        # return puede no tener expresión (para tasks sin retorno)
        if self._check(TokenType.NEWLINE, TokenType.SEMICOLON, TokenType.RBRACE, TokenType.END, TokenType.EOF):
            return ReturnStmt(value=None, line=t.line, col=t.col)
        expr = self._parse_expr()
        return ReturnStmt(value=expr, line=t.line, col=t.col)

    def _parse_say(self) -> SayStmt:
        t = self._expect(TokenType.SAY, "'say'")
        self._expect(TokenType.LPAREN, "'('")
        args = []
        if not self._check(TokenType.RPAREN):
            args.append(self._parse_expr())
            while self._match(TokenType.COMMA):
                args.append(self._parse_expr())
        self._expect(TokenType.RPAREN, "')'")
        return SayStmt(args=args, line=t.line, col=t.col)

    def _parse_global(self) -> GlobalStmt:
        t = self._expect(TokenType.GLOBAL, "'global'")
        names = [self._expect(TokenType.IDENT, "nombre de variable").value]
        while self._match(TokenType.COMMA):
            names.append(self._expect(TokenType.IDENT, "nombre de variable").value)
        return GlobalStmt(names=names, line=t.line, col=t.col)

    def _parse_expr_or_assign(self) -> Stmt:
        """Sentencia que empieza con expresión: asignación o llamada."""
        t = self._peek()

        # Asignación múltiple: a-b-c = 1,2,3
        save = self.pos
        if t.type == TokenType.IDENT:
            names = [self._advance().value]
            while self._check(TokenType.MINUS) and self._peek(1).type == TokenType.IDENT:
                self._advance()
                names.append(self._advance().value)
            if len(names) > 1 and self._check(TokenType.ASSIGN):
                self._advance()
                values = [self._parse_expr()]
                while self._match(TokenType.COMMA):
                    values.append(self._parse_expr())
                if len(values) != len(names):
                    raise AyceSyntaxError(
                        self.filename, t.line, t.col,
                        f"Asignación múltiple requiere {len(names)} valores, se encontraron {len(values)}"
                    )
                targets = [IdentExpr(name=name, line=t.line, col=t.col) for name in names]
                return MultiAssignStmt(targets=targets, values=values,
                                      line=t.line, col=t.col)
            self.pos = save

        expr = self._parse_expr()
        if self._check(TokenType.ASSIGN):
            self._advance()
            value = self._parse_expr()
            return AssignStmt(target=expr, value=value, line=t.line, col=t.col)
        # Asignación compuesta (v0.4): +=, -=, *=, /=, //=, %=
        # (v0.6.1: también las bit a bit &=, |=, ^=, <<=, >>=)
        compound_ops = {
            TokenType.PLUS_ASSIGN: "+=",
            TokenType.MINUS_ASSIGN: "-=",
            TokenType.STAR_ASSIGN: "*=",
            TokenType.SLASH_ASSIGN: "/=",
            TokenType.DSLASH_ASSIGN: "//=",
            TokenType.PERCENT_ASSIGN: "%=",
            TokenType.AMP_ASSIGN: "&=",
            TokenType.OR_ASSIGN: "|=",
            TokenType.XOR_ASSIGN: "^=",
            TokenType.LSHIFT_ASSIGN: "<<=",
            TokenType.RSHIFT_ASSIGN: ">>=",
        }
        if self._peek().type in compound_ops:
            op_tok = self._advance()
            value = self._parse_expr()
            return CompoundAssignStmt(target=expr, op=compound_ops[op_tok.type],
                                       value=value, line=t.line, col=t.col)
        return ExprStmt(expr=expr, line=t.line, col=t.col)

    # ──────────────────────────────────────────────────────────────────
    #  Tipos
    # ──────────────────────────────────────────────────────────────────
    def _parse_type(self) -> TypeNode:
        t = self._peek()

        # none como marcador de modo flexible: none[], none<>, none(), none{}
        if t.type == TokenType.NONE:
            self._advance()
            if self._check(TokenType.LBRACKET):
                self._advance(); self._expect(TokenType.RBRACKET, "']'")
                return ListType(flexible=True, line=t.line, col=t.col)
            if self._check(TokenType.LT):
                self._advance(); self._expect(TokenType.GT, "'>'")
                return DictType(flexible=True, line=t.line, col=t.col)
            if self._check(TokenType.LPAREN):
                self._advance(); self._expect(TokenType.RPAREN, "')'")
                return TupleType(flexible=True, line=t.line, col=t.col)
            if self._check(TokenType.LBRACE):
                self._advance(); self._expect(TokenType.RBRACE, "'}'")
                return SetType(flexible=True, line=t.line, col=t.col)
            # none solo
            return PrimitiveType(name="none", line=t.line, col=t.col)

        # Tipo primitivo
        prim_map = {
            TokenType.INT_T:    "int",
            TokenType.FLOAT_T:  "float",
            TokenType.STRING_T: "string",
            TokenType.BOOL_T:   "bool",
            TokenType.BYTES_T:  "bytes",
            TokenType.NONE:     "none",
        }
        if t.type in prim_map:
            self._advance()
            base = PrimitiveType(name=prim_map[t.type], line=t.line, col=t.col)
            # Tipos colección estrictos basados en primitivo
            if self._check(TokenType.LBRACKET):
                self._advance(); self._expect(TokenType.RBRACKET, "']'")
                # Permitir anidamiento: int[][]
                result = ListType(elem=base, line=t.line, col=t.col)
                while self._check(TokenType.LBRACKET):
                    self._advance(); self._expect(TokenType.RBRACKET, "']'")
                    result = ListType(elem=result, line=t.line, col=t.col)
                return result
            if self._check(TokenType.LBRACE):
                self._advance(); self._expect(TokenType.RBRACE, "'}'")
                return SetType(elem=base, line=t.line, col=t.col)
            if self._check(TokenType.LPAREN):
                # Tupla homogénea: T()
                self._advance(); self._expect(TokenType.RPAREN, "')'")
                return TupleType(elem_types=[base], line=t.line, col=t.col)
            # Primitivo solo
            return base

        # Tipos colección "flexibles" (sin tipo de elemento): list / dict / tuple / set
        # v0.6.1: ahora son keywords, no caen al IDENT.
        if t.type == TokenType.LIST_T:
            self._advance()
            return ListType(flexible=True, line=t.line, col=t.col)
        if t.type == TokenType.DICT_T:
            self._advance()
            return DictType(flexible=True, line=t.line, col=t.col)
        if t.type == TokenType.TUPLE_T:
            self._advance()
            return TupleType(flexible=True, line=t.line, col=t.col)
        if t.type == TokenType.SET_T:
            self._advance()
            return SetType(flexible=True, line=t.line, col=t.col)

        # Diccionario: <K, V> o <K, V1, V2>
        if t.type == TokenType.LT:
            self._advance()
            self._skip_newlines()
            key_type = self._parse_type()
            self._skip_newlines()
            value_types = []
            while self._match(TokenType.COMMA):
                self._skip_newlines()
                value_types.append(self._parse_type())
                self._skip_newlines()
            self._expect(TokenType.GT, "'>'")
            d = DictType(key_type=key_type, value_types=value_types, line=t.line, col=t.col)
            # v0.6.2: sufijo [] sobre tipos colección — <K, V>[] (lista de dicts)
            return self._parse_type_suffix(d, t)

        # Tupla heterogénea: (T1, T2, ...)
        if t.type == TokenType.LPAREN:
            self._advance()
            elem_types = [self._parse_type()]
            while self._match(TokenType.COMMA):
                elem_types.append(self._parse_type())
            self._expect(TokenType.RPAREN, "')'")
            tt = TupleType(elem_types=elem_types, line=t.line, col=t.col)
            return self._parse_type_suffix(tt, t)

        # 'task' como tipo (para callbacks)
        if t.type == TokenType.TASK:
            self._advance()
            return TaskType(line=t.line, col=t.col)

        # Tipo definido por el usuario (Template, Shape, Variant) — referencia por nombre
        if t.type == TokenType.IDENT:
            self._advance()
            # v0.5: tipo cualificado de módulo: Module::Type
            if self._check(TokenType.DOUBLE_COLON):
                self._advance()
                type_name = self._expect(TokenType.IDENT, "nombre de tipo").value
                return QualifiedTypeName(module_name=t.value, type_name=type_name,
                                          line=t.line, col=t.col)
            # Tipos colección basados en tipo de usuario: T[], T{}, T()
            if self._check(TokenType.LBRACKET):
                self._advance(); self._expect(TokenType.RBRACKET, "']'")
                result = ListType(elem=UserTypeName(name=t.value, line=t.line, col=t.col),
                                  line=t.line, col=t.col)
                while self._check(TokenType.LBRACKET):
                    self._advance(); self._expect(TokenType.RBRACKET, "']'")
                    result = ListType(elem=result, line=t.line, col=t.col)
                return result
            return UserTypeName(name=t.value, line=t.line, col=t.col)

        raise AyceSyntaxError(
            self.filename, t.line, t.col,
            f"Se esperaba un tipo pero se encontró {t.value!r}"
        )

    def _parse_type_suffix(self, base, t):
        """v0.6.2: sufijos [] sobre tipos colección ya formados
        (<K, V>[], (T1, T2)[], ...) para declarar listas de dicts, etc."""
        result = base
        while self._check(TokenType.LBRACKET):
            self._advance()
            self._expect(TokenType.RBRACKET, "']'")
            result = ListType(elem=result, line=t.line, col=t.col)
        return result

    # ──────────────────────────────────────────────────────────────────
    #  Expresiones (con precedencia)
    # ──────────────────────────────────────────────────────────────────
    def _parse_expr(self, allow_is_expr=True) -> Expr:
        # Ternario v0.4: cond ? a : b  (al nivel más bajo, después de ||)
        # allow_is_expr=False lo usa guard para que `expr is <patrón>` llegue
        # vivo hasta _parse_guard (v0.6.4); en el resto del lenguaje 'is' es
        # el chequeo de variantes y se consume aquí.
        left = self._parse_or(allow_is_expr)
        if self._check(TokenType.QUESTION):
            t = self._advance()
            if_true = self._parse_expr()
            self._expect(TokenType.COLON, "':'")
            if_false = self._parse_expr()
            return TernaryExpr(cond=left, if_true=if_true, if_false=if_false,
                               line=t.line, col=t.col)
        return left

    def _parse_or(self, allow_is_expr=True) -> Expr:
        left = self._parse_and(allow_is_expr)
        while self._check(TokenType.OR):
            t = self._advance()
            right = self._parse_and(allow_is_expr)
            left = BinaryExpr(op="||", left=left, right=right, line=t.line, col=t.col)
        return left

    def _parse_and(self, allow_is_expr=True) -> Expr:
        left = self._parse_comparison(allow_is_expr)
        while self._check(TokenType.AND):
            t = self._advance()
            right = self._parse_comparison(allow_is_expr)
            left = BinaryExpr(op="&&", left=left, right=right, line=t.line, col=t.col)
        return left

    def _parse_comparison(self, allow_is_expr=True) -> Expr:
        left = self._parse_bit_or()
        # Operador `is` para variantes: expr is Tipo::Caso (v0.5: usa ::)
        # (allow_is_expr=False se conservó de la forma patrón del guard de
        # v0.6.4; hoy ningún constructor lo desactiva.)
        if self._check(TokenType.IS) and allow_is_expr:
            t = self._advance()
            type_name = self._expect(TokenType.IDENT, "nombre de tipo Variant").value
            self._expect(TokenType.DOUBLE_COLON, "'::'")
            case_name = self._expect(TokenType.IDENT, "nombre de caso").value
            return IsExpr(left=left, type_name=type_name, case_name=case_name,
                          line=t.line, col=t.col)
        # Pertenencia (v0.6.4): x in coleccion / x not in coleccion — mismo
        # nivel que las comparaciones. Sirve para lista, tupla, set, dict
        # (pregunta por CLAVES) y string (subcadena). Es terminal en este
        # nivel: `x in l && y` sigue por el &&, pero `x in l < 5` no existe.
        if self._check(TokenType.IN) or (
                self._check(TokenType.NOT) and self._peek(1).type == TokenType.IN):
            t = self._advance()  # 'in' o 'not'
            if t.type == TokenType.NOT:
                self._advance()  # consume el 'in' de 'not in'
            right = self._parse_bit_or()
            return MembershipExpr(value=left, container=right,
                                  negated=(t.type == TokenType.NOT),
                                  line=t.line, col=t.col)
        # Comparación simple o encadenada (v0.6.4): 0 <= x < 10 es
        # (0 <= x) && (x < 10) y cada operando intermedio se evalúa UNA vez.
        if self._check(TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
            t = self._advance()
            op = {TokenType.EQ:"==", TokenType.NEQ:"!=", TokenType.LT:"<",
                  TokenType.GT:">", TokenType.LTE:"<=", TokenType.GTE:">="}[t.type]
            right = self._parse_bit_or()
            if not self._check(TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
                return BinaryExpr(op=op, left=left, right=right, line=t.line, col=t.col)
            # Encadenada: recolectar los pares (op, operando) restantes
            ops = [op]
            rights = [right]
            while self._check(TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
                t2 = self._advance()
                ops.append({TokenType.EQ:"==", TokenType.NEQ:"!=", TokenType.LT:"<",
                            TokenType.GT:">", TokenType.LTE:"<=", TokenType.GTE:">="}[t2.type])
                rights.append(self._parse_bit_or())
            return ChainCompare(first=left, ops=ops, rights=rights,
                                line=t.line, col=t.col)
        return left

    def _parse_affirm(self) -> AffirmStmt:
        """Affirm <expr> [, "mensaje"] (v0.6.4) — la aserción del cliente.
        La condición debe ser bool; si da False, error en runtime con el
        mensaje (o con la expresión fallida si no hay mensaje)."""
        t = self._expect(TokenType.AFFIRM, "'Affirm'")
        cond = self._parse_expr()
        msg = None
        if self._match(TokenType.COMMA):
            msg = self._parse_expr()
        return AffirmStmt(condition=cond, message=msg, line=t.line, col=t.col)

    # Operadores bit a bit (v0.6.1), con la precedencia de Python:
    # comparación es más floja que | ^ & << >>, y entre ellos:
    # | (flojo) < ^ < & < << >> (fuerte).
    # Para '|' se mira el token SIGUIENTE: si puede iniciar un operando es
    # OR bit a bit; si no (return, nueva línea, ')', ...), es el separador
    # de overloads/cuerpos de task y no se consume como operador.
    _OPERAND_START = frozenset((
        TokenType.INT, TokenType.FLOAT, TokenType.STRING, TokenType.FSTRING,
        TokenType.BYTES, TokenType.TRUE, TokenType.FALSE, TokenType.NONE,
        TokenType.IDENT, TokenType.MINUS, TokenType.NOT, TokenType.BIT_NOT,
        TokenType.LPAREN, TokenType.LBRACKET, TokenType.LBRACE,
        TokenType.INT_T, TokenType.FLOAT_T, TokenType.STRING_T,
        TokenType.BOOL_T, TokenType.BYTES_T,
        TokenType.LIST_T, TokenType.DICT_T, TokenType.TUPLE_T,
        TokenType.SET_T, TokenType.RANGE, TokenType.NEW, TokenType.SELF,
        TokenType.BOX,   # v0.6.4: box es una expresión (variable mágica del match)
    ))

    def _operand_starts_here(self, tt) -> bool:
        return tt in self._OPERAND_START

    def _parse_bit_or(self) -> Expr:
        left = self._parse_bit_xor()
        while self._check(TokenType.PIPE) and self._operand_starts_here(self._peek(1).type):
            t = self._advance()
            right = self._parse_bit_xor()
            left = BinaryExpr(op="|", left=left, right=right, line=t.line, col=t.col)
        return left

    def _parse_bit_xor(self) -> Expr:
        left = self._parse_bit_and()
        while self._check(TokenType.BIT_XOR):
            t = self._advance()
            right = self._parse_bit_and()
            left = BinaryExpr(op="^", left=left, right=right, line=t.line, col=t.col)
        return left

    def _parse_bit_and(self) -> Expr:
        left = self._parse_shift()
        while self._check(TokenType.AMP):
            t = self._advance()
            right = self._parse_shift()
            left = BinaryExpr(op="&", left=left, right=right, line=t.line, col=t.col)
        return left

    def _parse_shift(self) -> Expr:
        left = self._parse_additive()
        while self._check(TokenType.LSHIFT, TokenType.RSHIFT):
            t = self._advance()
            op = "<<" if t.type == TokenType.LSHIFT else ">>"
            right = self._parse_additive()
            left = BinaryExpr(op=op, left=left, right=right, line=t.line, col=t.col)
        return left

    def _parse_additive(self) -> Expr:
        left = self._parse_multiplicative()
        while self._check(TokenType.PLUS, TokenType.MINUS):
            # El conector de State es 'then', así que '-' vuelve a ser
            # resta normal dentro del sujeto (State (a - b) sin paréntesis ya
            # no se come el conector). Si viene '-' seguido de '<' es la
            # sintaxis vieja 'State x - <' de la entrega original de la 0.6.4:
            # error con migración, sin citar números de versión confusos.
            if self._stop_state_subject and self._peek().type == TokenType.MINUS \
                    and self._peek(1).type == TokenType.LT:
                nt = self._peek()
                raise AyceSyntaxError(self.filename, nt.line, nt.col,
                    "El '-' antes de los brazos de State ya no se usa: "
                    "escribe 'State x then < ... >'")
            t = self._advance()
            op = "+" if t.type == TokenType.PLUS else "-"
            right = self._parse_multiplicative()
            left = BinaryExpr(op=op, left=left, right=right, line=t.line, col=t.col)
        return left

    def _parse_multiplicative(self) -> Expr:
        left = self._parse_power()
        while self._check(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT, TokenType.DOUBLE_SLASH):
            t = self._advance()
            op = {TokenType.STAR:"*", TokenType.SLASH:"/", TokenType.PERCENT:"%",
                  TokenType.DOUBLE_SLASH:"//"}[t.type]
            right = self._parse_power()
            left = BinaryExpr(op=op, left=left, right=right, line=t.line, col=t.col)
        return left

    def _parse_power(self) -> Expr:
        left = self._parse_unary()
        if self._check(TokenType.POW):
            t = self._advance()
            # ** asocia a derecha
            right = self._parse_power()
            left = BinaryExpr(op="**", left=left, right=right, line=t.line, col=t.col)
        return left

    def _parse_unary(self) -> Expr:
        if self._check(TokenType.NOT, TokenType.MINUS, TokenType.BIT_NOT):
            t = self._advance()
            if t.type == TokenType.NOT:
                op = "!"
            elif t.type == TokenType.MINUS:
                op = "-"
            else:
                op = "~"
            operand = self._parse_unary()
            return UnaryExpr(op=op, operand=operand, line=t.line, col=t.col)
        return self._parse_postfix()

    def _parse_postfix(self) -> Expr:
        """Aplica accesos y llamadas a una primaria."""
        expr = self._parse_primary()

        while True:
            t = self._peek()
            if t.type == TokenType.LBRACKET:
                self._advance()
                # Corte (v0.6.4): lista[ini:fin] — mitad-abierta [ini, fin),
                # ambos extremos opcionales ([:3], [1:], [:]). Sin ':' sigue
                # siendo el acceso por índice, que en v0.6.4 también acepta
                # negativos (lista[-1] = último).
                start = None
                if not self._check(TokenType.COLON) and not self._check(TokenType.RBRACKET):
                    start = self._parse_expr()
                if self._match(TokenType.COLON):
                    end = None
                    if not self._check(TokenType.RBRACKET):
                        end = self._parse_expr()
                    self._expect(TokenType.RBRACKET, "']'")
                    expr = SliceExpr(target=expr, start=start, end=end,
                                     line=t.line, col=t.col)
                else:
                    if start is None:
                        nt = self._peek()
                        raise AyceSyntaxError(self.filename, nt.line, nt.col,
                            "Se esperaba una expresión de índice dentro de [ ]")
                    self._expect(TokenType.RBRACKET, "']'")
                    expr = IndexExpr(target=expr, index=start, line=t.line, col=t.col)
            elif t.type == TokenType.LT:
                # Acceso a diccionario x<clave>
                # Heurística (extendida): tras '<' la clave puede ser
                #   - un literal simple (string/int/float/bool/none),
                #   - un identificador (o nombre de tipo stdlib como list/math)
                #     seguido de una cadena opcional de ::miembro y llamadas,
                #   - una expresión entre paréntesis (expr),
                # siempre seguidos del '>' de cierre. En otro caso '<' es
                # comparación. La comparación encadenada a < b > c ya está
                # prohibida desde v0.2, así que reconocer <clave> no es ambiguo:
                # evita el falso "comparaciones encadenadas" para x<v::cliente>.
                if isinstance(expr, (IdentExpr, DictAccessExpr, IndexExpr, MethodCallExpr, CallExpr, ModuleAccessExpr)):
                    save = self.pos
                    self._advance()  # '<'
                    key = self._try_parse_dict_key()
                    if key is not None:
                        self._expect(TokenType.GT, "'>'")
                        expr = DictAccessExpr(target=expr, key=key, line=t.line, col=t.col)
                        continue
                    # No era dict access: restaurar y salir (es comparación)
                    self.pos = save
                    break
                else:
                    break
            elif t.type == TokenType.DOUBLE_COLON:
                # Acceso a miembro con :: (v0.5: reemplaza a .)
                # Aplica a: módulos, instancias (método/campo), shapes, variants, strings, listas...
                self._advance()
                # v0.5: el nombre del miembro también puede ser un token de tipo
                # (para que funcionen cosas como math::int, list::range, etc.)
                member_type_tokens = {
                    TokenType.STRING_T: "string",
                    TokenType.INT_T:    "int",
                    TokenType.FLOAT_T:  "float",
                    TokenType.BOOL_T:   "bool",
                    TokenType.BYTES_T:  "bytes",
                    TokenType.RANGE:    "range",
                    TokenType.LIST_T:   "list",
                    TokenType.DICT_T:   "dict",
                    TokenType.TUPLE_T:  "tuple",
                    TokenType.SET_T:    "set",
                    # v0.6.4: match/guard volvieron a ser identificadores
                    # normales, así que re::match(...) se parsea solo.
                }
                if self._peek().type in member_type_tokens:
                    name_tok = member_type_tokens[self._peek().type]
                    self._advance()
                else:
                    name_tok = self._expect(TokenType.IDENT, "nombre de miembro").value
                # Si viene '(' es llamada a método; si no, es acceso a campo/caso/miembro
                if self._check(TokenType.LPAREN):
                    self._advance()
                    args = []
                    if not self._check(TokenType.RPAREN):
                        args.append(self._parse_expr())
                        while self._match(TokenType.COMMA):
                            args.append(self._parse_expr())
                    self._expect(TokenType.RPAREN, "')'")
                    expr = MethodCallExpr(target=expr, method=name_tok, args=args, line=t.line, col=t.col)
                else:
                    expr = ModuleAccessExpr(target=expr, name=name_tok, line=t.line, col=t.col)
            elif t.type == TokenType.LPAREN:
                # Llamada a tarea
                self._advance()
                args = []
                kwargs = []          # v0.6.4: argumentos nombrados [(nombre, expr, línea, col)]
                seen_named = False
                if not self._check(TokenType.RPAREN):
                    while True:
                        # Argumento nombrado (v0.6.4): f(nombre = valor)
                        if (self._check(TokenType.IDENT)
                                and self._peek(1).type == TokenType.ASSIGN):
                            name_tok = self._advance()
                            self._advance()  # '='
                            kwargs.append((name_tok.value, self._parse_expr(),
                                           name_tok.line, name_tok.col))
                            seen_named = True
                        else:
                            if seen_named:
                                nt = self._peek()
                                raise AyceSyntaxError(self.filename, nt.line, nt.col,
                                    "después de un argumento nombrado (nombre = valor) "
                                    "todos los argumentos deben ser nombrados")
                            args.append(self._parse_expr())
                        if not self._match(TokenType.COMMA):
                            break
                self._expect(TokenType.RPAREN, "')'")
                expr = CallExpr(target=expr, args=args, kwargs=kwargs, line=t.line, col=t.col)
            else:
                break
        return expr

    def _try_parse_dict_key(self):
        """Parsea la clave de un acceso a dict x<clave> (el '<' ya fue consumido).

        Devuelve la expresión de la clave si la forma es reconocible, o None si
        no (el llamador debe restaurar la posición y tratar el '<' como el
        inicio de una comparación). Este método nunca consume el '>' de cierre:
        de eso se encarga el llamador con _expect.
        Formas aceptadas:
          - literal simple: x<"a">, x<5>, x<True>, x<none>
          - identificador con cadena opcional de ::miembro / ::metodo(args),
            incluyendo el primer tramo con nombre de tipo stdlib (x<list::len(l)>)
          - expresión entre paréntesis: x<(expr)>
        """
        t = self._peek()
        # Literal simple (sólo si el '>' de cierre está pegado; si no, es
        # una comparación como `if x < 5 then`)
        if t.type in (TokenType.STRING, TokenType.INT, TokenType.FLOAT,
                      TokenType.TRUE, TokenType.FALSE, TokenType.NONE):
            if self._peek(1).type != TokenType.GT:
                return None
            return self._parse_primary()
        member_type_tokens = {
            TokenType.STRING_T: "string",
            TokenType.INT_T:    "int",
            TokenType.FLOAT_T:  "float",
            TokenType.BOOL_T:   "bool",
            TokenType.BYTES_T:  "bytes",
            TokenType.RANGE:    "range",
            TokenType.LIST_T:   "list",
            TokenType.DICT_T:   "dict",
            TokenType.TUPLE_T:  "tuple",
            TokenType.SET_T:    "set",
        }
        if t.type == TokenType.IDENT or t.type in member_type_tokens:
            # _parse_primary ya mapea nombres de tipo stdlib (string, list, ...)
            # a identificadores, así que el primer tramo sale de ahí.
            key = self._parse_primary()
            # Llamada directa sobre el primer tramo: x<string(n)>, x<int(v)>
            if self._check(TokenType.LPAREN):
                self._advance()
                args = []
                if not self._check(TokenType.RPAREN):
                    args.append(self._parse_expr())
                    while self._match(TokenType.COMMA):
                        args.append(self._parse_expr())
                self._expect(TokenType.RPAREN, "')'")
                key = CallExpr(target=key, args=args, line=t.line, col=t.col)
            # Cadena opcional de ::miembro / ::metodo(args)
            while self._check(TokenType.DOUBLE_COLON):
                self._advance()
                if self._peek().type in member_type_tokens:
                    mname = member_type_tokens[self._peek().type]
                    self._advance()
                else:
                    mname = self._expect(TokenType.IDENT, "nombre de miembro").value
                if self._check(TokenType.LPAREN):
                    self._advance()
                    args = []
                    if not self._check(TokenType.RPAREN):
                        args.append(self._parse_expr())
                        while self._match(TokenType.COMMA):
                            args.append(self._parse_expr())
                    self._expect(TokenType.RPAREN, "')'")
                    key = MethodCallExpr(target=key, method=mname, args=args,
                                         line=t.line, col=t.col)
                else:
                    key = ModuleAccessExpr(target=key, name=mname, line=t.line, col=t.col)
            if self._check(TokenType.GT):
                return key
            return None
        # Expresión entre paréntesis: x<(expr)>
        if t.type == TokenType.LPAREN:
            save = self.pos
            self._advance()
            try:
                inner = self._parse_expr()
            except AyceSyntaxError:
                self.pos = save
                return None
            if self._check(TokenType.RPAREN):
                self._advance()
                if self._check(TokenType.GT):
                    return inner
            self.pos = save
            return None
        return None

    def _parse_primary(self) -> Expr:
        t = self._peek()

        # Literales
        if t.type == TokenType.INT:
            self._advance()
            return IntLit(value=t.value, line=t.line, col=t.col)
        if t.type == TokenType.FLOAT:
            self._advance()
            return FloatLit(value=t.value, line=t.line, col=t.col)
        if t.type == TokenType.STRING:
            self._advance()
            return StringLit(value=t.value, line=t.line, col=t.col)
        if t.type == TokenType.FSTRING:
            self._advance()
            return self._build_fstring(t)
        if t.type == TokenType.BYTES:
            self._advance()
            return BytesLit(value=t.value, line=t.line, col=t.col)
        if t.type == TokenType.TRUE:
            self._advance()
            return BoolLit(value=True, line=t.line, col=t.col)
        if t.type == TokenType.FALSE:
            self._advance()
            return BoolLit(value=False, line=t.line, col=t.col)
        if t.type == TokenType.NONE:
            self._advance()
            return NoneLit(line=t.line, col=t.col)

        # Conversión de tipos (v0.4): int(x), float(x), string(x), bool(x), bytes(x)
        # Se distingue de una declaración de tipo porque va seguida de '('
        if t.type in (TokenType.INT_T, TokenType.FLOAT_T, TokenType.STRING_T,
                       TokenType.BOOL_T, TokenType.BYTES_T):
            # Miramos si viene '(' — si sí, es conversión
            if self._peek(1).type == TokenType.LPAREN:
                type_name = {TokenType.INT_T: "int", TokenType.FLOAT_T: "float",
                             TokenType.STRING_T: "string", TokenType.BOOL_T: "bool",
                             TokenType.BYTES_T: "bytes"}[t.type]
                self._advance()  # consume el tipo
                self._advance()  # consume '('
                arg = self._parse_expr()
                self._expect(TokenType.RPAREN, "')'")
                return TypeConvertExpr(target_type=type_name, arg=arg,
                                        line=t.line, col=t.col)

        # range([inicio,] fin [, paso]) — v0.6.4: 1, 2 o 3 argumentos
        if t.type == TokenType.RANGE:
            self._advance()
            self._expect(TokenType.LPAREN, "'('")
            first = self._parse_expr()
            if self._match(TokenType.COMMA):
                # range(a, b) o range(a, b, paso)
                start = first
                end = self._parse_expr()
                step = None
                if self._match(TokenType.COMMA):
                    step = self._parse_expr()
                self._expect(TokenType.RPAREN, "')'")
                return RangeExpr(start=start, end=end, step=step,
                                 line=t.line, col=t.col)
            # range(n): 0..n-1 (paso 1)
            self._expect(TokenType.RPAREN, "')'")
            return RangeExpr(start=None, end=first, step=None,
                             line=t.line, col=t.col)

        # self (dentro de métodos de Template)
        if t.type == TokenType.SELF:
            self._advance()
            return SelfExpr(line=t.line, col=t.col)

        # box — variable mágica con el valor evaluado en cada brazo de match
        # (v0.6.4). Fuera de un brazo match, el intérprete la reporta como
        # variable no declarada, igual que self fuera de un método.
        if t.type == TokenType.BOX:
            self._advance()
            return IdentExpr(name="box", line=t.line, col=t.col)

        # new Tipo { campo: valor, ... } — construcción de Shape
        if t.type == TokenType.NEW:
            self._advance()
            type_name = self._expect(TokenType.IDENT, "nombre de tipo").value
            self._skip_newlines()
            self._expect(TokenType.LBRACE, "'{'")
            self._skip_newlines()
            fields = []
            if not self._check(TokenType.RBRACE):
                fname = self._expect(TokenType.IDENT, "nombre de campo").value
                self._expect(TokenType.COLON, "':'")
                self._skip_newlines()
                fval = self._parse_additive()
                fields.append((fname, fval))
                while self._match(TokenType.COMMA):
                    self._skip_newlines()
                    if self._check(TokenType.RBRACE):
                        break
                    fname = self._expect(TokenType.IDENT, "nombre de campo").value
                    self._expect(TokenType.COLON, "':'")
                    self._skip_newlines()
                    fval = self._parse_additive()
                    fields.append((fname, fval))
            self._skip_newlines()
            self._expect(TokenType.RBRACE, "'}'")
            return NewExpr(type_name=type_name, fields=fields, line=t.line, col=t.col)

        # inlet(prompt, tipo) — lee string por defecto, o tipo específico
        if t.type == TokenType.INLET:
            self._advance()
            self._expect(TokenType.LPAREN, "'('")
            prompt = None
            target_type = ""
            if not self._check(TokenType.RPAREN):
                prompt = self._parse_expr()
                if self._match(TokenType.COMMA):
                    # El segundo argumento es el tipo: int, float, bool, string,
                    # bytes o none para detección dinámica.
                    type_tok = self._peek()
                    type_map = {TokenType.INT_T: "int", TokenType.FLOAT_T: "float",
                                TokenType.BOOL_T: "bool", TokenType.STRING_T: "string",
                                TokenType.BYTES_T: "bytes", TokenType.NONE: "none"}
                    if type_tok.type in type_map:
                        self._advance()
                        target_type = type_map[type_tok.type]
                    else:
                        raise AyceSyntaxError(self.filename, type_tok.line, type_tok.col,
                            "Se esperaba un tipo (int, float, bool, string, bytes o none) como segundo argumento de inlet")
            self._expect(TokenType.RPAREN, "')'")
            return InletExpr(prompt=prompt, target_type=target_type, line=t.line, col=t.col)

        # Identificador — incluido keywords de tipo usados como nombre de batch
        # (v0.6.1: list/dict/tuple/set/string/int/float/bool/bytes como primaria,
        #  para permitir list::range(10), string::upper("x"), etc.)
        type_as_ident = {
            TokenType.IDENT:    None,   # identificador normal
            TokenType.INT_T:    "int",
            TokenType.FLOAT_T:  "float",
            TokenType.STRING_T: "string",
            TokenType.BOOL_T:   "bool",
            TokenType.BYTES_T:  "bytes",
            TokenType.LIST_T:   "list",
            TokenType.DICT_T:   "dict",
            TokenType.TUPLE_T:  "tuple",
            TokenType.SET_T:    "set",
        }
        if t.type in type_as_ident:
            self._advance()
            name = type_as_ident[t.type] if t.type != TokenType.IDENT else t.value
            return IdentExpr(name=name, line=t.line, col=t.col)

        # ( expr ) — agrupación, o tupla literal
        if t.type == TokenType.LPAREN:
            self._advance()
            first = self._parse_expr()
            if self._match(TokenType.COMMA):
                elements = [first]
                while not self._check(TokenType.RPAREN):
                    elements.append(self._parse_expr())
                    if not self._match(TokenType.COMMA):
                        break
                self._expect(TokenType.RPAREN, "')'")
                return TupleLit(elements=elements, line=t.line, col=t.col)
            self._expect(TokenType.RPAREN, "')'")
            return first

        # [ ... ] — lista literal
        if t.type == TokenType.LBRACKET:
            self._advance()
            self._skip_newlines()
            elements = []
            if not self._check(TokenType.RBRACKET):
                elements.append(self._parse_expr())
                self._skip_newlines()
                while self._match(TokenType.COMMA):
                    self._skip_newlines()
                    if self._check(TokenType.RBRACKET):
                        break
                    elements.append(self._parse_expr())
                    self._skip_newlines()
            self._expect(TokenType.RBRACKET, "']'")
            return ListLit(elements=elements, line=t.line, col=t.col)

        # { ... } — set literal
        if t.type == TokenType.LBRACE:
            self._advance()
            self._skip_newlines()
            elements = []
            if not self._check(TokenType.RBRACE):
                elements.append(self._parse_expr())
                self._skip_newlines()
                while self._match(TokenType.COMMA):
                    self._skip_newlines()
                    if self._check(TokenType.RBRACE):
                        break
                    elements.append(self._parse_expr())
                    self._skip_newlines()
            self._expect(TokenType.RBRACE, "'}'")
            return SetLit(elements=elements, line=t.line, col=t.col)

        # < ... > — diccionario literal
        if t.type == TokenType.LT:
            self._advance()
            self._skip_newlines()
            pairs = []
            if not self._check(TokenType.GT):
                k = self._parse_additive()  # sin comparación, para no comer '>'
                self._skip_newlines()
                self._expect(TokenType.COLON, "':'")
                self._skip_newlines()
                v = self._parse_additive()  # sin comparación
                self._skip_newlines()
                pairs.append((k, v))
                while self._match(TokenType.COMMA):
                    self._skip_newlines()
                    if self._check(TokenType.GT):
                        break
                    k = self._parse_additive()
                    self._skip_newlines()
                    self._expect(TokenType.COLON, "':'")
                    self._skip_newlines()
                    v = self._parse_additive()
                    self._skip_newlines()
                    pairs.append((k, v))
            self._expect(TokenType.GT, "'>'")
            return DictLit(pairs=pairs, line=t.line, col=t.col)

        raise AyceSyntaxError(
            self.filename, t.line, t.col,
            f"Se esperaba una expresión pero se encontró {t.value!r}"
        )

    def _build_fstring(self, tok: Token) -> FStringLit:
        """Construye FStringLit a partir de las partes del lexer.
        Cada parte expr ahora es (expr_str, fmt_str)."""
        parts = []
        for item in tok.value:
            if item[0] == "text":
                parts.append(("text", item[1]))
            elif item[0] == "expr":
                expr_str = item[1]
                fmt_str = item[2] if len(item) > 2 else ""
                from .lexer import Lexer
                sub_lexer = Lexer(expr_str, filename=self.filename)
                sub_tokens = sub_lexer.tokenize()
                sub_parser = Parser(sub_tokens, filename=self.filename)
                expr = sub_parser._parse_expr()
                parts.append(("expr", expr, fmt_str))
        return FStringLit(parts=parts, line=tok.line, col=tok.col)