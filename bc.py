#!/usr/bin/env python

import sys, PL

if __name__ == "__main__":
    try:    src = sys.argv[1]
    except:    src = "test.bas"
    prg = PL.PL(src)