#!/usr/bin/python
import sys
from pprint import pprint
import myparse

DEBUG = False
OPTIMIZE = True

# Let's declare all of the opcodes that DCPU-16 supports
SET='SET'
ADD='ADD'
SUB='SUB'
MUL='MUL'
DIV='DIV'
MOD='MOD'
SHL='SHL'
SHR='SHR'
AND='AND'
BOR='BOR'
XOR='XOR'
IFE='IFE'
IFN='IFN'
IFG='IFG'
IFB='IFB'
JSR='JSR'

# I've made some of my own to print things ...
# These aren't here usually though.
PRT='PRT'
PTC='PTC'

# Make the reverse lookup table
instrLst = [SET, ADD, SUB, MUL, DIV, MOD, SHL, SHR, AND, BOR, XOR, IFE, IFN, IFG, IFB]
instrToByte = dict([(x,i+1) for i,x in enumerate(instrLst)])

# Manually patch what it should be for the longer opcodes.
instrToByte[PRT] = (0,0x3e)
instrToByte[PTC] = (0,0x3d)
instrToByte[JSR] = (0,0x01)

# Here are the parts of the C AST that we want to represent.
DEF = 'DEF'
CALL = 'CALL'
ASSIGN = 'ASSIGN'
PLUS = '+'
MINUS = '-'
MULTIPLY = '*'
DIVIDE = '/'
REMAINDER = '%'
BOOLAND = '&'
BOOLOR = '|'
PREINC = 'PREINC'
POSTINC = 'POSTINC'
BOOLXOR = '^'
SHIFTL = '<<'
SHIFTR = '>>'
IF = 'IF'
IFNOT = 'IFNOT'
WHILE='WHILE'
FOR='FOR'
EQ = '=='
NEQ = '!='
GR = '>'
GE = '>='
VAR = 'VAR'
LIT = 'LIT'
STRING = 'STRING'
GOTO = 'GOTO'
LABEL = 'LABEL'
ADDR = 'ADDR'
DEREF = 'DEREF'
PRINT = 'PRINT'
PUTCHAR = 'PUTCHAR'
RETURN = 'RETURN'
MOV = 'MOV'

# We'll prefix this for our IR of the C code.
IR='IR_'

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

def optimize_unusedVars(stmts):
    """
    When we go var1 -> var2, just use var1 instead of var2.
    Same for const -> var2, replace with const.
    """
    if DEBUG: print "BEFORE", len(stmts)
    if DEBUG: pprint(stmts)
    rest = []
    equal = {}
    for stmt in stmts:
        if stmt[0] == IR+VAR and stmt[2][0] == '_':
            equal[stmt[2]] = stmt[1]
        elif stmt[0] == IR+LIT and stmt[2][0] == '_':
            equal[stmt[2]] = stmt[1]
        else:
            rest.append(stmt)

    def fix(x):
        return equal[x] if x in equal else x

    for i in range(len(rest)):
        if rest[i][0] == IR+CALL:
            rest[i] = (rest[i][0], fix(rest[i][1]), map(fix, rest[i][2]), fix(rest[i][3]))
        else:
            rest[i] = tuple([rest[i][0]] + map(fix, rest[i][1:]))

    if DEBUG: print "AFTER", len(rest)
    if DEBUG: pprint(rest)
    return rest

def optimize_if(stmts):
    """
    Usually if (x > 2) {} will be converted to three instruction x > 2 test,
    followed by a test for if. This combines them in to one test.
    """
    res = []
    i = 0
    while i < len(stmts)-2:
        if stmts[i+1][0] == IR+IF and stmts[i+2][0] == GOTO:
            if stmts[i][0] in [IR+EQ, IR+NEQ, IR+GR, IR+GE]:
                res.append((stmts[i][0], stmts[i][1], stmts[i][2], None))
                i += 1
            else:
                res.append(stmts[i])
        else:
            res.append(stmts[i])
        i += 1
    return res+stmts[-2:]


