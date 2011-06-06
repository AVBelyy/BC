#!/usr/bin/env python

import re
from math import log
from Lexer import Lexer
from Token import Token
from Parser import Parser
from Config import cfg

class PL:
    default_vars = {
        # name     type
          "r0"  :  Token.T_INT | Token.T_STRING,
          "r1"  :  Token.T_INT | Token.T_STRING,
          "r2"  :  Token.T_INT | Token.T_STRING,
          "r3"  :  Token.T_INT | Token.T_STRING,
          "r4"  :  Token.T_INT | Token.T_STRING,
          "r5"  :  Token.T_INT | Token.T_STRING,
          "r6"  :  Token.T_INT | Token.T_STRING,
          "r7"  :  Token.T_INT | Token.T_STRING,
          "r8"  :  Token.T_INT | Token.T_STRING,
          "r9"  :  Token.T_INT | Token.T_STRING
    }
    default_subs = {
        # name               arg types
        # ---------------------------
        # libstd subs
          "pushmsg"     :    ( ( Token.T_INT, ), ( Token.T_INT, ), ( Token.T_INT, ) ),
          "signal"      :    ( ( Token.T_INT, ), ( Token.T_INT, ) ),
          "gotoxy"      :    ( ( Token.T_INT, ), ( Token.T_INT, ) ),
          "strcpy"      :    ( ( Token.T_STRING, ), ( Token.T_STRING, ) ),
          "itoa"        :    ( ( Token.T_STRING, ), ( Token.T_INT, ) ),
          "strlen"      :    ( ( Token.T_STRING, ), ),
          "puts"        :    ( ( Token.T_STRING, ), ),
          "gets"        :    ( ( Token.T_STRING, ), ),
          "localtime"   :    ( ( Token.T_INT, ), ),
          "setwin"      :    ( ( Token.T_INT, ), ),
          "putc"        :    ( ( Token.T_INT, ), ),
          "displaywin"  :    (),
          "hidecursor"  :    (),
          "showcursor"  :    (),
          "createwin"   :    (),
          "noscroll"    :    (),
          "refresh"     :    (),
          "clrscr"      :    (),
          "scroll"      :    (),
        # libbrt subs
          "puts_int"    :    ( ( Token.T_INT, ), ),
        # internal subs
          "sleep"       :    ( ( Token.T_INT, ), ),
          "int"         :    ( ( Token.T_INT, ), )
    }
    default_functions = {
        # name                 func type        arg types
          "str"         :    ( Token.T_STRING,  ( ( Token.T_INT, ), ) )
    }
    operands = {
          "*"    :    "mul",
          "/"    :    "div",
          "mod"  :    "mod",
          "+"    :    "add",
          "-"    :    "sub",
          "<<"   :    "shl",
          ">>"   :    "shr",
          "not"  :    "not",
          "and"  :    "and",
          "or"   :    "or",
          "xor"  :    "xor"
    }
    t_reg = r'[Rr]\d'
    indentData = (1, "\t") # size and symbol
    def indent(self):
        return self.curIndent*PL.indentData[0]*PL.indentData[1]
    def anyFreeInt(self, is_reg=False):
        try:
            varname = self.free_vars.pop()
        except IndexError:
            # create new temporary variable
            self._internal["stackPointer"] += 1
            varname = "__temp_%s" % self._internal["stackPointer"]
        if is_reg and not re.match(PL.t_reg, varname): # var isn't a register
            raise RuntimeError, "free regs run out. optimize your expression!"
        return self.parser.get_var(varname, Token.T_INT)
    def compile_operand(self, token, is_dest=False):
        if   Token.T_EXPRESSION in token and (len(token.children) == 3):
            if (token[0].type == token[1].type == 0):
                # const int expression
                return token[2].value
        elif not (token.type & Token.T_OPERAND): return None
        if   Token.T_VAR in token and token.value not in PL.default_vars: # var (int OR string)
            return "*"+token.value 
        elif Token.T_CSTRING in token:
            return '"%s"' % token.value
        else:
            return token.value
    def compile_expression(self, token, target=None):
        if not Token.T_EXPRESSION in token and Token.T_VAR in target:
            target_op = self.compile_operand(target, True)
            token_op = self.compile_operand(token)
            if (Token.T_CSTRING | Token.T_COPY) in token:
                self.output.append([self.indent()+"mov", "r0", target_op])
                self.output.append([self.indent()+"mov", "r1", token_op])
                self.output.append([self.indent()+"call", "strcpy"])
            else:
                self.output.append([self.indent()+"mov", target_op, token_op])
        elif Token.T_FUNCTION in token[0]:
            return self.compile_function(token[0], target)
        if not Token.T_VAR in target: return
        for x in xrange(0, len(token.children), 3):
            operand, lval, rval = token[x], token[x+1], token[x+2]
            if (Token.T_FUNCTION in lval) or (Token.T_FUNCTION in rval):
                if Token.T_FUNCTION in lval:
                    func = lval
                    val = rval
                else:
                    func = rval
                    val = lval
                self.compile_function(func, target)
                self.output.append([self.indent()+"mov", self.compile_operand(target), "r0"])
                lval, rval = Token(), val
            if lval.type and rval.type:
                self.output.append([self.indent()+"mov", self.compile_operand(target), self.compile_operand(lval)])
                lval = Token()
            if lval.type or rval.type:
                # translate operand
                if not operand.type:
                    # if const expression
                    self.output.append([self.indent()+"mov", self.compile_operand(target), self.compile_operand(rval)])
                    return
                try:
                    op = PL.operands[operand.value]
                except:
                    raise SyntaxError, "unknown operand: '%s'" % operand.value
                val = lval if not rval.type else rval
                t = self.compile_operand(target)
                if t in PL.default_vars:
                    # t is register
                    self.output.append([self.indent()+op, t, self.compile_operand(val)])
                else:
                    # t is variable
                    reg = self.compile_operand(self.anyFreeInt(True)) # free reg
                    self.output.append([self.indent()+"mov", reg, t])
                    self.output.append([self.indent()+op, reg, self.compile_operand(val)])
                    self.output.append([self.indent()+"mov", t, reg])
                    self.free_vars.append(reg)
    def compile_call(self, name, args):
        if len(args) > 5:
            raise SyntaxError, "%s(): too many args (%s given, 5 max)" % (name, len(args))
        for i, arg in enumerate(args):
            dst = self.parser.get_var("r%s"%i)
            if arg.type & Token.T_OPERAND:
                self.compile_expression(arg, dst)
            else:
                temp = self.anyFreeInt()
                self.compile_expression(arg, temp)
                arg_op = self.compile_operand(temp)
                self.output.append([self.indent()+"mov", self.compile_operand(dst), arg_op])
                self.free_vars.append(arg_op)
        self.output.append([self.indent()+"call", name])
        if name in ("puts_int",): self._internal["brtUsed"] = True
    def compile_function(self, func, target):
        if   func.value == "str":
            buf = self.parser.get_var("__itoa_buf", Token.T_STRING, 12)
            self.compile_call("itoa", [buf, func[0]])
            self.output.append([self.indent()+"mov", self.compile_operand(target), "r0"])
        else:
            self.compile_call(func.value, func.children)
    def optimize(self):
        for i, ln in enumerate(self.output):
            if ln[0].strip() == "call":
                self._internal["stackPointer"] = 0
            # mov rX optimizations
            try:
                cmd, src, dst = ln[0].strip(), ln[1], ln[2]
                if cmd == "mov" and re.match(PL.t_reg, src) and src == dst:
                    self.output[i] = []
            except: pass
            try:
                cmd, dst = ln[0].strip(), ln[1]
                if cmd == "mov" and re.match(PL.t_reg, dst) and int(dst[1]) == self._internal["stackPointer"]:
                    self._internal["stackPointer"] += 1
                    del self.output[i][1]
                    self.output[i][0] = self.output[i][0].replace("mov", "push")
            except: pass
            # inc/dec optimization
            try:
                cmd, rval = ln[0].strip(), ln[2]
                if   cmd == "add" and rval == "1":
                    del self.output[i][2]
                    self.output[i][0] = self.output[i][0].replace("add", "inc")
                elif cmd == "sub" and rval == "1":
                    del self.output[i][2]
                    self.output[i][0] = self.output[i][0].replace("sub", "dec")
                # and other stupid optimizations...
                elif (cmd in ("add", "sub", "shl", "shr") and rval == "0") or \
                     (cmd in ("mul", "div") and rval == "1"):
                        self.output[i] = []
                # mul/div to 2^x optimization
                elif (re.match(Lexer.t_int, rval)) and not (log(int(rval), 2) % 1):
                    if   cmd == "mul":
                        self.output[i][0] = self.output[i][0].replace("mul", "shl")
                        self.output[i][2] = str(int(log(int(rval), 2)))
                    elif cmd == "div":
                        self.output[i][0] = self.output[i][0].replace("div", "shr")
                        self.output[i][2] = str(int(log(int(rval), 2)))
            except: pass
    def compile(self, parent):
        for token in parent.children:
            if token.value == "_Info_": continue
            if   Token.T_COMMENT in token:
                self.output.append([self.indent()+"#"+token.value])
            elif Token.T_LET in token:
                src = Token(Token.T_EXPRESSION) # temporary token
                for x in xrange(0, len(token.children)-1):
                    src = src if not Token.T_EXPRESSION in src else token[x]
                    dst, flag = token[x+1], False
                    if not Token.T_VAR in dst:
                        raise SyntaxError, "can't assign to '%s'" % dst.value
                    src_op = self.compile_operand(src)
                    if src.type & Token.T_OPERAND:
                        self.compile_expression(src, dst)
                    else:
                        src_temp = self.anyFreeInt()
                        self.compile_expression(src, src_temp)
                        src_op = self.compile_operand(src_temp)
                        self.output.append([self.indent()+"mov", self.compile_operand(dst), src_op])
                        self.free_vars.append(src_op)
            elif Token.T_CALL in token:
                if   token.value in ("sleep", "int"):
                    flag, arg = False, self.compile_operand(token[0])
                    if not arg:
                        # is it expression?
                        arg_temp = self.anyFreeInt()
                        self.compile_expression(token[0], arg_temp)
                        arg = self.compile_operand(arg_temp)
                        flag = True
                    self.output.append([self.indent()+token.value, arg])
                    if flag: self.free_vars.append(arg)
                else:
                    self.compile_call(token.value, token.children)
            elif Token.T_FOR in token:
                downto = False
                fv_flag, to_flag, step_flag = False, False, False
                try:
                    # try to remove FOR variable from free_vars list
                    self.free_vars.remove(self.compile_operand(token[0][0]))
                    fv_flag = True
                except: pass
                # pre-calc 'to' if it's expression
                to = self.compile_operand(token[0][2])
                if not to:
                    # is it expression?
                    to_temp = self.anyFreeInt()
                    self.compile_expression(token[0][2], to_temp)
                    to = self.compile_operand(to_temp)
                    to_flag = True
                # pre-calc 'step'
                step = token[0][3]
                if Token.T_EXPRESSION in step:
                    # is it expression?
                    step_temp = self.anyFreeInt()
                    self.compile_expression(token[0][3], step_temp)
                    step = step_temp
                    step_flag = True
                elif Token.T_CINT in step and int(step.value) < 0:
                    downto, step.value = True, step.value[1:]
                self.compile_expression(token[0][1], token[0][0])
                self.output.append([self.indent()+"label", token.value])
                self.curIndent += 1
                self.compile(token)
                self.output.append([self.indent()+"if", "(%s==%s)" % (self.compile_operand(token[0][0]), to), "jmp", token.value+"_end"])
                self.compile_expression(Token(Token.T_EXPRESSION) << Token(Token.T_OPERATOR, "-" if downto else "+") << step << Token(), token[0][0])
                self.curIndent -= 1
                self.output.append([self.indent()+"jmp", token.value])
                self.output.append([self.indent()+"label", token.value+"_end"])
                if fv_flag:        self.free_vars.append(self.compile_operand(token[0][0]))
                if to_flag:        self.free_vars.append(to)
                if step_flag:    self.free_vars.append(self.compile_operand(step))
            elif Token.T_GOTO in token:
                self.output.append([self.indent()+"jmp", token.value])
            else:
                if token.value == "print":
                    options = [tok.value for tok in token[0].children]
                    # trunc '_Info_' section
                    del token[0]
                    for expr in token.children:
                        out = self.compile_operand(expr)
                        reg = "r0"
                        if cfg["optimize"] == "speed":
                            # create buffer for 'itoa'
                            self.parser.get_var("__itoa_buf", Token.T_STRING, 12)
                            if Token.T_INT in expr:
                                reg = "r1"
                                self.output.append([self.indent()+"mov", "r0", "__itoa_buf"])
                        if not out:
                            # is it expression?
                            out = reg
                            self.compile_expression(expr, self.parser.get_var(out))
                        else:
                            self.output.append([self.indent()+"mov", reg, out])        
                        if   Token.T_INT in expr:
                            if   cfg["optimize"] == "speed": self.output.append([self.indent()+"call", "itoa"])
                            elif cfg["optimize"] == "size":  self._internal["brtUsed"] = True
                            self.output.append([self.indent()+"call", "puts_int" if cfg["optimize"] == "size" else "puts"])
                        elif expr.type & Token.T_STRING:
                            self.output.append([self.indent()+"call", "puts"])
                        self.output.append([self.indent()+"call", "putc(' ')"])
                    if token.children: self.output.pop()
                    self.output.append([self.indent()+"call", "putc('%s')" % (" " if "NoNewLine" in options else "\\n")])
                    if cfg["dummy_output"]: self.output.append([self.indent()+"call", "refresh"])
    def __init__(self, filename):
        # init default vars
        self.lexer = Lexer(filename)
        self.parser = Parser(self.lexer, PL.default_vars, PL.default_subs, PL.default_functions) 
        self.curIndent = 1
        self._internal = {"stackPointer": 0, "fvCounter": 0, "brtUsed": False}
        self.free_vars = [ "r9", "r8", "r7", "r6", "r5" ] 
        self.output = []
        self.compile(self.parser.cur_parent)
        self.optimize()
        print ("#options=-lbrt\n\n" if self._internal["brtUsed"] else "") + "#include <libstd.inc>"
        if len(self.parser.var_table.children) > len(PL.default_vars): print "\nstatic:"
        print "\n".join(["\t%s %s" % (x.value, "int" if Token.T_INT in x else "string[%s]" % (x.type>>32)) for x in self.parser.var_table.children if x.value not in self.default_vars])
        print "code:"
        if cfg["dummy_output"]: print "\tcall createwin"
        print "\n".join([" ".join(x) for x in self.output + [["\tlabel", "__exit"]] if x])