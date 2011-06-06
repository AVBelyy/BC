#!/usr/bin/env python

import re

class Lexer:
    t_var = r'[_a-zA-Z][\w\d\$\%]*'
    t_int = r'(?i)(?:0x|&h)[\dabcdef]+|\d+'
    t_function = r'(%s)\((.*)\)' % t_var
    t_function_match = r'%s\(.*\)' % t_var
    t_string = r'".*"'
    t_arithop = r'(?i)\^|\*|/|\s+mod\s+|\+|-|<<|>>'
    t_logicop = r'(?i)\s+and\s+|\s+not\s+|\s+or\s+|\s+xor\s+'
    t_cmpop = r'<>|<=|>=|<|>|='
    t_operator = r'|'.join((t_arithop, t_logicop))
    t_operand = r'|'.join((t_int, t_string, t_function_match, t_var))
    t_term = "(\()?\s*(%s)\s*(\))?" % t_operand
    t_expr = "(?:%s)?\s*(?:(%s)\s*(?:%s)\s*)?" % (t_term, t_operator, t_term)
    t_term_match = "(?:\()?\s*(?:%s)\s*(?:\))?" % t_operand
    t_expr_match = "(?:%s)\s*(?:(?:%s)\s*(?:%s)\s*)*" % (t_term_match, t_operator, t_term_match)
    def __init__(self, filename):
        try:
            self.f = open(filename)
        except:
            raise IOError, "source '%s' not found" % filename
        self.lines = self.f.readlines()
    @staticmethod
    def build(tokens, to_str=False):
        return [x for x in reduce(lambda x,y:x+y, tokens) if x]
    @staticmethod
    def tokenize(expr, constants={}):
        priority = {
            # operand    priority
              "^"    :     9,
              "*"    :     8,
              "/"    :     8,
              "mod"  :     7,
              "+"    :     6,
              "-"    :     6,
              "<<"   :     5,
              ">>"   :     5,
              "not"  :     4,
              "and"  :     3,
              "or"   :     2,
              "xor"  :     1
        }
        tokens = Lexer.build(re.findall(Lexer.t_expr, expr))
        out, pr_list, pr, index, delta = [], [], 0, 0, 10**6.0
        for t in tokens:
            delta -= 1
            if not t: continue
            t = t.strip()
            if t.lower() in constants:
                t = constants[t.lower()]
            if   t == "(": pr += 100
            elif t == ")": pr -= 100
            elif t in priority.keys():
                out.append(t)
                pr_list.append((pr+priority[t]+delta/10**6, index))
                index += 1
            else:
                out.append(t)
                index += 1
        pr_list.sort(reverse=True)
        return out, [x[1] for x in pr_list]
