from astrepr import *

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
            

DEREFR = 0x08
DEREFPLUS = 0x10
DEREFNXTWD = 0x1e
NXTWD = 0x1f
A,B,C,X,Y,Z,I,J = 0,1,2,3,4,5,6,7
LITSMALL = 0x20
SP,PC = 0x1b, 0x1c
POP, PEEK, PUSH = 0x18, 0x19, 0x1a

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

def tobytes(instr):
    """
    Convert a tuple to the bytes which are actually the instruction.
    """
    if type(instrToByte[instr[0]]) == type(tuple()):
        return [(instrToByte[instr[0]][1]<<4) | (instr[1] << 10)] + list(instr[2:])
    return [instrToByte[instr[0]] | (instr[1]<<4) | (instr[2]<<10)] + list(instr[3:])

def toasm(prog, args=[], globFuncs={}, globVars={}, relativepos=0, DEBUG=False):
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
