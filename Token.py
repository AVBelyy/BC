#!/usr/bin/env python

class Token:
    # Token types
    T_CONTAINER = 0
    T_CONST = 1<<0
    T_VAR = 1<<1
    T_INT = 1<<2
    T_STRING = 1<<3
    T_FUNCTION = 1<<4
    T_SUB = 1<<5
    T_DECLARATION = 1<<6
    T_CALL = 1<<7
    T_OPERATOR = 1<<8
    T_EXPRESSION = 1<<9
    T_LET = 1<<10
    T_FOR = 1<<11
    T_GOTO = 1<<12
    T_COMMAND = 1<<13
    T_COMMENT = 1<<14
    # Mixed types
    T_OPERAND = T_CONST | T_VAR | T_INT | T_STRING | T_FUNCTION
    T_CINT = T_CONST | T_INT
    T_CSTRING = T_CONST | T_STRING
    # other
    T_COPY = 1<<15
    def __init__(self, type=0, value=""):
        self.type = type
        self.value = value
        self.parent = None
        self.children = []
    def __str__(self): # str(x)
        out = ""
        if   self.type & Token.T_CONST:        out += "const "
        if   self.type & Token.T_INT:        out += "int "
        elif self.type & Token.T_STRING:    out += "string "
        return out.strip()
    def __contains__(self, type): # x in y
        return self.type & type == type
    def __getitem__(self, item):  # x[y]
        return self.children[item]
    def __delitem__(self, item):  # x[y]
        del self.children[item]
    def __lshift__(self, token):  # x << y
        if not token: return self
        token.parent = self
        self.children.append(token)
        return self
    def __rrshift__(self, token): # y >> x
        if not token: return
        self.__lshift__(token)
        return token