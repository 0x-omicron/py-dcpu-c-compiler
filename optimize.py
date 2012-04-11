from astrepr import *
from IRtoAsm import getVarLocations

DEBUG = False


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
        if(stmt[0] == IR + VAR) and (stmt[2][0] == '_'):
            equal[stmt[2]] = stmt[1]

        elif(stmt[0] == IR + LIT) and (stmt[2][0] == '_'):
            equal[stmt[2]] = stmt[1]

        else:
            rest.append(stmt)

    def fix(x):
        return equal[x] if x in equal else x

    for i in range(len(rest)):
        if(rest[i][0] == IR + CALL):
            rest[i] = (rest[i][0], fix(rest[i][1]),
                        map(fix, rest[i][2]), fix(rest[i][3]))
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
    while i < (len(stmts) - 2):
        if (stmts[i + 1][0] == IR + IF) and (stmts[i + 2][0] == GOTO):
            if stmts[i][0] in [IR + EQ, IR + NEQ, IR + GR, IR + GE]:
                res.append((stmts[i][0], stmts[i][1], stmts[i][2], None))
                i += 1

            else:
                res.append(stmts[i])
        else:
            res.append(stmts[i])
        i += 1
    return res + stmts[-2::]


def replaceVarNames(instr, newnames):
    """
    Use the newnames function to find the new name for the SSA variables.
    """
    if instr[0] in [IR + IF, IR + PRINT, IR + PUTCHAR, IR + RETURN]:
        return (instr[0], newnames(instr[1]))

    elif instr[0] in [IR + VAR, IR + LIT, IR + ASSIGN, IR + DEREF, IR + ADDR]:
        return (instr[0], newnames(instr[1]), newnames(instr[2]))

    elif instr[0] == IR + STRING:
        return (instr[0], instr[1], newnames(instr[2]))

    elif instr[0] in [IR + PLUS, IR + MINUS, IR + MULTIPLY, IR + DIVIDE,
                      IR + REMAINDER, IR + EQ, IR + NEQ, IR + GR, IR + GE,
                      IR + SHIFTL, IR + SHIFTR, IR + BOOLAND, IR + BOOLOR,
                      IR + BOOLXOR]:
        return (instr[0], newnames(instr[1]), newnames(instr[2]),
                newnames(instr[3]))

    if instr[0] == IR + CALL:
        return (instr[0], newnames(instr[1]), map(newnames, instr[2]),
                newnames(instr[3]))

    return instr


def reuse_vars(stmts):
    """
    Convert away from SSA to use the same memory locations when we can.
    Doesn't do it in any intelligent manner right now -- just pick the first
    open spot. This helps us allocate registers as well.
    """
    locations = []
    newnames = {}

    def firstFree():
        for i in range(len(locations)):
            if locations[i] == None:
                return i
        locations.append(None)
        return len(locations) - 1

    for i, stmt in enumerate(stmts):
        tofree = []
        for v in getVarLocations(stmt):
            if type(v) == type("") and v[0] == '_':
                if v in locations:
                    tofree.append(locations.index(v))
                else:
                    ff = firstFree()
                    locations[ff] = v
                    newnames[v] = "_t" + str(ff)
        for each in tofree:
            locations[each] = None

    def rnewnames(x):
        if x in newnames:
            return newnames[x]
        else:
            return x
    return [replaceVarNames(x, rnewnames) for x in stmts]


def optimizeStmts(stmts, debug=False):
    global DEBUG
    DEBUG = debug
    last = reuse_vars(optimize_if(optimize_unusedVars(stmts)))
    if DEBUG: print "FINALLY", len(last)
    if DEBUG: pprint(last)
    return last
