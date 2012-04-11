# Here are the parts of the C AST that we want to represent.

# Definition tokens
DEF         = 'DEF'
CALL        = 'CALL'
ASSIGN      = 'ASSIGN'

# Operator tokens
PLUS        = '+'
MINUS       = '-'
MULTIPLY    = '*'
DIVIDE      = '/'
REMAINDER   = '%'
BOOLAND     = '&'
BOOLOR      = '|'
PREINC      = 'PREINC'
POSTINC     = 'POSTINC'
BOOLXOR     = '^'
SHIFTL      = '<<'
SHIFTR      = '>>'
DEREF       = 'DEREF'

# Flow control tokens
IF          = 'IF'
IFNOT       = 'IFNOT'
WHILE       = 'WHILE'
FOR         = 'FOR'
GOTO        = 'GOTO'
RETURN      = 'RETURN'

# Logical tokens
EQ          = '=='
NEQ         = '!='
GR          = '>'
GE          = '>='

# Internal variable tokens
VAR         = 'VAR'
LIT         = 'LIT'
STRING      = 'STRING'

# MSC. internal tokens
LABEL       = 'LABEL'
ADDR        = 'ADDR'
PRINT       = 'PRINT'
PUTCHAR     = 'PUTCHAR'
MOV         = 'MOV'

# We'll prefix this for our IR of the C code.
IR = 'IR_'
