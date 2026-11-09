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
        if t.type == TokenType.TRY:
            return self._parse_try()
        if t.type == TokenType.RAISE:
            return self._parse_raise()
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
        # Si no es keyword, es una asignación o llamada (ExprStmt)
        return self._parse_expr_or_assign()

    def _parse_var_decl(self) -> VarDecl:
        t = self._expect(TokenType.VAR, "'var'")
        name = self._expect(TokenType.IDENT, "nombre de variable").value
        self._expect(TokenType.COLON, "':'")
        type_node = self._parse_type()
        init = None
        if self._match(TokenType.ASSIGN):
            init = self._parse_expr()
        return VarDecl(name=name, type_node=type_node, init=init, line=t.line, col=t.col)

    def _parse_const_decl(self) -> ConstDecl:
        t = self._expect(TokenType.CONST, "'const'")
        name = self._expect(TokenType.IDENT, "nombre de constante").value
        self._expect(TokenType.COLON, "':'")
        type_node = self._parse_type()
        self._expect(TokenType.ASSIGN, "'=' (const requiere valor inicial)")
        init = self._parse_expr()
        return ConstDecl(name=name, type_node=type_node, init=init, line=t.line, col=t.col)

    def _parse_task_decl(self) -> TaskDecl:
        t = self._expect(TokenType.TASK, "'task'")
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
            self._expect(TokenType.SEMICOLON, "';'")
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
        # Revisar varargs (...)
        # El lexer no produce un token '...' — son tres DOT seguidos
        if self._check(TokenType.DOT) and self._peek(1).type == TokenType.DOT and self._peek(2).type == TokenType.DOT:
            self._advance(); self._advance(); self._advance()
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
        """Lee sentencias hasta encontrar '}', 'end', 'else', 'rescue' o EOF."""
        self._skip_separators()
        stmts = []
        while not self._check(TokenType.RBRACE, TokenType.END, TokenType.ELSE, TokenType.RESCUE, TokenType.EOF):
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
        while self._check(TokenType.ELSE):
            self._advance()
            if self._match(TokenType.IF):
                cond2 = self._parse_expr()
                self._expect(TokenType.THEN, "'then'")
                body2 = self._parse_block_body()
                branches.append((cond2, body2))
            else:
                # rama else final
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
        var_name = self._expect(TokenType.IDENT, "nombre de variable de iteración").value
        self._expect(TokenType.IN, "'in'")
        iterable = self._parse_expr()
        self._expect(TokenType.DO, "'do'")
        body = self._parse_block_body()
        self._expect(TokenType.END, "'end'")
        return ForStmt(var_name=var_name, iterable=iterable, body=body, line=t.line, col=t.col)

    def _parse_try(self) -> TryStmt:
        """try ... rescue(nombre: Tipo) ... end"""
        t = self._expect(TokenType.TRY, "'try'")
        body = self._parse_block_body()
        rescue_name = ""
        rescue_type = ""
        rescue_body = []
        if self._check(TokenType.RESCUE):
            self._advance()
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
        self._expect(TokenType.END, "'end'")
        return TryStmt(body=body, rescue_name=rescue_name, rescue_type=rescue_type,
                       rescue_body=rescue_body, line=t.line, col=t.col)

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
        expr = self._parse_expr()
        if self._check(TokenType.ASSIGN):
            self._advance()
            value = self._parse_expr()
            return AssignStmt(target=expr, value=value, line=t.line, col=t.col)
        # Asignación compuesta (v0.4): +=, -=, *=, /=, //=, %=
        compound_ops = {
            TokenType.PLUS_ASSIGN: "+=",
            TokenType.MINUS_ASSIGN: "-=",
            TokenType.STAR_ASSIGN: "*=",
            TokenType.SLASH_ASSIGN: "/=",
            TokenType.DSLASH_ASSIGN: "//=",
            TokenType.PERCENT_ASSIGN: "%=",
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
            return DictType(key_type=key_type, value_types=value_types, line=t.line, col=t.col)

        # Tupla heterogénea: (T1, T2, ...)
        if t.type == TokenType.LPAREN:
            self._advance()
            elem_types = [self._parse_type()]
            while self._match(TokenType.COMMA):
                elem_types.append(self._parse_type())
            self._expect(TokenType.RPAREN, "')'")
            return TupleType(elem_types=elem_types, line=t.line, col=t.col)

        # 'task' como tipo (para callbacks)
        if t.type == TokenType.TASK:
            self._advance()
            return TaskType(line=t.line, col=t.col)

        # Tipo definido por el usuario (Template, Shape, Variant) — referencia por nombre
        if t.type == TokenType.IDENT:
            self._advance()
            return UserTypeName(name=t.value, line=t.line, col=t.col)

        raise AyceSyntaxError(
            self.filename, t.line, t.col,
            f"Se esperaba un tipo pero se encontró {t.value!r}"
        )

    # ──────────────────────────────────────────────────────────────────
    #  Expresiones (con precedencia)
    # ──────────────────────────────────────────────────────────────────
    def _parse_expr(self) -> Expr:
        # Ternario v0.4: cond ? a : b  (al nivel más bajo, después de ||)
        left = self._parse_or()
        if self._check(TokenType.QUESTION):
            t = self._advance()
            if_true = self._parse_expr()
            self._expect(TokenType.COLON, "':'")
            if_false = self._parse_expr()
            return TernaryExpr(cond=left, if_true=if_true, if_false=if_false,
                               line=t.line, col=t.col)
        return left

    def _parse_or(self) -> Expr:
        left = self._parse_and()
        while self._check(TokenType.OR):
            t = self._advance()
            right = self._parse_and()
            left = BinaryExpr(op="||", left=left, right=right, line=t.line, col=t.col)
        return left

    def _parse_and(self) -> Expr:
        left = self._parse_comparison()
        while self._check(TokenType.AND):
            t = self._advance()
            right = self._parse_comparison()
            left = BinaryExpr(op="&&", left=left, right=right, line=t.line, col=t.col)
        return left

    def _parse_comparison(self) -> Expr:
        left = self._parse_additive()
        # Operador `is` para variantes: expr is Tipo.Caso
        if self._check(TokenType.IS):
            t = self._advance()
            type_name = self._expect(TokenType.IDENT, "nombre de tipo Variant").value
            self._expect(TokenType.DOT, "'.'")
            case_name = self._expect(TokenType.IDENT, "nombre de caso").value
            return IsExpr(left=left, type_name=type_name, case_name=case_name,
                          line=t.line, col=t.col)
        # Una sola comparación (no encadenada: a < b < c es error en v0.2)
        if self._check(TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
            t = self._advance()
            op = {TokenType.EQ:"==", TokenType.NEQ:"!=", TokenType.LT:"<",
                  TokenType.GT:">", TokenType.LTE:"<=", TokenType.GTE:">="}[t.type]
            right = self._parse_additive()
            left = BinaryExpr(op=op, left=left, right=right, line=t.line, col=t.col)
            # Prohibir comparación encadenada
            if self._check(TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
                nt = self._peek()
                raise AyceSyntaxError(
                    self.filename, nt.line, nt.col,
                    "Las comparaciones encadenadas (a < b < c) no están permitidas en v0.2"
                )
        return left

    def _parse_additive(self) -> Expr:
        left = self._parse_multiplicative()
        while self._check(TokenType.PLUS, TokenType.MINUS):
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
        if self._check(TokenType.NOT, TokenType.MINUS):
            t = self._advance()
            op = "!" if t.type == TokenType.NOT else "-"
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
                idx = self._parse_expr()
                self._expect(TokenType.RBRACKET, "']'")
                expr = IndexExpr(target=expr, index=idx, line=t.line, col=t.col)
            elif t.type == TokenType.LT:
                # Acceso a diccionario x<clave>
                # Heurística: si tras '<' hay un literal o identificador seguido de '>',
                # es dict access; en otro caso es comparación.
                # La clave se parsea con una restricción: sólo se permiten literales
                # o identificadores simples (no expresiones con comparaciones)
                # para evitar ambigüedad con el '>' de cierre.
                if isinstance(expr, (IdentExpr, DictAccessExpr, IndexExpr, MethodCallExpr, CallExpr)):
                    save = self.pos
                    self._advance()  # '<'
                    next_tok = self._peek()
                    # Caso simple: <literal> o <identificador> seguido de '>'
                    if next_tok.type in (TokenType.STRING, TokenType.INT, TokenType.FLOAT,
                                         TokenType.TRUE, TokenType.FALSE, TokenType.NONE):
                        if self._peek(1).type == TokenType.GT:
                            key = self._parse_primary()
                            self._expect(TokenType.GT, "'>'")
                            expr = DictAccessExpr(target=expr, key=key, line=t.line, col=t.col)
                            continue
                        else:
                            self.pos = save
                            break
                    if next_tok.type == TokenType.IDENT and self._peek(1).type == TokenType.GT:
                        key = self._parse_primary()
                        self._expect(TokenType.GT, "'>'")
                        expr = DictAccessExpr(target=expr, key=key, line=t.line, col=t.col)
                        continue
                    # No era dict access: restaurar y salir (es comparación)
                    self.pos = save
                    break
                else:
                    break
            elif t.type == TokenType.DOT:
                self._advance()
                name_tok = self._expect(TokenType.IDENT, "nombre de método o campo").value
                # Si viene '(' es llamada a método; si no, es acceso a campo
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
                    expr = FieldAccessExpr(target=expr, field=name_tok, line=t.line, col=t.col)
            elif t.type == TokenType.LPAREN:
                # Llamada a tarea
                self._advance()
                args = []
                if not self._check(TokenType.RPAREN):
                    args.append(self._parse_expr())
                    while self._match(TokenType.COMMA):
                        args.append(self._parse_expr())
                self._expect(TokenType.RPAREN, "')'")
                expr = CallExpr(target=expr, args=args, line=t.line, col=t.col)
            else:
                break
        return expr

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

        # range(a, b)
        if t.type == TokenType.RANGE:
            self._advance()
            self._expect(TokenType.LPAREN, "'('")
            start = self._parse_expr()
            self._expect(TokenType.COMMA, "','")
            end = self._parse_expr()
            self._expect(TokenType.RPAREN, "')'")
            return RangeExpr(start=start, end=end, line=t.line, col=t.col)

        # self (dentro de métodos de Template)
        if t.type == TokenType.SELF:
            self._advance()
            return SelfExpr(line=t.line, col=t.col)

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
                    # El segundo argumento es el tipo: int, float, bool, string
                    type_tok = self._peek()
                    type_map = {TokenType.INT_T: "int", TokenType.FLOAT_T: "float",
                                TokenType.BOOL_T: "bool", TokenType.STRING_T: "string"}
                    if type_tok.type in type_map:
                        self._advance()
                        target_type = type_map[type_tok.type]
                    else:
                        raise AyceSyntaxError(self.filename, type_tok.line, type_tok.col,
                            "Se esperaba un tipo (int, float, bool, string) como segundo argumento de inlet")
            self._expect(TokenType.RPAREN, "')'")
            return InletExpr(prompt=prompt, target_type=target_type, line=t.line, col=t.col)

        # Identificador
        if t.type == TokenType.IDENT:
            self._advance()
            return IdentExpr(name=t.value, line=t.line, col=t.col)

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
