#!/usr/bin/env python

import re
from Lexer import Lexer
from Token import Token
from Config import cfg

class Parser:
    valid_types = (
        # lvalue            rvalue              result            operators
        ( Token.T_INT,      Token.T_INT,        Token.T_INT,    ("+", "-", "*", "/", "^", "<<", ">>", "mod", "not", "and", "or", "xor") ),
        ( Token.T_CSTRING,  Token.T_CSTRING,    Token.T_CSTRING,("+",) ),
        ( Token.T_STRING,   Token.T_STRING,     Token.T_STRING,    ("+",) )
    )
    constants = {
        # find        replace
          "true"  :   "1",
          "false" :   "0"
    }
    @staticmethod
    def split(ln,symbol=",",regexp=""):
        if regexp:
            return [x.strip() for x in re.split("(%s)\s*(?:(?:\%s)\s*(%s)\s*)?" % (regexp, symbol, regexp), ln) if x and x != symbol]
        else:
            return [x.strip() for x in re.split('%s(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)' % symbol, ln) if x.strip()]
    def get_int(self, op, type=0):
        op = op.lower()
        if op[:2] in ("&h", "0x"): op = int("0x"+op[2:], 16)
        try:
            int(op)
        except:
            raise SyntaxError, "not an int: '%s'" % op
        return Token(Token.T_CINT, str(op))
    def get_string(self, op, type=0):
        if op[0] == op[-1] == '"':
            return Token(Token.T_CSTRING+((len(op)-1) << 32), op[1:-1])
        else:
            raise SyntaxError, "not a string: '%s'" % op
    def get_var(self, op, type=0, string_size=16):
        token = [var for var in self.var_table.children if var.value == op.lower()]
        if token == []: # unknown variable
            try:
                if re.match(Lexer.t_var, op).group() == op:
                    type = type or (Token.T_STRING if op[-1] == "$" else Token.T_INT)
                    var = Token(Token.T_VAR | type, op.lower()) >> self.var_table
                    if type & Token.T_STRING and not (var.type >> 32): var.type += string_size << 32
                    return var
            except:
                raise SyntaxError, "not a variable: '%s'" % op
        else:
            return token[0]
    def get_function(self, op, type=0):
        try:
            name, args = re.search(Lexer.t_function , op).groups()
            args = [self.get_expression(arg) for arg in Parser.split(args)]
            function = [f for f in self.func_table.children if f.value == name.lower()][0]
        except:
            raise SyntaxError, "not a function call: '%s'" % op
        # firstly, check arguments count
        if len(function.children) != len(args):
            raise TypeError, "%s() requires %s arg%s (%s given)" % \
                (name, len(function.children), "" if len(function.children) == 1 else "s", len(args))
        # secondly, check args type
        # d_types - declared types, c_arg - called arg
        for i, (d_types, c_arg) in enumerate(zip(function.children, args)):
            flag = False
            for d_type in d_types.children:
                if c_arg.type & d_type.type == d_type.type: flag = True
            if not flag:
                raise TypeError, "%s() argument #%s have incorrect type (%s)" % (name, i+1, c_arg)
        token = Token(Token.T_FUNCTION | function.type, name.lower())
        for arg in args: token << arg
        return token
    def get_operand(self, op, check=0):
        if not op: return Token()
        token = None
        for getter in (self.get_int, self.get_string, self.get_function, self.get_var):
            try:                token = getter(op, check)
            except SyntaxError: continue
            break
        if token == None:
            raise SyntaxError, "not an operand: '%s'" % op
        elif check and not (check & 2**32-1) & token.type:
            raise TypeError, "unexpected operand type of '%s'" % op
        return token
    def get_expression(self, expr, check=0):
        def interpret(expression, pr, action):
            lval, rval = self.get_operand(self.tokens[self.dp][pr-1]), self.get_operand(self.tokens[self.dp][pr+1])
            if (Token.T_CINT in lval) and (Token.T_CINT in rval):
                replace = {
                    "^"   :  "**",
                    "mod" :  "%",
                    "and" :  "&",
                    "or"  :  "|",
                    "xor" :  "^"
                }
                try:    self.tokens[self.dp][pr] = replace[self.tokens[self.dp][pr]]
                except: pass
                self.tokens[self.dp][pr] = str(eval(lval.value+self.tokens[self.dp][pr]+rval.value))
                self.types.append(Token.T_CINT)
            else:
                # DEBUG ONLY
                # without const flag
                if   not lval.type: lval.type = rval.type & ~Token.T_CONST
                elif not rval.type: rval.type = lval.type & ~Token.T_CONST
                for t in Parser.valid_types:
                    if (lval.type & t[0] == t[0]) and (rval.type & t[1] == t[1]) and (self.tokens[self.dp][pr] in t[3]):
                        self.types.append(t[2])
                        flag = True
                        break
                try:    flag
                except:    raise TypeError, "incorrect types in expression '%s'" % expr
                # DEBUG ONLY
                if not lval.value: lval.type = 0
                if not rval.value: rval.type = 0
                action(expression, lval, rval)
                self.tokens[self.dp][pr] = None
            del self.tokens[self.dp][pr-1], self.tokens[self.dp][pr]
            # change indexes in priority
            self.priority[self.dp] = [x-2 if x>pr else x for x in self.priority[self.dp]]
        expression = Token(Token.T_EXPRESSION)
        self.types = []
        self.dp += 1
        try:    self.tokens[self.dp] = []
        except: self.tokens.append([])
        try:    self.priority[self.dp] = []
        except: self.priority.append([])
        self.tokens[self.dp], self.priority[self.dp] = Lexer.tokenize(expr, Parser.constants)
        if len(self.tokens[self.dp]) == 1:
            op = self.get_operand(self.tokens[self.dp][0], check)
            if Token.T_FUNCTION in op:
                return Token(Token.T_EXPRESSION | op.type) << op
            else:
                self.dp -= 1
                return op
        for x in xrange(len(self.priority[self.dp])):
            pr = self.priority[self.dp][x]
            op = self.tokens[self.dp][pr]
            interpret(expression, pr, lambda e,x,y: e << Token(Token.T_OPERATOR, op) << x << y)
        expression.type |= self.types[0]
        try:
            int(self.tokens[self.dp][0])
            # it is const int expression
            return expression << Token() << Token() << Token(Token.T_CINT, self.tokens[self.dp][0])
        except:    return expression
        self.dp -= 1
        return expression
    def parse_for(self, ln):
        token = Token(Token.T_FOR, "__for"+str(self._internal["for_count"]))
        ln = ln.strip()
        try:
            var, start, end = re.search(r"for\s+(%s)\s*\=\s*(.*)\s+to\s+(.*)" % (Lexer.t_var), ln, re.IGNORECASE).groups()
        except:
            raise SyntaxError, "incorrect syntax: '%s'" % ln
        try:
            end, step = re.search(r"(.*)\s+step\s+(.*)", end).groups()
        except:
            step = "1"
        self._internal["for_count"] += 1
        container = Token(Token.T_CONTAINER, "_Info_") # container for 'FOR' params
        container \
            << self.get_operand(var,        Token.T_VAR | Token.T_INT) \
            << self.get_expression(start,    Token.T_INT) \
            << self.get_expression(end,        Token.T_INT) \
            << self.get_expression(step,    Token.T_INT)
        token << container # append container
        self.cur_parent = token >> self.cur_parent # append token to tokens tree
    def parse_let(self, args):
        let_token = Token(Token.T_LET)
        src_type = 0
        for x in reversed(Parser.split(args, "=")):
            expr = self.get_expression(x, src_type)
            expr.type |= Token.T_COPY # copy operand to dst
            let_token << expr
            src_type = (let_token[0].type if not Token.T_EXPRESSION in let_token[0] else expr.type) & ~Token.T_CONST # without const flag
        self.cur_parent << let_token
    def parse_next(self):
        if Token.T_FOR in self.cur_parent:
            self.cur_parent = self.cur_parent.parent
        else:
            raise SyntaxError, "unexpected NEXT"
    def parse_end(self, args):
        pass
    def parse_exit(self, args):
        if   args == "":
            return self.cur_parent << Token(Token.T_GOTO, "__exit")
        elif args == "for":
            while True:
                if Token.T_FOR in self.cur_parent:
                    return self.cur_parent << Token(Token.T_GOTO, self.cur_parent.value+"_end")
                try:    self.cur_parent = self.cur_parent.parent
                except:    raise SyntaxError, "unexpected 'exit %s'" % args
        else:
            raise SyntaxError, "unexpected 'exit %s'" % args
    def parse_call(self, name, args):
        # search sub in sub_table
        try:
            sub = [x for x in self.sub_table.children if x.value == name][0]
        except:
            raise NameError, "unknown command or sub: '%s'" % name
        # firstly, check arguments count
        if len(sub.children) != len(args):
            raise TypeError, "%s() requires %s arg%s (%s given)" % \
                (name, len(sub.children), "" if len(sub.children) == 1 else "s", len(args))
        # secondly, check args type
        # d_types - declared types, c_arg - called arg
        for i, (d_types, c_arg) in enumerate(zip(sub.children, args)):
            flag = False
            for d_type in d_types.children:
                if c_arg.type & d_type.type == d_type.type: flag = True
            if not flag:
                raise TypeError, "%s() argument #%s have incorrect type (%s)" % (name, i+1, c_arg)
        # all right, we can generate CALL token ...
        call = Token(Token.T_CALL | Token.T_SUB, name)
        for arg in args: arg >> call
        # ... and add it to AST
        call >> self.cur_parent
    def parse_1word(self, cmd, args):
        token = Token(Token.T_COMMAND, cmd)
        if cmd == "print":
            info = Token(Token.T_CONTAINER, "_Info_")
            if args and args[-1] == ",": info << Token(Token.T_CONTAINER, "NoNewLine")
            # add options to cmd token
            token << info
            for arg in Parser.split(args, ",", Lexer.t_expr_match): token << self.get_expression(arg)
            return self.cur_parent << token
        else:
            # it might be only a sub call
            self.parse_call(cmd.lower(), [self.get_expression(x) for x in Parser.split(args)])
    def __init__(self, lexer, default_vars={}, default_subs={}, default_functions={}):
        self.root        = Token()
        self.var_table   = Token() >> self.root
        self.header      = Token() >> self.root
        self.func_table  = Token() >> self.root
        self.sub_table   = Token() >> self.root
        self.cur_parent  = Token() >> self.root
        self._internal   = {"for_count": 0}
        self.lexer       = lexer
        self.tokens      = []
        self.priority    = []
        self.dp          = -1
        for name in default_vars:
            self.var_table << Token(Token.T_VAR | default_vars[name], name)
        for name in default_subs:
            sub_decl = Token(Token.T_DECLARATION | Token.T_SUB, name.lower()) >> self.sub_table
            for arg in default_subs[name]:
                types = Token() >> sub_decl
                for type in arg: Token(type) >> types
        for name in default_functions:
            func_decl = Token(default_functions[name][0], name.lower()) >> self.func_table
            for arg in default_functions[name][1]:
                types = Token() >> func_decl
                for type in arg: Token(type) >> types
        for ln in lexer.lines:
            ln = ln.strip()
            tmp_split = Parser.split(ln, "=")
            # empty line
            if ln == "": continue
            # comments
            elif ln[0] == "'":
                if not cfg["strip_comments"]:
                    self.cur_parent << Token(Token.T_COMMENT, ln[1:])
            # assignment
            elif len(tmp_split) > 1 and tmp_split[0] in re.findall(Lexer.t_var, tmp_split[0]):
                if   ln[:4] == "let ":    self.parse_let(ln[4:])
                else:                    self.parse_let(ln)
            # 1 word comands
            else:
                try:    cmd, args = re.split(r"\s+", ln, 1)
                except: cmd, args = ln, ""
                cmd = cmd.lower()
                if   cmd == "for":    self.parse_for(ln)
                elif cmd == "let":    self.parse_let(args)
                elif cmd == "end":    self.parse_end(args)
                elif cmd == "exit":    self.parse_exit(args)
                elif cmd == "next": self.parse_next()
                elif cmd == "call":
                    try:    s_name, s_args = re.match(Lexer.t_function, args).groups()
                    except:    raise SyntaxError, "invalid call statement: '%s'" % ln
                    self.parse_call(s_name.lower(), [self.get_expression(x) for x in Parser.split(s_args)])
                else:                self.parse_1word(cmd, args)
        if self.cur_parent != self.root[4]:
            raise SyntaxError, "missing close bracket(s)"