def replaceVarNames(instr, newnames):
    """
    Use the newnames function to find the new name for the SSA variables.
    """
    res = []
    if instr[0] in [IR+IF, IR+PRINT, IR+PUTCHAR, IR+RETURN]:
        return (instr[0], newnames(instr[1]))
    if instr[0] in [IR+VAR, IR+LIT, IR+ASSIGN, IR+DEREF, IR+ADDR]:
        return (instr[0], newnames(instr[1]), newnames(instr[2]))
    if instr[0] == IR+STRING:
        return (instr[0], instr[1], newnames(instr[2]))
    if instr[0] in [IR+PLUS, IR+MINUS, IR+MULTIPLY, IR+DIVIDE, IR+REMAINDER, 
                    IR+EQ, IR+NEQ, IR+GR, IR+GE, IR+SHIFTL, IR+SHIFTR, IR+BOOLAND, 
                    IR+BOOLOR, IR+BOOLXOR]:
        return (instr[0], newnames(instr[1]), newnames(instr[2]), newnames(instr[3]))
    if instr[0] == IR+CALL:
        return (instr[0], newnames(instr[1]), map(newnames,instr[2]), newnames(instr[3]))
    return instr

def getVarLocations(instr):
    """
    Return the SSA registers which are being used.
    """
    res = []
    if instr[0] in [IR+IF, IR+PRINT, IR+PUTCHAR, IR+RETURN]:
        res.append(instr[1]) 
    if instr[0] in [IR+VAR, IR+LIT, IR+ASSIGN, IR+DEREF, IR+ADDR]:
        res.append(instr[1]) 
        res.append(instr[2])
    if instr[0] == IR+STRING:
        res.append(instr[2])
    if instr[0] in [IR+PLUS, IR+MINUS, IR+MULTIPLY, IR+DIVIDE, IR+REMAINDER, 
                    IR+EQ, IR+NEQ, IR+GR, IR+GE, IR+SHIFTL, IR+SHIFTR, IR+BOOLAND, 
                    IR+BOOLOR, IR+BOOLXOR]:
        res.append(instr[1]) 
        res.append(instr[2])
        res.append(instr[3])
    if instr[0] == IR+CALL:
        res.append(instr[1])
        for x in instr[2]: res.append(x)
        res.append(instr[3])
    return res

def reuse_vars(stmts):
    """
    Convert away from SSA to use the same memory locations when we can.
    Doesn't do it in any intelligent manner right now -- just pick the first open spot.
    This helps us allocate registers as well.
    """
    locations = []
    newnames = {}

    def firstFree():
        for i in range(len(locations)):
            if locations[i] == None: return i
        locations.append(None)
        return len(locations)-1

    for i,stmt in enumerate(stmts):
        tofree = []
        for v in getVarLocations(stmt):
            if type(v) == type("") and v[0] == '_':
                if v in locations:
                    tofree.append(locations.index(v))
                else:
                    ff = firstFree()
                    locations[ff] = v
                    newnames[v] = "_t"+str(ff)
        for each in tofree:
            locations[each] = None

                    
    def rnewnames(x):
        if x in newnames:
            return newnames[x]
        else:
            return x
    return [replaceVarNames(x, rnewnames) for x in stmts]

def optimizeStmts(stmts):
    last = reuse_vars(optimize_if(optimize_unusedVars(stmts)))
    if DEBUG: print "FINALLY", len(last)
    if DEBUG: pprint(last)
    return last
            

DEREFR = 0x08
DEREFPLUS = 0x10
DEREFNXTWD = 0x1e
NXTWD = 0x1f
A,B,C,X,Y,Z,I,J = 0,1,2,3,4,5,6,7
LITSMALL = 0x20
SP,PC = 0x1b, 0x1c
POP, PEEK, PUSH = 0x18, 0x19, 0x1a

def tobytes(instr):
    """
    Convert a tuple to the bytes which are actually the instruction.
    """
    if type(instrToByte[instr[0]]) == type(tuple()):
        return [(instrToByte[instr[0]][1]<<4) | (instr[1] << 10)] + list(instr[2:])
    return [instrToByte[instr[0]] | (instr[1]<<4) | (instr[2]<<10)] + list(instr[3:])

