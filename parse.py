import sys

sys.path.append("external/")

from pycparser import c_parser
from pycparser.c_ast import *


def makelst(l):
    if type(l) == type(tuple()):
        return [l]
    return l


def convert(ast):
    if isinstance(ast, FileAST):
        res = []
        for _, decl in ast.children():
            res.append(convert(decl))
        return res

    elif isinstance(ast, FuncDef):
        name = ast.decl.name
        if ast.decl.type.args == None:
            args = []
        else:
            args = [('VAR', x[1].name) for x in ast.decl.type.args.children()]
        return ("DEF", ('VAR', name), args, convert(ast.body))

    elif isinstance(ast, Decl):
        if ast.init:
            init = convert(ast.init)
        else:
            init = ('LIT', 0)
        return ('ASSIGN', ('VAR', ast.name), init)

    elif isinstance(ast, Assignment):
        if ast.op == '=':
            return ('ASSIGN', convert(ast.lvalue), convert(ast.rvalue))
        else:
            lv = convert(ast.lvalue)
            return ('ASSIGN', lv, (ast.op[:-1], lv, convert(ast.rvalue)))

    elif isinstance(ast, Compound):
        return [convert(x[1]) for x in ast.children()]

    elif isinstance(ast, Constant):
        if ast.type == 'int':
            return ('LIT', int(ast.value))
        elif ast.type == 'string':
            return ('STRING', ast.value[1:-1])
        elif ast.type == 'char':
            return ('LIT', ord(ast.value[1:-1]))

    elif isinstance(ast, FuncCall):
        if ast.name.name == '__print':
            return ('PRINT', convert(ast.args.children()[0][1]))
        if ast.name.name == '__putchar':
            return ('PUTCHAR', convert(ast.args.children()[0][1]))
        return ('CALL', ("VAR", ast.name.name),
                [convert(x[1]) for x in ast.args.children()])

    elif isinstance(ast, ID):
        return ('VAR', ast.name)

    elif isinstance(ast, BinaryOp):
        swap = {'!=': lambda a, b: ('!=', a, b),
                '<=': lambda a, b: ('>=', b, a),
                '<': lambda a, b: ('>', b, a),
                '&&': lambda a, b: ('&', a, b),  # TODO fix
                '||': lambda a, b: ('|', a, b),  # TODO fix
                }
        op = ast.op
        a, b = convert(ast.left), convert(ast.right)
        if op in swap:
            return swap[op](a, b)
        return (op, a, b)

    elif isinstance(ast, UnaryOp):
        if ast.op == '&':
            return ('ADDR', convert(ast.expr))

        elif ast.op == '!':
            return ('NOT', convert(ast.expr))

        elif ast.op == '~':
            return ('BITWISENOT', convert(ast.expr))

        elif ast.op == '*':
            return ('DEREF', convert(ast.expr))

        elif ast.op == '++':
            return ('PREINC', convert(ast.expr))

        elif ast.op == 'p++':
            return ('POSTINC', convert(ast.expr))

        else:
            raise Exception("Unexpected UnaryOp, %s" % (str(ast.op)))

    elif isinstance(ast, If):
        f = []
        if ast.iffalse:
            f = convert(ast.iffalse)
        return ("IF", convert(ast.cond),
                 makelst(convert(ast.iftrue)), makelst(f))

    elif isinstance(ast, While):
        return ("WHILE", convert(ast.cond), makelst(convert(ast.stmt)))

    elif isinstance(ast, For):
        return ("FOR", convert(ast.init), convert(ast.cond),
                 convert(ast.next), makelst(convert(ast.stmt)))

    elif isinstance(ast, Return):
        return ("RETURN", convert(ast.expr))

    elif isinstance(ast, ArrayRef):
        return ("DEREF", ("+", convert(ast.name), convert(ast.subscript)))


def parse(inp, debug):
    parser = c_parser.CParser()
    ast = parser.parse(inp)
    if debug:
        ast.show(nodenames=True, attrnames=True)
    c = convert(ast)
    return c
