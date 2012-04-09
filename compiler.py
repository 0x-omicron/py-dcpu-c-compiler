#!/usr/bin/python
import sys
from pprint import pprint
from parse import parse
from IRtoAsm import toasm, tobytes
from optimize import optimizeStmts
from astrepr import *

DEBUG = False
OPTIMIZE = True

var_name = 0
def gensym():
    """
    Gives a unique name to a variable for the SSA IR.
    """

    global var_name
    var_name += 1
    return '_r'+str(var_name-1)

def flattenFunc(prog):
    """
    Flatten out a function definition.
    Turn if, while, and for into goto with labels.
    Try to do it in a somewhat efficient manner.
    """
    assert type(prog) == type(list())

    res = []
    for instr in prog:
        if instr[0] == IF:
            a,b,c = gensym(), gensym(), gensym()
            ift = flattenFunc(instr[2])
            iff = flattenFunc(instr[3])
            stmt = [(IR+IF, instr[1]), (GOTO, a)]
            stmt += iff + [(GOTO, c)]
            stmt += [(LABEL, a)] + ift
            stmt += [(LABEL, c)]
            res += stmt
        elif instr[0] == WHILE:
            test = gensym()
            top = gensym()
            stmt = [(GOTO, test), (LABEL, top)]+flattenFunc(instr[2])
            stmt += [(LABEL, test), (IR+IF, instr[1]), (GOTO, top)]
            res += stmt
        elif instr[0] == FOR:
            test = gensym()
            top = gensym()
            stmt = [instr[1]]
            stmt += [(GOTO, test), (LABEL, top)]+flattenFunc(instr[4])
            stmt += [instr[3]]
            stmt += [(LABEL, test), (IR+IF, instr[2]), (GOTO, top)]
            res += stmt
        else:
            # Don't do anything special
            res.append(instr)

    return res

def flattenStmt(exp, putres=None):
    """
    Generate the static single assignment (SSA) form.
    This isn't strictly SSA because we don't rebind named variables to unique names.
    This makes computing the address of the C variables much easier to compute.
    
    """
    if exp[0] == ASSIGN:
        if exp[1][0] == VAR:
            return flattenStmt(exp[2], exp[1][1])
        elif exp[1][0] == DEREF:
            a,b = gensym(),gensym()
            return flattenStmt(exp[1][1], a)+flattenStmt(exp[2], b)+[(IR+ASSIGN, b, a)]
    if exp[0] in [LIT, VAR, STRING]:
        return [(IR+exp[0], exp[1], putres)]
    if exp[0] == ADDR:
        a = gensym()
        return flattenStmt(exp[1], a)+[(IR+ADDR, a, putres)]
    if exp[0] == DEREF:
        a = gensym()
        return flattenStmt(exp[1], a)+[(IR+DEREF, a, putres)]
    if exp[0] in [PREINC, POSTINC]:
        assert exp[1][0] == 'VAR'
        a = (IR+PLUS, exp[1][1], 1, exp[1][1])
        b = (IR+MOV, exp[1][1], putres)
        if putres == None: return [a]
        return [a,b] if exp[0] == PREINC else [b,a]
    if exp[0] == RETURN:
        if exp[1] == None:
            return [(IR+RETURN, None)]
        a = gensym()
        return flattenStmt(exp[1], a)+[(IR+RETURN, a)]
    if exp[0] in [PLUS, MINUS, MULTIPLY, DIVIDE, REMAINDER, EQ, NEQ, GR, GE,
                  SHIFTL, SHIFTR, BOOLAND, BOOLOR, BOOLXOR]:
        a,b = gensym(), gensym()
        return flattenStmt(exp[1],a)+flattenStmt(exp[2],b)+[(IR+exp[0], a, b, putres)]
    if exp[0] == IR+IF:
        a = gensym()
        return flattenStmt(exp[1], a)+[(IR+IF, a)]
    if exp[0] in [PRINT, PUTCHAR]:
        a = gensym()
        return flattenStmt(exp[1],a)+[(IR+exp[0], a)]
    if exp[0] == CALL:
        r = []
        syms = []
        for arg in exp[2]:
            n = gensym()
            r += flattenStmt(arg, n)
            syms.append(n)
        v = gensym()
        return flattenStmt(exp[1], v)+r+[(IR+CALL, v, syms, putres)]
    return [exp]



def comp(prog):
    """
    Do the full compilation.
    """
    startup = None
    res = []
    funcList = {}
    varList = {}
    # The list of strings we need to allocate, or change the pointers of
    heapalloc = []
    OFFSET = 4 # words needed to have the startup code

    # Instructions we need to add to main to initialize globals.
    addToMain = []

    for func in prog:
        if func[0] == 'ASSIGN':
            heapalloc.append((None, "INTEGER", func[1][1]))
            varList[func[1][1]] = 0xFFFF
            addToMain.append(func)
            continue
        else:
            funcList[func[1][1]] = len(res)+OFFSET

        code = func[3]

        if func[1][1] == 'main':
            # TODO this is ugly.
            startup = tobytes(("JSR", 0x1F, len(res)+OFFSET))+[0x7dc1, 2] # first jump to main, then goto 2
            code = addToMain + code
            
        func1 = flattenFunc(code)+[(RETURN, None)]
        func2 = sum(map(flattenStmt,func1), [])
        if OPTIMIZE:
            func2 = optimizeStmts(func2, DEBUG)
        func3,ha = toasm(func2, [x[1] for x in func[2]], funcList, varList, len(res)+OFFSET, DEBUG)
        heapalloc += [(a+len(res)+OFFSET,b,c) for a,b,c in ha]
        res += func3

    res = startup+res
    end = len(res)


    # Here is where we fix any pointers to heap data.
    heap = []
    for change,kind,obj in heapalloc:
        if kind == "STRING":
            nxt = [ord(x) for x in obj]+[0]
            res[change] = len(res)+len(heap)
            heap += nxt
        if kind == "INTEGER":
            if change == None:
                # This is the init telling us to make the space.
                varList[obj] = len(res)+len(heap)
                heap += [0]
            else:
                res[change] = varList[obj]
            

    return res, heap


def run(prog):
    if DEBUG: print "PROG IS", prog
    prog = parse(prog, DEBUG)
    prog,heap = comp(prog)
    if DEBUG: print "NUMBYTES:", len(prog)
    if DEBUG: print
    return prog+heap
    

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print 'Usage: python compiler.py [-n] [-d] [-o outfile] input'
        print '   -n disables optimizations'
        print '   -d print debugging information about the compilation'
        print '   -o outfile writes the output to the given file'
        exit(0)
    i = 1
    fname = None
    while i != len(sys.argv)-1:
        if sys.argv[i] == '-n':
            OPTIMIZE = False
            i += 1
        if sys.argv[i] == '-o':
            fname = sys.argv[i+1]
            i += 2
        if sys.argv[i] == '-d':
            DEBUG = True
            i += 1
    
    if fname == None:
        fname = 'a.out'

    prog = open(sys.argv[i]).read()
    res = run(prog)
    
    if DEBUG: print " ".join(a)
    
    a = ["%04x"%x for x in res]
    open(fname, "w").write((" ".join(a)))