def toasm(prog, args=[], globFuncs={}, globVars={}, relativepos=0):
    """
    Convert the IR to the actual instructions.
    """
    if DEBUG: print
    if DEBUG: print "CONVERT TO ASM:"
    if DEBUG: pprint(prog)
    idents = {}
    def add(it):
        if type(it) == type(""):
            if it not in idents and it not in args:
                if it not in globVars and it not in globFuncs:
                    idents[it] = len(idents)

    occurances = {}
    for instr in prog:
        for each in getVarLocations(instr):
            add(each)
            if type(each) != type(""): continue
            if each not in occurances:
                occurances[each] = 0
            occurances[each] += 1
    if DEBUG: print "OCCURANCES", occurances
    stackspace = len(idents)

    for arg in args[::-1]:
        idents[arg] = len(idents)+1

    def numbytes(asm):
        return len(sum(map(tobytes, asm),[]))

    asm = []
    labelpos = {}
    fixgoto = []
    heapalloc = []

    activeRegisters = {}

    numcalls = sum([x[0] == IR+CALL for x in prog])

    # TODO: Don't need to make a register for J+0.

    for k,v in sorted(occurances.items(), key=lambda x: x[1]):
        if len(activeRegisters) >= 4: break
        if numcalls*2+2-v < 0:
            # It takes 2 words to restore for each function call, as well as 2 to set up.
            # So only do it if we'll get a benefit.
            if k in idents:
                # We don't want to move a heap object in to a register just yet.
                # It makes things complicated with patching things up.
                activeRegisters[k] = (len(activeRegisters), idents[k])

    if DEBUG: print "Active registers for this function are", activeRegisters

    def add(op, a, b, asisA=False, asisB=False, extra=None):
        if extra != None:
            rextra = extra;
        else:
            rextra = []
        extra = []

        track = []

        def doone(asis, ab):
            if asis:
                how = ab
            elif type(ab) == type(''):
                if ab in globFuncs:
                    how = NXTWD
                    extra.append(globFuncs[ab])
                elif ab in globVars:
                    how = DEREFNXTWD
                    extra.append(globVars[ab])
                    # Is this the first or the second? Modify the right thing.
                    track.append((ab == a, ab))
                elif ab in activeRegisters:
                    how = DEREFR+activeRegisters[ab][0]
                else:
                    if idents[ab] == 0:
                        how = DEREFR + J
                    else:
                        how = DEREFPLUS+J
                        extra.append(idents[ab])
            elif type(ab) == type(0):
                if ab <= 0x3F:
                    how = LITSMALL+ab
                else:
                    how = NXTWD
                    extra.append(ab)
            return how
        
        howa = doone(asisA, a)

        if b == None:
            asm.append(tuple([op, howa]+extra))
            if len(track) > 0:
                heapalloc.append((len(sum(map(tobytes,asm),[]))-1, "INTEGER", track[0][1]))
            return

        howb = doone(asisB, b)

        instr = tuple([op, howa, howb]+extra+rextra)
        asm.append(instr)

        for isita, each in track:
            if isita:
                heapalloc.append((len(sum(map(tobytes,asm[:-1]),[]))+1, "INTEGER", each))
            else:
                heapalloc.append((len(sum(map(tobytes,asm),[]))-1, "INTEGER", each))

    def restoreRegisters():
        for varname,(reg,pos) in activeRegisters.items():
            add(SET, reg, J, asisA=True, asisB=True)
            add(ADD, reg, pos, asisA=True)

    asm.append((SUB, SP, NXTWD, stackspace))
    asm.append((SET, J, SP))
    restoreRegisters()
    for instr in prog:
        if instr[0] == IR+LIT:
            add(SET, instr[2], instr[1])
        if instr[0] == IR+STRING:
            add(SET, instr[2], 0xFFFF)
            heapalloc.append((len(sum(map(tobytes,asm),[]))-1, STRING, instr[1]))
        elif instr[0] == IR+VAR:
            add(SET, instr[2], instr[1])
        elif instr[0] == IR+MOV:
            add(SET, instr[2], instr[1])
        elif instr[0] == IR+EQ:
            if instr[3] != None: add(SET, instr[3], 0)
            add(IFE, instr[1], instr[2])
            if instr[3] != None: add(SET, instr[3], 1)
        elif instr[0] == IR+NEQ:
            if instr[3] != None: 
                add(SET, instr[3], 1)
                add(IFE, instr[1], instr[2])
                add(SET, instr[3], 0)
            else:
                add(IFN, instr[1], instr[2])
        elif instr[0] == IR+GR:
            if instr[3] != None: add(SET, instr[3], 0)
            add(IFG, instr[1], instr[2])
            if instr[3] != None: add(SET, instr[3], 1)
        elif instr[0] == IR+GE:
            if instr[3] != None: 
                add(SET, instr[3], 1)
                add(IFG, instr[2], instr[1])
                add(SET, instr[3], 0)
            else:
                add(IFN, instr[2], instr[1])
                add(IFG, instr[1], instr[2])
                
        elif instr[0] in [IR+PLUS, IR+MINUS, IR+MULTIPLY, IR+DIVIDE, IR+REMAINDER,
                          IR+SHIFTL, IR+SHIFTR, IR+BOOLAND, IR+BOOLOR, IR+BOOLXOR]:
            conv = {IR+PLUS: ADD, IR+MINUS: SUB, IR+MULTIPLY: MUL, IR+DIVIDE: DIV, 
                    IR+REMAINDER: MOD, IR+SHIFTL: SHL, IR+SHIFTR: SHR, IR+BOOLAND: AND
                    , IR+BOOLOR: BOR, IR+BOOLXOR: XOR}[instr[0]]
            if instr[3] != instr[1]:
                add(SET, instr[3], instr[1])
            add(conv, instr[3], instr[2])
        elif instr[0] == IR+IF:
            add(IFN, 0, instr[1])
        elif instr[0] == LABEL:
            labelpos[instr[1]] = numbytes(asm)
        elif instr[0] == GOTO:
            fixgoto.append((len(asm),instr[1]))
            asm.append((SET, PC, NXTWD, 0xFFFF))
        elif instr[0] == IR+PRINT:
            add(PRT, instr[1], None)
        elif instr[0] == IR+PUTCHAR:
            add(PTC, instr[1], None)
        elif instr[0] == IR+ASSIGN:
            add(SET, I, instr[2], asisA=True)
            add(SET, DEREFR+I, instr[1], asisA=True)
        elif instr[0] == IR+DEREF:
            add(SET, I, instr[1], asisA=True)
            add(SET, instr[2], DEREFR+I, asisB=True)
        elif instr[0] == IR+ADDR:
            if instr[1] in globVars:
                add(SET, instr[2], NXTWD, asisB=True, extra=[0xFFFF])
                heapalloc.append((len(sum(map(tobytes,asm),[]))-1, "INTEGER", instr[1]))
            else:
                add(SET, instr[2], J, asisB=True)
                add(ADD, instr[2], NXTWD, asisB=True, extra=[idents[instr[1]]])
        elif instr[0] == IR+CALL:
            for each in instr[2]:
                add(SET, PUSH, each, asisA=True)
            add(JSR, instr[1], None)
            add(ADD, SP, NXTWD, asisA=True, asisB=True, extra=[len(instr[2])])
            add(SET, J, SP, asisA=True, asisB=True)
            restoreRegisters()
            
            if instr[3] != None:
                add(SET, instr[3], I, asisB=True)
        elif instr[0] == IR+RETURN:
            add(ADD, SP, stackspace, asisA=True)
            if instr[1] != None:
                add(SET, I, instr[1], asisA=True)
            add(SET, PC, POP, asisA=True, asisB=True)

    for pos,what in fixgoto:
        asm[pos] = (asm[pos][0], asm[pos][1], asm[pos][2], labelpos[what]+relativepos)
    
    return sum(map(tobytes, asm), []), heapalloc

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
            startup = tobytes((JSR, NXTWD, len(res)+OFFSET))+[0x7dc1, 2] # first jump to main, then goto 2
            code = addToMain + code
            
        func1 = flattenFunc(code)+[(RETURN, None)]
        func2 = sum(map(flattenStmt,func1), [])
        if OPTIMIZE:
            func2 = optimizeStmts(func2)
        func3,ha = toasm(func2, [x[1] for x in func[2]], funcList, varList, len(res)+OFFSET)
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


def run(prog, debug=False):
    if DEBUG: print "PROG IS", prog
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
    prog = myparse.parse(prog, DEBUG)
    res = run(prog, False)
    
    if DEBUG: print " ".join(a)
    
    a = ["%04x"%x for x in res]
    open(fname, "w").write((" ".join(a)))

